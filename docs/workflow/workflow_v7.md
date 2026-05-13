# FIR Decimation 프로젝트 워크플로우 v7

- 작성일: 2026-04-29
- 이전 버전: workflow_v6.md
- 변경 배경: 교수님 피드백("시연이 약하다, 발전된 모듈 필요") 반영

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
| 탭 수                | N = 43 (coefficient-based worst-case 기준 통과)  |
| 고정소수점 포맷      | Q1.15 (signed 16-bit)        |
| FIR 구조             | Transposed Form              |
| 클럭                 | 100 MHz (Clocking Wizard)    |
| 최종 목표 인터페이스 | AXI-Stream (Zynq PS-PL 연동) |

---

## 2. 현재 완료 상태

**N=5 Direct Form bring-up 보드 검증 완료**

- Python 레퍼런스 모델 (Kaiser 창함수, β=5.653)
- Q1.15 고정소수점 골든 모델 (ties-away-from-zero 반올림, 포화 연산)
- Verilog RTL 구현 (Direct Form, 48비트 누산기, 4사이클 레이턴시)
- iverilog self-checking 테스트벤치 PASS
- Zybo 보드 데모 셸 (BRAM 벡터 소스/체커, LED `0110` PASS 확인)
- Vivado 타이밍 클로저 (125MHz 기준 WNS=0.449ns)
- 리셋 버튼 → 재시작 동작 확인

> **N=5의 목적**: 실제 필터 스펙이 아닌, RTL → 합성 → 타이밍 → 보드 전체 파이프라인에
> 결함이 없음을 가장 단순한 케이스로 검증. Direct Form 한계도 이 단계에서 직접 체험.

---

## 3. v6 대비 변경 사항

| 항목 | v6 | v7 |
|------|----|----|
| FIR 구조 | Direct Form 베이스라인 후 Transposed Form 전환 | Transposed Form 바로 진입 |
| N=39/41 중간 단계 | 비교/평가군으로 구현 예정 | 전부 삭제 |
| 클럭 | 125 MHz 직접 사용 | 100 MHz Clocking Wizard |
| 최종 시연 | BRAM 콜드 데이터 + LED PASS/FAIL | PS-PL 실시간 FFT 스펙트럼 시각화 |
| 골든 모델 | Direct Form만 | Direct Form + Transposed Form 둘 다 |

### Direct Form 베이스라인 생략 근거

- N=5 bring-up에서 Direct Form 타이밍 한계를 이미 직접 체험
- N=5와 N=43은 탭 수가 다르므로 어차피 공정한 PPA 비교 불가
- 대신 Python 골든 레벨에서 Direct Form과 Transposed Form 출력을 비교해
  구조 정확성을 검증하는 것으로 대체

---

## 4. 전체 워크플로우

### Step 1 — N=43 골든 모델 구축 (약 1주)

#### 1-1. 기존 Direct Form 골든 N=43으로 확인

기존 `model/fixed/direct_form/` 코드는 `h`를 외부 주입받는 구조이므로
`design_kaiser_lpf(num_taps=43)`으로 생성한 계수를 넣으면 바로 동작한다.

```bash
.venv/bin/python -m sim.python.run_compare_ideal_vs_fixed --num-taps 43
```

확인 항목:
- N=43 Q1.15 계수 클리핑 없음 (기존 `07_coeff_stopband_spec_check.md` 결과 재확인)
- ideal vs fixed SNR, RMSE 지표 산출

#### 1-2. Transposed Form float64 ideal 골든 신규 작성

```
model/ideal/transposed_form/
    anti_alias_fir.py          # Transposed Form float64
    fir_decimator_transposed.py
```

Transposed Form 누산 구조:

```
매 입력 샘플 x[n]마다:
    state[k] = h[k] * x[n] + state[k+1]   (k = N-1 ... 0)
    출력 y[n] = state[0]
```

Direct Form과 달리 delay line이 입력 샘플이 아니라 누산 중간값을 저장한다.

#### 1-3. Transposed Form Q1.15 golden 신규 작성

```
model/fixed/transposed_form/
    anti_alias_fir.py          # Transposed Form Q1.15
    fir_decimator_transposed_golden.py
```

Direct Form 골든과 동일하게:
- 입력/계수: signed 16-bit Q1.15
- 곱셈 결과: Q2.30 해석
- 반올림: ties-away-from-zero
- 포화: 최종 출력 저장 시 1회 clip(-32768, 32767)
- intermediate wrap/saturation 없음

가변 탭 수: `h`를 외부 주입받는 구조로 작성 → `h.size`가 곧 탭 수

#### 1-4. 골든 모델 비교 검증

