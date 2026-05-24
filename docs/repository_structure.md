# Repository Structure

- Date: 2026-05-24
- Purpose: quick map of the repository layout and the role of each maintained script.
- Scope: source-controlled project layout plus generated-artifact policy. This document intentionally excludes `.git/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, and generated build internals.

---

## 1. Top-Level Map

```text
.
|-- README.md
|-- CLAUDE.md
|-- pyproject.toml
|-- uv.lock
|-- boards/
|-- docs/
|-- model/
|-- rtl/
|-- sim/
|-- sw/
|-- vivado/
|-- vitis/
|-- build/        # generated, not source-controlled
`-- todo.md
```

| Path | Role |
| --- | --- |
| `README.md` | Main user-facing runbook: main demo pipeline, verification pipeline, fast rebuild, board demo. |
| `CLAUDE.md` | Compact project state for assistant/context handoff. |
| `pyproject.toml` | Python project metadata and dependency/test configuration for `uv`/pytest. |
| `uv.lock` | Locked Python dependency graph for reproducible local verification. |
| `boards/` | Local Digilent Zybo Z7-20 Vivado board files. |
| `docs/` | Specs, workflows, debug logs, diagrams, and repository maps. |
| `model/` | Python ideal and fixed-point reference models. |
| `rtl/` | Verilog/SystemVerilog hardware source. |
| `sim/` | Python model scripts, RTL testbenches, and simulation Makefile. |
| `sw/` | Bare-metal C demo and PC-side Python UART/FFT demo. |
| `vivado/` | Vivado Tcl flows for main and debug hardware targets. |
| `vitis/` | Vitis workspace generation, BOOT image rebuild, and legacy XSDB helpers. |
| `build/` | Generated Vivado/Vitis/BOOT artifacts. Do not commit. |

---

## 2. Artifact Policy

Generated files are reproducibility outputs, not source.

```text
build/        # Vivado/Vitis/BOOT artifacts
sim/build/    # compiled simulation outputs
sim/output/   # generated .npy evidence
sim/vectors/  # generated .hex vectors
```

The repository tracks model, generator, RTL, testbench, Vivado, Vitis, and software sources. It does not track generated `.npy`, `.hex`, `.bit`, `.bin`, `.xsa`, `.elf`, `.jou`, or `.log` files.

---

## 3. Boards

```text
boards/
`-- Digilent/
    `-- zybo-z7-20/
        |-- board.xml
        |-- part0_pins.xml
        |-- preset.xml
        `-- xitem.json
```

These files let Vivado resolve the Zybo Z7-20 board part locally. They are support metadata, not an executable flow.

---

## 4. Documentation

```text
docs/
|-- repository_structure.md
|-- AXI-stream.md
|-- 데모 시나리오.md
|-- 하드웨어 파이프라인.md
|-- asset/
|-- log/
|-- spec/
`-- workflow/
```

| Path | Role |
| --- | --- |
| `docs/repository_structure.md` | This file; source tree and script-role map. |
| `docs/project_pipeline.md` | Actual project pipeline overview: verification, main demo build, board demo, fast rebuild, debug, and legacy flows. |
| `docs/spec/` | Stable design/spec decisions such as Q-format, model policy, and RTL contract. |
| `docs/workflow/` | Current and historical runbooks, dependency maps, and verification pipeline documents. |
| `docs/log/` | Chronological engineering/debug records. |
| `docs/asset/` | Diagrams, figures, PDFs, and other documentation assets. |
| `docs/AXI-stream.md` | AXI-Stream notes and signal-level study material. |
| `docs/데모 시나리오.md` | Demo scenario notes. |
| `docs/하드웨어 파이프라인.md` | Hardware pipeline explanation from PS/DMA/PL/UART perspective. |

### Key Workflow Documents

| File | Role |
| --- | --- |
| `docs/workflow/workflow_v16.md` | Next implementation plan for PC FFT visualization, numeric reporting, and report evidence capture. |
| `docs/workflow/workflow_v15.md` | Current runbook after SD boot and DMA length-width fix. |
| `docs/workflow/fir_n43_dependency_map.md` | Main `fir_n43` source/script/artifact dependency map. |
| `docs/workflow/fir_n43_verification_pipeline.md` | Canonical model -> vector -> RTL simulation verification flow. |

---

## 5. Python Model Layer

