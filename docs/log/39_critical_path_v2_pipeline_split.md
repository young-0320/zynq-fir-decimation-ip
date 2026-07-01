# 39. 120MHz 크리티컬 패스 분석 및 v2 파이프라인 분할

- 작성일: 2026-07-02
- 선행 문서:
  - `38_professor_meeting_2026_07_01.md`
  - `../workflow/workflow_v20.md`
  - `../workflow/workflow_v21.md`
  - `vivado/reports/sweep_summary.md`

---

## 배경

교수님 미팅(2026-07-02)에서 방향성은 승인받았고, ASIC 보조 지표/전력 실측 등
추가 지시가 있었다 (`38_professor_meeting_2026_07_01.md` 8절 참고). 이와 별개로,
클럭 스윕 결과(90~120 MHz)에서 확인된 120 MHz 타이밍 실패(WNS=-0.783ns)의
크리티컬 패스를 분석하고, 이를 보완하는 v2 설계를 시작했다.

목표: 120 MHz 병목을 해결하고 Fmax 130 MHz 이상 확보.

---

## 크리티컬 패스 분석

`vivado/reports/sweep_summary.md`의 120 MHz 빌드 타이밍 리포트 기준:

```
Source:      u_fir_n43/z_reg[1][2]        (FIR 딜레이 레지스터, z⁻¹)
Destination: u_fir_n43/round_reg_reg[45]  (라운딩 레지스터)

Data Path Delay: 8.664 ns  (요구: 8.000 ns, 초과 0.664 ns)
  Logic  : 6.057 ns (69.9%) — CARRY4×19, LUT×4, 총 23 로직 레벨
  Routing: 2.607 ns (30.1%)
```

### 병목 원인

`rtl/transposed_form/n43/fir_n43.v`의 기존(v1) 구조는 Stage 2 한 사이클 안에서
누산과 라운딩을 동시에 계산했다:

```verilog
z[0] <= prod_reg[0] + z[1];
// non-blocking 특성상 z[0] 직접 참조 불가 → prod_reg[0]+z[1] 직접 계산
round_reg <= round_q2_30_to_q1_15(prod_reg[0] + z[1]);
```

`round_q2_30_to_q1_15()` 함수 내부는 `abs(value)` → `+ROUND_BIAS` → 부호 재적용의
3단 연쇄 48-bit 연산이다. 여기에 입력으로 들어가는 `prod_reg[0] + z[1]` 누산까지
합쳐지면, 한 클럭 안에 48-bit add가 최대 3회 연쇄로 들어간다. 이 연쇄가 CARRY4 19개로
합성되어 8.664ns의 데이터 경로 지연을 만들었고, 120MHz(8.000ns 요구) 타이밍을
0.664ns 초과했다.

110/115 MHz에서 WNS가 동일하게 +0.178ns였던 것도 같은 크리티컬 패스가 두 클럭
구간(8.70ns/8.33ns) 모두에 들어맞았기 때문이며, 120MHz(8.00ns)에서 처음으로
경계를 넘었다.

---

## 보완 설계: v2 파이프라인 분할

### 핵심 아이디어

누산(Stage 2)과 라운딩(Stage 3)을 별도 사이클로 분리한다. 라운딩은 더 이상
`prod_reg[0]+z[1]`을 재계산하지 않고, 이미 레지스터에 저장된 `z[0]`을 다음
사이클에 읽어 계산한다. 재계산 대신 레지스터 참조로 바꾸면서 누산 add 1회분이
라운딩 로직의 크리티컬 패스에서 완전히 빠진다.

| 이전 (3단계, v1)                              | 변경 후 (4단계, v2)                          |
|-------------------------------------------|-------------------------------------------|
| Stage 1: 곱셈 → prod_reg                  | Stage 1: 곱셈 → prod_reg (동일)           |
| Stage 2: 누산 z[k] 갱신 **+ round 동시 계산** | Stage 2: 누산 z[k] 갱신만                 |
| Stage 3: 포화 → 출력                      | Stage 3: round(z[0]) — **레지스터 값 참조** |
|                                            | Stage 4: 포화 → 출력 (이전 Stage 3과 동일) |

