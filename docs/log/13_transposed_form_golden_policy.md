# 13. Transposed Form Q1.15 Golden Model Policy

- 작성일: 2026-04-29
- 단계: 5
- 목적: N=43 Transposed Form Q1.15 골든 모델 구현 전에 연산 정책을 확정하고 근거를 기록한다

## 1) 이번 세션 핵심 결정

1. Transposed Form delay register `z[k]`를 **signed 48-bit (wide accumulator)** 로 유지한다.
2. 곱셈 결과는 **16-bit × 16-bit → signed 32-bit 확정 후 48-bit sign-extend** 로 처리한다.
3. 반올림 정책은 기존과 동일하게 **ties-away-from-zero** 를 유지한다.
4. 반올림 시점은 **최종 출력 `z[0]` → Q1.15 변환 시 1회만** 수행한다.
5. 포화 적용 시점은 **최종 출력 저장 시점 1회만** `clip(-32768, 32767)` 한다.
6. intermediate wrap/saturation은 **없음** 으로 확정한다.
7. full convolution 경계 처리는 **output_len 구간 동안 루프, n >= len(x) 구간은 x_n = 0** 으로 처리한다.
8. 루프 안에서 `x[n]`은 **명시적으로 np.int32로 캐스팅** 한 뒤 곱셈에 사용한다.
9. `z[k]` 초기값은 **np.zeros(num_taps, dtype=np.int64)** 로 초기화한다.
10. 출력 길이는 **len(x) + len(h) - 1** 로 고정한다.
11. `x.size == 0`이면 **빈 np.int16 배열을 즉시 반환** 한다.
12. 입력 검증은 **Direct Form golden의 `_validate_q1_15_int_array`와 동일한 범위** 를 적용한다.

## 2) 결정 근거

### 판단 기준

정책 결정의 최우선 기준은 **RTL 구현과 골든 모델의 bit-exact 일치**다.

골든 모델의 존재 이유가 RTL 검증 기준선이므로, 골든이 RTL과 다른 정책을 쓰면 골든 자체가 의미없어진다. 따라서 정책 결정 순서는 RTL을 먼저 생각하고, 골든을 거기에 맞추는 것이다.

### 1. delay register 비트폭 — Wide (48-bit) 선택 근거

Transposed Form의 매 delay register 업데이트:

```
new_z[k]   = h[k] * x[n] + z[k+1]    (k = 0 ... N-2)
new_z[N-1] = h[N-1] * x[n]
y[n]       = new_z[0]  →  Q1.15로 변환
```

여기서 `z[k]`를 몇 비트로 유지할지가 핵심이다.

**Wide (48-bit) 선택 이유:**

첫째, N=5 bring-up에서 이미 wide accumulator(48-bit)를 RTL에서 사용했고 타이밍 클로저도 달성했다. Transposed Form은 Direct Form보다 carry chain이 짧아서 타이밍 압박이 오히려 줄어든다.

둘째, Narrow(16-bit)를 선택하면 매 delay register 업데이트마다 반올림이 발생해 N=43 기준 최대 42번 반올림 오차가 누산된다. 이 오차를 정량화하고 Direct Form과 비교 검증하는 비용이 불필요하게 커진다.

셋째, 이 프로젝트의 목표가 Transposed Form의 **Fmax 개선**을 보이는 것이다. 정확도를 희생하면 "더 빠르지만 덜 정확하다"는 불필요한 논점이 생긴다. Wide accumulator로 정확도는 Direct Form과 동등하게 유지하면서 Fmax가 개선되는 것이 핵심 주장이다.

넷째, N=43 worst-case 누산 bound:

```
sum(|h_q[k]|) = 56,025  (docs/log/07 기준)
max|x_q| = 32,768
max|acc| ≤ 32,768 × 56,025 = 1,835,827,200
```

이 값은 signed 32-bit 범위 안에 들어가며, 48-bit는 충분한 여유를 제공한다.

**Narrow (16-bit) 미선택 이유:**

매 register마다 반올림 → 오차 누산 → Direct Form golden과 차이 증가 → bit-exact 검증 불가. RTL 기준선으로서의 역할을 수행할 수 없다.

