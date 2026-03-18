# 06. Ideal vs Fixed 비교 (N=5)

- 작성일: 2026-03-18
- 단계: 4
- 목적: bring-up `N=5` 조건에서 `ideal(float64)` 모델과 `fixed(Q1.15)` golden 모델의 출력 차이를 정량 비교한다
- 후속 업데이트(2026-03-18): 이후 `docs/log/07_coeff_stopband_spec_check.md`에서 현재 공식 spec-check tap이 `N=43`으로 정리되었다. 아래의 초기 `N=41` 후속 작업 메모는 당시 기준 기록이며, 현재는 `N=43` 기준 확장이 우선이다.

## 1) 이번 세션 핵심 결정

1. `Q1.15` 양자화/복원 로직을 `model/q1_15.py`로 분리했다.
2. ideal-vs-fixed 비교는 단일 기준선 하나가 아니라 아래 2개 기준선을 함께 본다.
   - `vs_ideal_raw`: raw `float64` 입력/계수 기준
   - `vs_quantized_reference`: `Q1.15`로 양자화한 입력/계수를 다시 `float64`로 복원한 기준
3. 위 2개 기준선을 함께 두면 아래 2가지를 분리해서 해석할 수 있다.
   - 입력/계수 양자화까지 포함한 총 오차
   - 양자화된 입력/계수를 고정했을 때 fixed arithmetic 자체의 오차

## 2) 비교 조건

### 입력 조건

- 샘플 수: `8192`
- 입력 주파수: `Fs_in = 100 MHz`
- 멀티톤: `5 MHz`, `20 MHz`, `30 MHz`
- 진폭: `0.3`, `0.3`, `0.3`
- 위상: `0`, `0`, `0`

### 필터 조건

- 탭 수: `N = 5`
- `fp = 15 MHz`
- `fs = 25 MHz`
- `As = 60 dB`
- Kaiser window 기반 LPF

### 체인 조건

- 처리 순서: `FIR -> Decimator`
- decimation 계수: `M = 2`
- phase: `0`

## 3) 비교 기준 정의

### A. `vs_ideal_raw`

- ideal 경로 입력: raw `x_float`
- ideal 경로 계수: raw `h_float`
- fixed 경로 입력: `x_q15`
- fixed 경로 계수: `h_q15`
- 해석: 실제 fixed-point 설계가 raw ideal 기준선에서 얼마나 벗어나는지 본다

### B. `vs_quantized_reference`

- ideal 경로 입력: `dequantize(x_q15)`
- ideal 경로 계수: `dequantize(h_q15)`
- fixed 경로 입력: `x_q15`
- fixed 경로 계수: `h_q15`
- 해석: 입력/계수 양자화는 고정하고, fixed arithmetic/rounding/saturation 오차를 더 직접적으로 본다

## 4) 사용 스크립트와 산출물

실행 스크립트:

- `sim/python/run_compare_ideal_vs_fixed.py`

주요 helper:

- `model/q1_15.py`

결과 저장 위치:

- `sim/output/ideal_vs_fixed_n5/`

## 5) 수치 결과 요약

### 입력/계수 상태

| 항목                         |                    값 |
| ---------------------------- | --------------------: |
| input peak                   |      `0.6633390081` |
| input RMS                    |      `0.3674165535` |
| input Q1.15 clipping count   |                 `0` |
| input q15 peak               |             `21736` |
| coeff sum (float)            |               `1.0` |
| coeff sum (q15 -> float)     | `1.000030517578125` |
| coeff abs sum (float)        |               `1.0` |
| coeff abs sum (q15 -> float) | `1.000030517578125` |
| coeff Q1.15 clipping count   |                 `0` |

해석:

- 입력과 계수 모두 `Q1.15` 양자화에서 clipping이 발생하지 않았다.
- 양자화된 계수 합은 `1 + 1 LSB` 수준으로, 계수 양자화 후 재정규화를 하지 않는 현재 정책과 일치한다.

### FIR stage 비교

