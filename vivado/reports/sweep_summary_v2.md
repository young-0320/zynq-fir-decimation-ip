# FIR N43 (v2) Clock Sweep — clk_wiz 정밀 스윕

- 생성일: 2026-07-02
- 보드: Zybo Z7-20 (xc7z020clg400-1)
- 설계: N=43 taps, M=2, transposed form — **v2 (`fir_n43_v2.v`, 4-stage 파이프라인)**
- v1(`fir_n43.v`, 3-stage) 대비: round를 별도 stage로 분리, latency 3→4 cycle
- 방법: Clocking Wizard(MMCM)로 PL 전체를 목표 주파수로 **정확히 분주** (요청 = 실제, 오차 0).
  빌드: `vivado/fir_n43/build_bd_fir_dma_v2_clkwiz.tcl -tclargs <MHz>`

## 결과 (target = actual)

| actual_mhz | wns_ns | timing_pass | lut  | dsp48 | total_power_w |
| ---------- | ------ | ----------- | ---- | ----- | ------------- |
| 120.000    | +0.655 | true        | 4550 | 16    | 1.697         |
| 130.000    | +0.563 | true        | 4549 | 16    | 1.701         |
| 140.000    | +0.069 | true        | 4542 | 16    | 1.703         |
| 145.000    | +0.129 | true        | 4556 | 16    | 1.705         |
| 146.000    | +0.022 | true        | 4554 | 16    | 1.701         |
| 147.000    | -0.102 | false       | 4553 | 16    | 1.701         |
| 148.000    | -0.021 | false       | 4556 | 16    | 1.707         |
| 150.000    | -0.012 | false       | 4567 | 16    | 1.706         |

## Fmax vs 골든(보드 구동 주파수)

**확정 Fmax: 146 MHz** (WNS ≥ 0인 최대 실제 주파수)

- last PASS: **146.000 MHz** (WNS +0.022) / first FAIL: 147.000 MHz (WNS -0.102)
- 경계 해상도 1 MHz. v1(116 MHz) 대비 **+30 MHz**.

**골든(실보드 배포): 145 MHz** (WNS +0.129, Fmax 대비 마진 +0.107ns 확보)

Fmax(146)는 WNS +0.022ns로 여유가 거의 없다. 게다가 위 표에서 보듯 WNS는 주파수에
선형으로 감소하지 않는다(145 MHz의 WNS +0.129가 오히려 146 MHz의 +0.022보다 크다 —
Vivado가 제약이 빡빡할수록 배치를 다르게 최적화하기 때문, 절대 주파수가 아니라 매 실행의
place&route 결과에 좌우됨). 145 MHz는 146 대비 속도 손실이 0.7 MHz(0.7%)뿐인데 **정적
타이밍 마진은 약 6배**이므로, 실보드 배포 주파수로 145 MHz를 택한다.
bit/xsa: `build/fir_n43_v2_freq_145mhz/output/`
(재현: `vivado/fir_n43/build_bd_fir_dma_v2_clkwiz.tcl -tclargs 145` — 주파수별 디렉터리가
자동 생성되므로 동일 명령 재실행으로 그대로 재현 가능).
구 골든이었던 130.000 MHz 빌드는 `build/fir_n43_v2_freq_130mhz/`에 fallback으로 보존
(재현: 동일 스크립트 `-tclargs 130`). 146.000 MHz는 Fmax 확인용 참고 데이터로만
쓰고 배포용 빌드는 만들지 않는다(재현이 필요하면 `-tclargs 146`).

## 크리티컬 패스 — 상한을 정하는 건 FIR이 아니라 AXI DMA IP

147 MHz FAIL 경계의 worst 경로:
```
Source:      axi_dma_0/.../I_S2MM_REALIGNER/.../sig_max_first_increment_reg[1]
Destination: axi_dma_0/.../I_S2MM_REALIGNER/.../sig_btt_eq_0_reg
```
Xilinx **AXI DMA IP 내부**(S2MM realigner의 byte-count 로직)다. 경계 부근에서는 이 DMA 경로와
AXIS 래퍼 경로가 비슷하게 임계여서 배치에 따라 둘 중 하나가 worst가 되지만, **어느 쪽도 FIR
코어의 곱셈/누산/round 데이터패스가 아니다.**

**의미:** v2의 4-stage 분할이 v1 round CARRY4 병목을 제거하면서, 이제 전체 설계 상한은
FIR이 아니라 DMA IP가 결정한다. FIR 추가 개선(round 재분할 등)은 Fmax를 더 올리지 못한다.

## 비고

- DSP48 16개로 전 주파수 동일. LUT ~4542–4567 (clk_wiz MMCM/BUFG 포함분).
- 125.000 MHz는 PS7 하드 PLL ÷8로 정확히 만들어지는 native 지점(clk_wiz 불필요):
  base 빌드 WNS +0.261 PASS, LUT 4549, 1.572 W (MMCM 없어 전력 낮음).
