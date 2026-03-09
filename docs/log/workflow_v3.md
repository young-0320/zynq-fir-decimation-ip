# FIR Decimation 프로젝트 워크플로우 v3

- 작성일: 2026-03-09
- 목적: ideal reference model과 fixed-point golden model의 비교/정량 검증 단계를 재현 가능하게 운영

## 1) 완료 조건 (Definition of Done)

1. ideal과 fixed 출력이 동일 입력 벡터 기준으로 비교 가능하게 정렬되어 있음.
2. 합의된 비교 지표(SNR, MSE, max error, 필요 시 bit-exact 여부)가 산출되어 있음.
3. `downsample only` 대비 `FIR -> downsample` 경로의 alias 억제 효과가 PSD/FFT로 확인됨.
4. 비교 실험 스크립트와 재현 명령어가 문서에 남아 있음.
5. 결과 해석과 후속 액션이 `docs/log/*.md`에 정리되어 있음.

## 2) 주간 루틴

1. 월-화: ideal-vs-fixed 비교 스크립트 작성 및 테스트 벡터 정리.
2. 수-목: 정량 지표 산출(SNR, MSE, max error) 및 alias 비교 실험.
3. 금: 로그 정리(`docs/log/*.md`) + 다음 주 TODO 확정.
4. 주말: Velog 초안 업데이트(결정-근거-결과 구조).

## 3) 하루 운영 규칙

1. 하루 마감 10분 동안 아래 5줄을 `docs/log`에 전사:
   - 오늘 결정 1개
   - 근거 수치 1개
   - 실패/수정 1개
   - 재현 명령어 1줄
   - 다음 액션 1개

## 4) 산출물 위치 규칙

1. 스펙/의사결정: `docs/ideal_model_spec.md`, `docs/log/*.md`
2. ideal 기준 모델: `model/ideal/*.py`
3. fixed/golden 모델: `model/fixed/*.py`
4. 비교 테스트/스크립트: `sim/python/*.py`, `sim/python/test/*.py`
5. 결과 그래프/이미지: `docs/asset/*`

## 5) 의사결정 기록 템플릿

1. 문제 정의
2. 비교 조건(입력 벡터/정렬 기준/비교 지표)
3. 대안(A/B/C)
4. 선택안
5. 근거 데이터(숫자/리포트)
6. 트레이드오프와 후속 계획

## 6) 품질 게이트

1. 비교 스크립트가 재현 가능하게 실행됨
2. 비교 기준(정렬 방식, 오차 허용치, 지표)이 문서에 명시됨
3. 그래프나 수치 결과가 문서에 기록됨
4. 실험 실패 시 원인과 수정 방향이 로그에 남음
5. 다음 단계(RTL 비교)로 넘길 핵심 기준선이 정리됨

## 7) 업데이트 정책

1. `workflow_v3.md`는 주 1회만 수정(운영 흔들림 방지).
2. 실험/결정 기록은 `docs/log`에 매일 누적.
3. v3의 스코프는 ideal-vs-fixed 비교/정량 검증 단계까지로 한정한다.
4. RTL bit-exact 비교 단계부터는 별도 워크플로우 문서(v4)를 추가하는 것을 기본 원칙으로 한다.
