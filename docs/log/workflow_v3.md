# FIR Decimation 프로젝트 워크플로우 v3

- 작성일: 2026-03-11
- 목적: 입력 신호 제약을 바탕으로 fixed-point golden model 단계를 재현 가능하게 운영

## 1) 완료 조건 (Definition of Done)

1. `docs/input_signal_spec.md` 기준 입력 자극이 고정되어 있음.
2. `docs/fixed_model_spec.md`에 Q-format, quantization, rounding, saturation, overflow 정책이 명시되어 있음.
3. `model/fixed`에 golden model이 구현되어 있음.
4. fixed 모델 단독 동작과 예외 처리가 테스트로 검증되어 있음.
5. 이후 ideal-vs-fixed 비교 단계(v4)로 넘어가기 위한 고정소수점 기준 모델이 정리되어 있음.

## 2) 주간 루틴

1. 월-화: 동적 범위 분석과 Q-format/scaling 정책 정리.
2. 수-목: quantization/rounding/saturation 정책 구현 및 단위 테스트.
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

1. 스펙/의사결정: `docs/input_signal_spec.md`, `docs/fixed_model_spec.md`, `docs/log/*.md`
2. ideal 기준 모델: `model/ideal/*.py`
3. fixed/golden 모델: `model/fixed/*.py`
4. fixed 테스트: `sim/python/test/fixed/*.py`
5. 실험 보조 스크립트: `sim/python/*.py`
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
2. 입력 신호 제약과 fixed 정책의 연결 근거가 문서에 존재함
3. 테스트 최소 1개 이상 추가
4. 결과 수치가 문서에 기록됨
5. 재현 명령어가 문서에 존재함

## 7) 업데이트 정책

1. `workflow_v3.md`는 주 1회만 수정(운영 흔들림 방지).
2. 실험/결정 기록은 `docs/log`에 매일 누적.
3. v3의 스코프는 fixed-point golden model 단계까지로 한정한다.
4. ideal-vs-fixed 비교 및 정량 검증 단계부터는 `workflow_v4.md`를 기준 문서로 사용한다.