| Metric      |           vs_ideal_raw | vs_quantized_reference |
| ----------- | ---------------------: | ---------------------: |
| MAE         | `6.477226985084e-06` | `6.966726248107e-06` |
| MSE         | `6.353198677897e-11` | `6.369383319890e-11` |
| RMSE        | `7.970695501584e-06` | `7.980841634746e-06` |
| max_abs_err | `2.107295735186e-05` | `1.473724842072e-05` |
| mean_err    | `5.681333913771e-09` | `2.338305995661e-09` |
| SNR (dB)    |          `90.585212` |          `90.574220` |

### Decimator stage 비교

| Metric      |           vs_ideal_raw | vs_quantized_reference |
| ----------- | ---------------------: | ---------------------: |
| MAE         | `6.791356190727e-06` | `6.818118027474e-06` |
| MSE         | `8.017855238244e-11` | `6.832555999446e-11` |
| RMSE        | `8.954247728449e-06` | `8.265927654804e-06` |
| max_abs_err | `2.107295735186e-05` | `1.473724842072e-05` |
| mean_err    | `5.828642122691e-09` | `1.795829913278e-09` |
| SNR (dB)    |          `87.606072` |          `88.300888` |

### LSB 기준 정밀도 손실 해석

`Q1.15`의 1 LSB는 `1 / 32768 = 3.0517578125e-05` 이다.

| Reference                  | Stage | RMSE (LSB) |  MAE (LSB) | max_abs_err (LSB) |
| -------------------------- | ----- | ---------: | ---------: | ----------------: |
| `vs_ideal_raw`           | FIR   | `0.2612` | `0.2122` |        `0.6905` |
| `vs_ideal_raw`           | Decim | `0.2934` | `0.2225` |        `0.6905` |
| `vs_quantized_reference` | FIR   | `0.2615` | `0.2283` |        `0.4829` |
| `vs_quantized_reference` | Decim | `0.2709` | `0.2234` |        `0.4829` |

해석:

- 모든 경우에서 `RMSE < 0.3 LSB` 수준이다.
- 최악 오차도 `1 LSB` 미만이다.
- 즉 현재 `N=5` bring-up 조건에서는 fixed 출력이 `Q1.15` 분해능 안에서 매우 안정적으로 동작한다.

## 6) 해석

1. `N=5` bring-up 조건에서 fixed 모델의 출력 오차는 매우 작다.
2. 최대 오차도 `2.11e-05` 이하로, `Q1.15`의 1 LSB(`≈ 3.05e-05`)보다 작다.
3. LSB 기준으로 봐도 `RMSE < 0.3 LSB`, `max_abs_err < 1 LSB`라서 정밀도 손실이 작다.
4. `vs_quantized_reference`의 `max_abs_err`가 더 작다는 점은, raw ideal 대비 오차의 일부가 입력/계수 양자화에서 온다는 해석과 맞다.
5. `vs_quantized_reference` 기준 decimator SNR이 `88.30 dB`로, 현재 bring-up 조건에서는 fixed arithmetic에 의한 열화가 크지 않다.

## 7) 결론

현재 `N=5` bring-up 조건에서는:

- fixed golden 모델이 ideal 모델을 매우 잘 근사한다
- 입력/계수 양자화와 fixed arithmetic을 포함한 총 오차도 작다
- 양자화된 입력/계수를 기준선으로 두면 arithmetic 오차는 더욱 작게 보인다

즉, 현재 fixed path는 다음 단계(`N=43` ideal-vs-fixed 확장, alias 비교, RTL 기준선 준비`)로 넘어갈 만한 품질을 보인다.

## 8) 다음 액션

1. coefficient-based stopband 기준으로 선택된 `N=43`에 대해 동일 비교를 확장한다.
2. `N=5`와 `N=43`의 ideal-vs-fixed 지표를 나란히 비교하고, 필요하면 `N=39/41`를 비교군으로 추가한다.
3. `downsample only` 대비 `FIR -> decimation`의 PSD/FFT alias 비교를 문서화한다.
4. RTL 비교를 염두에 두고 vector dump 형식을 구체화한다.

## 9) 재현 커맨드

```bash
cd /home/young/dev/10_zynq-fir-decimation-ip
.venv/bin/pytest -q
.venv/bin/python -m sim.python.run_compare_ideal_vs_fixed
```
