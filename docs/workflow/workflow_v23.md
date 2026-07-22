# FIR Decimation Project Workflow v23

- Date: 2026-07-03
- Previous: `workflow_v22.md` (AXIS 래퍼 skid buffer 버그 수정 — 별도 RTL 트랙, 에이전트 구현 중)
  - **[갱신 2026-07-03]** v22 트랙 완료: 버그 1~4 + 잔존 데드락(hold-back)까지 수정·검증
    (log 42~44), 골든 재빌드·BOOT.bin 준비 완료(log 45). 아래 "v22 완료 대기" 항목들 착수 가능.
- Purpose: log38 §8 교수님 미팅 피드백(2026-07-02, 보조 지표 4건)을 반영하고 v1.0 문서를
  마무리하기 위해 **다음에 해야 할 작업들을 정리**한다.

---

## 배경 / v22와 v23을 분리하는 이유

- **v22 트랙(RTL)**: AXIS skid buffer 버그 1~4 수정. 순수 코드 작업, 시뮬레이션(`make run_bug`)
  만으로 완결·검증 가능 — **물리 보드 불필요**. 에이전트가 통째로 맡을 수 있어서 별도
  스펙 문서로 유지 중(에이전트 핸드오프 전용).
- **v23 트랙(이 문서)**: 교수님 log38 §8 지시 4건(ASIC 플로우, 전력 실측, CPU 스펙 등) +
  v1.0 문서 마무리. **상당수가 물리 보드·오실로스코프·학교 서버가 있어야만 되는 작업**이라
  에이전트가 대신할 수 없다. 두 트랙을 한 문서에 섞으면 "에이전트가 지금 구현 중인 RTL
  스펙"과 "사용자가 직접 손으로 해야 하는 일"이 뒤엉켜 핸드오프도 체크리스트도 불편해져서
  분리했다.
- 교수님 평가(2026-07-02): 방향성은 좋다. 추가 지시 4건(§8-1~8-4)은 **전부 미착수**.

**중요 연결 2가지:**

1. log38 §5.1 "보드 reset 없이 시나리오 연속 실행 시 MM2S timeout" 한계 = **v22에서 고치는
   AXIS 버그(2·3)와 동일 원인**. v22 완료 시 이 한계가 해소되므로, 그때 log38/README의
   "시나리오마다 reset" 주의 문구를 갱신한다(Track D, 에이전트 작업).
   - **[갱신 2026-07-03, 정정]** 해소는 **부분적**이다: 정상적인 반복 실행 경로는 RTL 수정으로
     해소(시뮬레이션 검증, 보드 확인은 실측 시). 단 **run이 타임아웃으로 중단(abort)된 뒤의
     복구는 여전히 불가** — 펌웨어에 PL 래퍼 리셋 수단이 없다(log 44 §4). README 문구는 이
     기준으로 갱신 완료. 실측에서 back-to-back PASS가 확인되면 "해소(정상 경로)"로 확정.
     **[확정 2026-07-22]** 전력 실측(Track B) 중 `mode 1-1`을 reset 없이 연속 반복 실행,
     전 회 정상 완료 — **해소(정상 경로) 확정**.
2. **Fmax 수치 갱신**: 교수님께 보고한 Fmax=115는 미팅 시점 값. 이후 clk_wiz 정밀 스윕(log40)으로
   **v1=116 / v2=146**으로 정밀화됨. 다음 보고·문서에 이 갱신값 반영(Track D, 에이전트 작업).

---

## 주체별 분리 (핵심)

### [에이전트] 코드/문서만으로 되는 일 — 물리 보드·장비 불필요

- **Track C**: CPU 벤치 PNG에 스펙·방법론 텍스트 삽입 (`sw/cpu_benchmark.py` 수정 + 재생성).
  단, CPU 스펙 값 자체는 사용자가 알려줘야 함(측정이 아니라 단순 정보 제공).
- **Track D 대부분**: Fmax 수치 갱신, README demo/PASS 기준 정리, report artifact 재검토,
  20MHz shared bin 해석 명시, CLAUDE.md 정정, Track A/B 결과가 들어오면 문서에 통합.
- **Track A 후반**: 서버에서 나온 ASIC 결과(면적/타이밍/전력 수치)를 받아서 표·문서로 정리.
- **Track B 후반**: 오실로스코프로 측정된 전력값을 받아서 Vivado 추정치와 비교분석 정리.

### [사용자 — 물리 보드/장비 직접 조작 필요]

