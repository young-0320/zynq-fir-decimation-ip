# 14. Transposed Form RTL Design Decisions

- 작성일: 2026-04-29
- 단계: 6
- 목적: N=43 Transposed Form RTL 구현 전에 설계 결정 사항을 확정하고 근거를 기록한다
- 선행 문서: `docs/log/13_transposed_form_golden_policy.md`

## 1) 이번 세션 핵심 결정

1. 처리 구조는 **1 sample/cycle 병렬 처리**로 확정한다.
2. 파이프라인은 **2단계**를 초기 설계안으로 잡고, 타이밍 위반 시 단계를 추가한다.
3. FIR latency는 **2 cycles**, top latency는 **3 cycles**로 초기 계약을 잡는다.
4. 계수 저장 방식은 **localparam 하드코딩**으로 확정한다.
5. `in_valid=0`일 때 `z[k]`는 **hold**한다.
6. 포트 인터페이스는 **bring-up N=5와 동일**하게 유지한다.
7. reset 규칙은 **active-high, z[k] 전부 0으로 초기화**로 확정한다.
8. 누산기 비트폭은 **signed 48-bit**로 확정한다.

## 2) 결정 근거

### 판단 기준

RTL 설계 결정의 최우선 기준은 두 가지다.

첫째, **골든 모델과 bit-exact 일치** — 골든이 정의한 연산 정책을 RTL이 정확히 구현해야 한다.
둘째, **100MHz 타이밍 클로저** — 목표 처리율 1 sample/cycle @ 100MHz를 달성해야 한다.

### 1. 1 sample/cycle 병렬 처리 구조 근거

Transposed Form의 z[k] 업데이트:

```
new_z[k]   = h[k] * x[n] + z[k+1]   (k = 0 ... N-2)
new_z[N-1] = h[N-1] * x[n]
y[n]       = round(new_z[0])
```

각 `new_z[k]`는 서로 독립적으로 계산 가능하다. 즉 N=43개의 MAC 연산을 같은 cycle에 병렬로 실행하면 1 sample/cycle이 달성된다.

순차 처리(1 sample/N cycles)를 선택하면 처리율이 `100MHz / 43 ≈ 2.3MHz`로 떨어져 프로젝트 목표와 맞지 않는다.

Zybo Z7-20의 DSP48 자원은 220개이고 N=43개는 충분히 수용 가능하다.

### 2. 파이프라인 단계 — 2단계 초기 설계안 근거

**Direct Form N=5 경험:**

N=5 bring-up에서 Direct Form의 critical path는 아래와 같았다.

```
tap reg → 5개 곱셈(병렬) → 5개 합산(carry chain) → acc_reg → round → out
```

이 carry chain이 길어서 최종적으로 4단계 파이프라인이 필요했다.

**Transposed Form의 critical path:**

```
x[n] 입력 → h[k]*x[n] (DSP 곱셈 1개) → + z[k+1] (48-bit 덧셈 1개) → z[k]
```

Direct Form과 달리 합산 경로가 `DSP 1개 + 덧셈 1개`로 끝난다. carry chain이 없다.

따라서 2단계로도 100MHz를 닫을 가능성이 높다.

```
Stage 1: in_valid 수신 → h[k]*x[n] 곱셈 → prod_reg[k] 저장
Stage 2: prod_reg[k] + z[k+1] → new_z[k] 저장, z[0] round/sat → out_sample
```

단, 실제 타이밍은 Vivado implementation 결과로만 확인 가능하다. 타이밍 위반 시 아래 순서로 단계를 추가한다.

```
위반 발생 시:
    Stage 2를 → round_reg 저장 + sat 출력으로 분리 → 3단계
```

### 3. Latency 계약 근거

2단계 파이프라인 기준:

```
accepted input @ cycle t
    → prod_reg 저장 @ t+1  (Stage 1)
    → z[k] 업데이트 + out_sample @ t+2  (Stage 2)
    → decimator output @ t+3  (keep sample 기준)
```

| 블록 | latency |
|------|---------|
| FIR (Transposed Form) | 2 cycles |
| Decimator | 1 cycle |
| Top | 3 cycles (keep sample 기준) |

N=5 bring-up의 top latency(5 cycles) 대비 2 cycles 단축. 이것이 Transposed Form의 Fmax 개선 외 추가 이점이다.

타이밍 위반으로 3단계로 늘어나면:

| 블록 | latency |
|------|---------|
| FIR | 3 cycles |
| Top | 4 cycles |

로 재조정한다.

### 4. 계수 저장 방식 — localparam 하드코딩 근거

- N=5 bring-up 방식과 동일하게 유지한다.
- AXI 래퍼 붙이기 전까지 coefficient reload가 필요 없다.
- localparam은 합성 시 상수로 처리되므로 DSP에 직접 folding되어 자원 효율이 좋다.
- 43개 나열이 길어 보이지만 Python 스크립트로 자동 생성 가능하다.

```verilog
localparam signed [15:0] COEFF_0  = 16'sd???;
localparam signed [15:0] COEFF_1  = 16'sd???;
// ... N=43개
localparam signed [15:0] COEFF_42 = 16'sd???;
```

계수값은 `model/ideal/design_kaiser_coeff.py`로 생성한 Q1.15 정수값을 사용한다.

