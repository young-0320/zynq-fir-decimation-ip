# FIR Decimator Fixed Model Spec

## 1. 목적

본 문서는 `model/fixed`에 구현할 고정소수점(fixed-point) golden 모델의 동작 사양 초안을 정의한다.

- 대상: `FIR anti-aliasing + decimation(M=2)` 파이프라인
- 용도: RTL bit-exact 비교 기준, ideal 모델과 RTL 사이의 golden reference
- 선행 조건: 입력 신호 생성 제약은 `docs/spec/bringup_input_signal_spec.md`에서 먼저 확정한다
- 단, FIR 계수 포맷은 `sim/python/inspect_kaiser_coeff.py` 결과를 근거로 별도 확정한다

## 2. 시스템 사양

- 입력 샘플링 주파수: `Fs_in = 100e6` (Hz)
- 디시메이션 계수: `M = 2`
- 출력 샘플링 주파수: `Fs_out = Fs_in / M = 50e6` (Hz)
- 통과대역 경계: `fp = 15e6` (Hz)
- 저지대역 시작: `fs = 25e6` (Hz)
- 목표 저지대역 감쇠: `As >= 60 dB`
- FIR 설계법: Kaiser window
- 기본 탭 수:
  - bring-up: `N = 5`
  - 비교/평가: `N = 39`, `N = 41`
  - 현재 coefficient-based spec-check 대상: `N = 43`
- 입력/출력 샘플 포맷: `signed 16-bit, Q1.15`
- FIR 계수 포맷: `signed 16-bit, Q1.15`
- 내부 곱셈 결과 포맷: `signed 32-bit, Q2.30`

## 3. 블록 정의

### 3.1 Anti-alias FIR

- 선형 위상 저역통과 FIR.
- 입력 `x[n]`에 대해 아래 수식을 따른다.

$$
y_{\mathrm{fir}}[n] = \sum_{k=0}^{N-1} h[k] \cdot x[n-k]
$$

- `x[n-k]`의 범위가 입력 밖이면 0으로 간주한다.
- 출력은 full convolution을 유지하며, 초기 과도응답과 tail을 그대로 포함한다.
- fixed/golden 모델은 ideal 모델과 동일한 처리 순서를 유지한다.

### 3.2 Decimator

- FIR 출력 `y_fir[n]`를 `M`배 다운샘플링한다.
- 위상 `phase` 기본값은 `0`.

$$
y_{\mathrm{decim}}[r] = y_{\mathrm{fir}}[rM + \mathrm{phase}]
$$

- 기본 정책: `phase = 0`, `M = 2`

### 3.3 Top-level Golden Reference

- 처리 순서는 반드시 아래를 따른다.

  1. `anti-aliasing`
  2. `decimation`
- 즉, `downsample only`는 본 기준 모델의 기본 경로가 아니다.
- golden 모델은 ideal 모델과 동일한 구조를 유지하되, 고정소수점 연산 정책을 반영한다.

## 4. 모듈/파일 계약

### 4.1 `model/fixed/anti_alias_fir.py`

필수 제공 함수:

- `anti_alias_fir_golden(x, h) -> np.ndarray`
  - 입력 `x`, `h`를 받아 causal FIR 출력을 반환
  - 반환 길이는 full convolution 기준 `len(y) = len(x) + len(h) - 1`
  - 반환 dtype: `np.int16`
  - 입력 `x` 계약: `np.ndarray` 1-D, `signed Q1.15` 샘플 배열
  - 입력 `h` 계약: `np.ndarray` 1-D, `signed Q1.15` 계수 배열
  - 내부 누산기 폭: golden 구현은 `np.int64`, 현재 `N=43` 기준 최소 요구 폭은 signed `32-bit`
  - 곱셈 결과 스케일 처리: `x(Q1.15) * h(Q1.15) -> product(Q2.30)`
  - rounding 정책: `Q2.30 -> Q1.15` 변환 시 `round-to-nearest with ties-away-from-zero`
  - saturation 정책: 최종 출력 배열 저장 직전에만 `clip(-32768, 32767)`
  - overflow 정책: intermediate wrap/saturation 없이 wide accumulator로 누산

