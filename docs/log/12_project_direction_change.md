# 12. Project Direction Change After Advisor Feedback

- 작성일: 2026-04-29
- 단계: 전환점
- 목적: 교수님 피드백 수렴 후 변경된 프로젝트 방향과 각 결정의 근거를 기록한다

## 1) 피드백 내용

> "시연에서 보여주는 게 약하고 너무 간단하다. 분발할 필요가 있다. 발전된 모듈이 필요하다."

## 2) 변경 사항 요약

### 변경 1 — 비교 실험 구조 축소

**변경 전**
```
N=5 bring-up
    → N=39/41/43 Direct Form 순차 구현
    → Improved (Transposed Form 등) 구현
    → Direct Form vs Improved PPA 비교
```

**변경 후**
```
N=5 bring-up ✓ (완료)
    → N=43 Transposed Form 직접 구현
    → AXI-Stream + PS-PL 실시간 시연
```

근거:
- N=43 Direct Form을 따로 만들어봤자 "역시 느리네"라는 이미 아는 결론만 나옴
- N=5 bring-up에서 Direct Form 타이밍 한계를 이미 직접 체험했으므로 정성적 근거 확보됨
- 의미없는 비교를 위한 시간 낭비 제거

### 변경 2 — N=39/41 중간 단계 제거

**변경 전**
- N=39, N=41을 비교/평가군으로 순차 구현 예정

**변경 후**
- 중간 탭 수 구현 단계 전부 삭제
- N=43 Q1.15 양자화 계수 스펙 통과 확인 완료로 N=43 확정

근거:
- 중간 탭 수 구현은 비교 데이터 수집 목적이었는데 비교 실험 자체가 축소됨
- N=43이 `f >= 25MHz` worst-case 기준으로 이미 스펙 통과 확인됨 (`docs/log/07_coeff_stopband_spec_check.md`)

### 변경 3 — 클럭 변경

**변경 전**
- 125MHz 시스템 클럭 직접 사용 (bring-up 단순화 목적)

**변경 후**
- 100MHz, Clocking Wizard 사용

근거:
- 시스템 목표 처리율이 100MHz인데 125MHz로 타이밍 맞추려다 불필요한 파이프라인 단계가 추가됨
- N=5 bring-up에서 FIR latency가 2 cycles → 4 cycles로 늘어난 원인이 여기 있음
- N=43으로 탭 수 늘어나면 타이밍 압박이 더 심해지므로 여유 확보 필요
- 연산 정확도는 클럭과 무관하므로 bring-up 검증 결과 유효성에 영향 없음

### 변경 4 — 최종 목표 추가 (실시간 시연)

**변경 전**
- BRAM 미리 저장된 데이터 재생 + LED PASS/FAIL 표시로 종료

**변경 후**
- AXI-Stream 래퍼 구현
- PS-PL DMA 연동
- bare-metal C로 멀티톤 신호 생성
- UART → PC Python FFT 실시간 스펙트럼 시각화

시연 시나리오:
```
PS에서 주파수/진폭 조합 변경
    → PL FIR Decimation 실시간 처리
    → UART → PC Python FFT 플롯
    → 필터 전/후 스펙트럼 실시간 비교
    → stopband tone(30MHz)이 출력에서 제거되는 것 시각적 확인
```

### 변경 5 — FIR 구조 조기 전환

**변경 전**
- Direct Form으로 N=43 베이스라인 먼저 구축 후 Transposed Form으로 전환

**변경 후**
- Direct Form 베이스라인 단계 생략
- N=43 Transposed Form으로 바로 진입
- 단, Python 골든 레벨에서 Direct Form과 Transposed Form 출력을 비교해 구조 정확성을 검증하는 것으로 대체

근거:
- N=5 bring-up에서 Direct Form 타이밍 한계를 이미 직접 체험
- N=5와 N=43은 탭 수가 달라 공정한 PPA 비교가 성립하지 않음
- Direct Form 베이스라인 생략으로 절약된 시간(약 2~3주)을 Transposed Form + AXI 실시간 시연에 집중
- Python 골든 2개(Direct + Transposed) 비교로 구조 정확성은 여전히 검증 가능

## 3) 변경되지 않은 것

| 항목 | 상태 |
| ---- | ---- |
| 필터 스펙 (fp=15MHz, fs=25MHz, As≥60dB) | 유지 |
| N=43 탭 수 | 유지 |
| Q1.15 고정소수점 포맷 | 유지 |
| Python golden → RTL bit-exact 검증 방식 | 유지 |
| 입력 신호 멀티톤 프로파일 | 유지 |
| Zybo Z7-20 타겟 보드 | 유지 |
| Kaiser window β=5.653 | 유지 |
| ties-away-from-zero 반올림 정책 | 유지 |
| 48-bit 누산기 | 유지 |

## 4) 확정 워크플로우 (변경 후)

```
1.  N=43 Direct Form 골든 확인
        └── 기존 코드 num_taps=43으로 실행 (코드 변경 없음)
2.  N=43 Transposed Form float64 ideal 골든 신규 작성
        └── model/ideal/transposed_form/anti_alias_fir.py
3.  N=43 Transposed Form Q1.15 golden 신규 작성
        └── model/fixed/transposed_form/anti_alias_fir.py
4.  골든 비교 검증
        └── float64: Direct vs Transposed → 완전 bit-exact
        └── Q1.15:   Direct vs Transposed → 0 or 최대 1 LSB
5.  N=43 Transposed Form RTL 구현
6.  RTL vs Q1.15 Transposed golden bit-exact 확인
7.  100MHz 타이밍 클로저 (Clocking Wizard)
8.  AXI-Stream 래퍼 구현
9.  PS-PL DMA 연동
10. bare-metal C + UART
11. PC Python FFT 실시간 시각화
```

## 5) 일정 기준점

- 전체 기간: 2026-04-29 ~ 2026-07-말 (약 13주 실질 구현 기간)
- **안전 마감선 (M4): 2026-06-말**
  - 이 시점에 AXI-Stream 래퍼 + BRAM 검증까지 완성돼 있으면 Plan A(실시간 시연) 계속 추진
  - 미달이면 스코프 재조정