Latency는 3 cycle → 4 cycle로 늘어난다. 하위 모듈(`decimator_m2_phase0.v`,
AXI-Stream 래퍼)이 모두 `valid` 핸드셰이크 기반이라 고정 latency를 가정하지
않으므로 추가 수정이 필요 없다 (grep으로 확인).

### v1을 직접 수정하지 않은 이유

`fir_n43.v`는 100 MHz 기준 v1.0 golden 검증이 끝난 현재 데모 기준선이므로
직접 수정하지 않았다. 대신 `fir_n43_v2.v`를 신규 파일로 만들었다.
`n43_v2/` 폴더 전체를 복제하는 방식도 검토했지만, `decimator_m2_phase0.v`나
AXI-Stream 래퍼처럼 이번 변경과 무관한 파일까지 중복되어 이후 버그 수정 시
두 곳을 동기화해야 하는 부담이 있어 폐기했다. 바뀌는 파일만 v2로 만들고
나머지는 그대로 재사용하는 쪽을 택했다.

또한 통합(top/bd) 파일까지 한 번에 만들지 않고 단계를 나눴다:

- **Stage A (완료)**: `fir_n43_v2.v` + `tb_fir_n43_v2.sv`만 생성. iverilog로
  기능 검증(출력값이 v1과 100% 동일한지)만 먼저 확인.
- **Stage B (Stage A 통과 후)**: `fir_decimator_n43_v2.v`,
  `fir_decimator_n43_axis_v2.v`, `bd_fir_dma_v2.tcl`을 추가해 Vivado 재스윕으로
  실제 타이밍(목표 130MHz)을 확인.

파이프라인 재배치에 버그가 있다면 저렴한 iverilog 단계에서 먼저 잡기 위함이다.

---

## 이번 세션 산출물

| 파일 | 상태 |
|------|------|
| `rtl/transposed_form/n43/fir_n43_v2.v` | 신규 생성, 파이프라인 4단계 분할 적용 |
| `sim/rtl/tb/transposed_form/tb_fir_n43_v2.sv` | 신규 생성, `tb_fir_n43.sv` 사본 (DUT만 v2로 교체) |
| `docs/workflow/workflow_v21.md` | 신규 생성, Stage A/B 검증 절차 문서화 |
| `rtl/transposed_form/n43/fir_n43.v` | **무수정** (v1 golden 기준선 그대로 보존) |

---

## 다음 작업 (Linux 머신, Vivado/iverilog 필요)

1. Stage A 실행: iverilog로 `tb_fir_n43_v2` 회귀, S1/S2 PASS 및 v1과 수치 100% 동일 확인
2. PASS 시 Stage B 파일 생성 (`fir_decimator_n43_v2.v` 등)
3. Vivado 재스윕: 120MHz부터 재검증, 목표 130MHz 이상 WNS≥0
4. 새 크리티컬 패스 기록 (`vivado/reports/sweep_summary_v2.md`)
5. 보드 golden 재비교 (SNR/max_error 기존 수준 유지 확인)

상세 절차는 `docs/workflow/workflow_v21.md` 참고.

---

## 참고: 이번 세션에서 검토했으나 범위 밖으로 판단한 추가 최적화

- DSP48 캐스케이드(PCIN/PCOUT) 기반 systolic 재설계 — Fmax 상한을 더 크게 올릴 수 있으나 구조 전면 재설계 수준
- 계수 대칭성(선형위상) 활용한 곱셈기 절반 축소 — transposed form에서는 direct form만큼 간단히 적용 안 됨, 구조 변경 필요
- 누산기 워드 폭(48-bit) right-sizing — 오버플로우 안전성 재검증 필요, 리스크 대비 이득 불확실

세 가지 모두 v3급 구조 변경으로 판단해 이번 v2 범위(120MHz 병목 제거, 130MHz 목표)에서 제외했다.
