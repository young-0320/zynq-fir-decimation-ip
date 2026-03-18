# 08. Context / Workflow 문서 Sync

- 작성일: 2026-03-18
- 단계: 4
- 목적: `docs/log/07_coeff_stopband_spec_check.md` 이후의 현재 해석을 `PROJECT_CONTEXT`, workflow, 관련 로그에 동기화한다

## 1) 이번 세션에서 확인한 것

1. coefficient 기반 stopband spec-check 결과는 이미 `docs/log/07_coeff_stopband_spec_check.md`에 기록되어 있다.
2. 그러나 `PROJECT_CONTEXT.md`와 일부 초기 로그, `workflow_v4.md`에는 여전히 `N=41` 중심의 오래된 서술이 남아 있었다.
3. 실행 결과를 새로 추가로 만들 필요는 없었고, 이미 존재하는 `07`의 결론을 현재 컨텍스트와 워크플로우에 반영하는 것이 필요했다.

## 2) 이번 sync에서 반영한 내용

- `PROJECT_CONTEXT.md`를 현재 snapshot으로 갱신
- `workflow_v4.md`를 `07` 이후 상태 기준으로 갱신
- `01_spec_and_kaiser.md`에 후속 superseded note 추가
- `03_coeff_qformat.md`에 `N=43`까지 포함한 범위 note 추가
- `05_bringup_input_signal.md`의 최종 데모 tap 후보를 `39/41/43`으로 보정
- `06_ideal_vs_fixed_compare_n5.md`의 후속 액션을 현재 기준(`N=43`)으로 보정

## 3) 현재 문서 해석 기준

1. `N=5`는 bring-up용이다.
2. `N=39`, `N=41`는 비교/near-spec tap이다.
3. `N=43`은 현재 공식 coefficient-based spec-check tap이다.
4. filter quality/spec satisfaction과 implementation accuracy는 다른 질문이므로 문서에서도 분리해서 본다.

## 4) 아직 로그로 남지 않은 실험 결과

아래 결과는 아직 별도 실험 로그가 없다.

- `N=43` ideal-vs-fixed 비교 결과
- `N=5/39/41/43` PSD/FFT alias 비교 결과
- RTL bring-up 결과

즉, 현재 로그 공백은 "stopband spec-check"가 아니라 그 다음 단계 실험들에 있다.

## 5) 현재 기준 다음 액션

1. `N=5 RTL bring-up`을 시작한다.
2. `N=43` ideal-vs-fixed 비교 로그를 추가한다.
3. `N=5/39/41/43` alias 비교 로그를 추가한다.
