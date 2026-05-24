# zynq-axi-fir-decimation-ip

## 한국어 개요

이 저장소는 Zybo Z7-20(Zynq-7000) 보드에서 N=43 FIR 저역통과 필터와 M=2 decimator를 실제로 구동하기 위한 end-to-end FPGA 프로젝트입니다. 단순히 RTL 필터 하나를 만드는 것이 아니라, 필터 사양 정의부터 Python 모델링, fixed-point 검증, RTL 구현, AXI-Stream/AXI DMA 기반 PS-PL 통합, Vitis bare-metal 애플리케이션, SD 부팅용 BOOT 이미지 생성, UART 기반 PC FFT 확인까지 한 번에 이어지는 전체 흐름을 재현하는 것이 핵심입니다.

프로젝트의 큰 과정은 다음과 같습니다.

1. **DSP 사양 및 기준 모델 작성**: Kaiser window 기반 N=43 FIR 저역통과 필터를 설계하고, Python float/fixed 모델로 계수와 Q1.15 fixed-point 동작을 검증합니다.
2. **RTL 구현 및 시뮬레이션**: transposed-form FIR, M=2 decimator, AXI-Stream wrapper를 작성하고 Python golden vector와 RTL testbench로 결과를 비교합니다.
3. **Vivado 하드웨어 플랫폼 구성**: Zynq PS, AXI DMA, HP0 DDR 경로, FIR/decimator RTL을 block design으로 연결하고 bitstream/XSA를 생성합니다.
4. **Vitis bare-metal 소프트웨어 작성**: PS에서 AXI DMA를 제어하는 C 애플리케이션을 빌드하고 FSBL, bitstream, ELF를 묶어 SD 부팅용 `BOOT.bin`을 만듭니다.
5. **보드 실행 및 PC 검증**: Zybo 보드를 SD 부팅한 뒤 UART에서 `READY FIR`를 확인하고, PC Python 스크립트로 입력 시나리오를 보내 FFT plot과 수치 결과를 확인합니다.
6. **디버그와 재현성 관리**: DMA 길이 폭, DDR/JTAG 이슈, AXI-Stream reset/timeout 같은 실제 bring-up 문제를 문서화하고, 현재 신뢰 가능한 SD boot + DMA + UART 경로를 기준 파이프라인으로 유지합니다.

따라서 이 프로젝트의 목적은 “필터 RTL이 시뮬레이션에서 맞는다”에서 끝나는 것이 아니라, **사양 -> 모델 -> RTL -> Vivado -> Vitis -> BOOT.bin -> 실제 보드 -> PC FFT 결과**까지 연결되는 end-to-end 검증 가능한 FIR decimation 시스템을 만드는 것입니다.

N=43 transposed-form FIR low-pass filter + M=2 decimator on Zybo Z7-20 (Zynq-7000).

## Current State

- FIR spec: Kaiser beta=5.653, fp=15 MHz, fs=25 MHz, As >= 60 dB, Q1.15 signed 16-bit samples/coefs.
- RTL path: transposed-form FIR + M=2 decimator + AXI-Stream wrapper.
- System path: AXI DMA simple mode, HP0 DDR, PS bare-metal C, UART 115200, PC Python FFT viewer.
- Board baseline: SD boot reaches `READY FIR`; Python demo modes `1-1` and `1-2` reach FFT plots when each scenario is started from a fresh board reset.
- Main root cause fixed: AXI DMA default 14-bit length field could not represent `MM2S_LENGTH = 8192 * 2 = 16384` bytes. All active BD Tcl variants now set `CONFIG.c_sg_length_width {23}`.
- JTAG `dow` / XSDB direct DDR write is not a trusted final path because byte lane 3 MSB corruption was observed. Use SD boot + DMA + UART for system verification.

Primary current context:

- `CLAUDE.md` - compact current project state and next work.
- `docs/project_pipeline.md` - actual project pipeline, scripts, artifacts, and PASS criteria.
- `docs/workflow/workflow_v16.md` - next demo/report polish plan.
- `docs/workflow/workflow_v15.md` - current runbook.
- `docs/workflow/fir_n43_verification_pipeline.md` - canonical model/vector/RTL simulation verification flow.
- `docs/workflow/fir_n43_dependency_map.md` - source/script/artifact dependency map for the canonical target.
- `docs/log/32_smoke_pass_after_dma_length_width_fix.md` - DMA timeout root-cause record.

## Repository Map

| Path                         | Purpose                                       |
| ---------------------------- | --------------------------------------------- |
| `model/`                   | ideal and fixed-point Python reference models |
| `rtl/transposed_form/n43/` | main N=43 FIR/decimator RTL                   |
| `rtl/debug/`               | DMA smoke/debug stream endpoints              |
| `sim/`                     | Python and RTL tests                          |
| `vivado/`                  | BD and bitstream/XSA regeneration Tcl scripts |
| `vitis/`                   | Vitis app/BOOT image rebuild scripts          |
| `sw/`                      | bare-metal C app and PC Python UART/FFT demo  |
| `docs/`                    | design specs, workflow records, debug logs    |

## Prerequisites

AMD Vivado + Vitis Embedded Development 2024.2 is required for hardware and bare-metal builds. The Vitis Core Development Kit alone is not enough for Zynq-7000 standalone ELF generation.

For each hardware build terminal, source the Vivado 2024.2 environment script from the machine's actual install path. Common Ubuntu install paths are `$HOME/Xilinx/Vivado/2024.2/settings64.sh` and `/opt/Xilinx/Vivado/2024.2/settings64.sh`.