```text
model/
|-- config.py
|-- q1_15.py
|-- ideal/
`-- fixed/
```

| Script | Role |
| --- | --- |
| `model/config.py` | Single source of truth for FIR defaults: sample rates, N=43, Q1.15, M=2, tone profile, and stopband target. |
| `model/q1_15.py` | Shared Q1.15 quantization/dequantization and clipping helpers. |
| `model/ideal/design_kaiser_coeff.py` | Designs Kaiser low-pass FIR coefficients from the project spec. |
| `model/ideal/gen_multitone.py` | Generates deterministic multitone input used by model comparison and demo vectors. |
| `model/ideal/anti_alias_fir.py` | Float64 direct-form FIR reference. |
| `model/ideal/fir_decimator_ideal.py` | Float64 FIR + M=2 decimator reference chain. |
| `model/ideal/decimator.py` | Float-domain decimator helper. |
| `model/fixed/decimator.py` | Q1.15 fixed-point decimator helper shared by fixed golden chains. |
| `model/fixed/direct_form/anti_alias_fir.py` | Q1.15 direct-form FIR golden model. |
| `model/fixed/direct_form/fir_decimator_golden.py` | Q1.15 direct-form FIR + decimator golden chain, mainly historical/bringup support. |
| `model/fixed/transposed_form/anti_alias_fir.py` | Q1.15 transposed-form FIR golden model aligned with RTL arithmetic policy. |
| `model/fixed/transposed_form/fir_decimator_golden.py` | Canonical Q1.15 transposed FIR + decimator golden chain for N=43 RTL vectors. |

---

## 6. RTL Layer

```text
rtl/
|-- transposed_form/
|   |-- decimator_m2_phase0.v
|   `-- n43/
|       |-- fir_n43.v
|       |-- fir_decimator_n43.v
|       |-- fir_decimator_n43_axis.v
|       `-- constrs/zybo_n43.xdc
|-- direct_form/
`-- debug/
```

| File | Role |
| --- | --- |
| `rtl/transposed_form/n43/fir_n43.v` | Canonical N=43 transposed-form FIR RTL core. |
| `rtl/transposed_form/n43/fir_decimator_n43.v` | Connects N=43 FIR output to M=2 decimator. |
| `rtl/transposed_form/n43/fir_decimator_n43_axis.v` | AXI-Stream wrapper with dynamic TLAST and auto-flush behavior for DMA integration. |
| `rtl/transposed_form/n43/constrs/zybo_n43.xdc` | Zybo-oriented constraints for N=43 target. |
| `rtl/transposed_form/decimator_m2_phase0.v` | M=2 phase-0 decimator in the transposed-form path. |
| `rtl/direct_form/decimator_m2_phase0.v` | Older direct-form decimator retained for N=5 bringup/legacy paths. |
| `rtl/direct_form/bringup_n5/*.v` | Historical N=5 direct-form board bringup RTL and LED/checker support. |
| `rtl/debug/axis_dma_smoke_test.v` | Debug RTL target for DMA/DDR/UART smoke testing without the FIR datapath. |
| `rtl/debug/axis_decimator_m2_n43_debug.v` | Debug RTL target for isolating AXI-Stream decimator behavior. |

---

## 7. Simulation Layer

```text
sim/
|-- Makefile
|-- python/
|-- rtl/tb/
|-- output/   # generated
|-- vectors/  # generated
`-- build/    # generated
```

### Make Targets

| Target | Role |
| --- | --- |
| `make -C sim run_all` | Canonical N=43 RTL verification gate. Runs FIR, FIR+decimator, and AXI wrapper TBs. |
| `make -C sim run_legacy_n5` | Historical N=5 direct-form bringup TBs. Not part of the canonical gate. |
| `make -C sim clean` | Removes compiled simulation outputs under `sim/build/`. |

### Python Scripts

| Script | Role |
| --- | --- |
| `sim/python/run_check_coeff_stopband_spec.py` | Checks ideal and quantized coefficient stopband attenuation. Exits non-zero when requested taps fail the spec unless `--allow-failures` is used. |
| `sim/python/run_compare_ideal_vs_fixed.py` | Generates float64 ideal outputs, Q1.15 fixed golden outputs, error metrics, and `.npy` artifacts. |
| `sim/python/export_rtl_bringup_vectors.py` | Converts generated `.npy` Q1.15 arrays into RTL `$readmemh` `.hex` files. |
| `sim/python/inspect_kaiser_coeff.py` | Prints/inspects generated Kaiser coefficients, useful when updating RTL localparams. |
| `sim/python/run_bringup_ideal.py` | Historical N=5 bringup ideal-vector generation helper. |
| `sim/python/downsample_only_ideal.py` | Simple downsample-only reference helper from early bringup work. |

### RTL Testbenches

| Testbench | Role |
| --- | --- |
| `sim/rtl/tb/transposed_form/tb_fir_n43.sv` | Compares N=43 FIR RTL output against `expected_fir_q15.hex`. |
| `sim/rtl/tb/transposed_form/tb_fir_decimator_n43.sv` | Compares FIR+decimator RTL output against `expected_decim_q15.hex`. |
| `sim/rtl/tb/transposed_form/tb_fir_decimator_n43_axis.sv` | Verifies AXI-Stream wrapper data, TLAST, backpressure, and reset recovery. |
| `sim/rtl/tb/direct_form/tb_fir_direct_n5.v` | Legacy N=5 direct-form FIR testbench. |
| `sim/rtl/tb/direct_form/tb_fir_decimator_direct_n5_top.v` | Legacy N=5 FIR+decimator testbench. |

---

## 8. Software Layer

```text
sw/
|-- fir_decimator_demo.c
|-- fir_decimator_demo.py
|-- bringup_demo.c
`-- test/
```

