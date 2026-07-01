# FIR Decimation Project Workflow v21

- Date: 2026-07-02
- Previous: `docs/workflow/workflow_v20.md`
- Purpose: 120 MHz 크리티컬 패스 보완 → Fmax 130 MHz 이상 확보
- 실행 환경: Vivado + iverilog가 있는 Linux 머신 (본 문서는 Windows 세션에서 draft만 작성됨, 실행/검증은 Linux에서)

---

## 배경

`vivado/reports/sweep_summary.md`의 120 MHz 크리티컬 패스 분석:

```
Source:      u_fir_n43/z_reg[1][2]
Destination: u_fir_n43/round_reg_reg[45]
Data Path Delay: 8.664 ns (요구: 8.000 ns, 초과 0.664 ns)
Logic: 6.057 ns (CARRY4×19 포함, 23 로직 레벨) / Routing: 2.607 ns
```

원인: 기존 RTL은 `round_reg`를 `prod_reg[0] + z[1]`로부터 **같은 클럭 사이클 안에서**
직접 계산했다 (`z[0]` 레지스터를 다음 사이클에 참조할 수 없어 재계산하는 구조,
`non-blocking 특성상 z[0] 직접 참조 불가` 주석 참고). 그 결과 한 클럭 안에
`(48-bit 누산 add) → (round 함수 내부 abs/+bias/부호 반영, 최대 48-bit add 2회)`가
연쇄로 들어가 CARRY4 체인이 길어졌다.

---

## 범위 결정: v1 유지 + v2 신규 파일 (in-place 수정 아님)

`rtl/transposed_form/n43/fir_n43.v`는 100 MHz 기준 v1.0 golden 검증이 끝난 파일이므로
**직접 수정하지 않는다.** 대신 같은 디렉터리에 `fir_n43_v2.v`를 신규로 만들어
파이프라인 변경을 적용한다. 이유:

- v1(`fir_n43.v`)은 현재 데모/제출 기준선이므로 언제든 즉시 되돌릴 수 있는 상태를 유지해야 함.
- `n43_v2/`처럼 폴더 전체를 복제하면 `decimator_m2_phase0.v`, AXI-Stream 핸드셰이크 로직처럼
  이번 변경과 무관한 파일까지 중복되어 이후 버그 수정 시 두 곳을 동기화해야 하는 부담이 생김
  → 폴더 복제는 하지 않는다.
- 대신 **바뀌는 파일만** v2로 새로 만들고, 바뀌지 않는 파일(`decimator_m2_phase0.v`,
  AXI-Stream 래퍼 로직)은 그대로 재사용한다.

### 단계적 접근 (Stage A → Stage B)

파이프라인 변경이 실제로 맞는지 확인하기 전에 통합 파일(top/bd)까지 다 만들 필요는 없다.
버그가 있다면 저렴한 단계에서 먼저 잡는 것이 목표.

**Stage A (코어 단독 검증) — 지금 진행**

| 파일 | 내용 |
|------|------|
| `rtl/transposed_form/n43/fir_n43_v2.v` | `fir_n43.v` 복사본에 파이프라인 변경 적용 (아래 "설계 변경" 참고) |
| `sim/rtl/tb/transposed_form/tb_fir_n43_v2.sv` | `tb_fir_n43.sv` 복사본, DUT만 `fir_n43_v2`로 교체 |

iverilog만으로 기능 검증 가능. Vivado/보드 불필요.

**Stage B (보드/타이밍 통합 검증) — Stage A PASS 확인 후 진행**

| 파일 | 내용 |
|------|------|
| `rtl/transposed_form/n43/fir_decimator_n43_v2.v` | `fir_n43_v2` + 기존 `decimator_m2_phase0.v`(재사용, 무수정) 결합 top |
| `rtl/transposed_form/n43/fir_decimator_n43_axis_v2.v` | 기존 AXI-Stream 래퍼 로직 재사용, 내부 코어만 v2로 교체 |
| `vivado/fir_n43/bd_fir_dma_v2.tcl` | 기존 bd tcl 복사, top 모듈 참조만 v2로 교체 |

Vivado 타이밍 클로저는 코어 모듈 단독이 아니라 block design 전체 기준으로 측정되므로
130 MHz 실측을 위해서는 이 단계가 필요하다. 단, Stage A가 PASS하기 전에는 만들지 않는다.

---

## 설계 변경 내용 (Stage A에서 `fir_n43_v2.v`에 적용할 것)

파이프라인 3단계 → 4단계로 확장.

| 이전 (3단계, `fir_n43.v`)                  | 변경 후 (4단계, `fir_n43_v2.v`)            |
|---------------------------------------------|-------------------------------------------|
| Stage 1: 곱셈 → prod_reg                    | Stage 1: 곱셈 → prod_reg (동일)            |
| Stage 2: 누산 z[k] 갱신 **+ round 동시 계산** | Stage 2: 누산 z[k] 갱신만                  |
| Stage 3: 포화 → 출력                        | Stage 3: round(z[0]) — **레지스터 값 참조** |
|                                              | Stage 4: 포화 → 출력 (이전 Stage 3과 동일)  |