- **Track A 실행**: 학교 서버에 접속해 OASIS synthesis + Nitro P&R **직접 실행**. **[확정]
  에이전트는 이 서버에 원격 접속 불가** — 전체가 사용자 몫. 결과 파일(면적/타이밍/전력
  리포트)을 받아오면 그다음은 에이전트가 정리.
- **Track B 실행**: HDS242 오실로스코프/멀티미터를 **보드에 직접 연결**해 전류/전압 실측.
  물리 계측이라 에이전트 불가. 측정값을 받아오면 그다음은 에이전트가 정리.
- **Fmax 보드 검증**: v1@115·116MHz / v2@145·146MHz BOOT.bin을 SD카드에 굽고 **보드 부팅 +
  UART 캡처**(wf22 로드맵 §3·§4 절차, v22 완료 후). 결과 파일을 받으면 반영은 에이전트.
- **v22 관련**: `docs/log/41_...` "확인 필요 1" — 같은 세션 run1/run2 raw 캡처를 **실보드에서
  직접 떠서** diff (버그 3 실보드 재현 확정용). 이것도 물리 보드 작업.

**패턴**: 거의 모든 트랙이 "① 사용자가 물리적으로 데이터를 만들어온다 → ② 에이전트가 정리·
문서화한다"의 2단계 구조. 순수하게 에이전트만으로 끝나는 건 Track C·D 뿐(그나마 Track C도
CPU 스펙이라는 사용자 제공 정보가 한 번은 필요).

---

## Track A — ASIC flow 보조 지표 (§8-1)

목표: 학교 서버에서 OASIS synthesis + Nitro P&R → **면적/타이밍/전력**을 FPGA 결과 옆 보조 지표로 제시.

- [사용자, 확정] 서버 접속 + OASIS synth + Nitro P&R **직접** 실행 (에이전트 원격 접속 불가).
- **[A1 확정, 갱신 2026-07-21]** 대상 RTL = `rtl/transposed_form/n43/fir_n43.v`(v1) +
  `fir_n43_v2.v`(v2) **둘 다**. AXI-Stream 래퍼/DMA/BD는 Zynq 전용이라 ASIC 비대상 →
  **순수 FIR core만**(decimator_m2_phase0 제외). 두 코어 모두 순수 behavioral Verilog
  (Xilinx primitive 없음)로 확인 — 포팅 장벽 없음.
  - 구 확정(v2 단독)의 근거였던 "v1→v2 분할은 FPGA 전용 병목(CARRY4 캐리 체인) 제거라
    ASIC에서 같은 critical path 보장 못 함"은 오히려 둘 다 돌려야 할 이유로 재해석:
    v1/v2를 **동일 제약**으로 돌리면 이 가설이 실증된다. v1 ≈ v2 Fmax + v1 면적 우위면
    "분할은 FPGA 전용 최적화"가 데이터로 확정되고, v2가 ASIC에서도 빠르면 분할의 범용성
    입증 — 어느 결과든 유의미. 증분 비용은 top module 교체 재실행뿐.
  - **방법론 조건**: 두 런의 목표 클럭·라이브러리·코너를 동일하게 (다르면 비교 무효).
- ✅ **[A2 해소 2026-07-21]** 환경 = 수업(2026-1 디지털시스템설계실습) GEMM 프로젝트와 동일:
  Tanner Generic 250nm PDK(`TANNER_TT_2P50V_25C.lib`, TT/2.5V/25°C), Oasys synthesis +
  Nitro P&R (TannerTools v2021.2). 목표 클럭은 고정값 대신 **sweep**(20000ps→8000ps,
  50→125MHz, v1/v2 동일 period 짝지어 실행)으로 각 버전 최속 passing period + 공통
  비교점 확보 (범위 근거는 `asic/oasys/README.md` §2).
  실행 준비물은 `asic/oasys/`(config·공용 sdc)·`asic/nitro/`(템플릿 tcl) 준비
  완료 — 서버에서 clone 후 config의 `REPO_ROOT`만 수정하면 됨. 절차는 `asic/*/README.md`.
