# 프로젝트 파이프라인

이 문서는 `fir_n43` 기준으로 실제 프로젝트를 굴리는 순서를 정리한다. `docs/workflow/`의 상세 runbook과 다르게, 여기서는 "무슨 단계에서 어떤 스크립트를 쓰고 어떤 산출물이 나오는가"를 먼저 본다.

현재 canonical 타깃은 `fir_n43`이다. N=5 direct-form bringup 경로는 legacy/debug 성격이며 공식 검증 게이트가 아니다.

## 전체 흐름

```text
Verification Pipeline
  -> Main Demo Build Pipeline
  -> Board Demo Pipeline
```

변경 범위가 C 애플리케이션에만 한정되고 기존 Vitis workspace가 유효하면 `Fast Rebuild Pipeline`을 사용한다. 보드 bringup이나 원인 분리가 필요할 때만 `Debug Pipeline`을 사용한다.

## 1. Verification Pipeline

목적은 Python 모델, Q1.15 fixed-point 정책, RTL 구현이 같은 수치 계약을 따르는지 확인하는 것이다. DSP 수학, 계수, Q-format, RTL datapath를 바꿨거나 보고서/릴리스용 근거를 남기기 전에는 이 파이프라인을 먼저 통과해야 한다.

생성되는 `sim/output/`, `sim/vectors/`, `sim/build/` 아래 파일은 재생성 가능한 산출물이며 git에 커밋하지 않는다.

| 단계 | 사용 스크립트/명령 | 주요 입력 | 주요 산출물 | PASS 기준 |
| --- | --- | --- | --- | --- |
| Python regression | `uv run pytest -q` | `model/`, `sim/python/`, `sw/fir_decimator_demo.py`, test files | 없음 | pytest 전체 PASS |
| 계수 stopband 검증 | `uv run python -m sim.python.run_check_coeff_stopband_spec --num-taps 43` | `model/config.py`, Kaiser 계수 설계, Q1.15 helper | `sim/output/coeff_stopband_spec_n43/summary.{txt,json}`, 계수/응답 `.npy` | ideal/quantized 모두 60 dB stopband 만족 |
| float/fixed golden 생성 | `uv run python -m sim.python.run_compare_ideal_vs_fixed --num-taps 43 --form transposed` | ideal model, fixed transposed model, multitone input | `sim/output/ideal_vs_fixed_trans_n43/*.npy`, `summary.{txt,json}` | 명령 성공, summary 생성 |
| RTL vector export | `uv run python -m sim.python.export_rtl_bringup_vectors --num-taps 43 --input-dir sim/output/ideal_vs_fixed_trans_n43 --output-dir sim/vectors/transposed_form/n43` | fixed golden `.npy` | `sim/vectors/transposed_form/n43/*.hex` | input/coeff/expected vector export 성공 |
| RTL simulation | `make -C sim clean run_all` | N=43 RTL, N=43 testbenches, regenerated hex vectors | `sim/build/*.out` | 모든 N=43 TB가 PASS, fail/mismatch/error 없음 |

Canonical RTL simulation 대상은 다음 세 개다.

| Testbench | 확인 범위 |
| --- | --- |
| `sim/rtl/tb/transposed_form/tb_fir_n43.sv` | `fir_n43` 단독 출력과 `expected_fir_q15.hex` 비교 |
| `sim/rtl/tb/transposed_form/tb_fir_decimator_n43.sv` | FIR + M=2 decimator 출력과 `expected_decim_q15.hex` 비교 |
| `sim/rtl/tb/transposed_form/tb_fir_decimator_n43_axis.sv` | AXI-Stream wrapper의 data, TLAST, backpressure, reset recovery 확인 |

N=5 direct-form TB는 필요할 때만 다음 명령으로 별도 실행한다.

```bash
make -C sim run_legacy_n5
```

## 2. Main Demo Build Pipeline

목적은 실제 보드에서 실행할 SD boot 이미지 `BOOT.bin`을 만드는 것이다. Verification Pipeline이 RTL 수치 정합성을 확인했다면, 이 단계는 Vivado/Vitis/bootgen을 통해 PS-PL 통합 이미지를 만든다.

