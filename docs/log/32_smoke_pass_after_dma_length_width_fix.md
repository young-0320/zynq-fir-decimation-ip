# 32. DMA smoke-test 통과 및 메인 FIR 복귀 기준

- 작성일: 2026-05-24
- 선행 문서: `31_dma_smoke_test_and_length_width_fix.md`
- 관련 파일:
  - `vivado/bd_fir_dma.tcl`
  - `vivado/bd_fir_dma_smoke.tcl`
  - `vivado/build_bd_fir_dma_smoke.tcl`
  - `rtl/debug/axis_dma_smoke_test.v`
  - `vitis/rebuild_boot_image.sh`
  - `sw/fir_decimator_demo.c`
  - `sw/fir_decimator_demo.py`

---

## 결론

`AXI DMA`의 `CONFIG.c_sg_length_width {23}` 수정 후 `SMOKE` BOOT가 보드에서 통과했다.

이로써 이전까지 반복되던 증상:

```text
ERR:1: MM2S DMA timeout
MM2S M=00000000 S=00000000 반복
```

은 `FIR RTL`이나 `AXI-Stream wrapper`의 1차 문제가 아니라, AXI DMA의 `LENGTH` field width 설정 문제였다고 판정한다.

핵심 원인:

```text
N_IN = 8192 samples
sample width = int16_t = 2 bytes
MM2S transfer length = 8192 * 2 = 16384 bytes = 0x4000

AXI DMA default c_sg_length_width = 14
14-bit max byte count = 2^14 - 1 = 16383 bytes

현재 전송 길이 16384 bytes는 default 14-bit limit를 정확히 1 byte 초과한다.
```

따라서 DMA가 `MM2S_LENGTH = 0x4000`을 정상적인 byte count로 처리하지 못했고, error bit 없이 running 상태에 머무는 timeout으로 관찰된 것으로 해석한다.

---

## 핵심 오류 발견 논리

이번 문제의 핵심은 처음부터 `CONFIG.c_sg_length_width`를 알고 찍은 것이 아니라, 가능한 원인을 하나씩 제거하면서 마지막에 `DMA LENGTH field width`로 좁혀졌다는 점이다.

이 과정을 나중에 다시 재현할 수 있어야 하므로, 판단 순서를 자세히 남긴다.

---

### 1. 처음 관찰한 현상은 FIR RTL 문제처럼 보였다

PC Python demo 실행 시 보드는 `READY`까지는 정상적으로 응답했다. 즉 SD boot, FSBL, baremetal app 진입, UART 수신 자체는 살아 있었다.

하지만 FIR demo를 실행하면 항상 DMA 단계에서 멈췄다.

```text
GEN
D0
D1
D2
ST2 M=00000001 S=00000001
D3
ST3 M=00000001 S=00000000
D4
ST4 M=00000000 S=00000000
MM2S M=00000000 S=00000000
MM2S M=00000000 S=00000000
MM2STO M=00000000 S=00000000
ERR:1
```

여기서 `ERR:1`은 C app에서 정의한 software error code이며, 의미는 `MM2S DMA timeout`이다.

이 상태를 처음 보면 가장 자연스러운 의심은 AXI-Stream handshake 문제다.

이유:

1. AXI DMA MM2S는 DDR에서 읽은 데이터를 PL의 `S_AXIS`로 내보낸다.
2. downstream 모듈이 `s_axis_tready`를 올리지 않으면 MM2S는 데이터를 더 밀어 넣지 못한다.
3. FIR wrapper가 `tvalid`, `tready`, `tlast`를 잘못 다루면 DMA가 packet 완료를 못 볼 수 있다.
4. 이전에도 TLAST/deadlock 계열 문제를 다룬 적이 있었다.

따라서 최초 가설은 다음이었다.

```text
가설 A:
rtl/transposed_form/n43/fir_decimator_n43_axis.v 내부 handshake 또는 TLAST 생성이 잘못되어
MM2S 또는 S2MM DMA가 끝나지 않는다.
```

이 가설은 충분히 합리적이었다. 특히 `FIR + M=2 decimator + AXI-Stream wrapper`는 단순한 combinational block이 아니고, 입력 8192개를 받아 출력 4096개를 만들어야 하므로 count, phase, TLAST, backpressure가 모두 맞아야 한다.

