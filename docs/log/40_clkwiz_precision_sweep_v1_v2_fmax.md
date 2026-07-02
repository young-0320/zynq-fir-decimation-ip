# 40. clk_wiz 정밀 주파수 스윕 — v2 실행 및 v1 Fmax 재측정

- 작성일: 2026-07-02
- 선행 문서:
  - `39_critical_path_v2_pipeline_split.md` (v2 설계/계획 — 실행 전)
  - `../workflow/workflow_v21.md`
  - `vivado/reports/sweep_summary.md` (v1, 재작성됨)
  - `vivado/reports/sweep_summary_v2.md` (v2, 신규)

---

## 배경

log 39는 v2 파이프라인 분할의 **설계/계획**까지였다(Stage A/B 절차, "다음 작업" 목록).
이 로그는 그 계획을 **실제 실행**하고, 실행 중 발견한 주파수 스윕 방법론 문제(요청≠실제)를
clk_wiz로 바로잡아 v1/v2의 Fmax를 정밀 확정한 기록이다.

---

## 1. Stage A/B 실행 (기능 검증, iverilog)

- **Stage A**: `fir_n43_v2` 코어 회귀 — S1(Happy Path)/S2(Random Bubble) PASS,
  v1과 출력 수치 100% 동일(golden 8234 samples 일치).
- **Stage B 파일 생성**: `fir_decimator_n43_v2.v`, `fir_decimator_n43_axis_v2.v`,
  `bd_fir_dma_v2.tcl`, `build_bd_fir_dma_v2.tcl` (기존 로직 재사용, 이름만 v2).
- **통합 iverilog**: `tb_fir_decimator_n43_v2`, `tb_fir_decimator_n43_axis_v2` S1/S2/S3 PASS.
  특히 AXIS 백프레셔(S2)가 통과 → latency 3→4 cycle 증가가 skid buffer와 충돌하지 않음을
  Vivado 진입 전에 확인.

---

## 2. 주파수 스윕 방법론 문제 발견 — 요청 ≠ 실제

Zynq PS7 하드 PLL은 1000 MHz를 **정수 분주만** 가능:
achievable = 90.909(÷11) / 100(÷10) / 111.111(÷9) / 125(÷8) / 142.857(÷7) …

- 요청 120·130 → 모두 실제 **125**로 스냅. v1의 "110"·"115"도 둘 다 실제 **111.111**.
- 즉 v1의 기존 `sweep_summary.md` "확정 Fmax 115"는 **오라벨** — 115도 120도 실제로 돌린 적 없다.
- XDC `create_clock`만 바꾸면 거짓 제약이지만, 우리가 바꾼 건 PS BD 설정 → 하드 PLL 분주기
  재프로그램 → **실제 주파수가 바뀜**(타이밍 분석 자체는 유효, 라벨만 틀렸음). 100 MHz는
  PS ÷10로 정확히 나오므로 clk_wiz 불필요.

---

## 3. 해결 — clk_wiz(MMCM) 정확 분주 (target = actual)

- `vivado/fir_n43/bd_clkwiz_overlay.tcl`: PS `FCLK_CLK0`(100 MHz)를 MMCM 입력으로,
  `clk_out1`을 목표 주파수로 합성해 PL 전체(DMA/HP·GP 포트/smartconnect/FIR)를 재구동.
  MMCM `locked` → proc_sys_reset `dcm_locked`. FCLK net 12개 소비 핀 전부 재배선.
- 빌드: `build_bd_fir_dma_clkwiz.tcl`(v1) / `build_bd_fir_dma_v2_clkwiz.tcl`(v2), `-tclargs <MHz>`.
- MMCM은 fractional 분주라 요청 = 실제(오차 0). 대가로 LUT +~5, 전력 +~0.12 W.

---

## 4. v1 재스윕 (clk_wiz) → Fmax 116 MHz

| actual MHz | WNS | 판정 |
|-----------|------|------|
| 110.000 | +0.381 | PASS |
| 115.000 | +0.231 | PASS |
| **116.000** | **+0.016** | **PASS ← Fmax** |
| 117.000 | -0.071 | FAIL |
| 118.000 | -0.044 | FAIL |
| 119.000 | -0.205 | FAIL |
| 120.000 | -0.098 | FAIL |

