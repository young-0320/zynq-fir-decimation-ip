# FIR N43 Verification Pipeline

- Date: 2026-05-24
- Scope: canonical verification flow for `fir_n43`
- Related documents:
  - `docs/workflow/workflow_v15.md`
  - `docs/workflow/fir_n43_dependency_map.md`
  - `docs/log/13_transposed_form_golden_policy.md`
  - `docs/log/15_rtl_vector_pipeline_extension.md`
  - `docs/log/28_axis_tb_update_for_log25_rtl_redesign.md`

---

## 1. Document Role

This document belongs under `docs/workflow/`.

It is not a `spec` document because it does not define a new fixed design rule such as Q-format, coefficient policy, reset contract, or RTL arithmetic behavior. Those rules are already captured in `docs/spec/` and design logs.

It is not only a `log` document because the goal is not to record one debugging session. The goal is to provide a repeatable runbook: which script to run, what artifact it creates, and why the next stage needs that artifact.

---

## 2. Canonical Target

The canonical verification target is:

```text
N=43 transposed-form FIR
  -> M=2 decimator
  -> AXI-Stream wrapper
```

N=5 direct-form bringup remains historical context. It can still be useful as a legacy regression, but it is not the canonical verification target for the current project direction.

Generated vectors are not source files. Files under `sim/output/` and `sim/vectors/` are regenerated artifacts and must not be committed.

---

## 3. End-To-End Flow

```text
model/config.py
  -> Python model regression
  -> coefficient stopband check
  -> float64 ideal vs Q1.15 fixed transposed golden
  -> .npy artifacts under sim/output/
  -> RTL .hex vectors under sim/vectors/
  -> iverilog self-checking RTL simulation
  -> Vivado/Vitis/BOOT.bin main demo pipeline
```

The verification pipeline itself is the model/vector/RTL simulation part. Vivado/Vitis/BOOT.bin belongs to the main demo pipeline and consumes RTL that has already passed local verification.

---

## 4. Source Of Truth

### Stage

Common configuration.

### Source

- `model/config.py`

### Defines

- Input sample rate: 100 MHz
- Passband edge: 15 MHz
- Stopband edge: 25 MHz
- Stopband attenuation target: 60 dB
- Fixed-point format: signed Q1.15
- Decimation factor: M=2
- Current spec tap count: N=43
- Bringup vector length: 8192 samples
- Bringup multitone profile: 5 MHz, 20 MHz, 30 MHz

### Reason

Every later stage must use the same numerical contract. If the Python model, vector generator, RTL testbench, and board demo use different assumptions, a mismatch cannot be interpreted reliably.

---

## 5. Python Regression

### Command

```bash
uv sync
uv run pytest -q
```

### Source Inputs

- `model/`
- `sim/python/`
- `sw/fir_decimator_demo.py`
- `sim/python/test/`
- `sw/test/`

### Artifacts

No canonical artifact is produced.

### Pass Criterion

All pytest tests pass.

### Reason

This catches broken model logic, Q1.15 helper behavior, vector-export behavior, and PC-side UART parsing before generating any verification vectors.

---

## 6. Coefficient Stopband Check

### Command

```bash
uv run python -m sim.python.run_check_coeff_stopband_spec --num-taps 43
```

### Script

- `sim/python/run_check_coeff_stopband_spec.py`

### Source Inputs

- `model/config.py`
- `model/ideal/design_kaiser_coeff.py`
- `model/q1_15.py`

### Generated Artifacts

```text
sim/output/coeff_stopband_spec_n43/
  freq_hz.npy
  n43_coeff_float.npy
  n43_coeff_q15.npy
  n43_coeff_q15_float.npy
  n43_ideal_mag_db.npy
  n43_quantized_mag_db.npy
  summary.json
  summary.txt
```

### Pass Criterion

For N=43, both ideal and quantized coefficient responses must report `meets_stopband_spec = true` in the summary. The summary also records `verdict.pass_count`, for example `2/2` for one tap count with ideal and quantized responses both passing.

The CLI exits non-zero and prints an error message when any requested tap/response fails the stopband criterion. Use `--allow-failures` only for exploratory tap sweeps where failing candidates are expected.

### Reason

This checks the filter coefficients before RTL is involved. If the coefficient response fails the 60 dB stopband target, RTL bit-exactness would only prove that the hardware correctly implements the wrong filter.

---

## 7. Float/Fixed Golden Generation

### Command

```bash
uv run python -m sim.python.run_compare_ideal_vs_fixed --num-taps 43 --form transposed
```

### Script

- `sim/python/run_compare_ideal_vs_fixed.py`

### Source Inputs

- `model/config.py`
- `model/ideal/fir_decimator_ideal.py`
- `model/ideal/gen_multitone.py`
- `model/ideal/design_kaiser_coeff.py`
- `model/fixed/transposed_form/fir_decimator_golden.py`
- `model/fixed/transposed_form/anti_alias_fir.py`
- `model/fixed/decimator.py`
- `model/q1_15.py`

### Generated Artifacts

```text
sim/output/ideal_vs_fixed_trans_n43/
  input_float.npy
  input_q15.npy
  input_q15_float.npy
  coeff_float.npy
  coeff_q15.npy
  coeff_q15_float.npy
  ideal_raw_fir.npy
  ideal_raw_decim.npy
  ideal_quantized_ref_fir.npy
  ideal_quantized_ref_decim.npy
  fixed_fir_q15.npy
  fixed_decim_q15.npy
  fixed_fir_float.npy
  fixed_decim_float.npy
  diff_vs_ideal_raw_fir.npy
  diff_vs_ideal_raw_decim.npy
  diff_vs_quantized_ref_fir.npy
  diff_vs_quantized_ref_decim.npy
  summary.json
  summary.txt
```

