# 03. FIR 계수 Q-format 확정

- 작성일: 2026-03-11
- 단계: 1
- fixed/golden FIR coefficient format 결정

## 1) 이번 세션 핵심 결정

1. FIR 계수 고정소수점 포맷을 `signed 16-bit, Q1.15`로 확정했다.
2. 이 결정은 입력 신호 제약과 분리해서, 필터 계수 자체의 동적 범위를 근거로 확정했다.
3. 근거 데이터는 `sim/python/inspect_kaiser_coeff.py`의 `N=5/15/35/37/39/41` 출력으로 남긴다.
4. 이후 입력 신호 포맷도 `04_input_qformat.md`에서 `signed 16-bit, Q1.15`로 확정했다.

## 2) 결정 근거

### 1. `Q1.15` 범위 안에 현재 FIR 계수가 모두 들어간 근거

- `signed Q1.15`의 표현 범위는 `[-1.0, 0.999969482421875]`이다.
- `inspect_kaiser_coeff.py` 실행 결과:

| 탭 수 | 계수 최대 | 계수 최소 | 계수 합산 |
| --- | ---: | ---: | ---: |
| `N=5`  | `0.563193` | `0.002685`  | `1.000000` |
| `N=15` | `0.400477` | `-0.038187` | `1.000000` |
| `N=35` | `0.399919` | `-0.065541` | `1.000000` |
| `N=37` | `0.399868` | `-0.066569` | `1.000000` |
| `N=39` | `0.400015` | `-0.067482` | `1.000000` |
| `N=41` | `0.400133` | `-0.068268` | `1.000000` |

- 현재 데모 대상 탭 수(`N=5/15/35/37/39/41`) 전체에서 계수 최대/최소가 `Q1.15` 표현 범위를 넘지 않는다.
- 특히 최댓값은 `N=5`일 때 `0.563193`, 최솟값은 `N=41`일 때 `-0.068268`으로, sign bit 외의 추가 정수 비트가 필요하지 않다.
- 계수 합산이 모두 `1.000000`으로 유지되어 unity DC gain 기준 설계 의도와도 일치한다.

### 2. 이 결정을 입력 신호 포맷 결정과 분리한 근거

- FIR 계수 포맷은 필터 설계 결과의 범위로 결정할 수 있다.
- 반면 입력/데이터 샘플 포맷은 멀티톤 입력의 tone 개수, 진폭 배분, crest factor, headroom 정책에 의해 달라진다.
- 계수 포맷을 먼저 확정한 뒤, 입력 포맷은 후속 문서 `04_input_qformat.md`에서 동일한 `Q1.15`로 정리했다.

## 3) 재현 명령어

```bash
.venv/bin/python -m sim.python.inspect_kaiser_coeff --num-taps 5
.venv/bin/python -m sim.python.inspect_kaiser_coeff --num-taps 15
.venv/bin/python -m sim.python.inspect_kaiser_coeff --num-taps 35
.venv/bin/python -m sim.python.inspect_kaiser_coeff --num-taps 37
.venv/bin/python -m sim.python.inspect_kaiser_coeff --num-taps 39
.venv/bin/python -m sim.python.inspect_kaiser_coeff --num-taps 41
```

## 4) 후속 액션

1. `docs/spec/fixed_model_spec.md`에 FIR 계수 포맷을 `Q1.15`로 반영한다.
2. 입력/데이터 포맷은 후속으로 `04_input_qformat.md`에서 `Q1.15`로 확정했다.
3. coefficient quantization의 rounding 정책은 별도 항목으로 확정한다.
