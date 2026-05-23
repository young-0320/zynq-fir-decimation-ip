# 29. PS7 init 및 JTAG DDR byte[3] 오염 재검증

- 작성일: 2026-05-23
- 선행 문서: `24_jtag_download_troubleshooting.md`, `27_ddr_msb_corruption_investigation.md`, `workflow_v14.md`

---

## 배경

workflow v14에서는 SD 부팅용 XSA/FSBL 체인을 재정리하면서, XSA 내부 `ps7_init.tcl` / `ps7_init.c`의 DDR 초기화값을 Digilent Z7-20 reference 계열과 비교하도록 했다.

그러나 새로 생성한 FIR DMA XSA에서 `hwh`의 DDR 설정은 정상처럼 보이지만 `ps7_init`의 DDRC 레지스터 값이 reference와 달랐다. 이 때문에 다음 두 가지 가능성을 분리해야 했다.

1. FIR DMA Block Design 또는 `bd_fir_dma.tcl`이 잘못되어 `ps7_init`이 틀리게 생성됨
2. `ps7_init` 값과 무관하게 XSDB/JTAG의 DDR write 경로 자체가 byte[3] 오염을 일으킴

---

## 문제 1: AXI-Stream RTL 결함 가능성 재검토

`fir_decimator_n43_axis.v`가 S2MM timeout의 원인일 가능성을 다시 검토했다. 현재 MSB 오염은 `dow`, `mwr`, `mrd`로 DDR을 직접 쓰고 읽는 경로에서 관찰되며, 이 경로는 PL FIR RTL이나 AXI-Stream wrapper를 거치지 않는다.

현재 워킹트리 기준 RTL 시뮬레이션도 재실행했다.

```text
make run_all 결과:
PASS [S1] TREADY=1 data+TLAST: 4096 samples
PASS [S2] Random Backpressure + Bubble: 4096 samples
PASS [S3] Reset Recovery: 4096 samples
PASS tb_fir_decimator_n43_axis: all scenarios
5개 TB 전부 PASS
```

판정: 현재 관찰 중인 DDR byte[3] 오염의 1차 원인으로 AXI-Stream RTL을 보기는 어렵다. RTL은 SD 부팅 후 UART `READY`가 뜨고 DMA runtime 단계에서 S2MM timeout이나 TLAST 문제가 재현될 때 다시 의심한다.

---

## 문제 2: FIR DMA XSA 내부 `ps7_init` 검사

새로 생성한 XSA:

```text
build/output/bd_fir_dma_wrapper.xsa
```

XSA 내부 파일명은 v14 기준으로 대체로 정상이다.

```text
bd_fir_dma.hwh
bd_fir_dma_wrapper.bit
ps7_init.tcl
ps7_init.c
```

`hwh`의 DDR 고수준 파라미터는 Zybo Z7-20 설정과 일치했다.

| 항목 | 값 |
|---|---|
| DDR part | `MT41K256M16 RE-125` |
| DDR bus width | `32 Bit` |
| Board delay | `0.221 / 0.222 / 0.217 / 0.244` |
| DQS-to-CLK delay | `-0.050 / -0.044 / -0.035 / -0.100` |
| CL / CWL | `7 / 6` |
| Speed bin | `DDR3_1066F` |
| tRCD / tRP / tRC / tRASmin | `7 / 7 / 48.75 / 35.0` |

하지만 XSA 내부 `ps7_init.tcl` / `ps7_init.c`는 다음 값을 생성했다.

| 레지스터 | 생성값 |
|---|---|
| `0xF8006004` | `0x00001082` / `0x00081082` |
| `0xF8006014` | `0x0004285B` |
| `0xF8006018` | `0x44E458D3` |
| `0xF800601C` | `0x7282BCE5` |
| `0xF8006030` | `0x00040B30` |

workflow v14에서 기대한 reference 계열은 다음이었다.

```text
0xF8006004 -> 0x00001081 / 0x00081081
0xF8006014 -> 0x0004281A
0xF8006018 -> 0x44E458D2
0xF800601C -> 0x720238E5
0xF8006030 -> 0x00040930
```

초기 해석은 "FIR DMA BD가 잘못되어 `ps7_init`이 틀렸다"였지만, 이후 최소 프로젝트 검증으로 이 가정은 약해졌다.

---

## 문제 3: 최소 Zynq PS7 프로젝트로 `ps7_init` 기준 확인

Vivado에서 깨끗한 최소 프로젝트를 생성했다.

| 항목 | 설정 |
|---|---|
| Project type | RTL Project |
| Sources / constraints | 추가 없음 |
| Board | Zybo Z7-20 |
| Block Design | ZYNQ7 Processing System 단독 |
| 적용 | Run Block Automation |
| 비트스트림 | 생성하지 않음 |
| Export | bitstream 없이 XSA export |

생성한 XSA:

```text
build/output/zybo_ps7_bringup_min.xsa
```

이 최소 XSA 내부 `ps7_init.tcl` / `ps7_init.c`도 FIR DMA XSA와 같은 DDRC 값을 생성했다.

```text
0xF8006004 -> 0x00001082 / 0x00081082
0xF8006014 -> 0x0004285B
0xF8006018 -> 0x44E458D3
0xF800601C -> 0x7282BCE5
0xF8006030 -> 0x00040B30
```

