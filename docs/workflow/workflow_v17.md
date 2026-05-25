# FIR Decimation Project Workflow v17

- Date: 2026-05-26
- Previous: `docs/workflow/workflow_v16.md`
- Purpose: rough post-v1.0 plan for characterization, BIST, reliability experiments, and v2.0 architecture work.
- Baseline evidence: `docs/report/fir_n43/`
- Planning source: `todo.md`

---

## 1. Positioning

v16 closed the main v1.0 demonstration/evidence path:

- FIR N43 transposed-form decimator runs on board through SD boot.
- Python viewer/report path compares board output against fixed-point golden output.
- Scenario 1-1 and 1-2 board evidence is saved under `docs/report/fir_n43/`.
- Shared output FFT bin ambiguity is explicitly marked as `INFO` in metrics and summary.

v17 starts after the v1.0 README cleanup. The next work is not another demo-polish cycle. It is a characterization and improvement cycle:

```text
v1.0 baseline freeze
  -> clock/timing/thermal/power characterization
  -> BIST/test-time reduction
  -> reliability/fault analysis
  -> v2.0 timing/reliability architecture
  -> v1.0 vs v2.0 PPA report
```

Important distinction:

```text
Input tone frequency contract: 1 MHz <= tone < 50 MHz
v17 frequency sweep: PL/FIR operating clock sweep, e.g. 50 MHz to 200 MHz
```

The 50-200 MHz sweep is not a signal-tone sweep. It is a hardware operating-condition sweep used to estimate timing margin, Fmax, correctness margin, thermal behavior, and optionally power.

---

## 2. v1.0 Closeout Gate

Before starting v17 work, freeze v1.0 with a short README update.

| Item | Required content |
| --- | --- |
| Live demo command | `sw/fir_decimator_demo.py --mode 0/1-1/1-2/2` usage |
| Report command | `sw/fir_decimator_report.py --mode 1-1/1-2 --port ...` usage |
| Board reset requirement | Run one board scenario per reset until software reset is implemented |
| Verdict meaning | `PASS`, `INFO`, `WARN`; transition/shared-bin rows are not hard PASS criteria |
| Evidence path | `docs/report/fir_n43/summary/*.md`, `metrics/*.json`, `plot/*.png` |

v1.0 should be treated as frozen once README points to the final evidence and commands.

---

## 3. v17 Scope

| Priority | Work item | Reason |
| --- | --- | --- |
| P0 | Clock sweep build/run environment | Needed to characterize timing margin and Fmax. |
| P0 | Correctness metrics under each clock point | Fmax is only meaningful if output still matches golden. |
| P0 | XADC temperature/voltage logging | Captures physical operating condition during repeated runs. |
| P1 | BIST architecture sketch and prototype | Enables fast in-hardware correctness screening and test-time comparison. |
| P1 | Board-level power/current measurement | Useful for PPA and energy-efficiency story if measured carefully. |
| P2 | Fault injection experiments | Useful for reliability narrative, but should not block Fmax/BIST work. |
| P2 | v2.0 pipeline/reliability redesign | Should be driven by measured v1.0 weaknesses, not guessed upfront. |

Power measurement is not too much if scoped correctly. It becomes too much only if the report claims IP-only power from a coarse board-level measurement. The safe scope is:

```text
Measure and report board-level or rail-level power trend under controlled conditions.
Use it as relative evidence, not as exact FIR-IP-only power.
```

---

## 4. Characterization Environment

Target output directory:

```text
docs/characterization/fir_n43_v1/
```

Suggested structure:

```text
docs/characterization/fir_n43_v1/
  raw/
    clock_050mhz/
    clock_075mhz/
    clock_100mhz/
    ...
  summary/
    clock_sweep.csv
    xadc_log.csv
    power_log.csv
    pass_fail_matrix.md
  plot/
    fmax_shmoo.png
    temp_vs_clock.png
    error_vs_clock.png
    power_vs_clock.png
```

First sweep points:

```text
50, 75, 100, 125, 150, 175, 200 MHz
```

After the first failure boundary is found, refine around it with smaller steps, for example 5 MHz or 10 MHz.

Required columns for `clock_sweep.csv`:

| Column | Meaning |
| --- | --- |
| `clock_mhz` | Target PL/FIR clock frequency |
| `vivado_wns_ns` | Worst negative slack from timing report |
| `vivado_tns_ns` | Total negative slack from timing report |
| `timing_pass` | Static timing pass/fail, usually `WNS >= 0` |
| `boot_pass` | Board boots and prints `READY FIR` |
| `report_1_1_pass` | Scenario 1-1 report overall verdict |
| `report_1_2_pass` | Scenario 1-2 report overall verdict |
| `max_error_lsb` | Worst sample-domain max error across selected scenarios |
| `snr_db` | Worst sample-domain SNR across selected scenarios |
| `failure_mode` | Timing fail, boot fail, DMA timeout, metric WARN, etc. |
| `evidence_path` | Path to raw logs/reports for that point |

Static timing and board behavior should be kept separate. If `WNS < 0` but the board appears to pass once, that is still not a clean pass. It should be recorded as a timing failure with observed functional behavior.

---

## 5. XADC Logging

Goal: record physical condition while the FIR path is exercised.

Preferred first implementation:

| Item | Direction |
| --- | --- |
| Source | Zynq XADC/System Monitor |
| Integration | Bare-metal app prints XADC readings over UART before/after report run, or exposes a small measurement command |
| Metrics | temperature, VCCINT, VCCAUX, VCCBRAM if available |
| Granularity | Start/end values first; periodic logging later if needed |
| Output | CSV rows joined with clock sweep result |

Minimum useful data:

```text
clock_mhz, scenario, temp_c_before, temp_c_after, vccint_v, vccaux_v, pass_fail, notes
```

Do not overfit the first version. Start with before/after readings around each scenario run. Continuous high-rate logging can come later if there is a clear thermal question.

---

## 6. Power Measurement

Power is worth including, but it should be scoped as a controlled, relative measurement.

Recommended priority:

| Level | Method | Use in report |
| --- | --- | --- |
| P1 | Digital multimeter measures board input current or accessible rail current | Relative board-level power trend vs clock |
| P1 | Vivado power estimate with consistent activity assumptions | Design-level estimate for v1.0/v2.0 comparison |
| P2 | Rail-specific current sense or shunt measurement | Better rail-level evidence if hardware access is practical |
| Avoid | Claiming exact FIR-IP-only power from USB/board total current | Too coarse and misleading |

If using a digital multimeter, record the measurement boundary explicitly:

```text
Measured quantity: board input current, not isolated FIR dynamic power.
Power estimate: P_board ~= V_input * I_input.
Interpretation: relative board-level trend across clock/configuration points.
```

Suggested `power_log.csv` columns:

| Column | Meaning |
| --- | --- |
| `clock_mhz` | Target PL/FIR clock |
| `scenario` | Idle, 1-1 loop, 1-2 loop, BIST loop, etc. |
| `voltage_v` | Measured input or rail voltage |
| `current_a` | Measured current |
| `power_w` | `voltage_v * current_a` |
| `measurement_point` | USB input, DC jack, VCCINT rail, etc. |
| `instrument` | DMM model or measurement method |
| `notes` | Ambient temperature, board state, fan/cooling, run duration |

Power should not block v17 P0. The first mandatory target is timing/correctness characterization. Power is valuable for PPA and final report once the measurement setup is stable.

---

## 7. BIST Direction

BIST should answer a practical question:

```text
How much faster can the design validate itself compared with UART output capture?
```

Initial BIST architecture:

```text
Pattern generator / ROM
  -> FIR decimator under test
  -> expected-output ROM or golden stream
  -> comparator
  -> counters/status registers
```

Minimum status fields:

| Field | Meaning |
| --- | --- |
| `done` | BIST completed |
| `pass` | No mismatch observed |
| `mismatch_count` | Number of mismatched samples |
| `first_mismatch_index` | First failing output sample index |
| `max_abs_error_lsb` | Worst observed sample error |
| `cycle_count` | Hardware test duration |

Comparison target:

| Method | Expected result |
| --- | --- |
| UART report path | Full output capture and Python metrics, slower but rich evidence |
| BIST path | On-chip pass/fail and error counters, faster but less detailed |

The report should quantify test-time reduction, not just say BIST exists.

---

## 8. Fault Injection And Reliability

Fault injection is valuable, but it should come after the baseline characterization and BIST skeleton.

Candidate injection points:

| Injection target | Expected observation |
| --- | --- |
| Coefficient bit flip | Stopband/passband response degradation |
| Accumulator bit flip | Large sample-domain error and SNR drop |
| AXI-Stream TLAST/drop fault | DMA timeout or packet mismatch |
| Control/status bit fault | BIST/report disagreement or stuck status |

Useful outputs:

```text
fault_id, injection_point, affected_bit, scenario, max_error_lsb, snr_db, verdict, failure_signature
```

Do not add fault injection into the clean v1.0 RTL path. Keep it under a separate build flag, variant module, or simulation-only path until the experiment is stable.

---

## 9. v2.0 Architecture Direction

v2.0 should be driven by v1.0 characterization data.

Candidate improvements:

| Trigger from v1.0 data | v2.0 response |
| --- | --- |
| Timing fails before target clock | Add pipeline stages around critical FIR/accumulator paths |
| BIST shows high test-time savings | Promote BIST to first-class testability feature |
| Temperature/power grows too quickly | Evaluate clock gating, lower toggle activity, or operating point constraints |
| Fault injection shows fragile node | Add diagnostic counter, redundancy, or safer saturation/control logic |

Expected v2.0 comparison dimensions:

```text
Performance: Fmax, throughput, latency
Power: board-level measured trend and/or Vivado power estimate
Area: LUT, FF, DSP48, BRAM
Correctness: max error, RMSE, SNR, PASS/INFO/WARN counts
Testability: BIST cycle count vs UART capture time
Reliability: fault signature and diagnosability
```

---

## 10. First Implementation Order

1. Finish README v1.0 closeout.
2. Create a clock-sweep build parameter for the FIR/PL clock.
3. Save timing summaries per clock point.
4. Run report scenario 1-1 and 1-2 at the baseline clock and at one lower/higher clock point.
5. Define `clock_sweep.csv` and write a small collector script.
6. Add XADC before/after readings to the board app or a small UART command.
7. Decide the DMM measurement point for board-level power.
8. Add BIST design sketch and pick the first pattern set.
9. Only then refine Fmax sweep and add fault-injection experiments.

---

## 11. Completion Criteria For v17

v17 is complete when:

| Criterion | Required result |
| --- | --- |
| v1.0 closeout | README points to final demo/report commands, verdict meaning, reset rule, and evidence path |
| Clock sweep | At least 50/75/100/125/150 MHz points have timing summaries and pass/fail records |
| Correctness sweep | At least scenario 1-1 and 1-2 are checked against golden at selected clock points |
| XADC logging | Temperature and voltage readings are captured with each board run or at least before/after each point |
| Power scope | DMM or Vivado power method is chosen and documented; initial data is optional for P0 but required for PPA report |
| BIST plan | BIST architecture and status fields are specified; prototype may start in v18 if v17 gets too large |
| v2.0 direction | At least one v2.0 improvement is justified by v1.0 characterization data |