### Pass Criterion

The command completes and writes the summary/artifacts. For release or report evidence, inspect `summary.txt` or `summary.json` for fixed-vs-ideal error metrics.

### Reason

RTL should be compared against the Q1.15 fixed golden model, not directly against the float64 ideal model. The fixed golden model includes the arithmetic policy that the RTL is expected to implement:

- signed Q1.15 input and coefficients
- 16-bit by 16-bit product
- signed 48-bit wide accumulator
- ties-away-from-zero rounding
- final output saturation only
- M=2, phase=0 decimation

---

## 8. RTL Vector Export

### Command

```bash
uv run python -m sim.python.export_rtl_bringup_vectors \
  --num-taps 43 \
  --input-dir sim/output/ideal_vs_fixed_trans_n43 \
  --output-dir sim/vectors/transposed_form/n43
```

### Script

- `sim/python/export_rtl_bringup_vectors.py`

### Source Inputs

```text
sim/output/ideal_vs_fixed_trans_n43/input_q15.npy
sim/output/ideal_vs_fixed_trans_n43/coeff_q15.npy
sim/output/ideal_vs_fixed_trans_n43/fixed_fir_q15.npy
sim/output/ideal_vs_fixed_trans_n43/fixed_decim_q15.npy
```

### Generated Artifacts

```text
sim/vectors/transposed_form/n43/
  input_q15.hex
  coeff_q15.hex
  expected_fir_q15.hex
  expected_decim_q15.hex
```

### Pass Criterion

The command prints the exported file names and lengths without error.

Expected N=43 lengths:

```text
input_q15.hex           8192
coeff_q15.hex             43
expected_fir_q15.hex    8234
expected_decim_q15.hex  4117
```

### Reason

The RTL testbenches use `$readmemh`. They need deterministic hex files derived from the same fixed golden model that produced the Python evidence.

### Artifact Policy

Do not commit these files. They are reproducible from the Python model pipeline.

---

## 9. RTL Simulation

### Command

```bash
cd sim
make clean
make run_all
cd ..
```

### Build Script

- `sim/Makefile`

### Canonical N=43 Testbenches

| Testbench | Purpose |
| --- | --- |
| `sim/rtl/tb/transposed_form/tb_fir_n43.sv` | FIR core output vs `expected_fir_q15.hex` |
| `sim/rtl/tb/transposed_form/tb_fir_decimator_n43.sv` | FIR + M=2 decimator output vs `expected_decim_q15.hex` |
| `sim/rtl/tb/transposed_form/tb_fir_decimator_n43_axis.sv` | AXI-Stream wrapper data, TLAST, backpressure, and reset recovery |

### Generated Artifacts

```text
sim/build/*.out
```

### Pass Criterion

All testbenches print `PASS` and no `FAIL`, `mismatch`, or `error` appears in the output.

For stricter shell checking:

```bash
cd sim
make clean
make run_all 2>&1 | tee /tmp/sim_run_all.log
cd ..
grep -iE "error|fail|mismatch" /tmp/sim_run_all.log
```

The final `grep` should print nothing.

### Reason

This closes the Python fixed-golden to RTL loop. The comparison is driven by output-valid or AXI handshakes rather than absolute cycle count, so pipeline latency changes do not create false failures.

The AXI-Stream wrapper testbench is part of the canonical gate because past bugs were exposed only under backpressure, TLAST, or reset-recovery scenarios. It intentionally consumes the first 4096 entries of `expected_decim_q15.hex`; Icarus Verilog may print a `$readmemh` "Too many words" warning because the regenerated decimator golden has 4117 entries including tail samples.

### Legacy N=5 Note

`make run_all` is the canonical N=43 gate and excludes the historical N=5 direct-form bringup testbenches. Those legacy tests can be run explicitly with `make run_legacy_n5` after regenerating or providing their vectors locally.

---

## 10. Main Demo Pipeline Boundary

After the verification pipeline passes, the main demo pipeline starts:

```text
vivado/fir_n43/build_bd_fir_dma.tcl
  -> build/fir_n43/output/bd_fir_dma_wrapper.bit
  -> build/fir_n43/output/bd_fir_dma_wrapper.xsa
  -> vitis/fir_n43/build_fir_decimator_demo.py
  -> build/fir_n43/output/BOOT.bin
  -> board demo
```

This is documented in:

- `README.md`
- `docs/workflow/workflow_v15.md`
- `docs/workflow/fir_n43_dependency_map.md`

---

## 11. Summary Command Set

From repo root:

```bash
uv sync
uv run pytest -q

uv run python -m sim.python.run_check_coeff_stopband_spec --num-taps 43
uv run python -m sim.python.run_compare_ideal_vs_fixed --num-taps 43 --form transposed
uv run python -m sim.python.export_rtl_bringup_vectors \
  --num-taps 43 \
  --input-dir sim/output/ideal_vs_fixed_trans_n43 \
  --output-dir sim/vectors/transposed_form/n43

cd sim
make clean
make run_all
cd ..
```

Expected result:

```text
Python tests pass.
N=43 coefficient check passes and records a `2/2` stopband verdict.
N=43 fixed golden .npy artifacts are regenerated.
N=43 RTL .hex vectors are regenerated.
RTL testbenches print PASS without fail/mismatch/error output.
```