### 4.2 `model/fixed/decimator.py`

필수 제공 함수:

- `decimate_golden(x, m=2, phase=0) -> np.ndarray`
  - 입력 `x`는 1-D 배열로 받는다
  - 구현 기준: `x[phase::m]`
  - 입력 dtype: `np.int16`
  - 반환 dtype: `np.int16`
  - 입력 검증 정책: `1-D ndarray`, integer dtype, `int16/Q1.15` 범위 확인
  - `phase` 해석: FIR 출력에서 몇 번째 샘플부터 유지할지 정하는 오프셋

### 4.3 `model/fixed/fir_decimator_golden.py`

필수 제공 함수:

- `run_fir_decimator_golden(x, h, m=2, phase=0, return_intermediate=False)`
  - 내부에서 FIR 후 decimation 수행
  - `return_intermediate`는 `bool`
  - 기본값(False)에서는 `y_decim`만 반환
  - `return_intermediate=True`일 때 `(y_fir, y_decim)` 튜플을 반환
  - 최종 반환 dtype: `np.int16`

## 5. 데이터 타입 및 수치 정책

| 항목                   | 현재 정책                |
| ---------------------- | ------------------------ |
| 입력 샘플 저장 포맷    | `signed 16-bit, Q1.15` |
| FIR 계수 저장 포맷     | `signed 16-bit, Q1.15` |
| 샘플 dtype             | `np.int16` (저장 기준)         |
| 계수 dtype             | `np.int16` (저장 기준)         |
| 출력 dtype             | `np.int16` (현재 golden 출력 저장 기준) |
| 내부 곱셈 dtype        | `np.int32` 또는 그 이상, `Q2.30` 해석 |
| 내부 누산 dtype        | golden 구현은 `np.int64`, RTL 구현 목표는 signed `48-bit` accumulator |
| 입력 생성 dtype        | `np.float64` |
| 입력 양자화 방식       | 멀티톤 합산 후 1회 `Q1.15` 양자화 |
| 계수 양자화 방식       | `float64` 계수를 `Q1.15`로 1회 양자화, 입력과 동일한 rounding 규칙 사용, 재정규화 없음 |
| 입력 양자화 rounding 시점 | 합산 후 1회 |
| 입력 양자화 rounding 모드 | `round-to-nearest, ties-away-from-zero` |
| 입력 양자화 saturation 시점 | rounding 직후 |
| 입력 양자화 saturation 범위 | `clip(-32768, 32767)` |
| 추가 정규화           | 없음 |
| 출력 리스케일         | `Q2.30 -> Q1.15`, `round-to-nearest with ties-away-from-zero` |
| 최종 출력 saturation  | 출력 배열 저장 시점에서 1회 `clip(-32768, 32767)` |
| overflow 처리          | intermediate wrap/saturation 없음, wide accumulator로 exact accumulation |
| 음수 right shift 해석  | raw arithmetic shift를 spec으로 사용하지 않음, rounding 규칙으로 정의 |
| state 초기값           | `0`                    |
| FIR 출력 길이 정책     | `full convolution`     |
| decimator phase 기본값 | `0`                    |
| decimator 계수 기본값  | `2`                    |

### 5.1 FIR 계수 포맷 확정 근거

- `signed Q1.15`의 표현 범위는 `[-1.0, 0.999969482421875]`이다.
- `sim/python/inspect_kaiser_coeff.py` 기준, 데모 대상 탭 수의 계수 범위는 아래와 같다.

