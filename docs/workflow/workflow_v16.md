# FIR Decimation Project Workflow v16

- Date: 2026-05-24
- Previous: `docs/workflow/workflow_v15.md`
- Purpose: final demo/report polish plan after the main verification/build/board pipelines were organized.
- Pipeline overview: `docs/project_pipeline.md`
- Dependency map: `docs/workflow/fir_n43_dependency_map.md`

---

## 1. Current Baseline

| Item | Current state |
| --- | --- |
| Canonical target | `fir_n43`: N=43 transposed-form FIR + M=2 decimator |
| Verification gate | Python model/vector generation + `make -C sim run_all` |
| Main build path | Vivado hardware build -> Vitis app/platform build -> `BOOT.bin` |
| Board path | SD boot + AXI DMA + UART + PC Python FFT viewer |
| Confirmed demo modes | `1-1` and `1-2` reach FFT plots when each scenario starts from a fresh board reset |
| PC-only mode | Scenario `0` compares downsample-only aliasing vs FIR + decimation |
| Interactive mode | Scenario `2` accepts user-provided tones |
| Missing numbered mode | Scenario `3` is not currently defined or implemented |

The project is no longer in the main bringup phase. The next work should improve how clearly the demo proves the filter behavior and how easily the result can be captured for a report.

---

## 2. Scope For v16

v16 focuses on demo/report quality, not new hardware plumbing.

| Priority | Work item | Reason |
| --- | --- | --- |
| P0 | Clean FFT visualization in `sw/fir_decimator_demo.py` | The current plot proves that data arrives, but the visual axis and tone evidence are not yet presentation-quality. |
| P0 | Print numeric peak/attenuation summaries | A report/demo should not depend only on eyeballing a matplotlib plot. |
| P0 | Compare board output against a Python reference | This turns the board demo from "looks right" into measured evidence. |
| P1 | Save representative plots and metrics under `docs/` | Captured artifacts are needed for documentation and final reporting. |
| P1 | Document final demo commands and expected PASS criteria | The project should be reproducible by running a small command set. |
| P2 | Decide whether scenario `3` is needed | Do not add a new mode unless it tells a different story than `0`, `1-1`, `1-2`, or `2`. |

---

## 3. Scenario Status

| Scenario | Status | Board required | Purpose |
| --- | --- | --- | --- |
| `0` | Implemented | No | PC-only explanation of aliasing: downsample-only vs FIR + decimation |
| `1-1` | Implemented | Yes | Happy case: 5 MHz passband, 20 MHz transition, 30 MHz stopband |
| `1-2` | Implemented | Yes | Edge case: 7 MHz passband, 15 MHz passband edge, 25 MHz stopband edge, 45 MHz deep stopband |
| `2` | Implemented | Yes | Interactive user-selected tones |
| `3` | Not defined | TBD | Reserved only if a new demo need appears |

Decision for now: do not implement scenario `3` until the existing modes have clean numeric reporting and saved evidence.

---

## 4. Python FFT Visualization Improvements

Target file:

```text
sw/fir_decimator_demo.py
```

Required improvements:

| Task | Expected behavior |
| --- | --- |
| Split input/output axis policy | Input FFT uses 100 MHz sample rate and displays 0-50 MHz. Output FFT uses 50 MHz sample rate and displays 0-25 MHz. |
| Show Nyquist limits clearly | Output plot should not leave an empty 25-50 MHz region. |
| Add tone markers | Draw vertical markers or labels for scenario tones that matter for the explanation. |
| Use consistent dB reference | Input/output plots should use a clear common reference so attenuation is interpretable. |
| Add scenario title/metadata | Plot title should include mode name, tones, sample rates, and whether data is PC-only or board-measured. |
| Keep scenario `0` visually separate | Scenario `0` should remain PC-only and explicitly show aliasing without requiring UART. |

Initial command checks:

```bash
python sw/fir_decimator_demo.py --mode 0
python sw/fir_decimator_demo.py --mode 1-1 --port /dev/ttyUSB1 --timeout 30
python sw/fir_decimator_demo.py --mode 1-2 --port /dev/ttyUSB1 --timeout 30
```

For `1-1` and `1-2`, continue to reset the board before each scenario until software-controlled PL/FIR reset is implemented.

---

## 5. Numeric Reporting Improvements

The PC script already receives board output samples as `sig_out` in `sw/fir_decimator_demo.py`. Do not create a second UART/capture CLI that duplicates mode parsing and serial protocol handling. Keep the existing demo script as the only board-facing entry point, and split only the pure measurement logic into a reusable module.

Recommended implementation boundary:

| File | Responsibility |
| --- | --- |
| `sw/fir_decimator_demo.py` | CLI entry point, mode selection, UART send/receive, plotting, `--save-dir` handling, and calls into metrics helpers |
| `sw/fir_decimator_metrics.py` | Pure numeric analysis: FFT peak extraction, alias-bin mapping, attenuation, Python reference generation, sample-domain metrics, report dict/CSV rows |
| `sw/test/test_fir_decimator_metrics.py` | Board-free unit tests for numeric analysis behavior |

The useful dataflow is:

```text
sig_in + sig_out
  -> metrics helpers
  -> sample-domain comparison
  -> tone/FFT peak table
  -> JSON/CSV report
  -> optional plot/save step
```

The PC script should print a compact table after each run.

Recommended fields:

