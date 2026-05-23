# 31. DMA smoke-test 분리 및 AXI DMA length width 수정

- 작성일: 2026-05-24
- 선행 문서: `29_ps7_init_and_jtag_ddr_write_recheck.md`, `30_new_board_sd_boot_ready_and_dma_trace.md`, `workflow_v14.md`

---

## 배경

log 30에서 새 보드 SD 부팅은 성공했다.

```text
READY
```

따라서 기존에 의심했던 PS7 init / DDR init / 보드 불량 문제는 1차 원인에서 내려왔다. 그러나 PC Python demo를 실행하면 DMA 단계에서 계속 멈췄다.

```bash
python sw/fir_decimator_demo.py --mode 1-1 --port /dev/ttyUSB1 --timeout 30
```

대표 에러:

```text
RuntimeError: 보드 DMA 오류 ERR:1: MM2S DMA timeout.
최근 UART 텍스트:
GEN | D0 | D1 | D2 |
ST2 M=00000001 S=00000001 |
D3 | ST3 M=00000001 S=00000000 |
D4 | ST4 M=00000000 S=00000000 |
MM2S M=00000000 S=00000000 |
...
MM2STO M=00000000 S=00000000 |
ERR:1 | ERR:1
```

이 로그의 의미는 다음과 같다.

| 지점 | 의미 |
|---|---|
| `D0` | source buffer cache flush 진입 |
| `D1` | AXI DMA soft reset 요청 |
| `D2`, `ST2 M=1 S=1` | reset 완료, 양 채널 halted 상태 |
| `D3`, `ST3 M=1 S=0` | S2MM 채널 시작됨 |
| `D4`, `ST4 M=0 S=0` | MM2S 채널도 시작됨 |
| `M=0 S=0` 반복 | DMA error bit 없이 running 상태 유지 |
| `ERR:1` | MM2S idle bit가 끝까지 올라오지 않음 |

즉 AXI-Lite 레지스터 접근, DMA reset, DMA run bit 설정 자체는 동작한다. 문제는 MM2S 전송이 끝나지 않는다는 점이다.

---

## 1차 가설: FIR AXI-Stream wrapper 문제

초기에는 `rtl/transposed_form/n43/fir_decimator_n43_axis.v`의 AXI-Stream handshake/TLAST 문제가 가장 그럴듯했다.

이유:

- DMA status상 slave/decode/internal error bit는 보이지 않았다.
- MM2S가 idle로 못 가는 것은 downstream backpressure로도 발생할 수 있다.
- FIR wrapper는 `s_axis_tready`, `m_axis_tvalid`, `m_axis_tlast`를 직접 제어한다.
- 이전 log 25에서도 TLAST/deadlock 계열 문제를 다룬 적이 있다.

따라서 기존 FIR RTL을 그대로 의심하지 않고, PL 쪽을 갈아끼울 수 있는 디버그 경로를 만들었다.

---

## 방법 B: 기존 BD를 보존하고 별도 debug BD 생성

기존 메인 설계 파일:

```text
vivado/bd_fir_dma.tcl
```

은 바로 수정하지 않고, 별도 디버그 BD를 생성하는 방식으로 진행했다.

이 방식의 목적:

1. 기존 FIR DMA BD를 보존한다.
2. PL stream endpoint만 바꿔서 같은 PS/DDR/DMA 조건에서 비교한다.
3. 결과가 나오면 원인을 FIR wrapper / DMA-BD / C 제어 중 어디에 둘지 분리한다.

---

## 디버그 래퍼 1: `axis_decimator_m2_n43_debug`

### 추가 파일

```text
rtl/debug/axis_decimator_m2_n43_debug.v
vivado/bd_fir_dma_axis_debug.tcl
vivado/build_bd_fir_dma_axis_debug.tcl
```

### 의도

기존 FIR 연산을 제거하고, 매우 단순한 M=2 decimator만 AXI-Stream으로 구현했다.

동작:

- 입력 AXI-Stream 16비트 수신
- 매 2번째 샘플만 출력
- 8192 input samples -> 4096 output samples
- 마지막 출력에 TLAST 생성
- 기존 FIR wrapper와 동일한 top-level port 이름 사용

핵심 포트 호환성:

```verilog
input  wire               s_axis_tvalid,
output wire               s_axis_tready,
input  wire signed [15:0] s_axis_tdata,
input  wire               s_axis_tlast,

output wire               m_axis_tvalid,
input  wire               m_axis_tready,
output wire signed [15:0] m_axis_tdata,
output wire               m_axis_tlast
```

### 빌드 결과

```text
Vivado synth/impl/bitgen 성공
WNS = 1.557 ns
```

산출물:

```text
build/output/bd_fir_dma_axis_debug_wrapper.bit
build/output/bd_fir_dma_axis_debug_wrapper.xsa
build/output/BOOT_axis_debug.bin
```

### 보드 결과

`BOOT_axis_debug.bin`으로 부팅 후 Python demo 실행 결과, 기존 FIR BOOT와 동일하게 실패했다.

```text
ERR:1: MM2S DMA timeout
ST4 M=00000000 S=00000000
MM2S M=00000000 S=00000000 반복
```

### 판정

단순 decimator에서도 같은 timeout이므로, "FIR 내부 계산 자체" 또는 "기존 FIR wrapper 단독" 문제 가능성은 낮아졌다.

다만 이 debug wrapper도 입력 stream과 출력 stream이 결합되어 있기 때문에, S2MM backpressure가 MM2S까지 전파되는 구조는 여전히 남아 있었다.

---

## 디버그 래퍼 2: `axis_dma_smoke_test`

### 추가 파일

```text
rtl/debug/axis_dma_smoke_test.v
vivado/bd_fir_dma_smoke.tcl
vivado/build_bd_fir_dma_smoke.tcl
```

### 의도

FIR, decimator, input-output 결합을 모두 제거하고 AXI DMA 자체를 smoke-test한다.

동작:

```text
MM2S input  -> 무조건 accept 후 discard
S2MM output -> 내부 counter pattern 4096 samples 생성
```

핵심:

```verilog
assign s_axis_tready = 1'b1;

assign m_axis_tvalid = out_active;
assign m_axis_tdata  = {4'h5, out_count};
assign m_axis_tlast  = out_active && (out_count == N_OUT[OUT_CNT_WIDTH-1:0] - 1'b1);
```

이 구조에서는 PL endpoint가 MM2S에 backpressure를 줄 수 없다. 따라서 smoke-test에서도 MM2S timeout이 나면, FIR wrapper나 decimator가 아니라 DMA MM2S read/length/config 쪽을 봐야 한다.

### 빌드 결과

초기 smoke-test 빌드:

```text
Vivado synth/impl/bitgen 성공
WNS = 1.395 ns
BOOT_smoke.bin 생성 성공
```

산출물:

```text
build/output/bd_fir_dma_smoke_wrapper.bit
build/output/bd_fir_dma_smoke_wrapper.xsa
build/output/BOOT_smoke.bin
```

### BOOT 식별 문제 해결

초기에는 FIR/AXISDBG/SMOKE BOOT가 UART banner상 구분되지 않았다. 그래서 C 앱과 boot rebuild script에 boot tag 기능을 추가했다.

수정 파일:

```text
sw/fir_decimator_demo.c
vitis/rebuild_boot_image.sh
```

C 앱은 optional header를 include한다.

```c
#if __has_include("boot_tag.h")
#include "boot_tag.h"
#endif

#ifndef BOOT_TAG
#define BOOT_TAG "FIR"
#endif
```

부팅 banner:

```c
uart_puts("READY ");
uart_puts(BOOT_TAG);
uart_puts("\r\n");
```

`vitis/rebuild_boot_image.sh`에는 `--boot-tag` 옵션을 추가했다.

예:

```bash
vitis/rebuild_boot_image.sh \
  --bit build/output/bd_fir_dma_smoke_wrapper.bit \
  --boot-out build/output/BOOT_smoke.bin \
  --boot-tag SMOKE
```

보드에서 실제로 다음 banner가 확인됐다.

```text
READY SMOKE
```

따라서 이후 smoke-test 실패는 "잘못된 BOOT를 올림" 문제가 아니다.

### 보드 결과

`READY SMOKE` 확인 후 Python demo 실행 결과:

```text
ERR:1: MM2S DMA timeout
ST4 M=00000000 S=00000000
MM2S M=00000000 S=00000000 반복
```