- ✅ **[Track A 완료 2026-07-21]** Oasys 합성 sweep 6페어(20000→6000ps) 완료 — 전 구간
  v1≈v2(노이즈 수준), 둘 다 ≥166.7MHz. "v2 분할의 이득은 FPGA CARRY4 전용" 가설 실증.
  결과 정리: `asic/oasys/results/sweep_report.md`(sweep·해석) +
  `docs/report/fir_n43/summary/asic_vs_fpga.md`(FPGA 대비 표, §8-4.5 통합용).
  Nitro P&R은 툴 내부 버그(SDA101)로 중단 — 실행 전 과정·의사결정 상세는 `docs/log/47`.
  - ✅ **[해소 2026-07-03] 코어 단독 수치 추출 완료**: v2@145 routed DCP에서 계층 스코프로
    추출 — 코어 `u_fir_n43_v2` 단독 LUT 1792 / FF 2113 / DSP 16 / 전력 0.015W (전체
    비트스트림 4556 LUT / 1.705W와 구분). 상세 표·리포트 경로는 `sweep_summary_v2.md`
    "코어 단독 utilization/전력" 절. ASIC 비교 표는 이 코어 단독 수치와 대응시킬 것.

---

## Track B — 전력 실측 보조 지표 (§8-3)

**상태: ✅ 실측·정리 완료 (2026-07-22)** — 결과 log 46 §5, 비교분석
`docs/report/fir_n43/summary/power_board_vs_vivado.md`. 요약: S0 1.72 / S1 2.21 /
S2 2.18W, S1−S0=0.49W, S2≈S1(예측 부합), Vivado 1.705W와 정합 범위.

목표: HDS242로 보드 동작 중 전류/전압 실측 → 전력. Vivado 추정과 비교분석.
비교 기준은 B2 확정에 따라 **v2@145 clk_wiz 빌드 1.705W** (`sweep_summary_v2.md`).
(참고: 구 90~120MHz 스윕 1.564~1.576W는 PS7 PLL 계열(MMCM 없음) 수치로, clk_wiz
빌드는 MMCM 때문에 약 +0.13W 높다 — 옵션인 100MHz 골든 추가 측정 시 분석 근거.)

- ✅ [사용자] HDS242를 보드에 연결해 전류/전압 실측 실행 — 완료 (2026-07-22).
- **[B1 확정 2026-07-03]** 측정 지점 = **보드 5V 입력 전체**(Zybo Z7-20 입력은 12V가 아니라
  5V — USB 또는 배럴잭) + **차분 프로토콜**(PL 미구성 baseline / boot 후 idle / mode 1-1
  실행 중). PL/코어 rail 개별 측정은 Zybo Z7에 전류 션트/헤더가 없어 배제(파괴적).
- **[B2 확정 2026-07-03]** 조건 = **v2@145MHz** (`build/fir_n43_v2_freq_145mhz/output/BOOT.bin`,
  수정 RTL 반영 v22 완료본), 시나리오 = `mode 1-1` one-shot 반복. (옵션: 현장 여유 시
  100MHz 골든 SD로 한 점 추가 — 구 스윕 1.567W와 직접 비교 + MMCM 차이 검출.)
- **[B3 확정 2026-07-03]** HDS242 대여 완료(스코프 프로브·악어케이블 보유). 직렬 삽입은
  희생 micro-USB 케이블 VBUS 절단 방식 — 아래 준비물 참고.
  - **[갱신 2026-07-22]** 실측은 무개조 대안인 **배럴잭 breakout**(5V/2A 어댑터 + DC잭
    피그테일, 전원 점퍼 WALL, micro-USB는 UART 전용)으로 실행 — 아래 결선도의 USB VBUS
    방식은 미사용. 경위는 log 46 §5.1.
- 확정 근거·검토 대안: `docs/log/46_power_measurement_hds242_decisions.md`.
- ✅ [에이전트] 결과 정리 완료: 실측 전력 표는 log 46 §5, Vivado 추정 대비 분석은
  `docs/report/fir_n43/summary/power_board_vs_vivado.md`.

### Track B 준비물 체크리스트

- [ ] HDS242 본체 + **DMM 테스트 리드**(바나나) — 대여 파우치 확인. 스코프 프로브(BNC)는
      전류 측정에 사용 불가
- [ ] DMM 리드를 **10A 전용 잭**에 연결 (예상 전류 0.4~0.7A — mA 잭은 퓨즈 위험)
- [ ] 희생용 micro-USB 케이블 1개 — 빨간 VBUS 선만 절단, D+/D−/GND 유지(UART 그대로 동작)
- [ ] 악어케이블(절단점 ↔ DMM 리드 연결), 칼/스트리퍼, 절연 테이프
- [ ] SD 카드: v2@145 BOOT.bin (`build/fir_n43_v2_freq_145mhz/output/`).
      옵션 측정용 100MHz 골든 BOOT.bin SD 별도 준비
- 브레드보드·외부 션트 저항 불필요 (DMM 내부 션트 사용)

### Track B 결선