- 확정 Fmax = **116 MHz**(116 PASS / 117 FAIL). 이전 "115"는 오라벨이었고 실제 111.111이었음.
- 크리티컬 패스: v1 round 데이터패스(`prod_reg → round_reg_reg[45]`, CARRY4 carry-ripple 체인).
  120 FAIL이 정확히 120.000 MHz 클럭에서 setup -0.098ns 위반임을 리포트로 직접 검증(거짓 제약 아님).

---

## 5. v2 스윕 (clk_wiz) → Fmax 146 MHz

| actual MHz | WNS | 판정 | 비고 |
|-----------|------|------|------|
| 120.000 | +0.655 | PASS | |
| 130.000 | +0.563 | PASS | **골든 배포 빌드**(bit/xsa) |
| 140.000 | +0.069 | PASS | |
| 145.000 | +0.129 | PASS | |
| **146.000** | **+0.022** | **PASS ← Fmax** | |
| 147.000 | -0.102 | FAIL | |
| 148.000 | -0.021 | FAIL | |
| 150.000 | -0.012 | FAIL | |

- 확정 Fmax = **146 MHz**(146 PASS / 147 FAIL). v1(116) 대비 **+30 MHz**.
- 125 MHz는 PS ÷8 native 기준점(clk_wiz 불필요, +0.261 PASS, 1.572 W).

---

## 6. 핵심 결론 — v2 FIR은 더 최적화할 부분이 없다

**v2 Fmax를 정하는 크리티컬 패스는 우리 FIR IP가 아니라 Xilinx AXI DMA IP다.**

147 MHz FAIL 경계의 worst 경로:
```
axi_dma_0/.../I_S2MM_REALIGNER/.../sig_max_first_increment → sig_btt_eq_0
```
= AXI DMA S2MM realigner의 byte-count 로직(Xilinx IP 내부). 경계 부근에서는 이 DMA 경로와
AXIS 래퍼 경로가 비슷하게 임계지만, **어느 쪽도 FIR 코어의 곱셈/누산/round 데이터패스가 아니다.**

- v1의 round CARRY4 병목(116 MHz 한계)은 v2 4-stage 분할로 **완전히 제거**됨.
- 그 결과 상한이 FIR(우리 IP)에서 **DMA IP + 보드 인프라**로 넘어갔다.
- 따라서 **FIR 코어 추가 최적화(round 재분할, DSP48 캐스케이드 등)로는 Fmax를 더 못 올린다.**
  더 높이려면 DMA IP 설정/교체나 보드 레벨 문제이지, **이제부터는 내 IP의 문제가 아니다.**

---

## 7. 정리

- 요약 2개를 clk_wiz 정밀 데이터만으로 재작성: `sweep_summary.md`(v1 Fmax 116),
  `sweep_summary_v2.md`(v2 Fmax 146). 옛 PS-PLL coarse/오라벨 내용 제거.
- 임시 스윕 빌드 dir(`*_sweep`)·v2 125 base 빌드·옛 PS-PLL 리포트 삭제(~350M). 골든 130 보존.

## workflow_v21 대비 커버리지

| 항목 | 상태 |
|------|------|
| Stage A (코어 iverilog) | ✅ |
| Stage B 파일 + 통합 iverilog | ✅ |
| Vivado 재스윕 / 목표 130+ | ✅ (초과 달성, Fmax 146 확정) |
| `sweep_summary_v2.md` + 크리티컬 패스 | ✅ |
| **보드 실측 golden 재검증(Step 5)** | ⛔ 미완 — 130 MHz BOOT.bin으로 scenario 1-2 SNR/max_error 확인 필요 |
| **git commit** | ⛔ 미완 |

즉 workflow_v21의 **RTL 설계·타이밍 스윕 부분은 전부(목표 초과) 달성**했고, 남은 것은
**보드 실측 재검증과 커밋** 두 가지다.