### 2. 곱셈 결과 비트폭 처리 — 명시적 결정

**결정: 16-bit × 16-bit 곱셈 결과를 signed 32-bit로 먼저 확정한 뒤, signed 48-bit로 sign-extend해서 누산한다.**

```
new_z[k] = h[k] * x[n]  +  z[k+1]
           ^^^^^^^^^^^     ^^^^^^^^
           16b × 16b       48-bit Q2.30
```

근거:
- Direct Form RTL에서 `prod = COEFF * sample`을 32-bit로 받아 48-bit sign-extend 후 누산하는 구조와 동일하게 맞춰야 RTL bit-exact가 보장된다
- Python은 정수 연산에서 자동 타입 확장이 일어나므로 명시하지 않으면 RTL 동작과 암묵적으로 달라질 수 있다
- 골든 코드에서 `np.int32` 곱셈 후 `np.int64` 누산으로 명시한다

골든 코드 구현 기준:

```python
prod = np.int64(np.int32(h[k]) * np.int32(x_n))  # 32-bit 곱셈 → 64-bit sign-extend
new_z[k] = prod + z[k + 1]                        # 48-bit 누산 (int64로 표현)
```

### 3. 반올림 정책 — ties-away-from-zero 유지 근거

- 기존 Direct Form RTL과 golden에서 이 정책으로 bit-exact가 이미 확인됐다.
- RTL 구현에서도 동일하게 적용하면 되므로 검증 파이프라인을 그대로 재사용할 수 있다.
- 변경할 이유가 없다.

### 4. 반올림 시점 — 최종 출력 1회 근거

- `z[k]`를 48-bit로 유지하므로 중간에 비트폭을 줄일 필요가 없다.
- 출력 시 `z[0]`(48-bit, Q2.30) → Q1.15 변환 시 딱 1회만 반올림한다.
- Direct Form golden의 반올림 시점과 동일한 구조다.

### 5. 포화 시점 — 최종 출력 1회 근거

- Wide accumulator로 intermediate overflow가 발생하지 않음이 worst-case 계산으로 확인됐다.
- 중간 포화를 넣으면 Direct Form golden과 출력이 달라져 bit-exact 검증이 깨진다.
- Direct Form golden과 동일하게 최종 출력 저장 시점 1회만 적용한다.

### 6. full convolution 경계 처리 근거

- Direct Form golden과 동일한 full convolution 계약을 유지해야 출력 길이와 tail이 일치한다.
- RTL testbench가 zero padding으로 tail을 flush하는 구조이므로, 골든도 동일하게 입력 범위 밖을 0으로 처리해야 bit-exact가 맞는다.
- float64 ideal Transposed Form에서 이미 동일한 방식으로 구현했고 Direct Form ideal과 bit-exact가 확인됐다.

### 7. x_n 타입 처리 근거

- `x`는 `np.int16`으로 들어오므로 `x[n]`은 `np.int16` 타입이다.
- 곱셈에서 피연산자 타입을 양쪽 모두 `np.int32`로 명시해야 RTL의 `16-bit × 16-bit → 32-bit` 동작과 정확히 대응된다.
- Python 자동 타입 확장에 의존하면 나중에 RTL mismatch 발생 시 원인 추적이 어려워진다.

골든 코드 구현 기준:

```python
x_n = np.int32(x[n]) if 0 <= n < input_len else np.int32(0)
```

### 8. z[k] 초기값 근거

- RTL 스펙(`09_bringup_rtl_decisions.md`)에서 reset 시 모든 state register를 0으로 초기화하는 것이 확정돼 있다.
- 골든 모델도 동일한 초기 조건에서 시작해야 RTL과 bit-exact 비교가 성립한다.
- dtype을 `np.int64`로 명시해야 48-bit 누산 중 overflow가 발생하지 않는다.

```python
z = np.zeros(num_taps, dtype=np.int64)
```

### 9. 출력 길이 계약 근거

- Direct Form golden과 동일한 계약이다.
- RTL testbench가 `INPUT_LEN + FLUSH_LEN` 기준으로 벡터를 생성하고 비교하는 구조이므로, 골든 출력 길이가 이 계약을 따라야 hex 벡터 export가 정상 동작한다.
- `FLUSH_LEN = num_taps - 1`이 이 계약에서 파생된다.

