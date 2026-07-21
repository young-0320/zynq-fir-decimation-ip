# ASIC(Oasys) Synthesis Frequency Sweep — FIR v1/v2

- 대상: `fir_n43`(v1) / `fir_n43_v2`(v2) — 순수 FIR core, 단일 파일 (`rtl/transposed_form/n43/`)
- 합성 도구: Oasys-RTL, 공정: Tanner Generic 250nm (`TANNER_TT_2P50V_25C.lib`, TT/2.5V/25°C)
- 방법론: `asic/oasys/clk.sdc` 하나를 v1/v2가 공유 — **같은 period로 페어 실행**한 결과만 비교표에 올린다
- 목적: workflow_v23 Track A(§8-1) ASIC 보조 지표 + "v1의 critical path 병목(FPGA CARRY4
  캐리 체인)은 FPGA 전용"이라는 가설 실증
- 작성일: 2026-07-21 (sweep 진행에 따라 갱신)

## 1. Sweep 결과 — v1 (`fir_n43`)

margin(%) = WNS / period × 100.

| period(ps) | freq(MHz) | WNS(ps) | margin(%) | cells | area(sq um) | total_power(mW) | result |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 20000 | 50.0 | +1757.5 | 8.8 | 16918 | 1115360 | 689.0 | pass |
| 15000 | 66.7 | | | | | | |
| 12000 | 83.3 | | | | | | |
| 10000 | 100.0 | | | | | | |
| 8000 | 125.0 | | | | | | |

## 2. Sweep 결과 — v2 (`fir_n43_v2`)

| period(ps) | freq(MHz) | WNS(ps) | margin(%) | cells | area(sq um) | total_power(mW) | result |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 20000 | 50.0 | +2039.1 | 10.2 | 16799 | 1122327 | 682.3 | pass |
| 15000 | 66.7 | | | | | | |
| 12000 | 83.3 | | | | | | |
| 10000 | 100.0 | | | | | | |
| 8000 | 125.0 | | | | | | |

(주1) power는 `report_power -total_only`로 추출 — 한 줄에 internal/switching/leakage/total
분해가 모두 포함된다(PF-263). 기본 `report_power`는 계층 없는 코어 직접 합성이라 인스턴스
4096개에서 잘리며 total이 생략되므로 쓰지 않는다. 이 power는 워크로드 VCD가 아닌 기본
toggle-rate 가정 기반 추정치.

## 3. v1 vs v2 비교 (동일 period 페어)

| period(ps) | v1 WNS | v2 WNS | ΔWNS(v2−v1) | v1 area | v2 area | Δarea | v1 P(mW) | v2 P(mW) | ΔP |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 20000 | +1757.5 | +2039.1 | +281.6 | 1115360 | 1122327 | +0.6% | 689.0 | 682.3 | −1.0% |

### Critical path 구조 (핵심 관찰)

| | startpoint | endpoint | logic depth | 경로 구조 |
| --- | --- | --- | ---: | --- |
| v1 @20000ps | `prod_reg_reg[10][1]/Q` | `z_reg[32][47]/DATA` | 85 | Stage2 가산기 (prod_reg + z → z_reg), AOI22/BUFI4 반복 = ripple-carry 체인 |
| v2 @20000ps | `prod_reg_reg[8][1]/Q` | `z_reg[34][47]/DATA` | 84 | 동일 구조 |

## 4. 해석 (sweep 진행하며 갱신)

20000ps 첫 페어 기준의 잠정 관찰 — **확정은 sweep 완료 후**:

- **두 버전 모두 critical path가 같은 곳이며, v2가 분할한 경로가 아님**: ASIC 병목은
  순수 탭 누산 경로(Stage2, prod_reg[k]+z[k+1]→z_reg[k], 48-bit add 1회)의 ripple-carry
  체인. 반면 v1의 FPGA 병목(log 39)은 누산+라운딩이 한 사이클에 겹친
  `z_reg[1]→round_reg` 경로였고 v2는 그 경로를 분리한 것 — 즉 **FPGA와 ASIC은 병목
  경로 자체가 다르다.**
- **왜 v1 ≈ v2인가** (WNS 차이 281.6ps, period의 1.4%): FPGA는 전용 CARRY4 덕에 48-bit
  add 1회가 싸서(수 ns) add 1회짜리 탭 경로는 널널했고, add+round가 겹친 경로만 한계를
  넘었다 → 분할이 26% Fmax 이득. ASIC(느슨한 20000ps 제약)에서는 합성기가 면적 최소인
  ripple-carry(게이트 깊이 85 ≈ 17.9ns)로 매핑해 **add 1회 자체가 이미 지배적** — 탭
  경로 43개가 전부 같은 급이라 그 중 하나가 critical이 되고, v2의 개선이 걸릴 자리가
  없다. "분할의 이득은 FPGA 물리 구조(CARRY4)에 종속"이라는 가설과 일치하는 방향.
- **전력도 v1 ≈ v2** (689.0 vs 682.3mW, −1.0%): 파이프라인 분할이 전력에도 유의미한
  차이를 만들지 않음. leakage는 5.6µW로 total의 0.001% — 250nm에서 leakage 무시 가능
  예상과 일치, "ASIC total ≈ dynamic"으로 취급해도 됨.
- 단, 느슨한 제약에서는 합성기가 최저 면적(ripple) 매핑을 선택한 결과라는 점에 주의 —
  period를 조이면 두 버전 모두 더 빠른 가산기 구조로 재합성되므로, 결론 확정은
  타이트한 period의 pass/fail 경계로 한다.
- **면적도 v1 ≈ v2** (Δ+0.6%): 여유 constraint에서는 차이 미미. 타이트해질수록 벌어지는지
  관찰 대상.

## 5. FPGA 대비 (sweep 완료 후 작성)

FPGA 코어 단독 수치(`vivado/reports/sweep_summary_v2.md`): v2@145MHz — LUT 1792 /
FF 2113 / DSP 16 / 0.015W. v1 코어 단독 수치는 ASIC 결과 확정 시 같은 방식으로 추출 예정.

(28nm Zynq vs 250nm 표준셀이라 절대치 비교가 아니라 "같은 RTL이 타겟에 따라 어떤
지표로 실현되는지" 보조 지표로 제시.)

## 6. 남은 작업 / 이슈

- [x] ~~power total 재추출~~ — 20000ps 페어 `-total_only`로 재추출 완료. `-total_only`
      한 줄에 internal/switching/leakage 분해까지 포함되므로(PF-263) 이후 sweep도 이
      명령만 쓰면 됨 (`-all` grep 불필요).
- [ ] sweep 계속: 15000 → 12000 → 10000 → 8000ps, 첫 FAIL 후 마지막 PASS와 이분탐색
- [ ] 버전별 최속 passing period + 공통 비교 period 확정 → §4 해석 확정
- [ ] (범위 축소 결정 반영) Nitro P&R은 공통 비교 period 1개에서 v1/v2 각 1런만

## Raw 리포트 경로

```text
asic/oasys/results/v1/v1_<period>ps_{synth.v,timing.rpt,area.rpt,power.rpt}
asic/oasys/results/v2/v2_<period>ps_{synth.v,timing.rpt,area.rpt,power.rpt}
```