---

### 2. DMA status 로그는 "register 접근 불능"이 아니라 "running stuck"을 가리켰다

UART debug trace에서 `ST2`, `ST3`, `ST4`를 찍은 것이 중요했다.

상태 변화:

```text
ST2 M=00000001 S=00000001
```

DMA reset 직후 양쪽 채널이 halted 상태라는 뜻이다. 최소한 AXI-Lite register read/write가 동작한다.

```text
ST3 M=00000001 S=00000000
```

S2MM 채널을 먼저 start한 뒤 S2MM halted bit가 내려갔다. 즉 S2MM start command가 DMA에 들어갔다.

```text
ST4 M=00000000 S=00000000
```

MM2S 채널도 start한 뒤 MM2S halted bit가 내려갔다. 즉 MM2S start command도 DMA에 들어갔다.

반복된 상태:

```text
MM2S M=00000000 S=00000000
```

여기서 중요한 점은 error bit가 보이지 않는다는 것이다. AXI DMA가 decode error, slave error, internal error를 명확히 보고하는 형태가 아니라, running 상태에 들어간 뒤 idle로 돌아오지 않았다.

따라서 이 시점의 해석은 다음이었다.

```text
AXI-Lite register 접근: 가능
DMA reset/start: 가능
DMA가 완전히 죽은 상태: 아님
문제: start 이후 transfer completion이 발생하지 않음
```

이 해석 때문에 처음에는 PL stream handshake 쪽이 더 그럴듯했다.

---

### 3. FIR를 제거한 단순 decimator도 같은 timeout을 냈다

첫 번째 분리 실험은 FIR 연산부를 빼고, AXI-Stream 모양만 유지한 단순 decimator를 넣는 것이었다.

추가한 debug endpoint:

```text
rtl/debug/axis_decimator_m2_n43_debug.v
vivado/bd_fir_dma_axis_debug.tcl
vivado/build_bd_fir_dma_axis_debug.tcl
```

이 모듈의 의도:

```text
FIR MAC 연산 제거
coefficient 제거
transposed-form pipeline 제거
입력 2개 중 1개만 출력하는 단순 M=2 decimator만 남김
```

기대했던 판정:

```text
만약 FIR 내부 계산 또는 coefficient/pipeline이 원인이면
단순 decimator BOOT에서는 timeout이 사라져야 한다.
```

하지만 결과는 동일했다.

```text
ERR:1: MM2S DMA timeout
ST4 M=00000000 S=00000000
MM2S M=00000000 S=00000000 반복
```

이 결과로 배제된 것:

```text
FIR MAC datapath 단독 문제
coefficient 값 단독 문제
transposed-form FIR pipeline 단독 문제
```

하지만 이 단계만으로는 AXI-Stream wrapper 전체를 완전히 배제할 수 없었다. 단순 decimator도 여전히 입력 stream과 출력 stream이 서로 연결되어 있고, 출력 쪽 backpressure가 입력 쪽 `tready`에 영향을 줄 수 있기 때문이다.

따라서 다음 단계는 "입력 stream을 절대 막지 않는 endpoint"가 필요했다.

---

### 4. smoke-test는 PL backpressure 가능성을 제거하기 위해 만들었다

두 번째 분리 실험은 `axis_dma_smoke_test`였다.

추가한 파일:

```text
rtl/debug/axis_dma_smoke_test.v
vivado/bd_fir_dma_smoke.tcl
vivado/build_bd_fir_dma_smoke.tcl
```

이 모듈의 핵심은 입력을 무조건 받는 것이다.

```verilog
assign s_axis_tready = 1'b1;
```

이 한 줄 때문에 smoke-test의 의미가 매우 커졌다.

만약 `s_axis_tready`가 항상 1이면, MM2S 입장에서 PL endpoint가 backpressure를 걸 수 없다. 즉 MM2S가 DDR에서 데이터를 읽고 AXI-Stream으로 내보내는 과정은 downstream ready 때문에 막히지 않는다.

출력은 FIR 결과가 아니라 내부 counter로 만든다.