| Script | Role |
| --- | --- |
| `sw/fir_decimator_demo.c` | Bare-metal PS application. Generates input, controls AXI DMA, reads PL output, and streams results over UART. |
| `sw/fir_decimator_demo.py` | PC-side UART client and FFT viewer for board demo modes `1-1` and `1-2`. |
| `sw/bringup_demo.c` | Historical bare-metal bringup app kept for reference. |
| `sw/test/test_fir_decimator_demo.py` | Unit tests for PC-side UART command/packet parsing and analysis helpers. |

---

## 9. Vivado Flows

```text
vivado/
|-- fir_n43/
`-- debug/
    |-- smoke/
    `-- axis_debug/
```

| Script | Role |
| --- | --- |
| `vivado/fir_n43/build_bd_fir_dma.tcl` | Canonical Vivado batch build for PS + AXI DMA + N=43 FIR/decimator block design. Creates `build/fir_n43/{vivado,vitis,output}` artifacts. |
| `vivado/fir_n43/bd_fir_dma.tcl` | Block Design construction script sourced by the main Vivado build wrapper. |
| `vivado/fir_n43/build_fir_transposed_n43.tcl` | RTL-only Vivado build helper for the N=43 transposed FIR target. |
| `vivado/debug/smoke/build_bd_fir_dma_smoke.tcl` | Debug Vivado build wrapper for DMA/DDR/UART smoke target. |
| `vivado/debug/smoke/bd_fir_dma_smoke.tcl` | Block Design construction for the smoke target. |
| `vivado/debug/axis_debug/build_bd_fir_dma_axis_debug.tcl` | Debug Vivado build wrapper for AXI-Stream decimator isolation target. |
| `vivado/debug/axis_debug/bd_fir_dma_axis_debug.tcl` | Block Design construction for the AXI debug target. |

---

## 10. Vitis Flows

```text
vitis/
|-- fir_n43/
`-- legacy/
```

| Script | Role |
| --- | --- |
| `vitis/fir_n43/build_fir_decimator_demo.py` | Canonical Vitis script. Builds platform/app from the main XSA and copies FSBL, app ELF, and BIF inputs to `build/fir_n43/output/`. |
| `vitis/fir_n43/rebuild_boot_image.sh` | Fast rebuild path for C-only or selected bitstream changes. Rebuilds app and repackages BOOT image from an existing Vitis workspace. |
| `vitis/legacy/download_and_run.py` | Historical XSDB/JTAG loader. Retained for debug context, not trusted final validation. |
| `vitis/legacy/bringup_demo/download_bringup.py` | Historical bringup XSDB/JTAG loader. |
| `vitis/legacy/test_uart.py` | Minimal legacy UART smoke reader for old bringup/debug flow. |

---

## 11. Generated Build Layout

The canonical main target writes generated files under:

```text
build/
`-- fir_n43/
    |-- vivado/
    |-- vitis/
    `-- output/
```

Debug targets use:

```text
build/
`-- debug/
    |-- smoke/
    |   |-- vivado/
    |   `-- output/
    `-- axis_debug/
        |-- vivado/
        `-- output/
```

These directories are generated by scripts and should not be treated as source. The future `build/fir_n43_pipelined/` target is reserved conceptually but should not be created until the corresponding source flow exists.

---

## 12. Main Script Flow Summary

```text
Verification:
  uv run pytest -q
  uv run python -m sim.python.run_check_coeff_stopband_spec --num-taps 43
  uv run python -m sim.python.run_compare_ideal_vs_fixed --num-taps 43 --form transposed
  uv run python -m sim.python.export_rtl_bringup_vectors ...
  make -C sim run_all

Hardware build:
  vivado -mode batch -source vivado/fir_n43/build_bd_fir_dma.tcl

Software/BOOT:
  vitis -s vitis/fir_n43/build_fir_decimator_demo.py
  bootgen -arch zynq -image build/fir_n43/output/fir_decimator_demo.bif -o build/fir_n43/output/BOOT.bin -w on

Fast rebuild:
  vitis/fir_n43/rebuild_boot_image.sh --boot-tag FIR

Board demo:
  python sw/fir_decimator_demo.py --mode 1-1 --port /dev/ttyUSB1 --timeout 30
  python sw/fir_decimator_demo.py --mode 1-2 --port /dev/ttyUSB1 --timeout 30
```