```
PC/충전기 쪽 VBUS ── (악어) ── DMM(10A 레인지, 직렬) ── (악어) ── 보드 쪽 VBUS
D+/D−/GND는 절단 없이 유지 (한 케이블로 UART + 전원 겸용)
```

- 전압은 전류 리드를 잠깐 풀고 절단점의 보드 쪽 VBUS ↔ GND를 DMM 전압 모드로 순차 측정
  (10A 션트 burden 강하는 무시 가능).
- 측정 중 악어클립 탈락 = 보드 전원 차단이므로, 물림 상태 확인 후 부팅할 것.

### Track B 실행 절차 (상태당 5회 판독, 중앙값 채택)

| 상태 | 조건 |
| ---- | ---- |
| S0 | SD 미삽입 전원 인가 (BootROM 대기, PL 미구성) — baseline |
| S1 | SD boot 완료, `READY FIR` 프롬프트 idle (PL 구성 + 145MHz 클럭, FIR idle) |
| S2 | `mode 1-1` one-shot 반복 실행 중 (S2 ≈ S1 예상 — log 46 §1 한계 참고) |

### Track B 기록 양식

| 상태 | V [V] | I₁ | I₂ | I₃ | I₄ | I₅ [A] | I_med [A] | P = V×I_med [W] |
| ---- | ----- | -- | -- | -- | -- | ------ | --------- | --------------- |
| S0   |       |    |    |    |    |        |           |                 |
| S1   |       |    |    |    |    |        |           |                 |
| S2   |       |    |    |    |    |        |           |                 |

---

## Track C — CPU 벤치 PNG 주석 (§8-2)

목표: `docs/report/fir_n43/plot/cpu_vs_fpga_timing_window.png`에 CPU 스펙 +
측정 방법론 텍스트 기입. **[갱신 2026-07-03] Ubuntu는 보조 지표이며 최종 발표에서는
사용하지 않기로 확정 — 실제 데모 노트북(Windows)만 대상으로 진행.**

- ✅ **C1 CPU 스펙**: Windows 데모 노트북 = 13th Gen Intel Core i5-1340P
  (12C/16T, L1 1.1MB, L2 9MB, L3 12MB).
- ✅ [에이전트] `sw/cpu_benchmark.py`에 CPU 스펙 + 측정 방법론(log38 §0-2: numpy float64
  `np.convolve`, `perf_counter`, convolve 구간만, UART 제외) 텍스트를 차트 하단에 기입하는
  로직 추가 → 기존 실측값(CPU median 162.0µs, FPGA 83.0µs) 기준으로
  `cpu_vs_fpga_timing_window.png` 재생성 완료. (한글 텍스트는 폰트 미지원으로 깨져 영문으로
  작성.)

---

## Track D — v1.0 문서 마무리 (log38 §5 + §8-4.5)

전부 [에이전트] 작업 (코드/문서 편집, 물리 보드 불필요). 단 마지막 항목은 A/B 결과 도착 후.

**[갱신 2026-07-03] 실사 결과 — Track D의 즉시 가능 항목은 대부분 이미 완료.** 아래 상태 표기.
문서 배치 원칙(사용자 확정): README는 "이 IP가 무엇인지 + 레포 조작 명령어"만 담고, Fmax
등 세부 엔지니어링 수치는 `docs/`(현재 `vivado/reports/sweep_summary*.md`)에 둔다.

- ✅ README에 demo command 정리 (§5.3) — `mode 1-1/1-2/2` `uv run` 명령·Expected result 존재.
  PASS 기준은 `docs/project_pipeline.md`(README §52에서 링크)에 유지.
- ✅ report artifact 재검토 (§5.4) — `docs/report/fir_n43/summary`·`metrics` 최신·정합.
- ✅ scenario 1-1 20 MHz shared bin 해석 명시 (§5.2) — `scenario1_1.md`에 Output Bin Sources
  컬럼(20,30) + Notes에 shared bin=INFO 명시 완료.
- ✅ **Fmax 수치 갱신**: v1 116 / v2 146 — `sweep_summary.md`/`_v2.md`에 정확히 반영됨(올바른
  배치처). 배포 주파수 v1 115 / v2 145는 Fmax 바로 아래 마진 확보 근거까지 같은 문서에 기재.
  README에는 수치를 넣지 않음(위 배치 원칙).
- ✅ **§5.1 "연속 실행 timeout" 한계 → v22 수정으로 해소** 표시 — `README.md` "Status update
  (2026-07-03)" 문단(운용 동작 설명이라 README 범위에 부합).
