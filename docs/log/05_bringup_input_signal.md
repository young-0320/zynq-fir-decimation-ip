# 05. Bring-up 입력 신호 계약 확정

- 작성일: 2026-03-11
- 단계: 2
- bring-up multitone input profile 결정
- 후속 업데이트(2026-03-18): bring-up 입력 프로파일은 그대로 유지되며, 이후 최종 데모 / alias 시각화 대상 tap 후보는 `N=39/41/43`로 본다.

## 1) 이번 세션 핵심 결정

1. 현재 입력 신호는 bring-up용 deterministic 3-tone sine으로 확정했다.
2. 입력 길이는 `8192`, 출력 배열 계약은 `1-D ndarray`로 확정했다.
3. 톤 주파수는 `5 MHz`, `20 MHz`, `30 MHz`, 각 진폭은 `0.3`, 위상은 모두 `0`으로 확정했다.
4. 입력 생성 dtype은 `np.float64`, 최종 저장 포맷은 `signed 16-bit, Q1.15`로 확정했다.
5. 양자화는 멀티톤 합산 후 1회만 수행하고, rounding은 `round-to-nearest, ties-away-from-zero`, saturation은 `clip(-32768, 32767)`로 확정했다.
6. 추가 정규화는 수행하지 않기로 결정했다.

## 2) 확정 프로파일

| 항목            | 확정값                                    |
| --------------- | ----------------------------------------- |
| 목적            | bring-up 동작 확인                        |
| 파형 종류       | `sine`                                  |
| 샘플 수         | `8192`                                  |
| 생성 dtype      | `np.float64`                            |
| 출력 배열       | `1-D ndarray`                           |
| 저장 포맷       | `signed 16-bit, Q1.15`                  |
| tone 개수       | `3`                                     |
| 주파수          | `5 MHz`, `20 MHz`, `30 MHz`         |
| 각 tone 진폭    | `0.3`, `0.3`, `0.3`                 |
| 위상            | `0`, `0`, `0`                       |
| headroom budget | `0.1`                                   |
| 추가 정규화     | 없음                                      |
| 양자화 시점     | 합산 후 1회                               |
| rounding 모드   | `round-to-nearest, ties-away-from-zero` |
| saturation 범위 | `clip(-32768, 32767)`                   |

## 3) 입력 생성 수식

$$
x[n] = \sum_{k=0}^{2} A_k \sin\left(2\pi \frac{f_k}{F_s} n + \phi_k\right)
$$

- `Fs = 100e6`
- `A = [0.3, 0.3, 0.3]`
- `f = [5e6, 20e6, 30e6]`
- `phi = [0, 0, 0]`
- `n = 0, 1, ..., 8191`

## 4) 결정 근거

### 1. bring-up 용도로 충분히 단순하다

- `3`-tone 구성은 파형/스펙트럼 해석이 어렵지 않다.
- `phase=0`은 재현성이 높고 디버깅이 단순하다.
- `8192 = 2^13` 길이는 메모리/버퍼/벡터 파일 관리가 편하다.

### 2. 대역별 자극을 최소 구성으로 포함한다

1. `5 MHz`: passband 대표
1. `20 MHz`: transition band 대표
1. `30 MHz`: stopband 대표
1. 이 profile은 alias가 가장 잘 분리되는 최종 데모 벡터는 아니지만, bring-up 단계에서는 대역별 반응 확인에 충분하다.

### 3. 양자화 규칙을 명시적으로 닫아 bit-exact 혼선을 줄인다

1. `ties-away-from-zero`는 signed 데이터에서 규칙 해석이 직관적이다.
1. `clip(-32768, 32767)`를 함께 명시하면 `int16` 변환 경계가 모호하지 않다.
1. 톤별 양자화가 아니라 합산 후 1회 양자화를 사용하면 불필요한 quantization noise를 줄일 수 있다.
1- 4. 추가 정규화를 금지해 amplitude 계약을 보존한다

- 각 tone 진폭을 `0.3`으로 명시했으면, 합성 후 다시 normalize하면 이 계약이 깨진다.
- 따라서 amplitude 합 `0.9`, headroom budget `0.1`은 설계 budget으로 그대로 유지한다.

## 5) 후속 액션

1. 현재 profile은 bring-up용으로 사용한다.
2. `N=39/41/43` 탭 기준 최종 데모용 입력 신호는 alias 시각화 목적에 맞게 재구성한다.
3. 이후 RTL vector dump와 Python 비교 스크립트도 현재 계약을 기준으로 정렬한다.
