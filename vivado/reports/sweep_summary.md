# FIR N43 Clock Sweep Summary

- 생성일: 2026-07-01
- 보드: Zybo Z7-20 (xc7z020clg400-1)
- 설계: N=43 taps, M=2, transposed form

## 결과

| target_mhz | wns_ns  | timing_pass | lut  | dsp48 | total_power_w |
|-----------|---------|-------------|------|-------|---------------|
| 90        | +1.883  | true        | 4583 | 16    | 1.564         |
| 100       | +0.692  | true        | 4584 | 16    | 1.567         |
| 110       | +0.178  | true        | 4583 | 16    | 1.570         |
| 115       | +0.178  | true        | 4583 | 16    | 1.570         |
| 120       | -0.783  | false       | 4584 | 16    | 1.576         |

## Fmax

확정 Fmax: **115 MHz** (WNS ≥ 0인 최대 주파수)

pass → fail 전환: 115 MHz (PASS) → 120 MHz (FAIL), 경계 해상도 5 MHz

## 비고

- LUT/DSP48은 클럭 변경에 무관하게 일정 (combinational logic)
- 전력은 클럭 증가에 따라 미세 증가 (1.564 → 1.576 W, +0.8%)
- 100 MHz 기준 WNS=+0.692ns → Fmax 여유 +15 MHz
