# FIR N43 — ASIC vs FPGA 보조 지표 비교 (Track A, §8-1)

- 대상 RTL: `fir_n43`(v1) / `fir_n43_v2`(v2) 순수 코어 (래퍼/DMA 제외, 두 타겟 동일 소스)
- FPGA: Zynq-7020 (28nm), Vivado — `vivado/reports/sweep_summary.md`/`_v2.md`
- ASIC: Tanner Generic 250nm (TT/2.5V/25°C), Oasys-RTL 합성 —
  `asic/oasys/results/sweep_report.md` (6페어 sweep, 20000→6000ps)
- 성격: 논리합성(P&R 전) 결과 기준의 보조 지표. 절대치 비교가 아니라 "같은 RTL이
  타겟에 따라 어떻게 실현되는가"를 보이는 목적.

## 1. 핵심 결과 — v1↔v2 격차는 타겟 종속

| | FPGA (28nm, CARRY4) | ASIC (250nm 표준셀 합성) |
| --- | ---: | ---: |
| v1 Fmax | 116 MHz | ≥ 166.7 MHz (한계 미탐색) |
| v2 Fmax | 146 MHz | ≥ 166.7 MHz (한계 미탐색) |
| v1↔v2 격차 | +26% | 노이즈 수준 (전 구간 slack 차 ≤ period의 6%, 순위 요동) |

같은 v1 critical path(`z_reg[1] → round_reg`, 누산+라운딩 병합)의 타겟별 처리:

| 타겟 | 이 경로의 지연 | 결과 |
| --- | ---: | --- |
| FPGA CARRY4 (고정 캐리 체인) | 8.664 ns | 120MHz fail → v2 분할로 해결 (log 39) |
| ASIC 표준셀 (carry-save 재구조화) | 5.719 ns | 166.7MHz에서도 pass — 분할 불필요 |

해석: v2 파이프라인 분할의 26% 이득은 FPGA CARRY4가 add 2회 병합을 재구조화할 수
없는 데서 온 타겟 특화 효과다. 표준셀 합성은 multi-operand 가산을 carry-save로
병합·흡수하므로 v1도 같은 한계까지 조여진다 (상세 메커니즘·sweep 전 과정은
`asic/oasys/results/sweep_report.md` §4). 이는 datapath 최적화를 갖춘 현대 합성 툴
공통의 능력으로, 상위 툴(DC/Genus)일수록 이 결론은 강화된다.

## 2. 자원/전력 (참고 — 지표의 성격이 달라 절대 비교 불가)

| 항목 | FPGA v2 코어 @145MHz | ASIC v1 @166.7MHz | ASIC v2 @166.7MHz |
| --- | ---: | ---: | ---: |
| 로직 | LUT 1792 / FF 2113 / DSP 16 | 28615 cells | 27506 cells |
| 면적 | XC7Z020 점유율 LUT 3.4% / FF 2.0% / DSP 7.3% (주1) | 1.42 mm² | 1.41 mm² |
| 전력 | 0.015 W (코어 스코프) | 1.331 W | 1.342 W |

(주1) FPGA는 기성 칩의 자원을 점유하는 방식이라 mm² 절대 면적이 정의되지 않음 —
면적의 등가물로 디바이스 자원 점유율(LUT 1792/53200, FF 2113/106400, DSP 16/220)을
기재. ASIC mm²와 직접 비교 불가.

비교 한계:

- 전력 산정 방식이 다름: FPGA 0.015W는 Vivado routed 디자인의 코어 계층 스코프
  (vectorless) 추정, ASIC은 Oasys 기본 toggle-rate 가정·2.5V·250nm 합성 추정 —
  절대치 비교는 무의미. v1↔v2 상대 비교(ASIC 내 Δ≈1%)만 유효.
- DSP48 하드블록(FPGA) vs 표준셀 곱셈기(ASIC)라 "로직 규모"의 단위도 대응되지 않음.
- ASIC은 합성 단계 값 — P&R 후 배선 지연/면적이 추가된다. (Nitro P&R은 v1 1런을
  시도했으나 placer 내부 버그(SDA101 assertion, 2020.2)로 중단 — 시도·원인 기록은
  `asic/oasys/results/sweep_report.md` §6. 비교 결론은 합성 결과로 완결.)
- ASIC 면적/전력은 주파수에 따라 증가 (50MHz: 1.12mm²/0.69W → 166.7MHz:
  1.42mm²/1.33W) — 지점별 수치는 sweep_report §1/§2.

## 3. 결론

> v1→v2 개선은 FPGA 병목(CARRY4 캐리 체인)을 정확히 겨냥한 타겟 특화 최적화다.
> 같은 RTL을 ASIC에 합성하면 도구가 그 병목을 스스로 흡수해 v1/v2가 동률이 되며
> (둘 다 ≥166.7MHz, 250nm임에도 28nm FPGA의 146MHz 초과), 이는 최적화가
> 아키텍처가 아니라 타겟 물리 구조에 속함을 실측으로 보여준다.

## 원본 데이터

- ASIC sweep 전체: `asic/oasys/results/sweep_report.md` (raw rpt는 같은 폴더 v1/, v2/)
- FPGA: `vivado/reports/sweep_summary.md`(v1) / `sweep_summary_v2.md`(v2, 코어 단독
  utilization/전력 절 포함), critical path 분석 `docs/log/39`
- v1 FPGA 코어 단독 utilization/전력은 미추출 (필요시 v2와 같은 방식으로 routed DCP
  계층 스코프 추출 — 현재 표의 비교 논지에는 불필요)
