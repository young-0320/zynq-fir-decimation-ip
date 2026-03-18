# 07. Coefficient 기반 Stopband Spec Check

- 작성일: 2026-03-18
- 단계: 4
- 목적: 입력 신호와 무관하게 FIR coefficient 자체의 주파수 응답으로 `As >= 60 dB` 충족 여부를 재현 가능하게 판정한다

## 1) 이번 세션 핵심 결정

1. `As >= 60 dB` 판정은 멀티톤 입력 결과가 아니라 coefficient frequency response로 한다.
2. stopband 판정 기준은 `25 MHz` 한 점이 아니라 `f >= 25 MHz` 전체에서의 worst-case attenuation이다.
3. 현재 Kaiser 설계 구현 기준에서는 `N=39`, `N=41`가 모두 strict worst-case 기준에서 미달이며, `N=43`이 처음으로 `As >= 60 dB`를 만족한다.
4. 따라서 `N=41`은 near-spec 비교군으로 유지하고, 현재 공식 spec-check 대상은 `N=43`으로 갱신한다.

## 2) 왜 입력 신호와 분리해서 봐야 하는가

- 필터 스펙 질문: coefficient 응답 `|H(f)|`가 `f >= 25 MHz`에서 최소 `60 dB` 감쇠를 주는가
- 시스템 실험 질문: 실제 입력을 넣었을 때 alias가 얼마나 남는가

위 두 질문은 다르다.

- 첫 번째는 입력과 무관한 필터 자체 성질이다.
- 두 번째는 입력 스펙트럼과 진폭에 따라 달라지는 시스템 레벨 결과다.

따라서 `39/41/43` 탭 비교에서의 pass/fail은 멀티톤 입력이 아니라 coefficient 주파수 응답으로 판정해야 한다.

## 3) 재현 스크립트

추가한 스크립트:

- `sim/python/run_check_coeff_stopband_spec.py`

기능:

- 탭 수 리스트별 coefficient 생성
- `ideal float64 coefficient` 응답 계산
- `Q1.15 quantized coefficient` 응답 계산
- `f >= fs_hz` 전체 stopband worst-case attenuation 계산
- 결과를 `summary.json`, `summary.txt`, `.npy` artifact로 저장

생성 테스트:

- `sim/python/test/test_check_coeff_stopband_spec.py`

## 4) 재현 커맨드

```bash
cd /home/young/dev/10_zynq-fir-decimation-ip
.venv/bin/pytest -q sim/python/test/test_check_coeff_stopband_spec.py
.venv/bin/python -m sim.python.run_check_coeff_stopband_spec
```

기본 실행은 아래 탭 수를 함께 평가한다.

- `N=39`
- `N=41`
- `N=43`

기본 출력 디렉터리:

- `sim/output/coeff_stopband_spec_n39_n41_n43/`

주요 산출물:

- `summary.json`
- `summary.txt`
- `freq_hz.npy`
- `n39/n41/n43` 각각의 coefficient 및 magnitude response `.npy`

## 5) 비교 조건

### 설계 조건

- `Fs_in = 100 MHz`
- `fp = 15 MHz`
- `fs = 25 MHz`
- `As = 60 dB`
- Kaiser `beta = 5.65326`

### 수치 평가 조건

- 주파수 응답 계산: `scipy.signal.freqz`
- grid size: `524288`
- 주파수 분해능: 약 `95.367431640625 Hz`
- stopband 판정: `f >= 25 MHz`

## 6) 결과 요약

| N | ideal @25 MHz (dB) | ideal worst-case attenuation (dB) | ideal worst-case freq (MHz) | ideal pass/fail | quantized @25 MHz (dB) | quantized worst-case attenuation (dB) | quantized worst-case freq (MHz) | quantized pass/fail |
| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| `39` | `-71.270209` | `59.170829` | `25.463295` | fail | `-72.247199` | `59.325039` | `25.465679` | fail |
| `41` | `-60.384099` | `59.616800` | `25.153732` | fail | `-60.205999` | `59.446883` | `25.154400` | fail |
| `43` | `-60.248585` | `60.248585` | `25.000000` | pass | `-61.061039` | `61.061039` | `25.000000` | pass |

핵심 해석:

1. `N=41`은 `25 MHz` 한 점만 보면 `-60.384 dB`라서 통과처럼 보이지만, stopband 전체 worst-case는 `59.617 dB`이므로 strict 기준에서는 미달이다.
2. `N=39`은 `25 MHz`에서 더 깊게 떨어지더라도, stopband 안쪽의 다른 주파수에서 worst-case가 더 커져서 역시 미달이다.
3. `N=43`은 ideal과 quantized 모두에서 stopband worst-case가 `60 dB`를 넘는다.

## 7) 계수/고정소수점 관점의 추가 관찰

| N | coeff clip count | coeff max (float) | coeff min (float) | sum(abs(h_q15_float)) |
| --- | ---: | ---: | ---: | ---: |
| `39` | `0` | `0.400014611249` | `-0.067482120930` | `1.670349121094` |
| `41` | `0` | `0.400132621395` | `-0.068268305277` | `1.690795898438` |
| `43` | `0` | `0.400052770178` | `-0.068919703494` | `1.709747314453` |

해석:

- `N=43`까지도 coefficient는 `Q1.15` 범위를 넘지 않는다.
- 이번 spec 변경은 coefficient 포맷 변경이 아니라 tap 수 변경 문제다.
- `N=43`에서도 현재 fixed-point 가정(`signed 16-bit, Q1.15`)은 유지 가능하다.

## 8) 결론

현재 저장소의 Kaiser 설계 구현과 strict stopband 판정 기준(`f >= 25 MHz` worst-case)으로 보면:

- `N=39`: spec 미달
- `N=41`: near-spec이지만 미달
- `N=43`: spec 충족

따라서 현재 문서 기준에서는:

- `N=5`는 bring-up 전용
- `N=39/41`는 비교/평가용
- `N=43`는 공식 spec-check 대상

으로 해석하는 것이 가장 정직하고 재현 가능하다.

## 9) 다음 액션

1. `ideal-vs-fixed` 비교의 공식 tap 수를 `N=43`까지 확장한다.
2. `N=39`, `N=41`, `N=43`의 alias 비교를 PSD/FFT로 나란히 기록한다.
3. 이후 RTL 기준선도 `N=43`을 기본 candidate로 맞춘다.
