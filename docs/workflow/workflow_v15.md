# FIR Decimation Project Workflow v15

- Date: 2026-05-24
- Previous: `docs/workflow/workflow_v14.md`
- Purpose: current runbook after the AXI DMA length-width fix and SD-boot end-to-end pass.
- Dependency map: `docs/workflow/fir_n43_dependency_map.md`

---

## 1. Current Baseline

| Item | Current state |
| --- | --- |
| Main RTL | N=43 transposed-form FIR + M=2 decimator |
| Interface | AXI-Stream wrapper with dynamic TLAST and auto-flush |
| System path | PS bare-metal C -> AXI DMA -> PL -> AXI DMA -> DDR -> UART -> PC Python |
| Boot path | SD `BOOT.bin` is the trusted path |
| Board evidence | `READY FIR`; Python modes `1-1` and `1-2` reach FFT plots |
| Main timing | Vivado main FIR build WNS = +0.692 ns at 100 MHz |
| Root cause fixed | AXI DMA `c_sg_length_width` default 14 bits could not represent 16384-byte MM2S transfer |

Active BD Tcl files must include:

```tcl
CONFIG.c_include_sg {0}
CONFIG.c_sg_length_width {23}
CONFIG.c_m_axis_mm2s_tdata_width {16}
CONFIG.c_s_axis_s2mm_tdata_width {16}
```

---

## 2. Canonical Artifacts

| Artifact | Path |
| --- | --- |
| Main Vivado work dir | `build/fir_n43/vivado/` |
| Main Vitis workspace | `build/fir_n43/vitis/` |
| Main output dir | `build/fir_n43/output/` |
| Main bitstream | `build/fir_n43/output/bd_fir_dma_wrapper.bit` |
| Main XSA | `build/fir_n43/output/bd_fir_dma_wrapper.xsa` |
| FSBL ELF | `build/fir_n43/output/fsbl.elf` |
| App ELF | `build/fir_n43/output/fir_decimator_demo.elf` |
| BIF | `build/fir_n43/output/fir_decimator_demo.bif` |
| Main boot image | `build/fir_n43/output/BOOT.bin` |

Do not use IDE-temporary paths such as `untitled.bif`, `_ide/bitstream/...`, or `db_fir_dma_wrapper.*` as canonical inputs.

---

## 3. Local Verification

From repo root:

```bash
uv sync
uv run pytest -q
cd sim
make run_all
```

Expected: Python tests pass and all RTL testbenches print PASS without mismatch/fail/error.

---

## 4. Full Hardware Regeneration

Use this when RTL, BD Tcl, XSA, or platform inputs changed.

```bash
export VIVADO_SETTINGS=/path/to/Xilinx/Vivado/2024.2/settings64.sh
source "$VIVADO_SETTINGS"
mkdir -p build/fir_n43/vivado build/fir_n43/vitis build/fir_n43/output
cd build/fir_n43/vivado

vivado -mode batch \
  -journal vivado.jou \
  -log vivado.log \
  -source ../../../vivado/fir_n43/build_bd_fir_dma.tcl

cd ../../..

vitis -s vitis/fir_n43/build_fir_decimator_demo.py

bootgen -arch zynq \
  -image build/fir_n43/output/fir_decimator_demo.bif \
  -o build/fir_n43/output/BOOT.bin -w on
```

Minimum completion checks:

```bash
test -d build/fir_n43/vivado
test -d build/fir_n43/vitis
test -d build/fir_n43/output
test -f build/fir_n43/output/bd_fir_dma_wrapper.bit
test -f build/fir_n43/output/bd_fir_dma_wrapper.xsa
test -f build/fir_n43/output/fsbl.elf
test -f build/fir_n43/output/fir_decimator_demo.elf
test -f build/fir_n43/output/fir_decimator_demo.bif
test -f build/fir_n43/output/BOOT.bin
```

---

## 5. Fast Rebuild

Use this only when the existing `build/fir_n43/vitis` workspace is valid and the change is limited to the C app or selected bitstream packaging.

```bash
vitis/fir_n43/rebuild_boot_image.sh --boot-tag FIR
```

Smoke/debug packaging examples:

```bash
vitis/fir_n43/rebuild_boot_image.sh \
  --bit build/debug/smoke/output/bd_fir_dma_smoke_wrapper.bit \
  --boot-out build/debug/smoke/output/BOOT.bin \
  --boot-tag SMOKE

vitis/fir_n43/rebuild_boot_image.sh \
  --bit build/debug/axis_debug/output/bd_fir_dma_axis_debug_wrapper.bit \
  --boot-out build/debug/axis_debug/output/BOOT.bin \
  --boot-tag AXISDBG
```

---

## 6. Board Demo

1. Copy `build/fir_n43/output/BOOT.bin` to the SD card root as `BOOT.bin`.
2. Set JP5 to SD boot, insert the card, connect USB, power the board.
3. Confirm UART banner:

```text
READY FIR
```

4. Run:

```bash
python sw/fir_decimator_demo.py --mode 1-1 --port /dev/ttyUSB1 --timeout 30
python sw/fir_decimator_demo.py --mode 1-2 --port /dev/ttyUSB1 --timeout 30
```

Current known result: both modes reach matplotlib plots. The next step is to make the numeric FFT verdict explicit.

---

## 7. Debug Policy

- Final system validation uses SD boot + DMA + UART.
- JTAG `dow`, XSDB `mwr/mrd`, and `vitis/legacy/download_and_run.py` are retained as historical/debug references, not as the trusted main path.
- If DMA sample counts change, verify:

```text
N_IN  * sizeof(sample) <= 2^c_sg_length_width - 1
N_OUT * sizeof(sample) <= 2^c_sg_length_width - 1
```

Current values:

```text
c_sg_length_width = 23
MM2S_LENGTH = 8192 * 2 = 16384 bytes
S2MM_LENGTH = 4096 * 2 = 8192 bytes
```

---

## 8. Next Engineering Work

1. Add numeric FFT peak reporting to `sw/fir_decimator_demo.py`.
2. Clarify output-axis scaling for the 50 MHz output sample rate.
3. Compare board output against Python golden/reference metrics.
4. Save representative plots and numeric evidence under `docs/`.