```verilog
assign m_axis_tvalid = out_active;
assign m_axis_tdata  = {4'h5, out_count};
assign m_axis_tlast  = out_active && (out_count == N_OUT[OUT_CNT_WIDTH-1:0] - 1'b1);
```

따라서 smoke-test의 판정력은 다음과 같다.

```text
smoke가 통과하면:
  PS/DDR/AXI DMA/UART/Python transport는 살아 있음

smoke도 MM2S timeout이면:
  FIR RTL이나 FIR wrapper 때문이라고 보기 어려움
  DMA MM2S 설정, transfer length, C register programming 쪽을 봐야 함
```

초기 smoke-test도 `CONFIG.c_sg_length_width` 수정 전에는 같은 timeout을 냈다.

이 순간 원인 후보가 크게 바뀌었다.

```text
이전 주 후보:
  FIR AXI-Stream wrapper handshake

smoke 실패 후 주 후보:
  AXI DMA MM2S 설정 또는 C에서 쓰는 transfer length
```

---

### 5. MM2S만 timeout이라는 점이 transfer length 비대칭과 맞았다

C app의 DMA 길이를 다시 확인했다.

```c
#define N_IN 8192
#define N_OUT 4096

DMA_REG(S2MM_LENGTH) = N_OUT * sizeof(int16_t);
DMA_REG(MM2S_LENGTH) = N_IN * sizeof(int16_t);
```

각 length 계산:

```text
S2MM_LENGTH = 4096 * 2 = 8192 bytes  = 0x2000
MM2S_LENGTH = 8192 * 2 = 16384 bytes = 0x4000
```

AXI DMA의 기본 `c_sg_length_width`가 14비트라면 표현 가능한 최대 byte count는 다음이다.

```text
2^14 - 1 = 16383 bytes = 0x3FFF
```

여기서 매우 중요한 비대칭이 나온다.

```text
S2MM_LENGTH = 8192  bytes <= 16383 bytes  -> 14비트 안에 들어감
MM2S_LENGTH = 16384 bytes >  16383 bytes  -> 1바이트 초과
```

관찰된 software error도 `S2MM timeout`이 아니라 `MM2S timeout`이었다.

```text
ERR:1 = MM2S DMA timeout
```

즉 실제 실패 방향과 length 초과 방향이 정확히 맞았다.

이 점이 결정적이었다. 만약 HP0 DDR path 전체가 죽었거나, PS7 DDR init이 틀렸거나, AXI-Lite가 잘못됐거나, UART가 깨졌다면 실패가 이렇게 `MM2S length만 1바이트 초과하는 방향`과 맞아떨어지기 어렵다.

이때의 핵심 가설:

```text
AXI DMA IP가 default 14-bit buffer length field로 생성되어 있고,
C app은 MM2S_LENGTH에 0x4000을 write한다.
0x4000은 14-bit max 0x3FFF보다 1 크므로 DMA가 정상적인 byte count로 처리하지 못한다.
그 결과 MM2S channel은 start되지만 complete/idle로 돌아오지 않는다.
```

---

### 6. `c_sg_length_width` 이름 때문에 놓치기 쉬운 지점

설정 이름은 `c_sg_length_width`라서 scatter-gather mode에서만 관련 있어 보일 수 있다.

하지만 현재 AXI DMA는 scatter-gather를 끈 simple/direct register mode다.

```tcl
CONFIG.c_include_sg {0}
```

그럼에도 AXI DMA IP의 buffer length register가 실제로 몇 비트의 byte count를 받을 수 있는지는 IP customization parameter에 의해 결정된다. 이 프로젝트에서는 그 parameter가 명시되지 않았고, Vivado가 기본값 14비트로 생성한 것으로 판단했다.

문제는 C 코드에서 `MM2S_LENGTH`가 32비트 memory-mapped register처럼 보인다는 점이다.

```c
DMA_REG(MM2S_LENGTH) = 16384;
```

C 관점에서는 아무 문제가 없어 보인다. 하지만 IP 내부에서 유효한 length field width가 14비트면, 0x4000은 표현 범위 밖이다.

이 버그가 까다로운 이유:

1. C compile error가 없다.
2. Vivado build error가 없다.
3. AXI-Lite write/read 자체는 된다.
4. DMA start bit도 들어간다.
5. DMASR error bit가 명확히 뜨지 않는다.
6. 결과적으로 software에서는 단순 timeout처럼 보인다.

