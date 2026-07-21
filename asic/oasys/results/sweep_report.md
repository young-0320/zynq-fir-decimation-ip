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
| 15000 | 66.7 | +946.6 | 6.3 | 25193 | 1333340 | 794.0 | pass |
| 12000 | 83.3 | +1133.5 | 9.4 | 25387 | 1337280 | 843.0 | pass |
| 10000 | 100.0 | +199.0 | 2.0 | 25994 | 1354345 | 944.4 | pass |
| 8000 | 125.0 | | | | | | |

## 2. Sweep 결과 — v2 (`fir_n43_v2`)

| period(ps) | freq(MHz) | WNS(ps) | margin(%) | cells | area(sq um) | total_power(mW) | result |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 20000 | 50.0 | +2039.1 | 10.2 | 16799 | 1122327 | 682.3 | pass |
| 15000 | 66.7 | +4680.8 | 31.2 | 25118 | 1344378 | 781.1 | pass |
| 12000 | 83.3 | +1680.8 | 14.0 | 25118 | 1344378 | 847.5 | pass |
| 10000 | 100.0 | +129.2 | 1.3 | 25689 | 1360577 | 954.4 | pass |
| 8000 | 125.0 | | | | | | |

(주1) power는 `report_power -total_only`로 추출 — 한 줄에 internal/switching/leakage/total
분해가 모두 포함된다(PF-263). 기본 `report_power`는 계층 없는 코어 직접 합성이라 인스턴스
4096개에서 잘리며 total이 생략되므로 쓰지 않는다. 이 power는 워크로드 VCD가 아닌 기본
toggle-rate 가정 기반 추정치.

## 3. v1 vs v2 비교 (동일 period 페어)

| period(ps) | v1 WNS | v2 WNS | ΔWNS(v2−v1) | v1 area | v2 area | Δarea | v1 P(mW) | v2 P(mW) | ΔP |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 20000 | +1757.5 | +2039.1 | +281.6 | 1115360 | 1122327 | +0.6% | 689.0 | 682.3 | −1.0% |
| 15000 | +946.6 | +4680.8 | +3734.2 | 1333340 | 1344378 | +0.8% | 794.0 | 781.1 | −1.6% |
| 12000 | +1133.5 | +1680.8 | +547.3 | 1337280 | 1344378 | +0.5% | 843.0 | 847.5 | +0.5% |
| 10000 | +199.0 | +129.2 | −69.8 | 1354345 | 1360577 | +0.5% | 944.4 | 954.4 | +1.1% |

### Critical path 구조 (핵심 관찰)

| | startpoint | endpoint | logic depth | 경로 구조 |
| --- | --- | --- | ---: | --- |
| v1 @20000ps | `prod_reg_reg[10][1]/Q` | `z_reg[32][47]/DATA` | 85 | Stage2 가산기 (prod_reg + z → z_reg), AOI22/BUFI4 반복 = ripple-carry 체인 |
| v2 @20000ps | `prod_reg_reg[8][1]/Q` | `z_reg[34][47]/DATA` | 84 | 동일 구조 |
| v1 @15000ps | `prod_reg_reg[10][1]/Q` | `round_reg_reg[32]/DATA` | 50 | **누산+라운딩 병합 경로 — v2가 분할한 바로 그 경로** (탭 가산기는 재구조화로 빨라져 depth 85→50, 대신 이 병합 경로가 병목으로 부상) |
| v2 @15000ps | `in_sample[3]` (input port) | `prod_reg_reg[23][26]/DATA` | 48 | 입력→곱셈 경로 (미제약 입력, rtDefaultClock). worst가 이 경로라는 것 = **내부 reg-to-reg 전부 slack ≥ +4680.8** |
| v1 @12000ps | `prod_reg_reg[10][1]/Q` | `round_reg_reg[31]/DATA` | 40 | 여전히 누산+라운딩 병합 경로. 합성기가 더 조여서 depth 50→40, slack은 15000ps 때보다 오히려 개선(+946.6→+1133.5) |
| v2 @12000ps | `in_sample[3]` | `prod_reg_reg[23][26]/DATA` | 48 | 15000ps와 **동일 netlist** (cells/area/arrival 10038.9ps 완전 동일 — 여유가 있어 재합성 불필요). 한계는 입력→곱셈 경로 ~10039ps |
| v1 @10000ps | `prod_reg_reg[0][6]/Q` | `round_reg_reg[30]/DATA` | 40 | 병합 경로가 arrival 9520.7ps까지 압축 — 12000ps 때 "하한"으로 보였던 곱셈 경로(10039ps)보다도 빨라짐 (곱셈 경로도 재구조화됨) |
| v2 @10000ps | `z_reg[0][47]/Q` | `round_reg_reg[32]/DATA` | 33 | **v2 자신의 라운딩 스테이지**(Stage3, z[0]→round_reg)가 병목으로 등장, arrival 9590.5ps — v1의 병합 경로와 사실상 같은 수준 |