- `round_reg`는 `prod_reg[0] + z[1]`을 재계산하지 않고, 이미 레지스터에 저장된 `z[0]`을
  다음 사이클에 읽어 `round_q2_30_to_q1_15(z[0])`을 계산한다.
- 누산 add 1회분이 round 로직과 분리되어 크리티컬 패스에서 빠진다.
- Latency: 3 cycles → **4 cycles**. `decimator_m2_phase0.v`, AXI-Stream 래퍼는 모두
  `valid` 핸드셰이크 기반이라 고정 latency를 가정하지 않음 (grep 확인 완료, 무수정 재사용 가능).
- 출력 수치는 v1과 100% 동일해야 한다 (라운딩 로직 자체는 변경 없음, 계산 순서만 재배치,
  latency만 1 cycle 증가).

### 예상 효과

round 함수 진입 전 add 1개가 빠지므로 크리티컬 패스의 체인 길이가 줄어든다.
sweep_summary.md의 자체 예측: **Fmax 150+ MHz**. 다만 이는 미검증 추정치이며,
아래 검증 절차로 실측해야 한다.

---

## 검증 절차 (Linux 머신에서 실행)

### Step 1 (Stage A). 기능 회귀 — iverilog, 코어 단독

```bash
iverilog -g2012 -o build/sim/tb_fir_n43_v2 \
  rtl/transposed_form/n43/fir_n43_v2.v \
  sim/rtl/tb/transposed_form/tb_fir_n43_v2.sv
vvp build/sim/tb_fir_n43_v2
```

기대 결과: S1 Happy Path, S2 Random Bubble 모두 PASS, `fir_n43.v` 원본과 완전히 동일한
golden 벡터 사용, 출력값 100% 동일 확인.

**이 Step이 FAIL하면 Stage B로 넘어가지 않는다.** 파이프라인 재배치 로직 자체를 다시 본다.

### Step 2 (Stage B 시작). 통합 파일 생성

Step 1 PASS 확인 후, 위 "Stage B" 표의 3개 파일을 생성한다.
`decimator_m2_phase0.v`, 기존 AXI-Stream 핸드셰이크 로직은 그대로 재사용 (수정 없음).

### Step 3. Vivado 타이밍 재스윕

`vivado/README.md`의 "동적 주파수 결정 알고리즘" 절차를 그대로 재사용하되,
`bd_fir_dma_v2.tcl` 기준으로 Phase 2 시작점을 120 MHz로 잡는다
(v1의 90/100/110/115 MHz PASS 결과는 이미 확정되어 있으므로 v2에서 재확인 불필요):

```
Phase 2 (v2 재검증, 10MHz 단계): 120 MHz부터 시작
  WNS >= 0 → next = current + 10 MHz
  WNS <  0 → 코스 탐색 종료, Phase 3(5MHz 이분)로 이행
목표: 130 MHz 이상에서 WNS >= 0 확인
```

결과를 `vivado/reports/sweep_summary_v2.md`로 별도 기록 (v1의 `sweep_summary.md`는 보존).
새 크리티컬 패스도 함께 기록 (이번에도 round 관련 경로인지, 다른 경로로 바뀌었는지 확인).

### Step 4. 보드 정확도 재검증

130 MHz(혹은 확정된 새 Fmax)에서 v2 bd 기준 BOOT.bin을 만들어 `workflow_v20.md`
Step 2~4와 동일하게 scenario 1-2를 돌려 golden과 일치하는지 확인한다.
Latency가 1 cycle 늘었을 뿐 수치는 동일해야 하므로, SNR/max_error는 v1의 100 MHz/115 MHz
결과와 동일한 수준(SNR 72.2 dB, max_error 7 LSB)이 나와야 한다.
크게 달라지면 파이프라인 재배치에 버그가 있다는 신호.

### Step 5. 결과 반영

- v1(`fir_n43.v`, 100 MHz 데모 기준선)과 v2(`fir_n43_v2.v`, 130 MHz 목표)를 병행 유지할지,
  v2 검증 완료 후 v1을 교체할지 결정 (교체는 v1.0 제출/발표 일정과 맞물려 있으므로 신중히).
- CLAUDE.md, README 등에 v2 latency(4 cycle) 및 신규 Fmax 반영.

---

## 완료 기준

**Stage A**
- [ ] `fir_n43_v2.v`, `tb_fir_n43_v2.sv` 생성
- [ ] iverilog 회귀: S1/S2 PASS, v1과 수치 100% 동일 확인

**Stage B (Stage A 통과 후)**
- [ ] `fir_decimator_n43_v2.v`, `fir_decimator_n43_axis_v2.v`, `bd_fir_dma_v2.tcl` 생성
- [ ] Vivado 재스윕: 120 MHz 이상에서 WNS >= 0, 목표 130 MHz 달성
- [ ] 새 크리티컬 패스 분석 기록 (`sweep_summary_v2.md`)
- [ ] 보드 실측 golden 비교 PASS (SNR/max_error v1 수준 유지)
- [ ] git commit

---

## 롤백

v1(`fir_n43.v`)은 애초에 수정하지 않으므로 롤백이 필요 없다.
v2 접근이 막히면 신규 파일(`fir_n43_v2.v` 등)만 삭제하면 v1 기준선은 항상 그대로 보존된다.