| 비교 쌍 | 기대 결과 |
|---------|-----------|
| float64 Direct vs float64 Transposed (N=43) | 완전 bit-exact |
| Q1.15 Direct vs Q1.15 Transposed (N=43) | 차이 0 or 최대 1 LSB → 정상 / 2 LSB 이상 → 골든 버그 |

> Q1.15에서 1 LSB 오차는 정상이다. Direct Form은 샘플 방향으로,
> Transposed Form은 계수 방향으로 누산하므로 반올림이 쌓이는 위치가 다르기 때문이다.

완료 기준:
- [ ] float64 레벨 bit-exact 확인
- [ ] Q1.15 레벨 최대 오차 1 LSB 이내 확인
- [ ] pytest 테스트 추가

---

### Step 2 — N=43 Transposed Form RTL 구현 (약 2~3주)

#### 2-1. RTL 설계

```
rtl/transposed_form/
    fir_transposed_n43.v
    fir_decimator_transposed_n43_top.v
```

포트 인터페이스는 bring-up과 동일:

```verilog
input         clk;
input         rst;        // active-high
input         in_valid;
input  signed [15:0] in_sample;
output        out_valid;
output signed [15:0] out_sample;
```

Transposed Form RTL 구조:
- N=43개의 state register (각 signed 48-bit)
- 매 valid cycle마다 전체 state를 한 칸씩 shift하면서 `h[k]*x[n]` 누산
- 파이프라인 단계는 타이밍 클로저 결과 보고 결정

계수 공급: N=43 Q1.15 계수 내부 하드코딩 (bring-up 방식 유지)

누산기 폭 worst-case 계산:

```
sum(|h_q[k]|) for N=43: docs/log/07에서 abs_sum_q15_float ≈ 1.709747
→ 정수 기준: round(1.709747 * 32768) = 56,025
max|x_q| = 32768
max|acc| ≤ 32768 * 56025 = 1,835,827,200
→ signed 32-bit 범위 안 (최소 요구 폭)
→ 실제 구현: signed 48-bit (DSP48 정렬, 여유 확보)
```

#### 2-2. 테스트벤치 및 시뮬레이션

```
sim/rtl/tb/transposed_form/
    tb_fir_transposed_n43.v
    tb_fir_decimator_transposed_n43_top.v
```

벡터 생성:

```bash
.venv/bin/python -m sim.python.run_compare_ideal_vs_fixed --num-taps 43
.venv/bin/python -m sim.python.export_rtl_bringup_vectors --num-taps 43
```

출력 벡터 저장 위치:

```
sim/vectors/transposed_form/n43/
    input_q15.hex
    expected_fir_q15.hex
    expected_decim_q15.hex
```

완료 기준:
- [ ] tb_fir_transposed_n43 PASS
- [ ] tb_fir_decimator_transposed_n43_top PASS

#### 2-3. Vivado 합성 및 100MHz 타이밍 클로저

- Clocking Wizard로 100MHz 생성 (125MHz sysclk → 100MHz)
- 목표: WNS ≥ 0
- 파이프라인 단계는 timing report 보고 추가

완료 기준:
- [ ] synthesis/implementation PASS
- [ ] WNS ≥ 0 @ 100MHz
- [ ] `All user specified timing constraints are met.`

---

### Step 3 — AXI-Stream 래퍼 구현 (약 2~3주)

AXI-Stream 인터페이스로 감싸서 Zynq PS-PL DMA와 연동 가능한 구조로 만든다.

```
rtl/transposed_form/
    fir_decimator_axi_wrapper.v
```

포트:

```verilog
// AXI-Stream Slave (입력)
input  wire        s_axis_tvalid,
output wire        s_axis_tready,
input  wire [15:0] s_axis_tdata,

// AXI-Stream Master (출력)
output wire        m_axis_tvalid,
input  wire        m_axis_tready,
output wire [15:0] m_axis_tdata
```

검증 방법:
- BRAM 콜드 데이터로 먼저 AXI 인터페이스 동작 확인 (실시간 이전 안전망)
- 이 단계에서 BRAM 입출력 + PC Python 오프라인 FFT로 필터 전/후 스펙트럼 확인 가능

완료 기준:
- [ ] AXI-Stream 인터페이스 시뮬레이션 PASS
- [ ] BRAM 콜드 데이터 기준 보드 동작 확인

---

### Step 4 — PS-PL 연동 및 DMA (약 2~4주)

Vivado Block Design에서 Zynq PS + AXI DMA + FIR IP를 연결한다.

구성:
```
Zynq PS
    → AXI DMA (S2MM: PS→PL, MM2S: PL→PS)
    → FIR Decimator AXI-Stream IP
```