## 4. 해석 (sweep 진행하며 갱신)

**20000ps (느슨한 제약) — 잠정 "v1 ≈ v2"로 보였던 구간:**

- 두 버전 모두 critical path가 순수 탭 누산 경로(prod_reg[k]+z[k+1]→z_reg[k])의
  ripple-carry 체인(depth 85). 느슨한 제약에서 합성기가 면적 최소인 ripple 매핑을
  선택해 add 1회 자체가 지배적이었고, v2가 분할한 누산+라운딩 병합 경로는 한계를
  정하는 경로가 아니었다 → WNS 차이 1.4%p로 "분할은 FPGA 전용" 가설과 일치해 보임.

**15000ps (타이트한 제약) — 반전, 분할이 ASIC에서도 유효:**

- 제약을 조이자 합성기가 탭 가산기를 더 빠른 구조로 재합성(depth 85→50, 그 대가로
  cells +49%/area +19%). 그러자 **v1의 병목이 누산+라운딩 병합 경로
  (prod_reg→round_reg)로 이동 — FPGA에서와 같은, v2가 분할한 바로 그 경로다.**
- v2는 그 경로가 없어 WNS +4680.8 vs v1 +946.6 — **slack 5배 차이.** v2의 worst 경로는
  미제약 입력 경로(in_sample→prod_reg)라서 내부 reg-to-reg 한계는 이보다도 위에 있다.
- 잠정 Fmax 추정(1/(period−WNS)): v1 ≈ 71MHz, v2 ≥ 97MHz — **파이프라인 분할이
  ASIC에서도 유효하다는 방향.** "분할은 FPGA 전용 최적화" 가설은 느슨한 제약에서만
  성립하는 착시였고, 도구가 가산기를 최적화하고 나면 타겟 불문 "add+round 병합"이
  구조적 병목이라는 쪽으로 수렴 중. 확정은 pass/fail 경계(이분탐색)로.
- **전력·면적은 여전히 v1 ≈ v2** (ΔP −1.6%, Δarea +0.8%): 분할의 비용이 사실상 0이라는
  점도 v2의 손을 들어줌. leakage는 total의 0.001% — 250nm 예상대로 무시 가능,
  "ASIC total ≈ dynamic" 취급 유효.

**12000ps — 격차는 좁혀지나 순서는 유지, 공통 하한(곱셈 경로) 등장:**

- v1: 합성기가 라운딩 병합 경로를 더 조여(depth 50→40, cells +194) slack이 15000ps보다
  오히려 개선(+1133.5). v2: 15000ps netlist 그대로 재사용(여유 충분) — 한계는 입력→곱셈
  경로 arrival ~10039ps로 고정.
- 잠정 Fmax 추정: v1 ≈ 92MHz, v2 ≈ 97MHz — 15000ps에서 5배였던 slack 격차가 좁혀짐.
  ~~곱셈 경로 ~10ns가 공통 하한~~ → 10000ps에서 곱셈 경로도 재구조화되어 하한이
  아니었음이 확인됨(아래).

**10000ps — 수렴: 둘 다 PASS(100MHz), v1이 근소 우위로 역전:**

- v1 +199.0 vs v2 +129.2 (ΔWNS −69.8ps, period의 0.7%) — 12000ps까지의 v2 우위가
  사라지고 사실상 동률(오히려 v1이 근소 우위).
- 메커니즘: 합성기를 한계까지 밀자 **v1의 누산+라운딩 병합 경로가 9520.7ps까지 압축**됨
  (multi-operand add를 carry-save/compound 구조로 재조직 — 표준셀에서는 add 2회
  병합이 add 1회 + 압축단 수준의 비용). 한편 **v2는 자신의 라운딩 스테이지(z[0]→
  round_reg, 48-bit 라운딩 가산)가 새 병목**으로 등장, 9590.5ps — 결국 양쪽 다
  "라운딩이 포함된 최종 가산" 하나가 한계를 정하는 동일 구도로 수렴.
- **이것이 FPGA와의 구조적 차이**: FPGA CARRY4는 고정 캐리 체인이라 add 2회 병합을
  재구조화할 수 없어 v1의 병합 경로가 통째로 두 체인 값을 냈고(그래서 분할이 26%
  이득), ASIC 표준셀 합성은 그 병합을 흡수해버린다 — **"분할의 이득은 FPGA 물리
  구조에 종속" 가설이 pass/fail 경계 근처에서 결국 성립하는 방향.**
- 잠정 Fmax 추정: v1 ≈ 102MHz, v2 ≈ 101MHz. 다음: 8000ps는 arrival ~9.5ns 대비 required
  7719.7ps라 둘 다 확실한 FAIL — 건너뛰고 **9000ps 페어로 이분탐색 시작** 권장
  (fail 시 9500ps, pass 시 8500ps).

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