- v1 상세 스윕/Fmax는 `sweep_summary.md` 참조.

---

## AXIS 래퍼 수정(log 42~44) 반영 재빌드 — 골든 주파수 검증 (2026-07-03)

래퍼 RTL이 2차례 수정됨(skid 4칸+flush 제거+`|tlast` tready = log 42, hold-back = log 43/44,
commit `6a4bf36`). 위 스윕 표는 **수정 전(log 40) 넷리스트** 결과이므로, 수정 후 넷리스트로
골든 주파수를 재빌드해 타이밍 영향을 검증했다.

| actual_mhz | wns_ns | timing_pass | lut  | dsp48 | total_power_w | 비고 |
| ---------- | ------ | ----------- | ---- | ----- | ------------- | ---- |
| 145.000    | +0.129 | true        | 4556 | 16    | 1.705         | 수정 전 골든 행과 **전 수치 동일** |

- worst 경로: `waiting_for_last_out_reg → u_fir_n43_v2/prod_comb(DSP48.A)` — 래퍼 FSM에서
  코어 인터페이스로 들어가는 기존 경로(tready→core_in_valid 계열)로, **수정 전과 슬랙까지
  동일**(+0.129). 위 "크리티컬 패스" 절이 기록했듯 145+ 경계에서는 DMA IP/래퍼 인터페이스
  경로가 원래 비슷하게 임계였다 — hold-back이 새로 만든 경로가 아니다.
- **판정: Fmax 146 MHz 특성은 수정 후 넷리스트에서도 유효. 재스윕 불필요.**
- correctness: v2@145MHz 보드 기능 동작 확인 완료 (SD boot + `mode 1-1` 데모 정상,
  workflow_v22 §4). 전력 실측(Track B)도 이 빌드로 수행 — reset 없는 `mode 1-1` 반복
  실행 정상까지 확인 (log 46 §5). Fmax 정밀 측정(오실로스코프 등)은 범위 제외.

---

## 코어 단독 utilization/전력 — ASIC(Track A) 비교용 (2026-07-03)

위 스윕 표의 LUT/전력은 clk_wiz(MMCM)·AXI DMA·interconnect·PS7 연결을 포함한 **전체
비트스트림** 수치라, `fir_n43_v2.v` 코어 단독인 ASIC 결과와 직접 비교하면 안 된다.
v2@145 골든 routed DCP(`build/fir_n43_v2_freq_145mhz/.../impl_1/bd_fir_dma_wrapper_routed.dcp`)
에서 계층 스코프로 별도 추출한 수치:

| 스코프 | LUT | FF | DSP48 | BRAM | 전력 [W] |
| ------ | --- | -- | ----- | ---- | -------- |
| `u_fir_n43_v2` 코어 단독 (ASIC 대응 스코프) | 1792 | 2113 | 16 | 0 | 0.015 |
| AXIS IP 전체 (`fir_decimator_n43_ax_0`, 래퍼+decimator+코어) | 1948 | 2286 | 16 | 0 | 0.017 |
| (참고) 전체 비트스트림 | 4556 | — | 16 | 0 | 1.705 |

- 인스턴스 경로: `bd_fir_dma_i/fir_decimator_n43_ax_0/inst/u_core/u_fir_n43_v2`.
  CARRY4 452개 포함(v2에서 파이프라인 분할한 가산 트리).
- 전력 계층 분해: Total On-Chip 1.711W 중 **PS7이 1.407W로 지배적**, PL 전체 dynamic은
  ~0.16W, 그중 코어 몫은 0.015W. 즉 ASIC 전력과 비교할 FPGA 값은 1.7W가 아니라
  **코어 0.015W**(vectorless 추정치임을 명시할 것).
  (재실행 report_power의 Total 1.711W는 스윕 표의 1.705W와 기본 설정 차이로 소폭 상이.)
- 리포트 파일: `vivado/reports/v2_145mhz_core_only_utilization.rpt`,
  `v2_145mhz_axis_ip_utilization.rpt`, `v2_145mhz_power_hier.rpt`.

---

## 보조지표 교차 참조 (§8, 2026-07-22 통합)

- **ASIC 합성 대비 (Track A)**: v1/v2 동일 제약 sweep — v2 분할의 +26%는 FPGA CARRY4
  종속(같은 경로 8.664ns vs 표준셀 5.719ns), 표준셀 합성에서는 v1≈v2 동률.
  `docs/report/fir_n43/summary/asic_vs_fpga.md`
- **보드 전력 실측 (Track B)**: 이 빌드(v2@145) 기준 5V 입력 실측 S0 1.72 / S1 2.21 /
  S2 2.18W — 위 추정 1.705W와 정합 범위(USB-UART 0.22W 실측 분리, 레귤레이터 효율
  85~90% 가정). `docs/report/fir_n43/summary/power_board_vs_vivado.md`
