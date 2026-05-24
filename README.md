# zynq-axi-fir-decimation-ip

N=43 transposed-form FIR low-pass filter + M=2 decimator on Zybo Z7-20 (Zynq-7000).

## Current State

- FIR spec: Kaiser beta=5.653, fp=15 MHz, fs=25 MHz, As >= 60 dB, Q1.15 signed 16-bit samples/coefs.
- RTL path: transposed-form FIR + M=2 decimator + AXI-Stream wrapper.
- System path: AXI DMA simple mode, HP0 DDR, PS bare-metal C, UART 115200, PC Python FFT viewer.
- Board baseline: SD boot reaches `READY FIR`; Python demo modes `1-1` and `1-2` reach FFT plots.
- Main root cause fixed: AXI DMA default 14-bit length field could not represent `MM2S_LENGTH = 8192 * 2 = 16384` bytes. All active BD Tcl variants now set `CONFIG.c_sg_length_width {23}`.
- JTAG `dow` / XSDB direct DDR write is not a trusted final path because byte lane 3 MSB corruption was observed. Use SD boot + DMA + UART for system verification.

Primary current context:

- `CLAUDE.md` - compact current project state and next work.
- `docs/workflow/workflow_v15.md` - current runbook.
- `docs/workflow/fir_n43_dependency_map.md` - source/script/artifact dependency map for the canonical target.
- `docs/log/32_smoke_pass_after_dma_length_width_fix.md` - DMA timeout root-cause record.

## Repository Map

| Path | Purpose |
| --- | --- |
| `model/` | ideal and fixed-point Python reference models |
| `rtl/transposed_form/n43/` | main N=43 FIR/decimator RTL |
| `rtl/debug/` | DMA smoke/debug stream endpoints |
| `sim/` | Python and RTL tests |
| `vivado/` | BD and bitstream/XSA regeneration Tcl scripts |
| `vitis/` | Vitis app/BOOT image rebuild scripts |
| `sw/` | bare-metal C app and PC Python UART/FFT demo |
| `docs/` | design specs, workflow records, debug logs |

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

| Tool | Use |
| --- | --- |
| `uv` + Python 3.13 | Python environment/tests |
| `iverilog` 11+ | RTL simulation |
| `minicom` or equivalent | UART console |
| Digilent Zybo Z7-20 board files | Vivado board part |

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

4. Run PC-side FFT checks:

```bash
python sw/fir_decimator_demo.py --mode 1-1 --port /dev/ttyUSB1 --timeout 30
python sw/fir_decimator_demo.py --mode 1-2 --port /dev/ttyUSB1 --timeout 30
```

Expected result: both commands receive board output and reach FFT plots.

## Verification Pipeline

Use this path when changing DSP math, Q-format policy, RTL datapath, coefficients, or before recording a release/report result. Generated files under `sim/output/` and `sim/vectors/` are disposable artifacts and do not need to be committed.

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

Expected result: Python tests pass, the 43-tap coefficient response meets the stopband criterion, and N=43 transposed fixed-point vectors are regenerated.

### 2. RTL Simulation

```bash
cd sim
make clean
make run_all
cd ..
```

Expected result: all testbenches print PASS without fail/mismatch/error output.

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