완료 기준:
- [ ] Block Design DRC PASS
- [ ] bare-metal C에서 DMA 송수신 동작 확인
- [ ] PS에서 생성한 멀티톤이 PL 필터를 통과해 PS로 돌아옴

---

### Step 5 — bare-metal C 신호 생성 + UART (약 1~2주)

```c
// 멀티톤 생성 (5 MHz + 20 MHz + 30 MHz, Q1.15)
// AXI DMA로 PL 전송
// 필터 출력 수신
// UART로 PC 전송
```

완료 기준:
- [ ] 멀티톤 생성 및 DMA 전송 동작
- [ ] UART 출력 PC에서 수신 확인

---

### Step 6 — PC Python FFT 실시간 시각화 (약 1~2주)

```python
# UART 수신
# 필터 전/후 신호 FFT
# 실시간 스펙트럼 플롯
```

시연 시나리오:
```
PS에서 주파수/진폭 조합 변경
    → PL FIR Decimation 실시간 처리
    → UART → PC Python FFT 플롯
    → 필터 전/후 스펙트럼 실시간 비교
    → stopband tone(30MHz)이 출력에서 제거되는 것 시각적 확인
```

완료 기준:
- [ ] 실시간 스펙트럼 플롯 동작
- [ ] 필터 전/후 비교 시각적으로 명확

---

## 5. 마일스톤 및 일정

| 마일스톤 | 목표 시점 | 내용 |
|---------|-----------|------|
| M1 | 5월 2주차 | N=43 골든 모델 4종 완성 + 비교 검증 |
| M2 | 5월 4주차 ~ 6월 1주차 | N=43 Transposed Form RTL + 시뮬레이션 PASS |
| M3 | 6월 2주차 | 100MHz 타이밍 클로저 |
| **M4 (안전 마감선)** | **6월 말** | **AXI-Stream 래퍼 + BRAM 검증 완료** |
| M5 | 7월 2주차 | PS-PL DMA 연동 완료 |
| M6 | 7월 3주차 | 실시간 시연 파이프라인 완성 |
| M7 | 7월 말 | 발표 준비 + 보고서 완성 |

> **M4가 안전 마감선이다.**
> 6월 말 기준으로 M4가 완성돼 있으면 Plan A(실시간 시연)를 계속 추진한다.
> M4도 안 됐으면 스코프를 다시 조정해야 한다.

### Plan A vs Plan B

**Plan A (목표):** Step 1~6 전체 완성 → 실시간 FFT 스펙트럼 시각화 시연

**Plan B (안전 마감):** Step 1~3 완성
- N=43 Transposed Form RTL
- AXI-Stream 래퍼
- BRAM 콜드 데이터 + PC Python 오프라인 FFT 스펙트럼 비교
- "설계 의도가 하드웨어에서 동작함"을 보여줄 수 있는 최소 시연

---

## 6. 변경되지 않은 것

| 항목                                     | 상태 |
| ---------------------------------------- | ---- |
| 필터 스펙 (fp=15MHz, fs=25MHz, As≥60dB) | 유지 |
| N=43 탭 수                               | 유지 |
| Q1.15 고정소수점 포맷                    | 유지 |
| Python golden → RTL bit-exact 검증 방식 | 유지 |
| 입력 신호 멀티톤 프로파일                | 유지 |
| Zybo Z7-20 타겟 보드                     | 유지 |
| Kaiser window β=5.653                   | 유지 |
| ties-away-from-zero 반올림               | 유지 |
| 48-bit 누산기                            | 유지 |

---

## 7. 디렉토리 구조 변경 예정

```
model/
├── ideal/
│   ├── anti_alias_fir.py              # Direct Form float64 (기존)
│   ├── transposed_form/               # 신규
│   │   ├── anti_alias_fir.py
│   │   └── fir_decimator_transposed.py
│   └── ...
└── fixed/
    ├── direct_form/                   # 기존
    └── transposed_form/               # 신규
        ├── anti_alias_fir.py
        └── fir_decimator_transposed_golden.py

rtl/
├── direct_form/                       # 기존 (N=5 bring-up)
└── transposed_form/                   # 신규
    ├── fir_transposed_n43.v
    ├── fir_decimator_transposed_n43_top.v
    ├── fir_decimator_axi_wrapper.v
    └── constrs/
        └── zybo_n43.xdc

sim/
├── rtl/tb/
│   ├── direct_form/                   # 기존
│   └── transposed_form/               # 신규
│       ├── tb_fir_transposed_n43.v
│       └── tb_fir_decimator_transposed_n43_top.v
└── vectors/
    ├── direct_form/                   # 기존
    └── transposed_form/
        └── n43/
            ├── input_q15.hex
            ├── expected_fir_q15.hex
            └── expected_decim_q15.hex
```