- ✅ CLAUDE.md "다음 작업 순서" 정정 — v1/v2 보드 실측 ✅ 반영 완료.
- ✅ (2026-07-22) 위 Track A~C 결과를 v1.0 문서에 **보조 지표로 통합** (§8-4.5) 완료 —
  `sweep_summary.md`/`_v2.md`에 보조지표 교차 참조 절 + correctness 보드 확인 반영,
  `final_report_draft.md`·`presentation_outline.md`의 [TrackB] 플레이스홀더 전부 해소.
  통합 리포트: `summary/asic_vs_fpga.md`(A) + `summary/power_board_vs_vivado.md`(B).

---

## 순서 / 의존 (착수 시 적용될 순서 — 아직 미착수)

- **v22와 무관한 착수 가능한 트랙**: Track C(CPU 스펙 받으면), Track A 서버 실행(대상 RTL
  확정 후), Track D 문서 일부(Fmax 갱신·20MHz bin·README).
- **v22 완료 후에만 착수**: Track B(전력 실측 — 수정본으로), Fmax 보드 검증(v1@115/116·
  v2@145/146, 절차는 wf22 로드맵 §3·§4), §5.1 한계 해소 표시, log 41 "확인 필요 1"
  run1/run2 raw diff.
- 물리 보드/장비가 필요한 작업(Track A·B 실행, Fmax 검증, log41 raw diff)은 전부 사용자,
  결과 정리·문서 반영은 전부 에이전트.

---

## 확인 필요 사항 (모든 트랙 착수 전 게이트 — 이 문서의 실질적 To-Do)

1. ~~**A1** ASIC 대상 RTL~~ — **[해결, 갱신 2026-07-21] `fir_n43.v`(v1) + `fir_n43_v2.v`(v2)
   둘 다, 동일 제약으로 확정** (구 확정 v2 단독에서 변경 — 근거는 Track A A1 항목).
2. ~~**A2** PDK/tech node·목표 클럭~~ — **[해소 2026-07-21] GEMM 프로젝트 환경 동일
   (Tanner Generic 250nm), 클럭은 sweep 방식. `asic/` 실행 준비물 작성 완료.**
3. **B1~B3** 전력 측정 rail / 조건(BOOT.bin) / HDS242 보유 여부.
4. ~~**C1** Windows·Ubuntu CPU 스펙(모델/코어/클럭)~~ — **[해결] Windows i5-1340P 스펙 확보,
   PNG 반영 완료(Ubuntu는 최종 발표 미사용으로 범위 제외).**
5. v23와 v22 우선순위: Track C·D 문서 작업을 지금(에이전트가 v22 하는 동안) 병행 착수할지,
   v22 완료까지 전부 대기할지.

---

## 실행 순서 요약 (표 — 위 확인 사항 해소 후 착수할 순서)

| 순서     | 작업                                                       | 주체                                      | 상태/의존                                                              |
| -------- | ---------------------------------------------------------- | ----------------------------------------- | ---------------------------------------------------------------------- |
| C        | CPU 벤치 PNG에 스펙·방법론 텍스트 (§8-2)                 | 사용자(스펙 제공) → 에이전트(구현)       | ✅ 완료 (Windows PNG만, Ubuntu 범위 제외)                              |
| D1       | Fmax 수치 갱신 + 20MHz bin + README demo/PASS 기준         | 에이전트                                  | ✅ 완료 (수치는 sweep_summary, README엔 미기재 — 배치 원칙)            |
| A        | OASIS synth + Nitro P&R → 면적/타이밍/전력 (§8-1)        | 사용자(서버 실행, 확정) → 에이전트(정리) | ✅ 완료 — 합성 sweep 완결, P&R은 툴 버그로 중단·문서화 (log 47)        |
| —       | (v22 완료 대기)                                            | 에이전트                                  | —                                                                     |
| B        | HDS242 전력 실측 → Vivado 추정 대비 분석 (§8-3)          | 사용자(보드 실측) → 에이전트(정리)       | ✅ 완료 (2026-07-22) — log 46 §5, summary/power_board_vs_vivado.md     |
| Fmax검증 | v1/v2 BOOT.bin 재생성 + 보드 실측 (wf22 로드맵 §3·§4)   | 사용자(보드 실행) → 에이전트(반영)       | ✅ 보드 실행(기능 동작) 완료, Fmax 정밀 측정은 미포함 |
| D2       | §5.1 한계 해소 표시 + A/B/C 결과 v1.0 문서 통합 (§8-4.5) | 에이전트                                  | ✅ 완료 (2026-07-22) — sweep_summary 교차참조·[TrackB] 해소 포함        |