### 2.1 Vivado Hardware Build

보통 Vivado journal/log가 레포 루트에 흩어지지 않도록 `build/fir_n43/vivado/`에서 실행한다.

```bash
source "$VIVADO_SETTINGS"
mkdir -p build/fir_n43/vivado build/fir_n43/vitis build/fir_n43/output
cd build/fir_n43/vivado

vivado -mode batch \
  -journal vivado.jou \
  -log vivado.log \
  -source ../../../vivado/fir_n43/build_bd_fir_dma.tcl

cd ../../..
```

| 역할 | 경로 |
| --- | --- |
| Vivado build wrapper | `vivado/fir_n43/build_bd_fir_dma.tcl` |
| Block Design Tcl | `vivado/fir_n43/bd_fir_dma.tcl` |
| FIR core | `rtl/transposed_form/n43/fir_n43.v` |
| FIR + decimator top | `rtl/transposed_form/n43/fir_decimator_n43.v` |
| AXI-Stream wrapper | `rtl/transposed_form/n43/fir_decimator_n43_axis.v` |
| Decimator | `rtl/transposed_form/decimator_m2_phase0.v` |

| 산출물 | 경로 |
| --- | --- |
| Vivado work dir | `build/fir_n43/vivado/` |
| Canonical bitstream | `build/fir_n43/output/bd_fir_dma_wrapper.bit` |
| Canonical XSA | `build/fir_n43/output/bd_fir_dma_wrapper.xsa` |
| Timing report | `build/fir_n43/vivado/fir_decimator_trans_n43_timing_summary.rpt` |
| Utilization report | `build/fir_n43/vivado/fir_decimator_trans_n43_utilization.rpt` |

### 2.2 Vitis Platform/App Build

Vivado에서 만든 XSA를 입력으로 받아 platform, FSBL, bare-metal app을 만든다.

```bash
vitis -s vitis/fir_n43/build_fir_decimator_demo.py
```

| 역할 | 경로 |
| --- | --- |
| Vitis build script | `vitis/fir_n43/build_fir_decimator_demo.py` |
| Bare-metal app source | `sw/fir_decimator_demo.c` |
| Hardware input XSA | `build/fir_n43/output/bd_fir_dma_wrapper.xsa` |

| 산출물 | 경로 |
| --- | --- |
| Vitis workspace | `build/fir_n43/vitis/` |
| Platform component | `build/fir_n43/vitis/fir_decimator_pf/` |
| App component | `build/fir_n43/vitis/fir_decimator_demo/` |
| FSBL copy | `build/fir_n43/output/fsbl.elf` |
| App ELF copy | `build/fir_n43/output/fir_decimator_demo.elf` |
| BIF | `build/fir_n43/output/fir_decimator_demo.bif` |

### 2.3 BOOT Image Packaging

FSBL, bitstream, app ELF를 하나의 SD boot 이미지로 묶는다.

```bash
bootgen -arch zynq \
  -image build/fir_n43/output/fir_decimator_demo.bif \
  -o build/fir_n43/output/BOOT.bin -w on
```

| 입력 | 경로 |
| --- | --- |
| BIF | `build/fir_n43/output/fir_decimator_demo.bif` |
| FSBL | `build/fir_n43/output/fsbl.elf` |
| Bitstream | `build/fir_n43/output/bd_fir_dma_wrapper.bit` |
| App ELF | `build/fir_n43/output/fir_decimator_demo.elf` |

| 산출물 | 경로 |
| --- | --- |
| SD boot image | `build/fir_n43/output/BOOT.bin` |

## 3. Board Demo Pipeline

목적은 생성된 `BOOT.bin`이 실제 Zybo Z7-20 보드에서 PS-PL-DMA-UART 경로로 동작하는지 확인하는 것이다.