판정: 현재 Vivado 2024.2 + 현재 Zybo Z7-20 board file 조합에서는, 순수 PS7-only 프로젝트도 `00001082` 계열 `ps7_init`을 생성한다. 따라서 `bd_fir_dma.tcl` 또는 FIR DMA BD만의 문제라고 보기 어렵다.

---

## 문제 4: reference / bringup `ps7_init`로 JTAG DDR write 재검증

기존 bringup Vitis workspace에는 reference 계열 `ps7_init.tcl`이 남아 있었다.

```text
build/vitis_bringup/fir_dma_bringup_demo/_ide/psinit/ps7_init.tcl
build/vitis_bringup/fir_dma_bringup_pf/export/fir_dma_bringup_pf/hw/ps7_init.tcl
```

해당 파일은 기대한 reference DDRC 값을 포함한다.

```text
0xF8000180 -> 0x00100A20
0xF8000190 -> 0x00100500
0xF8006004 -> 0x00001081 / 0x00081081
0xF8006014 -> 0x0004281A
0xF8006018 -> 0x44E458D2
0xF800601C -> 0x720238E5
0xF8006030 -> 0x00040930
```

XSDB에서 ARM target을 선택한 뒤 이 `ps7_init`으로 초기화하고 DDR burst write를 수행했다.

```tcl
targets -set 2
stop
rst -processor

source /home/young/dev/10_zynq-fir-decimation-ip/build/vitis_bringup/fir_dma_bringup_demo/_ide/psinit/ps7_init.tcl
ps7_init
ps7_post_config

mwr -force 0x00100000 {0x11111111 0x22222222 0x33333333 0x44444444}
mrd -force 0x00100000 4
```

결과:

```text
100000: D7111111
100004: E9222222
100008: 4D333333
10000C: EF444444
```

reference 계열 `ps7_init`을 사용해도 byte[3] 오염이 재현됐다.

---

## 문제 5: 최소 XSA `ps7_init`로 JTAG DDR write 재검증

이번에는 최소 PS7 XSA 내부에서 꺼낸 `ps7_init.tcl`을 사용했다.

```bash
cd /home/young/dev/10_zynq-fir-decimation-ip
unzip -p build/output/zybo_ps7_bringup_min.xsa ps7_init.tcl \
  > /tmp/zybo_ps7_bringup_min_ps7_init.tcl
```

XSDB 실행:

```tcl
targets -set 2
stop
rst -processor

source /tmp/zybo_ps7_bringup_min_ps7_init.tcl
ps7_init
ps7_post_config

mwr -force 0x00100000 {0x11111111 0x22222222 0x33333333 0x44444444}
mrd -force 0x00100000 4
```

결과:

```text
100000: 00111111
100004: 00222222
100008: 00333333
10000C: 44444444
```

현재 Vivado가 생성한 `00001082` 계열 `ps7_init`을 사용해도 byte[3] 오염이 재현됐다.

---

## 최종 판정

이번 재검증으로 다음을 확인했다.

| 항목 | 결과 | 해석 |
|---|---|---|
| AXI-Stream RTL TB | PASS | 현재 DDR byte[3] 오염의 1차 원인 아님 |
| FIR DMA XSA `hwh` | 정상 | DDR 고수준 파라미터는 Zybo Z7-20 preset과 일치 |
| FIR DMA XSA `ps7_init` | `00001082` 계열 | v14 reference와 다르지만 FIR BD 고유 문제는 아님 |
| 최소 PS7 XSA `ps7_init` | `00001082` 계열 | 현재 Vivado/board file의 기본 생성 결과로 보임 |
| reference bringup `ps7_init` JTAG test | byte[3] 오염 | reference 값도 JTAG DDR write 문제를 제거하지 못함 |
| 최소 XSA `ps7_init` JTAG test | byte[3] 오염 | 생성값 종류와 무관하게 오염 재현 |

따라서 현재 결론은 다음과 같다.

**JTAG `dow` / `mwr`로 DDR에 ELF 또는 연속 워드를 적재하는 경로는 신뢰할 수 없다.**  
byte[3] 오염은 `ps7_init` 종류만으로 해결되지 않으며, XSDB/JTAG DDR write path 문제로 보는 것이 타당하다.

---

## 다음 액션

1. JTAG ELF loading / `dow` / burst `mwr` 기반 부팅 경로는 폐기한다.
2. SD카드 BOOT.bin 부팅 경로로 진행한다.
3. workflow v14의 "`ps7_init`이 `00001082` 계열이면 XSA FAIL" 기준은 재검토한다.
4. SD 부팅용 FSBL은 XSA에서 생성된 `ps7_init.c`를 사용하되, 실제 판정은 DONE LED, UART `READY`, Python FFT로 한다.
5. JTAG은 보드 연결 확인, FPGA programming, 단순 target 제어 용도로만 사용하고 DDR bulk load 검증에는 사용하지 않는다.

---

## 핵심 교훈

**`ps7_init` 값 mismatch와 JTAG DDR write 오염을 같은 문제로 묶으면 원인 추적이 흐려진다.** 현재 Vivado가 생성한 PS7-only `ps7_init`도 FIR DMA XSA와 같은 값을 만들며, reference 계열 `ps7_init`을 사용해도 JTAG DDR byte[3] 오염은 사라지지 않았다. 따라서 다음 검증은 JTAG loading이 아니라 SD boot chain에서 수행해야 한다.
