# 30. 새 보드 SD boot READY 및 DMA runtime trace 진단

- 작성일: 2026-05-24
- 선행 문서: `29_ps7_init_and_jtag_ddr_write_recheck.md`, `workflow_v14.md`

---

## 배경

29번 로그까지의 결론은 JTAG `dow` / `mwr` 기반 DDR write path가 신뢰할 수 없으므로, 보드 검증은 SD카드 `BOOT.bin` 부팅으로 전환한다는 것이었다.

이후 새 Zybo Z7-20 보드로 같은 SD 부팅 흐름을 시도했다.

---

## 관찰 1: 새 보드에서 SD boot가 READY까지 진행됨

새 보드에 SD카드를 꽂고 전원을 인가하자 DONE LED가 켜졌다. 이어 UART에서 application banner가 출력됐다.

```text
READY
```

판정:

| 항목 | 판정 |
|---|---|
| FSBL 실행 | 성공 |
| DDR 초기화 | 최소한 app 진입까지 성공 |
| bitstream 로드 | DONE LED 점등으로 성공 |
| app ELF handoff | `READY` 출력으로 성공 |

이전 보드에서는 동일한 SD boot 시도에서 DONE LED가 켜지지 않았으므로, 이전 JTAG DDR byte[3] 오염 및 SD boot failure는 기존 보드 하드웨어 문제일 가능성이 크게 올라갔다.

현재부터 보드 검증의 기준은 새 보드로 고정한다.

---

## 관찰 2: Python FFT mode 1-1에서 timeout

`READY` 확인 후 PC Python demo를 실행했다.

```bash
cd /home/young/dev/10_zynq-fir-decimation-ip
python sw/fir_decimator_demo.py --mode 1-1 --port /dev/ttyUSB1
```

결과:

```text
TimeoutError: 보드 응답 없음 (timeout). 연결 및 비트스트림을 확인하세요.
```

해석:

- app ELF는 `READY`까지 출력했으므로 boot chain 자체는 통과했다.
- timeout은 PC가 command를 보낸 뒤 result packet magic `0xDEADBEEF`를 받지 못했다는 뜻이다.
- 기존 Python 수신기는 보드가 `ERR:1` 또는 `ERR:2`를 보내도 magic만 기다리기 때문에, DMA 오류가 timeout으로 묻힐 수 있었다.

따라서 다음 단계는 DMA/FIR runtime 경로를 trace해야 한다.

---

## 수정 1: Python UART 수신 진단 강화

수정 파일:

```text
sw/fir_decimator_demo.py
sw/test/test_fir_decimator_demo.py
```

`uart_recv_result()`가 보드의 ASCII error line을 감지하도록 수정했다.

| 보드 출력 | Python 해석 |
|---|---|
| `ERR:1` | `MM2S DMA timeout` |
| `ERR:2` | `S2MM DMA timeout` |
| `ERR:3` | `AXI DMA reset timeout` |

또 timeout 발생 시 최근 UART text line을 같이 보여주도록 했다.

```text
TimeoutError: 보드 응답 없음 (timeout). 최근 UART 텍스트: ...
```

테스트 추가:

```text
test_uart_recv_result_reports_mm2s_error
test_uart_recv_result_reports_s2mm_error
test_uart_recv_result_reports_dma_reset_error
```

검증:

```text
.venv/bin/pytest -q sw/test/test_fir_decimator_demo.py
28 passed
```

---

## 수정 2: bare-metal C app에 DMA trace 추가

수정 파일:

```text
sw/fir_decimator_demo.c
```

짧은 UART trace를 추가했다.

| Trace | 의미 |
|---|---|
| `CMD` | PC command 수신 완료 |
| `GEN` | input multitone 생성 완료 |
| `D0` | `dma_run()` 진입 |
| `D1` | AXI DMA soft reset write 직전 |
| `D2` | AXI DMA reset bit clear 확인 |
| `D3` | S2MM 주소/길이 설정 완료 |
| `D4` | MM2S 주소/길이 설정 완료 |
| `D5` | MM2S idle 확인 |
| `D6` | S2MM idle 확인 |

기존에는 DMA reset bit clear를 무한 대기했다. 이를 timeout 가능하도록 바꾸고, reset이 완료되지 않으면 `ERR:3`을 보내도록 했다.

```text
0: 성공
1: MM2S timeout
2: S2MM timeout
3: AXI DMA reset timeout
```

---

## 진단용 BOOT_trace.bin 생성

현재 `build/output`에는 canonical SD boot 산출물이 완성되어 있지 않았다.

확인 결과:

```text
build/output/bd_fir_dma_wrapper.xsa
build/output/untitled.bif
build/output/zybo_ps7_bringup_min.xsa
```

`build/output/BOOT.bin`, `build/output/fsbl.elf`, `build/output/fir_decimator_demo.elf`, `build/output/bd_fir_dma_wrapper.bit`는 없었다.

또 기존 `untitled.bif`는 Vitis IDE 내부 산출물과 old `db_fir_dma_wrapper.bit`를 참조하고 있었다.

