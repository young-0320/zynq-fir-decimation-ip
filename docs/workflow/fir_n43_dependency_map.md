# fir_n43 Dependency Map

- Target: `fir_n43`
- Scope: canonical N=43 transposed-form FIR + M=2 decimator demo pipeline
- Build artifact root: `build/fir_n43/`
- Debug artifact root: `build/debug/`

This document maps source-controlled inputs, generated artifacts, and script-to-script dependencies. It is the first place to update when moving files or changing pipeline paths.

---

## 1. Canonical Main Pipeline

```text
RTL + BD Tcl
  -> Vivado hardware build
  -> XSA + bitstream
  -> Vitis platform/app build
  -> FSBL + app ELF + BIF
  -> bootgen
  -> BOOT.bin
  -> SD boot board demo
```

### 1.1 Vivado Hardware Build

Command, usually from `build/fir_n43/vivado/` to keep Vivado logs local:

```bash
vivado -mode batch \
  -journal vivado.jou \
  -log vivado.log \
  -source ../../../vivado/fir_n43/build_bd_fir_dma.tcl
```

Source-controlled inputs:

| Role | Path |
| --- | --- |
| Build wrapper | `vivado/fir_n43/build_bd_fir_dma.tcl` |
| Block Design Tcl | `vivado/fir_n43/bd_fir_dma.tcl` |
| FIR core | `rtl/transposed_form/n43/fir_n43.v` |
| FIR + decimator core | `rtl/transposed_form/n43/fir_decimator_n43.v` |
| AXI-Stream wrapper | `rtl/transposed_form/n43/fir_decimator_n43_axis.v` |
| Decimator phase logic | `rtl/transposed_form/decimator_m2_phase0.v` |
| Board files | `boards/` |

Generated artifacts:

| Role | Path |
| --- | --- |
| Vivado project/work dir | `build/fir_n43/vivado/` |
| Implementation bitstream | `build/fir_n43/vivado/fir_decimator_trans_n43.runs/impl_1/bd_fir_dma_wrapper.bit` |
| Canonical bitstream copy | `build/fir_n43/output/bd_fir_dma_wrapper.bit` |
| Canonical XSA | `build/fir_n43/output/bd_fir_dma_wrapper.xsa` |
| Timing report | `build/fir_n43/vivado/fir_decimator_trans_n43_timing_summary.rpt` |
| Utilization report | `build/fir_n43/vivado/fir_decimator_trans_n43_utilization.rpt` |

Path invariants:

| Script line of responsibility | Required behavior |
| --- | --- |
| `SCRIPT_DIR` in `vivado/fir_n43/build_bd_fir_dma.tcl` | Resolves to `vivado/fir_n43/` |
| `REPO_ROOT` in `vivado/fir_n43/build_bd_fir_dma.tcl` | Resolves to repository root with `../..` |
| `source $SCRIPT_DIR/bd_fir_dma.tcl` | Sources the sibling BD Tcl, not a root-level legacy path |
| `OUT_DIR` | Must stay `build/fir_n43/output` for main artifacts |

### 1.2 Vitis Platform/App Build

Command from repo root:

```bash
vitis -s vitis/fir_n43/build_fir_decimator_demo.py
```

Source-controlled inputs:

| Role | Path |
| --- | --- |
| Vitis build script | `vitis/fir_n43/build_fir_decimator_demo.py` |
| Bare-metal app source | `sw/fir_decimator_demo.c` |
| Hardware input XSA | `build/fir_n43/output/bd_fir_dma_wrapper.xsa` |

Generated artifacts:

| Role | Path |
| --- | --- |
| Vitis workspace | `build/fir_n43/vitis/` |
| Platform component | `build/fir_n43/vitis/fir_decimator_pf/` |
| App component | `build/fir_n43/vitis/fir_decimator_demo/` |
| FSBL copy | `build/fir_n43/output/fsbl.elf` |
| App ELF copy | `build/fir_n43/output/fir_decimator_demo.elf` |
| BIF | `build/fir_n43/output/fir_decimator_demo.bif` |

