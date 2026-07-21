# 47. ASIC Track A 실행 — Oasys v1/v2 합성 sweep 완결, Nitro P&R 중단

- 작성일: 2026-07-21
- 선행 문서:
  - `../workflow/workflow_v23.md` Track A (§8-1 지시, A1/A2 확정)
  - `39_critical_path_v2_pipeline_split.md` (FPGA v1 크리티컬 패스·v2 분할 설계)
  - `vivado/reports/sweep_summary.md` / `_v2.md` (FPGA Fmax 116/146, v2 코어 단독 수치)
- 결과 문서:
  - `asic/oasys/results/sweep_report.md` (sweep 전 지점 표·critical path·해석)
  - `docs/report/fir_n43/summary/asic_vs_fpga.md` (FPGA 대비 비교, §8-4.5 통합용)

---

## 1. 의사결정 이력 (착수 전)

### 1.1 A1 재확정: v2 단독 → v1+v2 페어

구 확정(workflow_v23 초판)은 "v2 단독" — 근거는 "v1→v2 파이프라인 분할은 FPGA 전용
병목(CARRY4 캐리 체인) 제거라 ASIC에서 같은 critical path를 보장 못 함"이었다.
재검토에서 이 근거를 뒤집어 읽었다: **그 명제 자체가 실증 가능한 가설**이므로, v1/v2를
동일 제약으로 돌리면 "분할이 타겟 특화 최적화인가"가 데이터로 판정된다. 증분 비용은
top module 교체 재실행뿐. → **v1+v2 페어, 동일 clk.sdc 공유(제약 동일성 강제)로 확정.**

### 1.2 A2 해소: 환경 = GEMM 수업 플로우 그대로

`simple-cpu-gemm-accelerator/asic`(2026-1 디지털시스템설계실습)를 참조 프로젝트로 채택.
Tanner Generic 250nm PDK(`TANNER_TT_2P50V_25C.lib`, TT/2.5V/25°C), Oasys-RTL 합성 +
Nitro P&R(TannerTools v2021.2 공정 파일, Nitro 빌드 2020.2). 두 코어 모두 순수
behavioral Verilog(Xilinx primitive 없음)로 포팅 장벽 없음을 사전 확인.

### 1.3 준비물 구성 (asic/)

- `asic/oasys/v1_config.tcl`/`v2_config.tcl` — GEMM step2 config 기반, top만 교체.
  소스가 각 1파일이라 GEMM의 `.f` filelist 방식은 제거하고 경로 직접 기재
  (filelist는 소스 7개·조합 8개였던 GEMM 규모에서만 의미 — 오버엔지니어링 지적 반영).
- `asic/oasys/clk.sdc` — v1/v2 공용 1파일. sweep 시 이 파일만 수정 → 두 런의 제약
  동일성이 구조적으로 보장됨.
- sweep 범위 20000→8000ps: 이 PDK의 유일한 참조점인 GEMM 결과(유사 16-bit MAC
  datapath, 13000~15000ps PASS, 최종 8500ps)를 양쪽으로 감싸는 구간. FPGA
  Fmax(28nm)는 250nm 예측에 사용 불가.

### 1.4 export 자동화의 변천

1. 수동 4명령(write_verilog + report_timing/area/power) + 셸 mv
2. `export.tcl` (변수 지정 + source) — 파일명 조립·폴더 생성 자동화
3. **proc화**: `ex v1 12000ps` 한 줄 (session당 source 1회)
4. **config 자동 source**: config.tcl 말미에 export.tcl source 추가 — config 로드만
   하면 `ex` 사용 가능. (Nitro tcl처럼 "스크립트 말미에 report 명령"은 불가 — Oasys
   config는 flow 스크립트가 아니라 로드 시점에 읽히는 선언 파일이라 합성 전에 실행됨.)

---

## 2. Oasys sweep 결과 요약 (상세 표는 sweep_report.md)

| period(ps) | freq | v1 WNS | v2 WNS | 판정 |
| ---: | ---: | ---: | ---: | --- |
| 20000 | 50.0 | +1757.5 | +2039.1 | 둘 다 pass, v1≈v2 |
| 15000 | 66.7 | +946.6 | +4680.8 | 둘 다 pass, **v2 5배 우위(반전)** |
| 12000 | 83.3 | +1133.5 | +1680.8 | 둘 다 pass, 격차 축소 |
| 10000 | 100.0 | +199.0 | +129.2 | 둘 다 pass, **v1 재역전(수렴)** |
| 9000 | 111.1 | +100.2 | +526.3 | 둘 다 pass, v2 재역전(요동) |
| 8000 | 125.0 | +52.0 | +72.3 | 둘 다 pass, Δ20ps 완전 수렴 |
| 6000 | 166.7 | +0.3 | +13.5 | 둘 다 pass(v1 턱걸이), **sweep 중단** |