### 10. 빈 입력 처리 근거

- Direct Form golden과 동일한 엣지 케이스 처리다.
- 빈 입력에 대해 루프를 돌면 `output_len = len(h) - 1`이 되어 의미없는 zero 출력이 나온다.
- 호출자가 빈 입력을 넣었을 때 예측 가능한 동작을 보장한다.

### 11. 입력 검증 범위 근거

검증 항목:
- `np.ndarray` 여부 → `TypeError`
- 1-D 여부 → `ValueError`
- integer dtype 여부 → `TypeError`
- Q1.15 범위 (-32768 ~ 32767) 여부 → `ValueError`
- `h.size == 0` → `ValueError`

근거:
- 골든 모델 간 인터페이스 계약을 통일해야 상위 체인(`fir_decimator_transposed_golden`)에서 동일한 방식으로 호출할 수 있다.
- 잘못된 입력이 들어왔을 때 어느 레이어에서 걸러지는지 명확해야 디버깅이 쉽다.
- Direct Form golden에서 이미 검증된 패턴을 재사용하므로 추가 설계 비용이 없다.

## 3) 확정 정책 요약

| 항목 | 결정 |
| ---- | ---- |
| delay register `z[k]` 비트폭 | signed 48-bit (wide accumulator) |
| `z[k]` Q-format 해석 | Q2.30 |
| `z[k]` 초기값 | `np.zeros(num_taps, dtype=np.int64)` |
| 곱셈 결과 비트폭 | 16-bit × 16-bit → signed 32-bit 확정 후 48-bit sign-extend |
| x_n 타입 | `np.int32` 명시 캐스팅 |
| 반올림 정책 | ties-away-from-zero |
| 반올림 시점 | 최종 출력 `z[0]` → Q1.15 변환 시 1회 |
| 포화 시점 | 최종 출력 저장 시점 1회 `clip(-32768, 32767)` |
| intermediate wrap | 없음 |
| intermediate saturation | 없음 |
| full convolution 경계 | n >= len(x) 구간은 x_n = 0 |
| 출력 길이 | `len(x) + len(h) - 1` |
| 빈 입력 처리 | 빈 `np.int16` 배열 즉시 반환 |
| 입력 검증 | Direct Form golden과 동일한 범위 |

## 4) 기대 검증 결과

이 정책으로 구현하면 Q1.15 레벨 비교에서:

| 비교 쌍 | 기대 결과 |
| ------- | --------- |
| float64 Direct vs float64 Transposed | 완전 bit-exact (머신 엡실론 수준) |
| Q1.15 Direct vs Q1.15 Transposed | 차이 0 or 최대 1 LSB → 정상 |
| Q1.15 Transposed golden vs RTL | 완전 bit-exact |

Q1.15 레벨에서 1 LSB 오차가 허용되는 이유:
- Direct Form: 샘플 방향으로 누산 후 1회 반올림
- Transposed Form: 계수 방향으로 누산 후 1회 반올림
- 두 구조 모두 반올림은 1회이지만 누산 순서가 달라 floating point 덧셈 결합법칙에 의해 미세한 차이가 발생할 수 있다.
- 2 LSB 이상 차이가 나면 골든 로직 버그로 간주한다.

## 5) 구현 대상 파일

```
model/fixed/transposed_form/
    __init__.py
    anti_alias_fir.py          ← 이번 정책 기준으로 구현
    fir_decimator_transposed_golden.py
```

함수 시그니처는 Direct Form golden과 동일한 패턴을 따른다:

```python
def anti_alias_fir_transposed_golden(x: np.ndarray, h: np.ndarray) -> np.ndarray:
    # x, h: signed Q1.15 int16 입력
    # 반환: signed Q1.15 int16, full convolution 길이
```

## 6) 재현 명령어 (구현 후)

```bash
# Q1.15 Direct vs Transposed 비교
.venv/bin/python -m sim.python.run_compare_direct_vs_transposed_golden --num-taps 43

# 전체 pytest
.venv/bin/pytest -q
```