| 탭 수 | 계수 최대 | 계수 최소 | 계수 합산 |
| --- | ---: | ---: | ---: |
| `N=5`  | `0.563193` | `0.002685`  | `1.000000` |
| `N=15` | `0.400477` | `-0.038187` | `1.000000` |
| `N=35` | `0.399919` | `-0.065541` | `1.000000` |
| `N=37` | `0.399868` | `-0.066569` | `1.000000` |
| `N=39` | `0.400015` | `-0.067482` | `1.000000` |
| `N=41` | `0.400133` | `-0.068268` | `1.000000` |
| `N=43` | `0.400053` | `-0.068920` | `1.000000` |

- 현재 데모 대상 탭 수(`N=5/15/35/37/39/41/43`) 모두에서 계수 최소/최대/합산 결과가 `Q1.15` 범위 안에 들어간다.
- 따라서 FIR 계수 저장 포맷은 `signed 16-bit, Q1.15`로 확정한다.
- 이 결정은 입력 멀티톤의 진폭/headroom과 직접 연결되는 샘플 포맷 결정과는 분리한다.

### 5.2 입력 신호 포맷 확정 근거

- 입력 신호 포맷도 `signed 16-bit, Q1.15`로 확정한다.
- 표현 범위는 `[-1.0, +0.999969482421875]`, 분해능은 `2^-15 ~= 0.0000305`이다.
- coefficient와 동일한 `Q1.15`를 사용하면 내부 곱셈 결과를 일관되게 `Q2.30`으로 해석할 수 있다.
- 16-bit 양자화 SNR은 약 `96 dB`로, 현재 저지대역 감쇠 목표 `As = 60 dB`를 충분히 상회한다.
- 확장 데모에서 16-bit ADC 입력을 정규화해 붙일 때도 인터페이스를 바꾸지 않아도 된다.

### 5.3 Bring-up 입력 생성 계약

- 현재 기준 입력 신호는 bring-up용 deterministic 3-tone sine이다.
- tone 주파수는 `5 MHz`, `20 MHz`, `30 MHz`로 고정한다.
- 각 tone 진폭은 `0.3`, 위상은 모두 `0`이다.
- 샘플 수는 `8192`, 생성 dtype은 `np.float64`, 최종 저장은 `1-D np.int16 ndarray`이다.
- 입력 양자화는 멀티톤 합산 후 1회만 수행한다.
- 입력 양자화는 `round-to-nearest, ties-away-from-zero` 후 `clip(-32768, 32767)`를 적용한다.
- 추가 정규화는 수행하지 않는다.

### 5.4 계수 양자화 및 누산기 폭 근거

- FIR 계수도 입력과 동일하게 `float64 -> scale by 2^15 -> round-to-nearest with ties-away-from-zero -> clip(-32768, 32767) -> int16` 규칙으로 양자화한다.
- 계수 양자화 후 합이 정확히 `1.0`이 되도록 추가 재정규화하지 않는다.
- `N=43` 계수의 `sum(abs(h_q)) = 56025`, `max|x_q| = 32768`으로 두면, 현재 스펙 기준 누산 상한은 아래와 같다.

$$
\max |acc| \le 32768 \cdot 56025 = 1,835,827,200
$$

- 이 값은 signed `32-bit` 범위 안에 들어가므로, 현재 `N=43` 기준 최소 누산 폭은 signed `32-bit`이다.
- 다만 RTL 구현은 DSP 경로와 정렬하기 위해 signed `48-bit` accumulator를 사용해도 무방하다.
- full convolution은 출력 길이를 늘릴 뿐, 한 출력 샘플의 최대 누산 항 개수는 tap 수(`N`)를 넘지 않으므로 누산기 폭 결정 기준은 per-sample MAC bound이다.

## 6. 인터페이스 정책