그래서 처음에는 RTL handshake 문제처럼 보였다.

---

### 7. 수정은 smoke/main/debug BD 모두에 적용했다

원인을 검증하려면 smoke-test에만 적용하면 된다. 하지만 같은 실수를 반복하지 않기 위해 모든 관련 BD Tcl에 동일한 설정을 넣었다.

대상:

```text
vivado/bd_fir_dma.tcl
vivado/bd_fir_dma_axis_debug.tcl
vivado/bd_fir_dma_smoke.tcl
```

수정:

```tcl
set_property -dict [list \
  CONFIG.c_include_sg {0} \
  CONFIG.c_sg_length_width {23} \
  CONFIG.c_m_axis_mm2s_tdata_width {16} \
  CONFIG.c_s_axis_s2mm_tdata_width {16} \
] $axi_dma_0
```

여기서 `23`은 data width가 아니다. AXI-Stream payload는 여전히 16비트다.

```text
tdata width = 16 bit 유지
sample type = int16_t 유지
MM2S byte count 표현 범위만 증가
```

23비트의 최대 byte count:

```text
2^23 - 1 = 8,388,607 bytes
```

현재 필요한 MM2S length:

```text
16,384 bytes
```

즉 23비트는 현재 전송 길이에 대해 충분한 여유가 있다.

---

### 8. 검증 순서는 smoke 먼저, 메인 FIR 나중이었다

수정 후 바로 메인 FIR를 보지 않고 smoke-test를 먼저 다시 실행했다.

이유:

```text
메인 FIR가 통과하면 좋지만,
통과하지 않을 경우 length width 문제와 FIR wrapper 문제를 다시 구분하기 어렵다.

smoke가 먼저 통과해야
"DMA/DDR/UART transport는 해결됐다"는 기준점을 만들 수 있다.
```

수정 후 smoke 재빌드:

```bash
/home/young/Xilinx/Vivado/2024.2/bin/vivado \
  -mode batch \
  -source vivado/build_bd_fir_dma_smoke.tcl
```

smoke BOOT 재생성:

```bash
vitis/rebuild_boot_image.sh \
  --bit build/output/bd_fir_dma_smoke_wrapper.bit \
  --boot-out build/output/BOOT_smoke.bin \
  --boot-tag SMOKE
```

보드에서 확인한 tag:

```text
READY SMOKE
```

그 뒤 Python demo가 timeout 없이 plot까지 도달했다.

이것이 1차 확증이다.

```text
수정 전 smoke: MM2S timeout
수정 후 smoke: plot까지 도달
```

smoke-test는 FIR를 통과하지 않기 때문에, 이 차이는 FIR coefficient나 FIR datapath가 아니라 DMA transfer 설정 수정의 효과라고 볼 수 있다.

---

### 9. 메인 FIR도 통과하면서 원인이 사실상 확정됐다

smoke-test 통과 후 메인 FIR BD도 같은 length width 설정으로 재빌드했다.

```bash
/home/young/Xilinx/Vivado/2024.2/bin/vivado \
  -mode batch \
  -source vivado/build_bd_fir_dma.tcl
```

결과:

```text
WNS = 0.692 ns
bitstream = build/output/bd_fir_dma_wrapper.bit
XSA       = build/output/bd_fir_dma_wrapper.xsa
```

메인 FIR BOOT 재생성:

```bash
vitis/rebuild_boot_image.sh --boot-tag FIR
```

보드에서 확인해야 하는 tag:

```text
READY FIR
```

이후 `mode 1-1`, `mode 1-2` 모두 plot까지 도달했다.

이 결과로 최종 판정은 다음과 같다.

```text
반복되던 MM2S timeout의 직접 원인:
  AXI DMA c_sg_length_width 기본 14비트

왜 터졌는가:
  MM2S_LENGTH = 8192 samples * 2 bytes = 16384 bytes
  14-bit max = 16383 bytes
  정확히 1 byte 초과

왜 FIR RTL처럼 보였는가:
  DMA가 error bit 없이 running 상태로 멈췄고,
  downstream AXI-Stream backpressure 증상과 겉모습이 비슷했기 때문

왜 FIR RTL이 1차 원인이 아니라고 볼 수 있는가:
  s_axis_tready=1 smoke-test도 수정 전에는 실패했고,
  length width 수정 후 smoke와 메인 FIR가 모두 통과했기 때문
```

