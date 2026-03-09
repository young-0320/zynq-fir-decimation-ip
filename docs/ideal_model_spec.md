# FIR Decimator Ideal Model Spec

## 1. 목적

본 문서는 `model/ideal`에 구현할 부동소수점(ideal) 기준 모델의 동작 사양을 정의한다.

- 대상: `FIR anti-aliasing + decimation(M=2)` 파이프라인
- 용도: 알고리즘 성능 검증, 고정소수점(golden) 모델 및 RTL 비교의 상위 참조
- 비대상: 비트 정확도(bit-exact), 오버플로/포화, 고정소수점 양자화 모델링

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
  - 제출용: `N = 41`

## 3. 블록 정의

### 3.1 Anti-alias FIR

- 선형 위상 저역통과 FIR.
- 입력 `x[n]`에 대해 아래 수식을 따른다.

$$
y_{\mathrm{fir}}[n] = \sum_{k=0}^{N-1} h[k] \cdot x[n-k]
$$

- `x[n-k]`의 범위가 입력 밖이면 0으로 간주한다.
- 출력은 full convolution을 유지하며, 초기 과도응답과 tail을 그대로 포함한다.
- ideal 모델에서는 계수/연산 모두 `float64`를 사용한다.

### 3.2 Decimator

- FIR 출력 `y_fir[n]`를 `M`배 다운샘플링한다.
- 위상 `phase` 기본값은 0.

$$
y_{\mathrm{decim}}[r] = y_{\mathrm{fir}}[rM + \mathrm{phase}]
$$

- 기본 정책: `phase = 0`, `M = 2`.

### 3.3 Top-level Ideal Reference

- 처리 순서는 반드시 아래를 따른다.

  1. `anti-aliasing`
  2. `decimation`
- 즉, `downsample only`는 본 기준 모델의 기본 경로가 아니다(비교 실험용 경로로만 허용).
- 비교용 `downsample only` baseline 경로는 `sim/downsample_only_ideal.py`에서 별도로 다룬다.

## 4. 모듈/파일 계약

### 4.1 `model/ideal/design_kaiser_coeff.py`

필수 제공 함수:

- `design_kaiser_lpf(fs_in_hz, fp_hz, fs_hz, as_db, num_taps=None) -> np.ndarray`
  - 반환: `float64` FIR 계수 `h` (길이 `N`, odd 권장)
  - 역할: Kaiser window 기반 LPF 계수 설계 전용 모듈

### 4.2 `model/ideal/anti_alias_fir.py`

필수 제공 함수:

- `anti_alias_fir_ideal(x, h) -> np.ndarray`
  - 입력 `x`, `h`를 받아 causal FIR 출력을 반환
  - 입력/계수는 `np.ndarray` 1-D 배열로 받는다
  - 내부 연산 및 반환 dtype은 `np.float64`
  - 반환 길이는 full convolution 기준 `len(y) = len(x) + len(h) - 1`
  - `x`가 빈 배열이면 빈 `float64` 배열을 반환한다
  - 계수 `h`는 외부에서 주입받는다

### 4.3 `model/ideal/decimator.py`

필수 제공 함수:

- `decimate(x, m=2, phase=0) -> np.ndarray`
  - 입력 `x`는 `np.ndarray` 1-D 배열로 받는다
  - 내부 연산 및 반환 dtype은 `np.float64`
  - 구현 기준: `x[phase::m]`
  - 입력 검증:
    - `x`는 finite 값만 포함해야 함
    - `m`과 `phase`는 `int`
    - `m >= 1`
    - `0 <= phase < m`
  - `phase=0`이면 `0, 2, 4, ...`, `phase=1`이면 `1, 3, 5, ...` 인덱스를 선택한다 (`m=2` 기준)

### 4.4 `model/ideal/fir_decimator_ideal.py`

필수 제공 함수:

- `run_fir_decimator_ideal(x, h, m=2, phase=0, return_intermediate=False)`
  - 내부에서 FIR 후 decimation 수행
  - `return_intermediate`는 `bool`이어야 함
  - 기본값(False)에서는 `y_decim`만 반환
  - `return_intermediate=True`일 때 `(y_fir, y_decim)` 튜플을 반환

### 4.5 `sim/downsample_only_ideal.py`

비교 실험용 제공 함수:

- `run_downsample_only_ideal(x, m=2, phase=0) -> np.ndarray`
  - FIR 없이 입력을 바로 decimation하는 baseline 경로
  - anti-alias FIR 유무에 따른 alias 차이 비교용으로만 사용한다

## 5. 데이터 타입 및 수치 정책

- 기본 dtype: `np.float64`
- 스케일링: 입력 스케일은 호출자가 관리(모델 내부에서 자동 정규화하지 않음)
- NaN/Inf 입력은 지원하지 않음(검증 단계에서 에러 처리)
- ideal 모델에서는 clipping/saturation/rounding을 수행하지 않음

## 6. 검증 기준 (ideal 단계)

### 6.1 기능 검증

- `Fs_out == Fs_in / M`가 항상 성립해야 함.
- FIR 출력 길이:
  - `len(y_fir) == len(x) + len(h) - 1`
- Decimator 출력 길이:
  - `len(y_decim) == len(y_fir[phase::m])`
- `downsample only` baseline 출력 길이:
  - `len(y_downsample_only) == len(x[phase::m])`

### 6.2 주파수 특성 검증

- 설계된 FIR의 응답이 아래를 만족해야 함(수치 오차 허용 범위 내):
  - 통과대역 ripple: 프로젝트에서 정한 한계 이하
  - 저지대역 감쇠: `>= 60 dB`

### 6.3 비교 실험 검증

- `downsample only` 대비 `FIR -> downsample` 경로에서 alias 억제가 PSD/FFT로 관찰되어야 함.

## 7. 향후 golden 모델과의 관계

- ideal 모델은 알고리즘 기준선(reference)이다.
- `model/fixed/fir_decimator_golden.py`는 Q4.12 고정소수점 및 RTL bit-exact 판정 기준이다.
- golden 모델은 ideal 모델과 동일한 처리 순서(FIR 후 decimation)를 반드시 유지한다.

## 8. 구현 체크리스트

- [ ] `design_kaiser_coeff.py`에 Kaiser 기반 LPF 계수 설계 함수 구현
- [ ] FIR 적용 함수 구현(초기 상태 0, full convolution 출력)
- [ ] Decimation 함수 구현(`x[phase::m]`)
- [ ] Top-level 연결 함수 구현
- [ ] 멀티톤 입력으로 alias 억제 동작 확인
- [ ] N=5, N=41 모두 동작 확인
