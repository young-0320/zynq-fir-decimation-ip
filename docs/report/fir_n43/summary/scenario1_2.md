# FIR N43 Board Evidence - Scenario 1-2

## Summary

| Field | Value |
|---|---:|
| Scenario | Scenario 1-2 |
| Comparison | Board output vs fixed-point golden model |
| Tones (MHz) | 7, 15, 25, 45 |
| Output Samples Compared | 4096 |
| Overall | PASS |
| Max Error (LSB) | 7 |
| Mean Error (LSB) | 0.002 |
| RMSE (LSB) | 1.805 |
| SNR (dB) | 72.216 |
| Correlation | 1.000000 |
| Board Saturation Count | 0 |
| Latency Aligned | True |
| Trimmed Samples | head=0, tail=0 |
| FFT PNG | [../plot/scenario1_2_fft.png](../plot/scenario1_2_fft.png) |
| Metrics JSON | [../metrics/scenario1_2_metrics.json](../metrics/scenario1_2_metrics.json) |

## Board vs Golden Tone Peaks

| Tone (MHz) | Region | Expected Out (MHz) | Output Bin Sources (MHz) | Input (dB) | Board (dB) | Golden (dB) | Board-Golden (dB) | Board Atten (dB) | Golden Atten (dB) | Verdict |
|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| 7 | passband | 7 | 7 | -2.96 | -8.99 | -8.99 | -0.00 | -6.03 | -6.03 | PASS |
| 15 | passband | 15 | 15 | -0.58 | -6.61 | -6.62 | 0.00 | -6.03 | -6.03 | PASS |
| 25 | transition | 25 | 25 | 0.00 | -60.33 | -60.25 | -0.08 | -60.33 | -60.25 | INFO |
| 45 | stopband | 5 | 45 | -2.43 | -66.93 | -67.00 | 0.06 | -64.51 | -64.57 | PASS |

## Notes

- Run one report scenario per board reset.
- Transition-band tones are reported as INFO, not hard PASS criteria.