---

### 10. 이 문제를 다시 피하기 위한 체크 규칙

앞으로 DMA transfer length를 바꾸거나 sample count를 바꾸면 다음을 반드시 확인한다.

```text
MM2S_LENGTH = N_IN  * sizeof(sample)
S2MM_LENGTH = N_OUT * sizeof(sample)

MM2S_LENGTH <= 2^c_sg_length_width - 1
S2MM_LENGTH <= 2^c_sg_length_width - 1
```

현재 설정:

```text
c_sg_length_width = 23
max length = 8,388,607 bytes
```

현재 전송:

```text
MM2S_LENGTH = 16,384 bytes
S2MM_LENGTH = 8,192 bytes
```

따라서 현재 구조에서는 충분히 안전하다.

---

## 증거 화면

사용자가 smoke-test 재실행 후 다음 plot 화면을 확인했다.

```text
Figure 1
Scenario 1: 5MHz / 20MHz / 30MHz
왼쪽: 입력 FFT
오른쪽: 출력 FFT (FIR 후)
```

첨부된 스크린샷에서 확인되는 점:

1. Python demo가 timeout exception으로 종료되지 않고 `matplotlib` plot까지 도달했다.
2. 왼쪽 입력 FFT에는 5 MHz, 20 MHz, 30 MHz 성분이 보인다.
3. 오른쪽 출력 FFT가 그려졌으므로, 보드가 UART로 결과 payload를 PC에 반환했다.
4. 즉 SD boot -> baremetal app -> AXI DMA MM2S/S2MM -> DDR buffer -> UART transfer -> Python receive/plot 경로가 끝까지 한 번 통과했다.

주의:

이 화면은 `SMOKE` bitstream 기준이다. 따라서 FIR 필터 성능을 검증한 화면이 아니라, DMA/DDR/UART/Python 데이터 경로가 정상 완료됨을 보여주는 smoke-test 통과 증거다.

채팅에 첨부된 스크린샷의 실제 이미지 파일은 현재 repo 파일로 직접 접근되지 않았다. 나중에 이미지 파일을 repo에 저장한다면 아래 경로로 두고 이 문서에서 링크하면 된다.

```text
docs/log/assets/32_smoke_pass_after_dma_length_width_fix.png
```

권장 markdown 링크:

```markdown
![Smoke-test pass after DMA length width fix](assets/32_smoke_pass_after_dma_length_width_fix.png)
```

---

## 어떤 smoke-test였나?

이번에 통과한 smoke-test는 `rtl/debug/axis_dma_smoke_test.v`를 PL endpoint로 사용한다.

이 모듈의 목적은 FIR 계산을 검증하는 것이 아니라, AXI DMA가 실제로 다음 두 방향을 완료할 수 있는지 확인하는 것이다.

```text
MM2S: DDR source buffer -> AXI DMA -> PL stream input
S2MM: PL stream output -> AXI DMA -> DDR destination buffer
```

`axis_dma_smoke_test`는 입력 stream을 실제 FIR에 넣지 않는다.

```verilog
assign s_axis_tready = 1'b1;
```

즉 MM2S에서 들어오는 샘플은 항상 accept하고 버린다. 이 구조에서는 PL 쪽 backpressure가 MM2S timeout의 원인이 될 수 없다.

출력 stream은 내부 counter pattern으로 만든다.

```verilog
assign m_axis_tvalid = out_active;
assign m_axis_tdata  = {4'h5, out_count};
assign m_axis_tlast  = out_active && (out_count == N_OUT[OUT_CNT_WIDTH-1:0] - 1'b1);
```

즉 S2MM은 FIR 출력이 아니라 deterministic counter stream을 DDR에 쓴다.

이 smoke-test가 통과했다는 뜻:

1. PS가 AXI-Lite로 DMA register를 쓸 수 있다.
2. DMA reset/start sequence가 동작한다.
3. MM2S가 DDR에서 16384 bytes를 읽어 PL stream으로 보낼 수 있다.
4. S2MM이 PL stream 8192 bytes를 DDR destination buffer에 쓸 수 있다.
5. C app이 destination buffer를 읽어 UART로 PC에 보낼 수 있다.
6. Python script가 UART 결과를 받아 plot까지 생성할 수 있다.

검증하지 않은 것:

1. 실제 FIR coefficient가 맞는지
2. `fir_decimator_n43_axis.v`의 filtering 결과가 golden model과 일치하는지
3. FIR wrapper의 TLAST/valid/ready 처리가 긴 스트림에서 항상 안전한지
4. 5 MHz passband, 20/30 MHz stopband 감쇠가 spec을 만족하는지

따라서 smoke-test 통과는 "인프라가 살아났다"는 의미이고, "FIR가 완전히 맞다"는 의미는 아니다.

---

## 통과까지의 경로

### 1. 기존 실패 로그

기존 FIR BOOT와 단순 decimator debug BOOT는 모두 같은 형태로 실패했다.

```text
D2
ST2 M=00000001 S=00000001
D3
ST3 M=00000001 S=00000000
D4
ST4 M=00000000 S=00000000
MM2S M=00000000 S=00000000
MM2S M=00000000 S=00000000
MM2STO M=00000000 S=00000000
ERR:1
```

이 로그는 DMA가 error bit를 세우지 않고 running 상태에서 끝나지 않는다는 점이 특징이었다.

처음에는 AXI-Stream handshake 문제, 특히 FIR wrapper의 `tready`, `tvalid`, `tlast` 문제가 유력해 보였다. 하지만 FIR를 제거한 단순 decimator에서도 같은 문제가 났고, 입력을 무조건 accept하는 smoke-test에서도 같은 문제가 나면서 원인은 PL 계산부가 아니라 DMA transfer 설정 쪽으로 이동했다.

### 2. length width 가설

C app은 MM2S에 8192개 `int16_t` sample을 보낸다.

```c
#define N_IN 8192
DMA_REG(MM2S_LENGTH) = N_IN * sizeof(int16_t);
```

결과 byte count는 `16384 bytes`다.

AXI DMA IP의 `c_sg_length_width`가 기본값 14비트라면 최대 표현 가능한 byte count는 `16383 bytes`다.

이 프로젝트의 전송 길이는 그 한계를 정확히 1 byte 넘는다.

이 조건은 다음 현상과 잘 맞았다.

```text
DMA start bit는 들어감
DMASR error bit는 안 뜸
idle bit도 끝까지 안 뜸
결국 software timeout
```

### 3. Tcl 수정

다음 BD Tcl에 `CONFIG.c_sg_length_width {23}`를 명시했다.

```text
vivado/bd_fir_dma.tcl
vivado/bd_fir_dma_axis_debug.tcl
vivado/bd_fir_dma_smoke.tcl
```

수정 형태:

```tcl
set_property -dict [list \
  CONFIG.c_include_sg {0} \
  CONFIG.c_sg_length_width {23} \
  CONFIG.c_m_axis_mm2s_tdata_width {16} \
  CONFIG.c_s_axis_s2mm_tdata_width {16} \
] $axi_dma_0
```

여기서 `23`은 AXI-Stream data width를 23비트로 바꾸는 것이 아니다.

변하지 않는 것:

```text
AXI-Stream tdata width = 16 bit
C sample type = int16_t
input sample count = 8192
output sample count = 4096
```

바뀌는 것:

```text
AXI DMA LENGTH register가 표현할 수 있는 byte count range
```

23비트일 때 최대 length:

```text
2^23 - 1 = 8,388,607 bytes
```

현재 필요한 `16384 bytes`보다 충분히 크다.

### 4. smoke bitstream 재빌드

수정 반영 후 smoke BD를 다시 빌드했다.

```bash
/home/young/Xilinx/Vivado/2024.2/bin/vivado \
  -mode batch \
  -source vivado/build_bd_fir_dma_smoke.tcl
```

빌드 결과:

```text
Vivado synth/impl/bitgen 성공
WNS = 1.485 ns
```

산출물:

```text
build/output/bd_fir_dma_smoke_wrapper.bit
build/output/bd_fir_dma_smoke_wrapper.xsa
```