```bash
export VIVADO_SETTINGS=/path/to/Xilinx/Vivado/2024.2/settings64.sh
source "$VIVADO_SETTINGS"

vivado -version
vitis -version
bootgen -help >/dev/null
```

On this development machine, `VIVADO_SETTINGS=$HOME/Xilinx/Vivado/2024.2/settings64.sh`.

Other expected tools:

| Tool                            | Use                      |
| ------------------------------- | ------------------------ |
| `uv` + Python 3.13            | Python environment/tests |
| `iverilog` 11+                | RTL simulation           |
| `minicom` or equivalent       | UART console             |
| Digilent Zybo Z7-20 board files | Vivado board part        |

## Main Demo Pipeline

The main demo pipeline is the shortest source-to-board path for reproducing the current SD-boot demo. It focuses on hardware/software image generation and board execution. Model and RTL regression checks are documented separately in the verification pipeline.

### 1. Hardware Platform Build

From repo root:

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

Expected artifacts:

```text
build/fir_n43/output/bd_fir_dma_wrapper.bit
build/fir_n43/output/bd_fir_dma_wrapper.xsa
```

### 2. Application And BOOT Image

Build the Vitis platform/app from the canonical XSA, then package FSBL + bitstream + app ELF:

```bash
vitis -s vitis/fir_n43/build_fir_decimator_demo.py

bootgen -arch zynq \
  -image build/fir_n43/output/fir_decimator_demo.bif \
  -o build/fir_n43/output/BOOT.bin -w on
```

Expected artifacts:

```text
build/fir_n43/output/fsbl.elf
build/fir_n43/output/fir_decimator_demo.elf
build/fir_n43/output/fir_decimator_demo.bif
build/fir_n43/output/BOOT.bin
```

### 3. Board Demo

1. Copy `build/fir_n43/output/BOOT.bin` to the FAT32 SD card root as `BOOT.bin`.
2. Set JP5 to SD boot, insert SD, connect USB, power the board.
3. Confirm UART banner:

```text
READY FIR
```

4. Run one PC-side FFT check after each board reset:

```bash
python sw/fir_decimator_demo.py --mode 1-1 --port /dev/ttyUSB1 --timeout 30
python sw/fir_decimator_demo.py --mode 1-2 --port /dev/ttyUSB1 --timeout 30
```

Expected result: each command receives board output and reaches an FFT plot when the board has been reset before that scenario.

Known limitation: running `1-1` and then `1-2` back-to-back without a board reset can fail with `ERR:1` / MM2S timeout. The current firmware resets the AXI DMA before a transfer, but does not yet issue a full software-controlled PL/FIR AXIS reset equivalent to the board reset button.

## Verification Pipeline

Use this path when changing DSP math, Q-format policy, RTL datapath, coefficients, or before recording a release/report result. Generated files under `sim/output/` and `sim/vectors/` are disposable artifacts and must not be committed. Vector files are regenerated from the Python model pipeline when needed; the repository tracks the model, generator, and testbench sources, not generated `.npy` or `.hex` vectors.

### 1. Python Float/Fixed Model And Vector Generation

```bash
uv sync
uv run pytest -q

uv run python -m sim.python.run_check_coeff_stopband_spec --num-taps 43
uv run python -m sim.python.run_compare_ideal_vs_fixed --num-taps 43 --form transposed
uv run python -m sim.python.export_rtl_bringup_vectors \
  --num-taps 43 \
  --input-dir sim/output/ideal_vs_fixed_trans_n43 \
  --output-dir sim/vectors/transposed_form/n43
```

Expected result: Python tests pass; the 43-tap ideal and quantized coefficient responses meet the 60 dB stopband criterion; and N=43 transposed fixed-point vectors are regenerated. The coefficient check exits non-zero and prints the failing tap/response when the stopband criterion is not met.

### 2. RTL Simulation

```bash
cd sim
make clean
make run_all
cd ..
```

Expected result: all canonical N=43 testbenches print PASS without fail/mismatch/error output. N=5 direct-form bringup tests are legacy-only and can be run separately with `make run_legacy_n5`.

## Fast Rebuild

Use this path when only `sw/fir_decimator_demo.c` changed and the existing `build/fir_n43/vitis` workspace is valid. It reuses the current hardware/platform and regenerates the app ELF, BIF, and BOOT image.

```bash
vitis/fir_n43/rebuild_boot_image.sh --boot-tag FIR
```

Expected artifact:

```text
build/fir_n43/output/BOOT.bin
```

## Debug And Historical Flows

Smoke/debug paths remain in the repo as regression and root-cause tools, but they are not the main reproducible pipeline:

- `rtl/debug/axis_dma_smoke_test.v`
- `rtl/debug/axis_decimator_m2_n43_debug.v`
- `vivado/debug/smoke/build_bd_fir_dma_smoke.tcl`
- `vivado/debug/axis_debug/build_bd_fir_dma_axis_debug.tcl`
- `vitis/legacy/download_and_run.py` and `vitis/legacy/bringup_demo/download_bringup.py` are historical JTAG/XSDB flows, not trusted final validation paths.

Use `docs/workflow/workflow_v15.md` and `docs/log/32_smoke_pass_after_dma_length_width_fix.md` when debugging DMA/DDR/UART transport issues.

## Next Work

The next technical step is not more bring-up plumbing. It is to make the PC FFT output presentation and numeric pass/fail reporting clean enough for demo/report use:

- print peak dB values for expected tones in modes `1-1` and `1-2`;
- compare hardware output against Python golden/reference metrics;
- fix the output FFT axis/layout so the 50 MHz output sample-rate Nyquist limit is visually clear;
- save representative plots and measured numbers into `docs/`.
