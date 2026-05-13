
# FIR Decimation 프로젝트 워크플로우 v6

* 작성일: 2026-04-29

---

## 1. 프로젝트 개요

**Zybo Z7-20 FPGA 위에서 동작하는 FIR 저역통과 필터 + M=2 데시메이터 IP 설계**

| 항목                 | 값                           |
| -------------------- | ---------------------------- |
| 입력 샘플링 주파수   | Fs_in = 100 MHz              |
| 출력 샘플링 주파수   | Fs_out = 50 MHz (M=2)        |
| 통과대역 경계        | fp = 15 MHz                  |
| 차단대역 시작        | fs = 25 MHz                  |
| 목표 감쇠            | As ≥ 60 dB                  |
| 고정소수점 포맷      | Q1.15 (signed 16-bit)        |
| 최종 목표 인터페이스 | AXI-Stream (Zynq PS-PL 연동) |

---

## 2. 현재 완료 상태

**N=5 Direct Form bring-up 보드 검증 완료**

* Python 레퍼런스 모델 (Kaiser 창함수, β=5.653)
* Q1.15 고정소수점 골든 모델 (ties-away-from-zero 반올림, 포화 연산)
* Verilog RTL 구현 (Direct Form, 48비트 누산기, 4사이클 레이턴시)
* iverilog 자체 검증 테스트벤치 PASS
* Zybo 보드 데모 셸 (BRAM 벡터 소스/체커, LED `0110` PASS 확인)
* Vivado 타이밍 클로저 (125MHz 기준 WNS=0.449ns)
* 리셋 버튼 → 재시작 동작 확인

> **N=5의 목적** : 실제 필터 스펙이 아닌, RTL → 합성 → 타이밍 → 보드 전체 파이프라인에 결함이 없음을 가장 단순한 케이스로 검증.

---

## 3. 시스템 구조

```
입력 (Q1.15, 100MHz)
    ↓
fir_direct_n5        ← Direct Form FIR
    ↓ out_valid
decimator_m2_phase0  ← M=2, phase=0 (keep/drop selector)
    ↓
출력 (Q1.15, 50MHz)
```

**보드 데모 셸 구조**

```
전원 인가
    → reset_conditioner      (debounce + POR)
    → bringup_vector_source  (BRAM, 8192샘플 자동 재생)
    → FIR + Decimator
    → bringup_output_checker (Python golden 자동 비교)
    → LED[3:0]               (0110 = PASS)
```

---

## 4. 다음 작업 순서

### Step 1 — N=43 Direct Form 베이스라인 구축 (약 2주)

* [ ] Q1.15 양자화 계수 기준 스펙 확인 (`run_check_coeff_stopband_spec.py`)
* [ ] Clocking Wizard로 100MHz 클럭 변경 (125MHz → 100MHz)
* [ ] Generic FIR RTL 작성 (N을 파라미터로, coefficient 파일 분리)
* [ ] 누산기 폭 worst-case 재계산 (N=43 기준)
* [ ] Python 벡터 재생성 (input/expected hex)
* [ ] 시뮬레이션 검증 PASS
* [ ] 보드 데모 LED `0110` 확인

> 이 단계에서 **Naive RTL 베이스라인** 비교 기준점 확보

### Step 2 — FIR Compiler 베이스라인 수집

* [ ] 동일 조건 (N=43, Q1.15, 100MHz)으로 Xilinx FIR Compiler IP 생성
* [ ] 합성 결과 수집: LUT / DSP / Fmax / 레이턴시

### Step 3 — Improved 설계 구현 (약 2주)

교수님과 합의한 범위에 따라 아래 단계 중 적용:

| 단계       | 내용                      | 개선 효과            |
| ---------- | ------------------------- | -------------------- |
| Improved 1 | Transposed Form           | Fmax 개선            |
| Improved 2 | + 계수 대칭성 활용        | DSP 사용량 절반 감소 |
| Improved 3 | + Polyphase Decomposition | 연산량 추가 감소     |

* [ ] 시뮬레이션 검증 PASS
* [ ] 보드 데모 확인

### Step 4 — 비교 결과 정리

| 항목     | Naive RTL | FIR Compiler | Improved |
| -------- | --------- | ------------ | -------- |
| LUT      | -         | -            | -        |
| DSP      | -         | -            | -        |
| Fmax     | -         | -            | -        |
| 레이턴시 | -         | -            | -        |

---

## 5. 교수님 미팅 확인 사항

1. **Improved 범위** : Transposed Form + 계수 대칭성까지 vs Polyphase까지
2. **AXI-Stream / PS-PL DMA** : 이번 프로젝트 범위 포함 여부 (한 달 일정상 포함 시 타이트)
3. **클럭 변경** : 100MHz Clocking Wizard 사용 동의 확인

---

## 6. 클럭 변경 배경

N=5 bring-up에서 125MHz 시스템 클럭을 그대로 사용하다 타이밍 클로저를 위해 파이프라인 스테이지를 불필요하게 추가했음. 목표 처리율이 100MHz이므로 본 설계(N=43)부터 Clocking Wizard로 100MHz를 생성해 진행. 이는 타이밍 여유 확보와 파이프라인 단순화에 기여함.

---

## 7. 참고: AXI-Stream 연동 순서 (범위 포함 시)

```
N=43 베이스라인 보드 검증 완료
    ↓
AXI-Stream 래퍼 구현 (N=43 코어 기준)
    ↓
PS-PL DMA 연동 + bare-metal C 검증
    ↓
최종 통합
```

> AXI 래퍼와 datapath를 분리 설계하면, N=43 → Improved 교체 시 인터페이스를 수정하지 않아도 됨.