### 5. smoke BOOT 재생성

다음 명령으로 `SMOKE` tag가 들어간 BOOT image를 만들었다.

```bash
vitis/rebuild_boot_image.sh \
  --bit build/output/bd_fir_dma_smoke_wrapper.bit \
  --boot-out build/output/BOOT_smoke.bin \
  --boot-tag SMOKE
```

산출물:

```text
build/output/BOOT_smoke.bin
```

보드 부팅 시 확인해야 하는 banner:

```text
READY SMOKE
```

사용자가 실제로 `READY SMOKE`를 확인했다. 따라서 이 테스트는 잘못된 BOOT로 수행된 것이 아니다.

### 6. Python demo 재실행

보드 부팅 후 PC에서 기존 Python demo를 실행했다.

```bash
python sw/fir_decimator_demo.py --mode 1-1 --port /dev/ttyUSB1 --timeout 30
```

이전에는 `ERR:1: MM2S DMA timeout`으로 끝났지만, length width 수정 후에는 plot 창까지 도달했다.

이 차이가 이번 수정의 핵심 판정 근거다.

---

## smoke 통과가 의미하는 원인 배제

### 배제 가능성이 커진 것

아래 항목은 지금 단계에서 1차 원인 가능성이 낮아졌다.

```text
보드 불량
PS7 init / DDR init 문제
UART 기본 통신 문제
Python timeout만의 문제
AXI-Lite DMA register 접근 문제
HP0 DDR read/write path 전체 불능
FIR 내부 MAC 연산 자체 때문에 MM2S가 멈춘다는 가설
```

### 여전히 남아 있는 검증 대상

이제 진짜 검증해야 할 대상은 메인 FIR path다.

```text
rtl/transposed_form/n43/fir_decimator_n43_axis.v
vivado/bd_fir_dma.tcl
sw/fir_decimator_demo.c의 FIR mode runtime sequence
Python golden/reference 비교
```

단, 이제는 infrastructure 문제가 아니라 실제 FIR output correctness 문제로 들어갈 수 있다.

---

## JTAG MSB 오염과의 관계

이번 `CONFIG.c_sg_length_width` 문제와 이전에 관찰한 JTAG/XSDB DDR write의 MSB 오염은 같은 원인으로 묶지 않는 것이 맞다.

판정:

```text
JTAG MSB 오염:
  별도 디버그 경로 문제 또는 보드/케이블/XSDB/JTAG access path 문제일 가능성이 높음

DMA MM2S timeout:
  AXI DMA IP의 buffer length field width 설정 문제
```

두 문제가 헷갈렸던 이유는 둘 다 "DDR에 쓰고 읽는 데이터가 이상하다"는 큰 범주 안에 있었기 때문이다. 하지만 실제 경로는 다르다.

JTAG/XSDB DDR write 경로:

```text
PC xsdb
-> JTAG cable
-> DAP/ARM debug access path
-> PS DDR controller
-> DDR
```

SD boot 이후 baremetal DMA 경로:

```text
PS C app
-> AXI DMA register programming
-> AXI DMA MM2S/S2MM
-> PS HP0 port
-> DDR
-> UART return
```

이 두 경로는 DDR 자체를 공유하지만, 데이터가 DDR까지 도달하는 access path가 다르다.

특히 결정적인 차이는 다음이다.

1. JTAG `mwr/mrd`에서는 MSB 오염이 관찰됐다.
2. 그러나 SD boot에서는 `READY`, `SMOKE`, `FIR` app이 정상 실행됐다.
3. smoke-test 통과 후에는 DMA가 DDR source buffer를 읽고 destination buffer에 쓰고, C app이 이를 UART로 반환했다.
4. 메인 FIR도 plot까지 도달했다.
5. 따라서 PS DDR controller나 DDR chip이 일반적으로 깨져 있다고 보기는 어렵다.

만약 JTAG MSB 오염과 DMA timeout이 같은 근본 원인이었다면, `CONFIG.c_sg_length_width`만 바꿨을 때 smoke와 메인 FIR가 동시에 통과하는 결과가 나오기 어렵다.

이번 timeout 문제는 아래 조건과 너무 정확히 맞는다.