### 판정

`axis_dma_smoke_test`는 `s_axis_tready = 1`이라 MM2S stream backpressure가 없어야 한다. 그런데도 MM2S가 idle로 가지 않는다.

따라서 다음 원인은 PL FIR/decimator가 아니라 AXI DMA MM2S 설정 또는 C에서 쓰는 DMA transfer length 쪽으로 좁혀졌다.

---

## 새 핵심 가설: AXI DMA Buffer Length Register width

현재 C 코드의 MM2S 길이:

```c
#define N_IN 8192
DMA_REG(MM2S_LENGTH) = N_IN * sizeof(int16_t);
```

계산:

```text
8192 samples * 2 bytes/sample = 16384 bytes = 0x4000
```

AXI DMA IP의 `c_sg_length_width` 기본값은 14비트다.

```text
2^14 - 1 = 16383 bytes
```

즉 현재 MM2S 전송 길이 `16384 bytes`는 AXI DMA 기본 length width가 표현할 수 있는 최대값보다 정확히 1바이트 크다.

이 경우 가능한 증상:

```text
C에서 MM2S_LENGTH = 0x4000 write
DMA 내부 length field가 14비트라면 0x4000은 표현 불가
하위 14비트만 보면 0으로 해석될 수 있음
DMA는 running 상태로 들어가지만 정상 완료하지 못함
DMASR error bit 없이 idle도 안 뜸
결과: MM2S timeout
```

이 증상은 지금까지 관찰한 로그와 잘 맞는다.

---

## 적용한 수정: `c_sg_length_width {23}`

AXI DMA 설정에 length width를 명시했다.

대상 파일:

```text
vivado/bd_fir_dma.tcl
vivado/bd_fir_dma_axis_debug.tcl
vivado/bd_fir_dma_smoke.tcl
```

추가 설정:

```tcl
set_property -dict [list \
  CONFIG.c_include_sg {0} \
  CONFIG.c_sg_length_width {23} \
  CONFIG.c_m_axis_mm2s_tdata_width {16} \
  CONFIG.c_s_axis_s2mm_tdata_width {16} \
] $axi_dma_0
```

### 왜 23비트인가?

최소 해결값은 15비트다.

```text
2^15 - 1 = 32767 bytes
```

그러나 23비트는 AXI DMA에서 흔히 쓰는 넉넉한 값이다.

```text
2^23 - 1 = 8,388,607 bytes ~= 8 MB
```

데이터 폭(`tdata=16`)을 바꾸는 것이 아니라, 한 번에 전송 가능한 byte count 범위만 키우는 설정이다.

변하지 않는 것:

- AXI-Stream `tdata` 폭: 16비트 유지
- 샘플 포맷: `int16_t`
- FIR coefficient / Q format
- DDR 폭
- UART packet format

바뀌는 것:

- AXI DMA `MM2S_LENGTH` / `S2MM_LENGTH` 레지스터가 표현할 수 있는 byte count 범위

---

## length width 수정 후 smoke 재빌드

수정 반영 후 smoke-test bitstream과 BOOT를 다시 생성했다.

Vivado:

```bash
/home/young/Xilinx/Vivado/2024.2/bin/vivado \
  -mode batch \
  -source vivado/build_bd_fir_dma_smoke.tcl
```

결과:

```text
Vivado synth/impl/bitgen 성공
WNS = 1.485 ns
```

BOOT 생성:

```bash
vitis/rebuild_boot_image.sh \
  --bit build/output/bd_fir_dma_smoke_wrapper.bit \
  --boot-out build/output/BOOT_smoke.bin \
  --boot-tag SMOKE
```

결과:

```text
Bootimage generated successfully
build/output/BOOT_smoke.bin
```

이 `BOOT_smoke.bin`은 length width 수정이 반영된 smoke-test image다.

---

## 현재 상태

### 확인 완료

1. 새 보드 SD boot는 된다.
2. `READY SMOKE`가 실제로 보였으므로 smoke BOOT 적용은 확인됐다.
3. FIR wrapper 대신 단순 decimator를 넣어도 기존과 같은 MM2S timeout이 났다.
4. FIR/decimator를 모두 제거한 smoke-test에서도 기존과 같은 MM2S timeout이 났다.
5. 따라서 기존 FIR RTL 단독 문제 가능성은 낮다.
6. AXI DMA default length width 14비트와 현재 16384 byte transfer가 충돌할 가능성이 높다.
7. `c_sg_length_width {23}` 수정은 Tcl에 반영했고, smoke BOOT도 재생성했다.