| 단계 | 사용 명령/동작 | 확인 결과 |
| --- | --- | --- |
| SD boot 준비 | `build/fir_n43/output/BOOT.bin`을 FAT32 SD 루트에 `BOOT.bin`으로 복사 | SD boot 입력 준비 |
| 보드 부팅 | JP5를 SD boot로 설정 후 전원 인가 | UART에 `READY FIR` 출력 |
| Demo scenario 1-1 | `python sw/fir_decimator_demo.py --mode 1-1 --port /dev/ttyUSB1 --timeout 30` | 보드 결과 수신, PC FFT plot 도달 |
| Demo scenario 1-2 | `python sw/fir_decimator_demo.py --mode 1-2 --port /dev/ttyUSB1 --timeout 30` | 보드 결과 수신, PC FFT plot 도달 |

현재 firmware 기준으로 `1-1` 실행 직후 reset 없이 `1-2`를 바로 실행하면 `ERR:1` / MM2S timeout이 날 수 있다. 신뢰 가능한 데모 경로는 각 시나리오를 보드 reset 후 하나씩 실행하는 것이다.

## 4. Fast Rebuild Pipeline

목적은 `sw/fir_decimator_demo.c`만 바뀐 경우 Vivado hardware build와 Vitis platform 재생성을 생략하고 app ELF와 `BOOT.bin`만 다시 만드는 것이다.

```bash
vitis/fir_n43/rebuild_boot_image.sh --boot-tag FIR
```

| 입력 | 경로 |
| --- | --- |
| Rebuild script | `vitis/fir_n43/rebuild_boot_image.sh` |
| Bare-metal app source | `sw/fir_decimator_demo.c` |
| Existing Vitis workspace | `build/fir_n43/vitis/` |
| Existing bitstream | `build/fir_n43/output/bd_fir_dma_wrapper.bit` |

| 산출물 | 경로 |
| --- | --- |
| FSBL copy | `build/fir_n43/output/fsbl.elf` |
| App ELF copy | `build/fir_n43/output/fir_decimator_demo.elf` |
| BIF | `build/fir_n43/output/fir_decimator_demo.bif` |
| BOOT image | `build/fir_n43/output/BOOT.bin` |

## 5. Debug Pipeline

Debug pipeline은 메인 데모가 실패했을 때 원인 분리를 위해 사용한다. 최종 검증 경로가 아니라 bringup/root-cause 도구로 취급한다.

| 타깃 | Vivado script | Vivado 산출물 | BOOT packaging |
| --- | --- | --- | --- |
| DMA smoke | `vivado/debug/smoke/build_bd_fir_dma_smoke.tcl` | `build/debug/smoke/output/bd_fir_dma_smoke_wrapper.{bit,xsa}` | `vitis/fir_n43/rebuild_boot_image.sh --bit build/debug/smoke/output/bd_fir_dma_smoke_wrapper.bit --boot-out build/debug/smoke/output/BOOT.bin --boot-tag SMOKE` |
| AXIS debug | `vivado/debug/axis_debug/build_bd_fir_dma_axis_debug.tcl` | `build/debug/axis_debug/output/bd_fir_dma_axis_debug_wrapper.{bit,xsa}` | `vitis/fir_n43/rebuild_boot_image.sh --bit build/debug/axis_debug/output/bd_fir_dma_axis_debug_wrapper.bit --boot-out build/debug/axis_debug/output/BOOT.bin --boot-tag AXISDBG` |

## 6. Legacy Pipeline

JTAG `dow`, XSDB direct DDR write, N=5 direct-form bringup 경로는 역사적 맥락과 긴급 디버그용으로만 남긴다. 현재 프로젝트의 최종 재현 경로는 SD boot + AXI DMA + UART다.

| 역할 | 경로 | 지위 |
| --- | --- | --- |
| Legacy XSDB loader | `vitis/legacy/download_and_run.py` | 최종 검증 경로 아님 |
| Bringup XSDB loader | `vitis/legacy/bringup_demo/download_bringup.py` | historical bringup |
| N=5 RTL TB | `make -C sim run_legacy_n5` | optional legacy regression |