### 2.1 해석의 변천 (중간 결론이 두 번 뒤집힘 — 기록 가치)

1. **20000ps**: 둘 다 critical = 탭 누산 ripple 체인(depth 85) → "v1≈v2, 가설(FPGA
   전용) 맞는 듯". 실제로는 느슨한 제약에서 합성기가 최소 면적 매핑을 고른 결과였음.
2. **15000ps**: 합성기가 탭 가산기를 재구조화하자 v1 병목이 누산+라운딩 병합 경로로
   이동(= v2가 분할한 그 경로) → v2 slack 5배. "가설이 틀렸고 분할이 ASIC에서도
   유효한가?"로 기울었음.
3. **10000ps~**: 한계까지 밀자 **v1의 병합 경로가 carry-save/compound 재구조화로
   흡수됨**(add 2회 병합 ≈ add 1회 + 압축단 비용). v2는 자신의 라운딩 스테이지가
   병목으로 등장. 양쪽 다 "라운딩 포함 최종 가산 1개"가 한계인 동일 구도로 수렴,
   이후 순위는 런별 휴리스틱 편차로 요동(Δ ≤ period의 6%).
4. **최종**: FPGA CARRY4는 고정 캐리 체인이라 add 2회 병합을 재구조화할 수 없어
   v1이 두 체인 값을 통째로 치렀고(26% 격차), 표준셀 합성은 그것을 흡수한다 —
   **"분할의 이득은 FPGA 물리 구조에 종속" 가설이 경계 근처에서 성립.** 중간 구간의
   v2 우위는 "합성기가 덜 조여진 상태"의 잔상. 6000ps에서 v1 critical이 FPGA와
   시작·끝이 동일한 경로(z_reg[1]→round_reg)로 회귀: 같은 경로를 CARRY4 8.664ns vs
   표준셀 5.719ns — 가장 직접적인 대비 증거.

### 2.2 sweep 중단 논리 (fail 앵커 미확보 상태로 종료)

margin이 매 지점 0으로 수렴하는 것은 한계 신호가 아니라 **제약 구동 합성의 본성**
(툴은 달성 가능한 목표면 면적을 태워 "겨우 맞추기"로 수렴 — cells 25994→28615).
8000ps·6000ps에서 "확실히 FAIL" 예측이 연속으로 반증되며 확인됨. 절대 Fmax는 목적
(보조 지표 + v1/v2 비교)에 불필요하고 탐색 비용은 상한이 없어, **"양쪽 ≥166.7MHz
(한계 미탐색), 전 구간 격차 노이즈 수준"을 최종 기록으로 채택**하고 종료.
부수 확인: 250nm ASIC이 28nm FPGA v2의 146MHz를 초과.

### 2.3 면적·전력

전 구간 v1≈v2 (Δ 1% 안팎). 주파수에 따라 면적 1.12→1.42mm²(+27%), 전력
689→1331mW — timing-area trade-off 전형 패턴(GEMM sweep과 동일). leakage는 total의
0.001%(250nm 예상대로) → "ASIC total ≈ dynamic" 취급 유효. 전력은 워크로드 VCD가
아닌 기본 toggle-rate 가정 추정치임을 명시.

---

## 3. 실행 중 사고·이슈 기록

1. **clk.sdc 콤마 사고 (15000ps 1차 무효)**: period 수정 중 전 줄 끝에 `,` 혼입 →
   `create_clock`이 `clk,` 포트를 찾다 실패 → **제약 0개로 합성**(`TA-118: no timing
   constraints`), timing/power rpt 무효. 콤마 제거 후 재합성으로 복구. 재발 방지:
   합성 전 `report_clocks` 확인 + timing rpt 머리의 `Clock shift` 확인 습관.
2. **report_power 4096 잘림**: 코어를 래퍼 없이 직접 top으로 합성 → top 아래가 leaf
   셀 수만 개 → 기본 `report_power`가 4096개에서 잘리며 TOTAL 행 생략(POWER-155).
   `help report_power`로 **`-total_only`** 발견 — 한 줄에 internal/switching/leakage/
   total 전부 출력(PF-263). 이후 표준 명령으로 채택.
