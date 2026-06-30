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

## 크리티컬 패스 분석 (120 MHz, WNS = -0.783 ns)

```
Source:      u_fir_n43/z_reg[1][2]        (FIR 딜레이 레지스터, z⁻¹)
Destination: u_fir_n43/round_reg_reg[45]  (라운딩 레지스터)

Data Path Delay: 8.664 ns  (요구: 8.000 ns)
  Logic  : 6.057 ns (69.9%) — CARRY4×19, LUT×4, 총 23 로직 레벨
  Routing: 2.607 ns (30.1%)
```

**병목 원인:** transposed form 누산기의 carry ripple 체인.
`z_reg → LUT2 → CARRY4×19 → round_reg_reg` 경로가
한 클럭 안에 CARRY4 19개를 연속 통과해야 한다.
로직 딜레이의 대부분(~90%)이 이 carry chain에 집중되어 있다.

**v2.0 개선 방향:** 누산기 중간에 파이프라인 레지스터 삽입 →
CARRY4 체인을 2 클럭으로 분할 → 예상 Fmax 150+ MHz.

## 비고

- LUT/DSP48은 클럭 변경에 무관하게 일정 (combinational logic)
- 전력은 클럭 증가에 따라 미세 증가 (1.564 → 1.576 W, +0.8%)
- 100 MHz 기준 WNS=+0.692ns → Fmax 여유 +15 MHz
