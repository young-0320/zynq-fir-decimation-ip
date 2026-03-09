# 02. Anti-alias FIR 기준 정리 + Full Convolution 확정

- 작성일: 2026-03-09
- 단계: 1
- ideal anti-alias FIR 구현/검증/문서 sync

## 1) 이번 세션 핵심 결정

1. `anti_alias_fir_ideal`의 입력/계수 계약을 `np.ndarray` 1-D 배열로 확정했다.
2. ideal anti-alias FIR 출력 정책을 `centered same-length`가 아니라 `causal full convolution`으로 확정했다.
3. ideal 모델에서는 초기 과도응답, tail, 필터 지연을 숨기지 않고 그대로 유지하기로 결정했다.
4. 입력 `x`와 계수 `h`의 유효성 검증은 모듈 내부 private helper (`_validate_x`, `_validate_h`)에서 수행하기로 결정했다.

## 2) 결정 근거

### 1. 입력/계수 타입을 `np.ndarray`로 좁힌 근거

- 실제 입력 생성이 멀티톤/FFT/PSD/필터 계수 주입까지 모두 `numpy` 흐름으로 이어지므로 `Sequence`를 넓게 허용할 실익이 거의 없음.
- ideal 모델 계약을 엄격하게 두는 편이 호출자와 테스트에서 더 명확함.
- 내부에서 `float64`로 통일하면 이후 golden/RTL 비교 시 dtype 기준선이 흔들리지 않음.

### 2. FIR 출력 정책을 full convolution으로 바꾼 근거

- ideal reference model은 하드웨어 동작과 비교 가능한 형태여야 하므로 causal FIR의 원형을 그대로 유지하는 편이 맞음.
- `centered same-length` 출력은 편의성은 있으나 필터 지연을 감추고, head/tail 출력을 잘라내어 RTL 기준선으로는 부적합함.
- 41탭 선형 위상 FIR 기준:
  - 과도응답/head-tail 길이: `L-1 = 40`
  - group delay: `(L-1)/2 = 20`
- 위 두 값은 서로 다른 물리량이므로 ideal 모델에서 둘 다 드러나게 두는 편이 해석과 검증에 유리하다고 판단.

### 3. 유효성 검증을 모듈 내부 helper로 둔 근거

- `anti_alias_fir.py`가 실제 공개 경계이므로 입력 계약 위반은 이 파일에서 즉시 잡는 편이 맞음.
- 현재는 `x`와 `h`의 검증 로직이 유사하지만, 이후 `h`에 홀수 탭 수/대칭성 등 추가 조건이 붙을 가능성이 있어 helper를 분리 유지하는 편이 안전함.
- ideal 단계에서는 clipping/saturation/rounding 없이 아래 항목만 검증하면 충분함:
  - `np.ndarray` 여부
  - 1-D 여부
  - `h` 비어 있지 않음
  - NaN/Inf 없음
  - 내부 `float64` 변환
