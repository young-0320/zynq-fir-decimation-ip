# FIR Decimation 설계 결정 요약

- sync 시점: 2026-03-09
- 목적: 프로젝트의 핵심 설계 결정을 한 번에 복기할 수 있는 단일 요약 문서
- 사용 원칙:
  - 설계 기록은  `docs/log/*.md`
  - 인터페이스/동작 계약은 `docs/*_spec.md`
  - 이 문서는 중요한 설계 결정만 추려서 현재 기준으로 정리한다

## 1) 시스템/알고리즘 스펙

| 항목               | 현재 결정                         | 상태 | 근거/출처                                                                  |
| ------------------ | --------------------------------- | ---- | -------------------------------------------------------------------------- |
| 입력 샘플링 주파수 | `Fs_in = 100 MHz`               | 확정 | `1 sample/cycle @ 100MHz` 처리율 목표. 계획서, `01_spec_and_kaiser.md` |
| 디시메이션 계수    | `M = 2`                         | 확정 | 출력 `Fs_out = 50 MHz` 목표. 계획서, `01_spec_and_kaiser.md`           |
| 출력 샘플링 주파수 | `Fs_out = 50 MHz`               | 확정 | `Fs_in / M`. 계획서, `ideal_model_spec.md`                             |
| 통과대역 경계      | `fp = 15 MHz`                   | 확정 | 천이대역 `10 MHz` 확보. 계획서, `01_spec_and_kaiser.md`                |
| 저지대역 시작      | `fs = 25 MHz`                   | 확정 | 출력 나이퀴스트 경계. 계획서,`01_spec_and_kaiser.md`                     |
| 목표 감쇠          | `As >= 60 dB`                   | 확정 | alias 억제 `1/1000` 수준 목표. 계획서, `01_spec_and_kaiser.md`         |
| 필터 설계법        | Kaiser window                     | 확정 | 재현성 확보 목적. 계획서,`01_spec_and_kaiser.md`                         |
| 탭 수 정책         | bring-up `N=5`, 제출용 `N=41` | 확정 | Kaiser 추정 + 여유 확보. 계획서,`01_spec_and_kaiser.md`                  |
| 처리 순서          | `Anti-alias FIR -> Decimator`   | 확정 | alias 억제는 FIR가 담당.`ideal_model_spec.md`, `01_spec_and_kaiser.md` |

## 2) Ideal Python 모델 결정

| 항목                 | 현재 결정                                                | 상태      | 근거/출처                                                        |
| -------------------- | -------------------------------------------------------- | --------- | ---------------------------------------------------------------- |
| 기준 dtype           | `np.float64`                                           | 구현 완료 | `ideal_model_spec.md`                                          |
| FIR 입력/계수 타입   | `np.ndarray` 1-D                                       | 구현 완료 | `02_spec.md`, `anti_alias_fir.py`                            |
| FIR 출력 정책        | causal full convolution                                  | 구현 완료 | `02_spec.md`, `anti_alias_fir.py`                            |
| FIR 출력 길이        | `len(x) + len(h) - 1`                                  | 구현 완료 | `ideal_model_spec.md`, `anti_alias_fir.py`                   |
| FIR 경계 처리        | 입력 밖 `x[n-k]`는 0으로 간주                          | 구현 완료 | `ideal_model_spec.md`, `anti_alias_fir.py`                   |
| FIR 과도응답/tail    | 숨기지 않고 그대로 유지                                  | 구현 완료 | `02_spec.md`, `anti_alias_fir.py`                            |
| FIR 유효성 검증      | `_validate_x`, `_validate_h` private helper          | 구현 완료 | `02_spec.md`, `anti_alias_fir.py`                            |
| Decimator 구현       | `x[phase::m]`                                          | 구현 완료 | `ideal_model_spec.md`, `decimator.py`                        |
| Decimator 기본값     | `m=2`, `phase=0`                                     | 구현 완료 | `ideal_model_spec.md`, `02_spec.md`, `decimator.py`        |
| `phase` 의미       | 몇 번째 샘플부터 살릴지 정하는 오프셋                    | 구현 완료 | `ideal_model_spec.md`, `02_spec.md`                          |
| Top-level 경로       | `run_fir_decimator_ideal(x, h, m=2, phase=0)`          | 구현 완료 | `fir_decimator_ideal.py`, `ideal_model_spec.md`              |
| 중간 출력 옵션       | `return_intermediate=True`면 `(y_fir, y_decim)` 반환 | 구현 완료 | `fir_decimator_ideal.py`, `ideal_model_spec.md`              |
| 비교용 baseline 경로 | `run_downsample_only_ideal(x, m=2, phase=0)`           | 구현 완료 | `sim/python/downsample_only_ideal.py`, `ideal_model_spec.md` |

