# FIR N43 (v1) Clock Sweep — clk_wiz 정밀 스윕

- 생성일: 2026-07-02
- 보드: Zybo Z7-20 (xc7z020clg400-1)
- 설계: N=43 taps, M=2, transposed form — **v1 (`fir_n43.v`, 3-stage 파이프라인)**
- 방법: Clocking Wizard(MMCM)로 PL 전체를 목표 주파수로 **정확히 분주** (요청 = 실제, 오차 0).
  PS7 하드 PLL은 정수 분주만 가능해 요청 주파수가 스냅되므로, 정확한 Fmax 측정을 위해 clk_wiz 사용.
  빌드: `vivado/fir_n43/build_bd_fir_dma_clkwiz.tcl -tclargs <MHz>`

## 결과 (target = actual)

| actual_mhz | wns_ns | timing_pass | lut  | dsp48 | total_power_w |
| ---------- | ------ | ----------- | ---- | ----- | ------------- |
| 110.000    | +0.381 | true        | 4582 | 16    | 1.695         |
| 115.000    | +0.231 | true        | 4582 | 16    | 1.699         |
| 116.000    | +0.016 | true        | 4581 | 16    | 1.699         |
| 117.000    | -0.071 | false       | 4586 | 16    | 1.705         |
| 118.000    | -0.044 | false       | 4582 | 16    | 1.701         |
| 119.000    | -0.205 | false       | 4586 | 16    | 1.691         |
| 120.000    | -0.098 | false       | 4589 | 16    | 1.699         |

## Fmax vs 골든(보드 구동 주파수)

**확정 Fmax: 116 MHz** (WNS ≥ 0인 최대 실제 주파수)

- last PASS: **116.000 MHz** (WNS +0.016) / first FAIL: 117.000 MHz (WNS -0.071)
- 경계 해상도 1 MHz.

**골든(실보드 배포): 115 MHz** (WNS +0.231, Fmax 대비 마진 +0.215ns 확보)

Fmax(116)는 WNS +0.016ns로 정적 타이밍 여유가 사실상 0에 가까워 실보드에서 온도/전압
변동에 따라 간헐적 오류가 날 위험이 있다. 따라서 **실제 배포/구동 주파수는 Fmax 바로 아래인
115 MHz로 낮춰 마진을 확보**한다. bit/xsa: `build/fir_n43_v1_freq_115mhz/output/`
(재현: `vivado/fir_n43/build_bd_fir_dma_clkwiz.tcl -tclargs 115` — 주파수별 디렉터리가
자동 생성되므로 동일 명령 재실행으로 그대로 재현 가능).

## 크리티컬 패스 (117~120 MHz FAIL, 전 주파수 동일 경로)

```
Source:      u_fir_n43/prod_reg_reg[0][2]_replica   (Stage1 곱셈 레지스터)
Destination: u_fir_n43/round_reg_reg[45]            (라운딩 레지스터)
Path Group:  clk_out1 (해당 목표 주파수, intra-clock setup)
```

transposed form 누산 → round 데이터패스의 CARRY4 carry-ripple 체인이 한 클럭 안에 들어가
병목이 된다(v1 3-stage 구조의 근본 한계). v2(4-stage)는 이 경로를 별도 stage로 분리해 Fmax를
크게 끌어올렸다 → `sweep_summary_v2.md` 참조.

## 비고

- DSP48 16개로 전 주파수 동일. LUT ~4581–4589 (clk_wiz MMCM/BUFG 포함분).
- 크리티컬 패스가 로직 지배(round CARRY4 체인)라, 실제 하드웨어 클럭을 정확히 116/117 MHz로
  분주해도 117에서 setup이 -0.071 ns 미달하는 진짜 FAIL이다(거짓 제약 아님).
