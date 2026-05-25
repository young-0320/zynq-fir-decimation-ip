# FIR N43 Board Evidence - Scenario 1-1

## Summary

| Field | Value |
|---|---:|
| Scenario | Scenario 1-1 |
| Comparison | Board output vs fixed-point golden model |
| Tones (MHz) | 5, 20, 30 |
| Output Samples Compared | 4096 |
| Overall | PASS |
| Max Error (LSB) | 6 |
| Mean Error (LSB) | 0.008 |
| RMSE (LSB) | 1.403 |
| SNR (dB) | 74.863 |
| Correlation | 1.000000 |
| Board Saturation Count | 0 |
| Latency Aligned | True |
| Trimmed Samples | head=0, tail=0 |
| FFT PNG | [../plot/scenario1_1_fft.png](../plot/scenario1_1_fft.png) |
| Metrics JSON | [../metrics/scenario1_1_metrics.json](../metrics/scenario1_1_metrics.json) |

## Board vs Golden Tone Peaks

| Tone (MHz) | Region | Expected Out (MHz) | Output Bin Sources (MHz) | Input (dB) | Board (dB) | Golden (dB) | Board-Golden (dB) | Board Atten (dB) | Golden Atten (dB) | Verdict |
|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| 5 | passband | 5 | 5 | -0.01 | -6.04 | -6.04 | 0.00 | -6.03 | -6.03 | PASS |
| 20 | transition | 20 | 20, 30 | -0.00 | -12.03 | -12.03 | -0.00 | -12.03 | -12.03 | INFO |
| 30 | stopband | 20 | 20, 30 | 0.00 | -12.03 | -12.03 | -0.00 | -12.03 | -12.03 | INFO |

## Notes

- Run one report scenario per board reset.
- Transition-band tones are reported as INFO, not hard PASS criteria.
- Shared output FFT bins are reported as INFO because per-tone attribution is ambiguous.