### 아직 미확인

length width 수정 후 `BOOT_smoke.bin`을 SD 카드에 다시 넣어 보드에서 재실행한 결과는 아직 문서화되지 않았다.

다음 테스트:

```bash
# SD 카드에는 build/output/BOOT_smoke.bin을 BOOT.bin으로 복사

python sw/fir_decimator_demo.py --mode 1-1 --port /dev/ttyUSB1 --timeout 30
```

부팅 후 먼저 확인:

```text
READY SMOKE
```

---

## 다음 판정 기준

### Case A: length width 수정 후 SMOKE 통과

가장 가능성 높은 시나리오다.

판정:

```text
원인 = AXI DMA c_sg_length_width 기본값 14비트
```

다음 작업:

1. 메인 FIR BD를 length width 수정 반영 상태로 재빌드
2. 새 `bd_fir_dma_wrapper.bit/.xsa` 생성
3. `vitis/rebuild_boot_image.sh --boot-tag FIR`로 새 `BOOT.bin` 생성
4. 원래 FIR demo 재실행

### Case B: length width 수정 후 SMOKE도 여전히 MM2S timeout

판정:

```text
length width는 필요한 수정이지만, 유일 원인은 아님
```

다음 후보:

- AXI DMA MM2S memory read path 설정
- HP0/interconnect read transaction 문제
- DMA register programming sequence 문제
- MM2S_LENGTH write 직후 실제 register readback 확인 필요
- 더 작은 length, 예: 8192 bytes 또는 1024 bytes로 C-level 축소 테스트 필요

### Case C: SMOKE에서 MM2S는 통과하고 S2MM timeout

판정:

```text
MM2S length 문제는 해결됐고, S2MM write/receive path 문제로 이동
```

다음 후보:

- S2MM output TLAST
- S2MM_LENGTH
- HP0 write path
- destination buffer/cache invalidate

---

## 재실행 명령 요약

### Smoke bit/XSA 재빌드

```bash
/home/young/Xilinx/Vivado/2024.2/bin/vivado \
  -mode batch \
  -source vivado/build_bd_fir_dma_smoke.tcl
```

### Smoke BOOT 재생성

```bash
vitis/rebuild_boot_image.sh \
  --bit build/output/bd_fir_dma_smoke_wrapper.bit \
  --boot-out build/output/BOOT_smoke.bin \
  --boot-tag SMOKE
```

### 보드 테스트

```bash
python sw/fir_decimator_demo.py --mode 1-1 --port /dev/ttyUSB1 --timeout 30
```

### 메인 FIR로 돌아갈 때

length width 수정이 smoke-test에서 효과가 확인되면 메인 FIR BD를 재빌드한다.

```bash
/home/young/Xilinx/Vivado/2024.2/bin/vivado \
  -mode batch \
  -source vivado/build_bd_fir_dma.tcl
```

그 다음 C/BOOT 재생성:

```bash
vitis/rebuild_boot_image.sh --boot-tag FIR
```

---

## 핵심 교훈

이번 문제는 RTL handshake 문제처럼 보였지만, smoke-test를 만들자 PL wrapper를 거의 배제할 수 있었다. 특히 `s_axis_tready=1`인 smoke endpoint에서도 MM2S가 끝나지 않았다는 점이 결정적이었다.

AXI DMA에서 `LENGTH`는 단순한 32비트 C register처럼 보이지만, 실제 유효 bit width는 IP 설정(`c_sg_length_width`)에 의해 제한된다. 현재 프로젝트의 8192개 `int16_t` 입력은 정확히 16384 bytes라서, 기본 14비트 최대값 16383 bytes를 1바이트 초과한다. 이 1바이트 차이가 MM2S timeout의 유력 원인이다.

앞으로 DMA packet length를 바꿀 때는 다음을 항상 같이 확인한다.

```text
N_IN * sizeof(sample) <= 2^c_sg_length_width - 1
N_OUT * sizeof(sample) <= 2^c_sg_length_width - 1
```