```text
[bootloader]build/vitis/fir_decimator_pf/export/fir_decimator_pf/sw/boot/fsbl.elf
build/vitis/fir_decimator_demo/_ide/bitstream/db_fir_dma_wrapper.bit
build/vitis/fir_decimator_demo/build/fir_decimator_demo.elf
```

따라서 이번에는 READY가 이미 확인된 기존 FSBL/bitstream 흐름을 유지하고, app ELF만 trace 버전으로 갱신하는 진단용 이미지를 만들었다.

### 1. Vitis workspace app source 갱신

기존 Vitis workspace는 repo의 `sw/fir_decimator_demo.c`가 아니라 복사본을 빌드한다.

```text
build/vitis/fir_decimator_demo/fir_decimator_demo.c
```

따라서 trace가 들어간 C 파일을 복사했다.

```bash
cp sw/fir_decimator_demo.c build/vitis/fir_decimator_demo/fir_decimator_demo.c
```

### 2. app ELF 재빌드

시스템 PATH에는 `ninja`가 없어서 Vitis bundled ninja를 사용했다.

```bash
PATH=/home/young/Xilinx/Vitis/2024.2/gnu/aarch32/lin/gcc-arm-none-eabi/bin:$PATH \
/home/young/Xilinx/Vitis/2024.2/tps/lnx64/lopper-1.1.0/env/lib/python3.8/site-packages/ninja/data/bin/ninja \
  -C build/vitis/fir_decimator_demo/build
```

결과:

```text
build/vitis/fir_decimator_demo/build/fir_decimator_demo.elf
```

### 3. bootgen 실행

기존 BIF를 사용해 진단용 boot image를 만들었다.

```bash
/home/young/Xilinx/Vitis/2024.2/bin/bootgen \
  -arch zynq \
  -image build/output/untitled.bif \
  -o build/output/BOOT_trace.bin \
  -w on
```

결과:

```text
build/output/BOOT_trace.bin
```

---

## BOOT_trace.bin의 성격

`BOOT_trace.bin`은 최종 canonical 산출물이 아니다.

| 항목 | 상태 |
|---|---|
| FSBL | 기존 Vitis workspace 산출물 사용 |
| bitstream | 기존 `_ide/bitstream/db_fir_dma_wrapper.bit` 사용 |
| app ELF | trace가 들어간 새 ELF 사용 |
| 목적 | runtime timeout 위치 분리 |

즉 이 이미지는 프로젝트 최종 재현성 확보용이 아니라, `READY` 이후 Python timeout이 DMA 어느 단계에서 발생하는지 자르기 위한 임시 진단 이미지다.

---

## 다음 액션

SD카드 루트에 `BOOT_trace.bin`을 `BOOT.bin` 이름으로 복사한다.

```bash
cp build/output/BOOT_trace.bin <SD_MOUNT>/BOOT.bin
sync
```

부팅 후 `READY`가 뜨면 다시 실행한다.

```bash
python sw/fir_decimator_demo.py --mode 1-1 --port /dev/ttyUSB1
```

출력 판정:

| 출력 | 해석 |
|---|---|
| `CMD`도 없음 | PC command가 보드 UART로 들어가지 않음, 또는 SD에 trace image가 반영되지 않음 |
| `CMD`, `GEN`, `D0`, `D1` 이후 timeout | AXI DMA reset register 접근 또는 DMA clock/reset 문제 |
| `ERR:3` | AXI DMA reset bit이 내려가지 않음 |
| `ERR:1` | MM2S path timeout |
| `ERR:2` | S2MM path, TLAST, FIR AXI-Stream 출력 timeout |
| `D6` 이후 magic packet 수신 | DMA/FIR path 성공 |

---

## 추가 수정: Vivado bitstream copy 경로

`vivado/build_bd_fir_dma.tcl`의 bitstream copy 경로가 한 단계 깊게 잡혀 있었다.

기존:

```tcl
set BIT_IMPL $BUILD_DIR/${PROJ_NAME}/${PROJ_NAME}.runs/impl_1/bd_fir_dma_wrapper.bit
```

수정:

```tcl
set BIT_IMPL $BUILD_DIR/${PROJ_NAME}.runs/impl_1/bd_fir_dma_wrapper.bit
```

이 수정은 다음 canonical build에서 `build/output/bd_fir_dma_wrapper.bit`가 정상 복사되도록 하기 위한 것이다. 이미 생성한 `BOOT_trace.bin`은 기존 Vitis IDE 내부 bitstream을 사용했으므로, 이 수정의 영향을 받지 않는다.

---

## 핵심 교훈

**SD boot에서 `READY`가 뜬 것과 현재 repo의 canonical 산출물이 정리된 것은 별개의 문제다.**  
새 보드로 boot chain은 통과했지만, 기존 SD image는 old Vitis workspace 산출물에 의존하고 있었다. 따라서 runtime timeout을 추적할 때는 `BOOT_trace.bin` 같은 명시적인 진단 이미지를 사용하고, 최종 마감 전에는 `build/output` 기준의 `FSBL + bit + ELF + BIF + BOOT.bin` 재현 체인을 반드시 정리해야 한다.
