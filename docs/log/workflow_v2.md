# FIR Decimation 프로젝트 워크플로우 v2

- 작성일: 2026-03-09
- 목적: fixed-point golden model 단계(model/fixed)를 재현 가능하게 운영

## 1) 완료 조건 (Definition of Done)

1. `model/fixed`에 Q4.12 기반 golden model이 구현되어 있음.
2. fixed/golden 출력이 ideal reference 대비 합의된 오차 또는 bit-exact 기준으로 검증 완료됨.
3. quantization, rounding, saturation, overflow 처리 정책이 문서에 명시되어 있음.
4. `sim/python/test/fixed` 기준 테스트가 통과함.
5. fixed 단계 실험 결과(정량 지표 + 재현 명령어 + 산출물 경로)가 문서에 남아 있음.

## 2) 주간 루틴

1. 월-화: fixed-point 포맷/연산 정책 정리 및 구현.
2. 수-목: ideal vs fixed 비교 테스트, 오차 분석(SNR, MSE, max error).
3. 금: 로그 정리(`docs/log/*.md`) + 다음 주 TODO 확정.
4. 주말: Velog 초안 업데이트(결정-근거-결과 구조).

## 3) 하루 운영 규칙 (아날로그 노트 병행)

1. 노트에는 자유롭게 사고/스케치 작성.
2. 하루 마감 10분 동안 아래 5줄을 `docs/log`에 전사:
   - 오늘 결정 1개
   - 근거 수치 1개
   - 실패/수정 1개
   - 재현 명령어 1줄
   - 다음 액션 1개

## 4) 산출물 위치 규칙

1. 스펙/의사결정: `docs/ideal_model_spec.md`, `docs/log/*.md`, 추후 fixed 정책 문서
2. ideal 기준 모델: `model/ideal/*.py`
3. fixed/golden 모델: `model/fixed/*.py`
4. fixed 테스트: `sim/python/test/fixed/*.py`
5. ideal-vs-fixed 비교 스크립트: `sim/python/*.py`
6. 이미지/그래프: `docs/asset/*`

## 5) 의사결정 기록 템플릿

1. 문제 정의
2. 제약 조건(비트폭/오차/재현성/RTL 대응)
3. 대안(A/B/C)
4. 선택안
5. 근거 데이터(숫자/리포트)
6. 트레이드오프와 후속 계획

## 6) 품질 게이트 (각 단계 공통)

1. 코드 실행 가능 (`uv run` 또는 `.venv/bin/python -m pytest` 기준)
2. 입력 검증/예외 처리 존재
3. 테스트 최소 1개 이상 추가
4. 결과 수치가 문서에 기록됨
5. 재현 명령어가 문서에 존재함

## 7) 업데이트 정책

1. `workflow_v2.md`는 주 1회만 수정(운영 흔들림 방지).
2. 실험/결정 기록은 `docs/log`에 매일 누적.
3. v2의 스코프는 fixed-point golden model 단계까지로 한정한다.
4. RTL 단계부터는 별도 워크플로우 문서(v3)를 추가하는 것을 기본 원칙으로 한다.