Path invariants:

| Script field | Required path |
| --- | --- |
| `REPO_ROOT` | `vitis/fir_n43/../..` |
| `XSA` | `build/fir_n43/output/bd_fir_dma_wrapper.xsa` |
| `WORKSPACE` | `build/fir_n43/vitis` |
| `OUT_DIR` | `build/fir_n43/output` |
| `SRC` | `sw/fir_decimator_demo.c` |

### 1.3 BOOT Image Packaging

Command from repo root:

```bash
bootgen -arch zynq \
  -image build/fir_n43/output/fir_decimator_demo.bif \
  -o build/fir_n43/output/BOOT.bin -w on
```

Inputs:

| Role | Path |
| --- | --- |
| BIF | `build/fir_n43/output/fir_decimator_demo.bif` |
| FSBL | `build/fir_n43/output/fsbl.elf` |
| Bitstream | `build/fir_n43/output/bd_fir_dma_wrapper.bit` |
| App ELF | `build/fir_n43/output/fir_decimator_demo.elf` |

Output:

| Role | Path |
| --- | --- |
| SD boot image | `build/fir_n43/output/BOOT.bin` |

---

## 2. Fast Rebuild Path

Use this path only when `sw/fir_decimator_demo.c` changed and the existing Vitis workspace is still valid.

Command from repo root:

```bash
vitis/fir_n43/rebuild_boot_image.sh --boot-tag FIR
```

Source-controlled inputs:

| Role | Path |
| --- | --- |
| Rebuild script | `vitis/fir_n43/rebuild_boot_image.sh` |
| Bare-metal app source | `sw/fir_decimator_demo.c` |

Required generated inputs:

| Role | Candidate path |
| --- | --- |
| Vitis app source copy | `build/fir_n43/vitis/fir_decimator_demo/fir_decimator_demo.c` |
| Vitis app build dir | `build/fir_n43/vitis/fir_decimator_demo/build/` |
| FSBL | `build/fir_n43/vitis/fir_decimator_pf/export/fir_decimator_pf/sw/boot/fsbl.elf` |
| FSBL fallback | `build/fir_n43/vitis/fir_decimator_pf/zynq_fsbl/build/fsbl.elf` |
| Bitstream candidate | `build/fir_n43/output/bd_fir_dma_wrapper.bit` |
| Bitstream fallback | `build/fir_n43/vivado/fir_decimator_trans_n43.runs/impl_1/bd_fir_dma_wrapper.bit` |
| Bitstream fallback | `build/fir_n43/vitis/fir_decimator_demo/_ide/bitstream/bd_fir_dma_wrapper.bit` |

Generated artifacts by default:

| Role | Path |
| --- | --- |
| FSBL copy | `build/fir_n43/output/fsbl.elf` |
| Bitstream copy | `build/fir_n43/output/<selected-bitstream-name>.bit` |
| App ELF copy | `build/fir_n43/output/fir_decimator_demo.elf` |
| BIF | `build/fir_n43/output/fir_decimator_demo.bif` |
| BOOT image | `build/fir_n43/output/BOOT.bin` |

`--boot-out` changes the packaging output directory. For example, debug packaging with `--boot-out build/debug/axis_debug/output/BOOT.bin` writes the BIF, copied FSBL, copied bitstream, copied app ELF, and BOOT image under `build/debug/axis_debug/output/`.

---

## 3. Debug Build Targets

Debug builds share the main Vitis app and boot packaging script, but their Vivado hardware artifacts are isolated under `build/debug/`.

### 3.1 Smoke Target

Vivado command, usually from `build/debug/smoke/vivado/`:

```bash
vivado -mode batch \
  -journal vivado.jou \
  -log vivado.log \
  -source ../../../../vivado/debug/smoke/build_bd_fir_dma_smoke.tcl
```

Source-controlled inputs:

| Role | Path |
| --- | --- |
| Build wrapper | `vivado/debug/smoke/build_bd_fir_dma_smoke.tcl` |
| Block Design Tcl | `vivado/debug/smoke/bd_fir_dma_smoke.tcl` |
| Debug stream endpoint | `rtl/debug/axis_dma_smoke_test.v` |

Generated artifacts:

| Role | Path |
| --- | --- |
| Vivado work dir | `build/debug/smoke/vivado/` |
| Smoke bitstream | `build/debug/smoke/output/bd_fir_dma_smoke_wrapper.bit` |
| Smoke XSA | `build/debug/smoke/output/bd_fir_dma_smoke_wrapper.xsa` |

BOOT packaging:

```bash
vitis/fir_n43/rebuild_boot_image.sh \
  --bit build/debug/smoke/output/bd_fir_dma_smoke_wrapper.bit \
  --boot-out build/debug/smoke/output/BOOT.bin \
  --boot-tag SMOKE
```

### 3.2 AXIS Debug Target

Vivado command, usually from `build/debug/axis_debug/vivado/`:

```bash
vivado -mode batch \
  -journal vivado.jou \
  -log vivado.log \
  -source ../../../../vivado/debug/axis_debug/build_bd_fir_dma_axis_debug.tcl
```

Source-controlled inputs:

| Role | Path |
| --- | --- |
| Build wrapper | `vivado/debug/axis_debug/build_bd_fir_dma_axis_debug.tcl` |
| Block Design Tcl | `vivado/debug/axis_debug/bd_fir_dma_axis_debug.tcl` |
| Debug stream endpoint | `rtl/debug/axis_decimator_m2_n43_debug.v` |

Generated artifacts:

| Role | Path |
| --- | --- |
| Vivado work dir | `build/debug/axis_debug/vivado/` |
| AXIS debug bitstream | `build/debug/axis_debug/output/bd_fir_dma_axis_debug_wrapper.bit` |
| AXIS debug XSA | `build/debug/axis_debug/output/bd_fir_dma_axis_debug_wrapper.xsa` |

BOOT packaging:

```bash
vitis/fir_n43/rebuild_boot_image.sh \
  --bit build/debug/axis_debug/output/bd_fir_dma_axis_debug_wrapper.bit \
  --boot-out build/debug/axis_debug/output/BOOT.bin \
  --boot-tag AXISDBG
```

---

## 4. Legacy Paths

These are retained for historical or emergency debug context. They are not trusted final validation paths.

| Role | Path | Notes |
| --- | --- | --- |
| Main legacy XSDB loader | `vitis/legacy/download_and_run.py` | Uses JTAG/XSDB and direct DDR writes. Not part of final validation. |
| Bringup legacy XSDB loader | `vitis/legacy/bringup_demo/download_bringup.py` | Expects historical bringup ELF under `build/legacy/bringup/`. |

Final validation uses SD boot + DMA + UART + PC Python, not JTAG `dow` or XSDB direct DDR writes.

---

## 5. Path Consistency Checklist

Run these checks after moving pipeline files or changing build directories:

```bash
rg -n "vitis/(build_fir_decimator_demo|rebuild_boot_image|download_and_run|bringup_demo)|vivado/(build_bd|bd_fir_dma|bd_fir_dma_axis|bd_fir_dma_smoke|build_fir_transposed)|build/(vivado|vitis|output)" \
  -g '!docs/log/**' \
  -g '!docs/workflow/workflow_v1[0-4].md' \
  -g '!docs/workflow/fir_n43_dependency_map.md' \
  -g '!build/**' \
  -g '!*.jou' \
  -g '!*.log'

bash -n vitis/fir_n43/rebuild_boot_image.sh
python -m py_compile \
  vitis/fir_n43/build_fir_decimator_demo.py \
  vitis/legacy/download_and_run.py \
  vitis/legacy/bringup_demo/download_bringup.py
```

Expected result: no stale canonical path matches, and syntax checks pass.

Do not commit generated files under `build/`, Vivado journals/logs, XSA/bit/bin/elf outputs, or Python `__pycache__/` directories.