## 3) Fixed / Golden 모델 결정

| 항목             | 현재 결정                                          | 상태      | 근거/출처                        |
| ---------------- | -------------------------------------------------- | --------- | -------------------------------- |
| 데이터/계수 포맷 | `16-bit signed, Q4.12`                           | 작업 가정 | 입력 신호 제약 확정 전 임시 가정. `01_spec_and_kaiser.md`, `fixed_model_spec.md` |
| 역할             | ideal 기준선과 RTL 사이 bit-exact/golden reference | 설계 확정 | 계획서,`ideal_model_spec.md`   |
| 처리 순서        | ideal과 동일하게 `FIR -> Decimator` 유지         | 설계 확정 | 계획서,`ideal_model_spec.md`   |

## 4) RTL / FPGA 계획 결정

| 항목             | 현재 결정                                                         | 상태             | 근거/출처            |
| ---------------- | ----------------------------------------------------------------- | ---------------- | -------------------- |
| 목표 처리율      | `1 sample/cycle @ 100MHz`                                       | 계획서 기준 확정 | 계획서               |
| RTL FIR 구조     | Transposed form                                                   | 계획서 기준 확정 | 계획서 2단계 설명    |
| 구조 선택 이유   | 파이프라인 레지스터 삽입이 자연스럽고 `Fmax 100MHz` 달성에 유리 | 계획서 기준 확정 | 계획서 2단계 설명    |
| PPA 우선순위     | DSP 사용량 최소화 우선,`Fmax/throughput` 방어                   | 계획서 기준 확정 | 계획서 3, 5단계 설명 |
| bring-up 전략    | `N=5`로 먼저 동작 확인 후 `N=41` 확장                         | 계획서 기준 확정 | 계획서 3단계 설명    |
| Baseline 비교군  | Naive RTL, FIR Compiler                                           | 계획서 기준 확정 | 계획서 5단계 설명    |
| 타겟 보드        | Zybo Z7-20                                                        | 계획서 기준 확정 | 계획서, 예산 항목    |
| 시스템 실증 방식 | PS-PL + AXI DMA + bare-metal C                                    | 계획서 기준 확정 | 계획서 6단계 설명    |

## 5) 검증 / 비교 실험 계획

| 항목                    | 현재 결정                                          | 상태             | 근거/출처                      |
| ----------------------- | -------------------------------------------------- | ---------------- | ------------------------------ |
| ideal 단계 단위테스트   | FIR, decimator, top-level, Kaiser 설계 함수 테스트 | 구현 완료        | `sim/python/test/ideal/*.py` |
| Python vs RTL 비교 방식 | Python golden model과 RTL 출력 bit-exact 자동 비교 | 계획서 기준 확정 | 계획서 1, 4단계 설명           |
| alias 비교 실험         | `downsample only` vs `FIR -> downsample`       | 설계 확정        | 계획서,`ideal_model_spec.md` |
| 비교 지표               | PSD/FFT, SNR, MSE                                  | 설계 확정        | 계획서                         |
| 공개 자산화             | GitHub, Velog, YouTube                             | 계획서 기준 확정 | 계획서 4, 7단계 설명           |

## 6) 미정 항목

| 항목                                         | 현재 상태 | 비고                                              |
| -------------------------------------------- | --------- | ------------------------------------------------- |
| 입력 신호 생성 제약(톤 개수/진폭/위상/headroom) | 미정      | `input_signal_spec.md`와 workflow v2에서 확정 예정 |
| 멀티톤 입력의 구체적 주파수 조합             | 미정      | 입력 신호 확정 단계에서 함께 결정 예정            |
| Q 포맷 최종 확정                             | 미정      | 입력 신호 제약과 동적 범위 분석 뒤 확정 예정      |
| symmetry 활용 RTL 세부 구조                  | 미정      | Transposed form 구현 세부 설계 단계에서 확정 예정 |
| AXI-Stream wrapper 및 backpressure 세부 동작 | 미정      | RTL/SoC 통합 단계에서 확정 예정                   |