### 5. in_valid=0 시 z[k] 동작 근거

- `in_valid=0`이면 z[k] 업데이트를 수행하지 않고 이전 값을 hold한다.
- Direct Form bring-up 스펙(`09_bringup_rtl_decisions.md`)과 동일한 정책이다.
- valid 기반으로 state가 움직여야 나중에 bubble이 생겨도 decimation phase가 깨지지 않는다.
- `out_valid=0`일 때 `out_sample`은 이전 값 hold. 비교 대상 아님.

### 6. 포트 인터페이스 근거

bring-up N=5와 동일하게 유지한다.

```verilog
input  wire               clk;
input  wire               rst;
input  wire               in_valid;
input  wire signed [15:0] in_sample;
output reg                out_valid;
output reg  signed [15:0] out_sample;
```

AXI-Stream 래퍼는 이 위에 별도로 덮어씌우는 구조로 간다. 코어 포트를 바꾸지 않아야 래퍼 교체 시 코어를 수정하지 않아도 된다.

### 7. reset 규칙 근거

- `rst`: active-high. bring-up N=5 방식과 동일.
- reset 시 초기화 대상:
  - `z[k]` 전부 0 (N=43개 레지스터)
  - `prod_reg[k]` 전부 0
  - `out_valid = 0`
  - `out_sample = 0`
- reset 직후 첫 valid 입력은 새 스트림의 첫 샘플로 처리된다.
- 골든 모델의 `z = np.zeros(num_taps, dtype=np.int64)` 초기 조건과 동일하다.

### 8. 누산기 비트폭 근거

골든 정책(`13_transposed_form_golden_policy.md`)과 동일하게 signed 48-bit를 사용한다.

```
z[k]: signed 48-bit (int64로 표현, 상위 16-bit는 sign-extend 영역)
prod_reg[k]: signed 48-bit (32-bit 곱셈 결과를 sign-extend)
```

N=43 worst-case bound:

```
max|z[k]| ≤ max|x| × sum(|h|) = 32,768 × 56,025 = 1,835,827,200
```

signed 32-bit 최대값(2,147,483,647) 안에 들어오므로 48-bit는 충분한 여유다.

## 3) 확정 설계 결정 요약

| 항목 | 결정 |
|------|------|
| 처리 구조 | 1 sample/cycle 병렬 (N=43개 MAC 동시) |
| 파이프라인 단계 | 2단계 초기 설계, 타이밍 위반 시 3단계로 확장 |
| FIR latency | 2 cycles (초기), 위반 시 3 cycles |
| Top latency | 3 cycles (초기), 위반 시 4 cycles |
| 계수 저장 | localparam 하드코딩 (N=43개) |
| in_valid=0 동작 | z[k] hold, out_valid=0 |
| 포트 인터페이스 | bring-up N=5와 동일 |
| reset 극성 | active-high |
| reset 시 초기화 | z[k], prod_reg[k], out_valid, out_sample 전부 0 |
| 누산기 비트폭 | signed 48-bit |
| 클럭 | 100MHz (Clocking Wizard) |

## 4) 파이프라인 구조 상세

```
[Stage 1] in_valid=1 수신
    → h[k] * in_sample  (k=0..42, DSP 43개 병렬)
    → prod_reg[k] 저장  (signed 48-bit, sign-extend)
    → prod_valid = 1

[Stage 2] prod_valid=1
    → new_z[k] = prod_reg[k] + z[k+1]  (k=0..41)
      new_z[42] = prod_reg[42]
    → z[k] = new_z[k]
    → rounded = round(z[0], Q2.30→Q1.15, ties-away-from-zero)
    → out_sample = saturate(rounded)
    → out_valid = 1
```

## 5) Direct Form N=5 대비 개선 예상

| 항목 | Direct Form N=5 | Transposed Form N=43 (예상) |
|------|-----------------|------------------------------|
| 파이프라인 단계 | 4단계 | 2단계 |
| Top latency | 5 cycles | 3 cycles |
| Critical path | 합산 carry chain (N개) | DSP 1개 + 덧셈 1개 |
| DSP 사용 | 5개 | 43개 |
| 클럭 | 125MHz (비효율) | 100MHz (목표 처리율) |

## 6) 구현 대상 파일

```
rtl/transposed_form/
    fir_transposed_n43.v               ← FIR 코어
    fir_decimator_transposed_n43_top.v ← FIR + Decimator 연결
    constrs/
        zybo_n43.xdc                   ← 핀 배치 (bring-up N=5 기반)

sim/rtl/tb/transposed_form/
    tb_fir_transposed_n43.v
    tb_fir_decimator_transposed_n43_top.v

sim/vectors/transposed_form/n43/
    input_q15.hex
    expected_fir_q15.hex
    expected_decim_q15.hex
```

## 7) 다음 액션

1. N=43 Q1.15 계수 정수값 생성 및 localparam 목록 준비
2. `fir_transposed_n43.v` 구현
3. `tb_fir_transposed_n43.v` 작성 및 iverilog 시뮬레이션
4. `fir_decimator_transposed_n43_top.v` 구현
5. `tb_fir_decimator_transposed_n43_top.v` PASS 확인
6. Vivado synthesis/implementation → WNS 확인
7. 타이밍 위반 시 파이프라인 단계 추가