3. **synth.v 리포 정리**: 전 지점 netlist(12개, 23MB)가 git에 들어갔던 것을 P&R
   입력(10000/12000ps 페어)만 남기고 정리, `.gitignore`로 이후 자동 배제. (이력에는
   잔존 — history rewrite는 규모상 불필요 판단.)
4. **양방향 git 운용 충돌**: 서버/로컬에서 같은 수정을 각자 커밋(REPO_ROOT), 서버
   `git add -A`가 로컬 신규 파일(step tcl들)을 삭제로 staging하는 사고 등 divergence
   4회. `pull.rebase true` 설정 + "한쪽에서 커밋·push, 반대쪽은 pull" 규칙으로 정리.
   emacs 잠금 파일(`#...#`)도 gitignore 처리.

---

## 4. Nitro P&R — 시도와 중단

### 4.1 대상 선정

10000ps netlist (후보 8000/9000/10000 중 **페어 최소 margin 최대**: 1.3% vs 1.1% vs
0.9% — P&R 성패는 나쁜 쪽이 결정). fallback = 12000ps(9.4%/14.0%). 어차피 모두 GEMM
권장 P&R margin(20~30%) 미달이라 post-route fail 리스크는 인지하고 착수.

### 4.2 실행 인프라

- GEMM `mode1_15000ps_nitro.tcl`과 명령·순서 동일함을 diff로 검증 (차이 3곳: 변수명,
  chip 면적, core_cell_util 80→70 — 전부 의도된 것).
- 콘솔 복붙이 화면 wrap 개행 때문에 `missing "` 에러 유발 → **pause 지점 단위로
  `nitro_step0~7.tcl` 분할**, 단계마다 `source $S/nitro_stepN.tcl` 한 줄로 실행
  (각 step 종료 시 다음 명령을 puts로 안내).

### 4.3 사고 연대기

1. **chip 면적 오판**: 최초 3000000a(300µm, 0.09mm²)로 설정 — "FIR이 GEMM step2보다
   작다"는 FPGA 자원 감각의 오판. 실제 셀 면적은 **1.35mm²로 GEMM step2(0.31mm²)의
   4배**(병렬 곱셈기 43개). 필요 변 = √(cell_area/util) 역산으로 1.4mm(14000000a,
   util 70%) 수정. 단위 a=0.1nm.
2. **datapath 블럭 배치 문제**: Oasys datapath 추출이 만든 블럭 36개가 고정 객체로
   칩 밖에 생성됨. `place_macros` 자동 배치 시도 → **PLC1020 "movable macro 없음"**
   으로 거부. 미배치 상태로 진행 시 routing 실패. → GEMM 수업 방식대로 **GUI 수동
   드래그 필요** 확인 (pause가 create_rows 앞에 있는 이유).
3. **placer 내부 크래시**: 수동 배치 후 `run_place_timing -effort high`에서
   **`SDA101: internal error 'grCapFrac <= 1'`**(densityboxcontrol.cpp, 2020.2 빌드)
   — placer density 엔진의 assertion 위반. chip 1.4→1.6mm(util 53%) 확대 + 재배치
   후에도 동일 지점 재현.

### 4.4 중단 결정

동일 internal error 2회 재현 + 사용자 측 회피 수단 소진(면적·밀도·배치 변경 무효)으로
**툴 내부 버그로 결론, P&R 중단**. 비교 결론(v1≈v2)은 합성 결과로 이미 완결이므로
P&R의 기대 기여는 "post-route에서도 유지" 방어 한 줄뿐이었고, 비용(시도당 수 시간 +
수동 배치)이 이를 초과. 스크립트·절차는 `asic/nitro/tcl/`에 재개 가능 상태로 보존.
보고 문구: "합성 기준 보조 지표 완비, P&R은 서버 툴 내부 버그(SDA101)로 중단·문서화".

---

## 5. 산출물 위치

```text
asic/oasys/results/sweep_report.md       sweep 표·critical path·해석·중단 논리
asic/oasys/results/v{1,2}/               timing/area/power rpt (전 지점),
                                         synth.v (10000/12000ps만)
docs/report/fir_n43/summary/asic_vs_fpga.md  FPGA 대비 표 (§8-4.5 통합용)
asic/oasys/                              config·clk.sdc·export.tcl (재현용)
asic/nitro/tcl/                          step0~7 분할 tcl (P&R 재개용, 중단 상태)
```

남은 Track A 후속: 없음 (완료). §8-4.5 문서 통합은 Track B 실측 데이터 도착 후 D2에서.