```text
실패 방향: MM2S
초과 length: MM2S_LENGTH만 14-bit limit를 1 byte 초과
S2MM_LENGTH는 14-bit limit 안에 있음
수정 내용: c_sg_length_width 확대
수정 결과: smoke 및 main FIR 통과
```

따라서 현재 결론:

```text
JTAG MSB 오염은 중요한 관찰이었지만,
이번 MM2S timeout의 직접 원인은 아니다.
```

다만 JTAG 문제를 완전히 무시하면 안 된다. 앞으로 JTAG로 DDR memory를 직접 쓰고 읽는 bring-up을 할 때는 여전히 신뢰성이 낮을 수 있다.

권장 정책:

```text
1. 최종 시스템 검증은 SD boot 기반으로 수행한다.
2. JTAG mwr/mrd 결과만으로 PS7 init 또는 DDR 설정 불량을 확정하지 않는다.
3. JTAG를 쓸 경우에는 작은 pattern, byte lane별 pattern, 여러 주소, 여러 케이블/보드로 별도 검증한다.
4. DMA/RTL 검증은 가능하면 SD boot + UART result path를 기준으로 삼는다.
```

즉 JTAG MSB 오염은 "debug transport가 불안정할 수 있다"는 경고로 남기고, 이번 `MM2S DMA timeout`의 root cause와는 분리한다.

---

## 메인 FIR 복귀 기준

smoke-test가 통과했으므로 다음 순서는 메인 FIR BD를 같은 length width 수정 상태로 재빌드하는 것이다.

명령:

```bash
/home/young/Xilinx/Vivado/2024.2/bin/vivado \
  -mode batch \
  -source vivado/build_bd_fir_dma.tcl
```

작성 시점에 메인 FIR BD 재빌드는 완료됐다.

```text
WNS = 0.692 ns
bitstream = build/output/bd_fir_dma_wrapper.bit
XSA       = build/output/bd_fir_dma_wrapper.xsa
```

다음에는 이 bitstream으로 메인 FIR BOOT를 만든다.

```bash
vitis/rebuild_boot_image.sh --boot-tag FIR
```

예상 산출물:

```text
build/output/BOOT.bin
```

SD 카드에는 이 파일을 `BOOT.bin` 이름으로 복사한다.

부팅 후 먼저 확인:

```text
READY FIR
```

그 다음 실제 FIR demo를 실행한다.

```bash
python sw/fir_decimator_demo.py --mode 1-1 --port /dev/ttyUSB1 --timeout 30
```

---

## 다음 판정

### Case A: 메인 FIR도 plot까지 도달

이 경우 DMA length width 문제가 전체 timeout의 직접 원인이었다고 확정한다.

그 다음 볼 것은 필터 성능이다.

```text
5 MHz 성분 보존
20 MHz / 30 MHz 성분 감쇠
Python golden model과 amplitude/phase 차이
출력 sample count 4096
```

### Case B: 메인 FIR에서 다시 timeout

이 경우 smoke는 통과했으므로 DMA/DDR/UART path는 기본적으로 살아 있다.

다음 의심 대상은 다시 FIR AXI-Stream wrapper다.

특히 확인할 것:

```text
s_axis_tready가 중간에 계속 low로 붙는지
m_axis_tvalid가 S2MM ready와 정상 handshake하는지
m_axis_tlast가 4096번째 output에서 정확히 1 cycle 발생하는지
input TLAST와 output TLAST 관계가 꼬이지 않는지
FIR latency 때문에 output count와 DMA S2MM_LENGTH가 어긋나지 않는지
```

### Case C: 메인 FIR는 통과하지만 spectrum이 이상함

이 경우 transport는 해결됐고, 순수 FIR correctness/debug 단계로 이동한다.

다음 후보:

```text
coefficient order
Q format scaling
rounding/saturation
decimation phase
transposed-form pipeline alignment
Python plot/golden scaling
```

---

## 한 줄 요약

이번 smoke 통과는 "AXI DMA가 안 도는 문제"를 해결했다는 의미다. 원인은 `AXI DMA c_sg_length_width` 기본 14비트와 `16384 bytes` MM2S transfer length의 1바이트 초과 충돌이었다. 이제 메인 FIR로 돌아가서 실제 필터 출력이 맞는지 확인할 단계다.