| Field | Meaning |
| --- | --- |
| `mode` | `0`, `1-1`, `1-2`, or `2` |
| `tone_mhz` | Original input tone |
| `region` | passband, transition, stopband-edge, or stopband |
| `input_peak_db` | Measured input FFT peak near the tone |
| `output_peak_db` | Measured output FFT peak near the expected output/alias bin |
| `attenuation_db` | `output_peak_db - input_peak_db` or board-vs-reference attenuation metric |
| `verdict` | PASS/WARN/INFO, depending on scenario policy |

Important measurement rule: after decimation, frequencies above the 25 MHz output Nyquist fold into the 0-25 MHz band if not removed. For stopband tones, the useful report is not only the folded-bin peak; it should also compare the board output against the Python reference to avoid ambiguous overlap between tones.

Initial scenario policy:

| Scenario | Expected numeric evidence |
| --- | --- |
| `1-1` | 5 MHz remains strong; 30 MHz contribution is strongly suppressed; 20 MHz is transition-band and should be reported as INFO/WARN rather than hard PASS. |
| `1-2` | 7 MHz and 15 MHz remain visible; 25 MHz and 45 MHz are suppressed according to the Python reference/stopband expectation. |
| `0` | Downsample-only view shows alias peaks; FIR + decimation view suppresses stopband/alias artifacts. |

Do not make the first implementation too strict. The first useful version should print stable measurements. Tight PASS thresholds can be added after observed board data is captured.

---

## 6. Python Reference Comparison

Board output should be compared against a Python-generated reference for the same tone list. This comparison belongs in `sw/fir_decimator_metrics.py`, not inside UART parsing code.

Preferred direction:

1. `sw/fir_decimator_demo.py` generates or records the same input tone list used for the board run.
2. The board returns `sig_out` through the existing UART path.
3. `sw/fir_decimator_metrics.py` generates the Python reference for the same tone list.
4. The metrics module compares `sig_out` against the reference output.
5. The demo script prints summary metrics and optionally saves JSON/CSV/PNG artifacts.

Do not duplicate these responsibilities in a separate `fir_decimator_measure.py` unless it is only a thin wrapper around the same metrics module. A second script that reopens UART, reparses modes, and reimplements capture would add maintenance risk.

Recommended metrics:

| Metric | Purpose |
| --- | --- |
| `max_abs_error_lsb` | Easy bit-level sanity check |
| `rmse_lsb` | Overall sample-level mismatch |
| `snr_db` | Report-friendly signal quality metric |
| `corr` | Quick shape agreement check |
| `peak_delta_db` | Frequency-domain agreement at expected tones |

Pass criteria can initially be documented as observed values from a known-good board run, then tightened if needed.

---

## 7. Saved Evidence

Representative outputs should be saved so the final report does not depend on re-running the board demo.

Recommended destination:

```text
docs/report/fir_n43_demo_evidence/
```

Recommended files:

| File | Content |
| --- | --- |
| `scenario0_aliasing.png` | PC-only aliasing comparison |
| `scenario1_1_board_fft.png` | Board-measured 1-1 input/output FFT |
| `scenario1_2_board_fft.png` | Board-measured 1-2 input/output FFT |
| `scenario1_1_metrics.json` | Numeric report for 1-1 |
| `scenario1_2_metrics.json` | Numeric report for 1-2 |
| `summary.md` | Short human-readable result summary |

Generated evidence can be committed only if it is intentionally selected for the final report. Raw regenerated vectors and build products remain untracked.

---

## 8. Optional Scenario 3 Decision

Only add scenario `3` if it adds a distinct message. Candidate meanings:

| Candidate | Value | Cost |
| --- | --- | --- |
| Report capture mode | Runs fixed scenarios and saves plots/metrics automatically | Useful, but can also be a `--save-dir` option instead of a new scenario |
| Stress/random tones | Shows robustness over many tone sets | Less useful for a clean demo; better as a test mode |
| Reset/recovery demo | Demonstrates current back-to-back scenario limitation or future software reset fix | Useful only after reset behavior is fixed |

Recommendation: do not add scenario `3` yet. Implement `--save-dir` and numeric reporting first. If automatic report capture becomes important, add it as an option that works for `0`, `1-1`, and `1-2`.

---

## 9. Suggested Implementation Order

1. Add `sw/fir_decimator_metrics.py` with board-free metric helpers and unit tests.
2. Refactor `sw/fir_decimator_demo.py` so `sig_out` is passed into the metrics module after UART receive.
3. Fix input/output FFT axis limits and labels.
4. Add tone peak extraction and print a simple table for modes `0`, `1-1`, and `1-2`.
5. Add Python reference generation and board-vs-reference metrics.
6. Add `--save-dir`, `--no-plot`, and JSON/CSV/PNG saving.
7. Update README demo commands and PASS criteria.
8. Capture final board evidence into `docs/report/fir_n43_demo_evidence/`.

This order keeps hardware risk low: the first several steps are PC-side only, and the board protocol remains unchanged.

---

## 10. Completion Criteria For v16

v16 is done when:

| Criterion | Required result |
| --- | --- |
| Scenario `0` | Produces a clean PC-only aliasing comparison plot |
| Scenario `1-1` | Board run prints numeric tone/metric summary and shows a clean FFT plot |
| Scenario `1-2` | Board run prints numeric tone/metric summary and shows a clean FFT plot |
| Reference comparison | Board output is compared against Python reference with sample/frequency-domain metrics |
| Report artifacts | Representative PNG/JSON/summary files are saved under `docs/report/fir_n43_demo_evidence/` |
| Documentation | README points to the final demo commands and PASS criteria |