| 항목                                     | 현재 정책 |
| ---------------------------------------- | --------- |
| 입력 `x` 형상                          | `1-D`   |
| 입력 `h` 형상                          | `1-D`   |
| 빈 입력 `x` 처리                       | 빈 `np.int16` 배열 반환 |
| 빈 계수 `h` 처리                       | `ValueError` |
| `NaN/Inf` 입력 처리                    | integer dtype만 허용하므로 해당 없음 |
| 비정수 dtype 입력 처리                   | `TypeError` |
| `m < 1` 처리                           | `ValueError` |
| `phase` 범위 위반 처리                 | `ValueError` |
| `return_intermediate` 비-`bool` 처리 | `TypeError` |

## 7. ideal 모델과의 관계

- ideal 모델은 알고리즘 기준선(reference)이다.
- fixed/golden 모델은 RTL bit-exact 판정 기준이다.
- 블록 순서는 ideal과 동일하게 `FIR -> Decimator`를 유지한다.
- 차이점은 아래 항목에서 발생한다:
  - 데이터 표현
  - rounding
  - saturation
  - overflow

## 8. 검증 기준 (fixed 단계)

### 8.1 기능 검증

- `Fs_out == Fs_in / M`가 성립해야 함.
- FIR 출력 길이:
  - `len(y_fir) == len(x) + len(h) - 1`
- Decimator 출력 길이:
  - `len(y_decim) == len(y_fir[phase::m])`
- `N = 5`와 `N = 43` 모두 동작해야 함.

### 8.2 bit-level 검증

- 동일 입력 벡터에 대해 Python golden 모델과 RTL 출력이 bit-exact로 일치해야 한다.
- 비교 기준 벡터 형식:
- 허용 오차:
- saturation/overflow 경계 케이스 포함 여부:

### 8.3 ideal-vs-fixed 비교

- 동일 입력 벡터에 대해 ideal 출력과 fixed 출력의 차이를 측정한다.
- 비교 지표:
  - PSD/FFT
  - SNR
  - MSE
- 추가 비교 지표:

## 9. 구현 체크리스트

- [X] `model/fixed/anti_alias_fir.py` 파일 생성
- [X] `model/fixed/decimator.py` 파일 생성
- [X] `model/fixed/fir_decimator_golden.py` 파일 생성
- [X] `anti_alias_fir_golden` 초기 구현 추가
- [X] `docs/spec/bringup_input_signal_spec.md` 기준으로 bring-up 입력 신호 제약 확정
- [X] 입력 quantization 정책 확정
- [X] 입력 rounding 정책 확정
- [X] 입력 saturation 정책 확정
- [X] overflow 정책 확정
- [X] decimator golden 구현
- [X] top-level golden 연결 구현
- [X] `sim/python/test/fixed` 테스트 확장

## 10. 미정 항목

| 항목                           | 현재 상태 | 비고                                                       |
| ------------------------------ | --------- | ---------------------------------------------------------- |
| bring-up 입력 신호 생성 제약  | 확정      | `5/20/30 MHz`, `A=0.3`, `phase=0`, `N=8192`, `headroom=0.1` |
| 입력 양자화 기준               | 확정      | `float64` 합산 후 1회 양자화, `ties-away-from-zero`, `clip(-32768, 32767)` |
| 계수 양자화 기준               | 확정      | 입력과 동일한 `ties-away-from-zero` 규칙 사용, 추가 재정규화 없음      |
| 39/41/43탭 기준 최종 demo 입력 신호 | 미정      | bring-up 이후 alias 시각화 목적에 맞춰 재설계 예정          |
| saturation 적용 지점           | 확정      | 최종 출력 배열 저장 시점에서만 1회 clip                    |
| overflow 정책                  | 확정      | intermediate wrap/saturation 없음, wide accumulator 사용   |
| accumulator 비트폭             | 확정      | 현재 `N=43` 기준 최소 signed `32-bit`, RTL 구현 목표는 signed `48-bit` |
| decimator 입력/출력 dtype 계약 | 확정      | FIR 출력과 동일하게 `np.int16` 유지                        |
