# FIR Decimation 프로젝트 워크플로우 v8

- 작성일: 2026-04-29
- 이전 버전: workflow_v7.md

---

## 1. 프로젝트 개요

**Zybo Z7-20 FPGA 위에서 동작하는 FIR 저역통과 필터 + M=2 데시메이터 IP 설계**

| 항목 | 값 |
|------|----|
| 입력 샘플링 주파수 | Fs_in = 100 MHz |
| 출력 샘플링 주파수 | Fs_out = 50 MHz (M=2) |
| 통과대역 경계 | fp = 15 MHz |
| 차단대역 시작 | fs = 25 MHz |
| 목표 감쇠 | As ≥ 60 dB |
| 탭 수 | N = 43 |
| 고정소수점 포맷 | Q1.15 (signed 16-bit) |
| FIR 구조 | Transposed Form |
| 클럭 | 100 MHz (Clocking Wizard) |
| 최종 목표 인터페이스 | AXI-Stream (Zynq PS-PL 연동) |

---

## 2. 현재 완료 상태

### 2-1. Python 모델 계층 (전체 완료)

| 항목 | 파일 | 상태 |
|------|------|------|
| Kaiser LPF 계수 설계 | `model/ideal/design_kaiser_coeff.py` | ✅ |
| float64 Direct Form ideal | `model/ideal/anti_alias_fir.py` | ✅ |
| float64 Transposed Form ideal | `model/ideal/transposed_form/anti_alias_fir.py` | ✅ |
| float64 FIR-Decimator (Direct) | `model/ideal/fir_decimator_ideal.py` | ✅ |
| float64 FIR-Decimator (Transposed) | `model/ideal/transposed_form/fir_decimator_transposed_ideal.py` | ✅ |
| Q1.15 Direct Form golden | `model/fixed/direct_form/anti_alias_fir.py` | ✅ |
| Q1.15 Transposed Form golden | `model/fixed/transposed_form/anti_alias_fir.py` | ✅ |
| Q1.15 FIR-Decimator golden (Direct) | `model/fixed/direct_form/fir_decimator_golden.py` | ✅ |
| Q1.15 FIR-Decimator golden (Transposed) | `model/fixed/transposed_form/fir_decimator_transposed_golden.py` | ✅ |
| Decimator (공용) | `model/fixed/decimator.py` | ✅ |

### 2-2. 검증

| 항목 | 결과 |
|------|------|
| float64 Direct vs Transposed bit-exact | ✅ max diff = 2.22e-16 (머신 엡실론) |
| Q1.15 Direct vs Transposed max diff | ✅ 0 LSB (완전 bit-exact) |
| pytest anti_alias_fir_transposed (18개) | ✅ 전부 통과 |
| pytest fir_decimator_transposed (10개) | ✅ 전부 통과 |
| N=43 stopband spec-check | ✅ worst-case ≥ 60dB 확인 |

### 2-3. N=5 Direct Form bring-up (전체 완료)

| 항목 | 상태 |
|------|------|
| Verilog RTL 구현 | ✅ |
| iverilog self-checking 시뮬레이션 PASS | ✅ |
| Vivado 타이밍 클로저 (125MHz, WNS=0.449ns) | ✅ |
| Zybo 보드 LED `0110` PASS | ✅ |
| reset 버튼 재시작 동작 확인 | ✅ |

### 2-4. 설계 문서

| 문서 | 내용 |
|------|------|
| `docs/log/12_project_direction_change.md` | 교수님 피드백 반영 방향 변경 |
| `docs/log/13_transposed_form_golden_policy.md` | Q1.15 골든 정책 확정 |
| `docs/log/14_transposed_form_rtl_decisions.md` | RTL 설계 결정 확정 |

---

## 3. 다음 작업 순서

### Step 1 — N=43 RTL 벡터 생성 (약 1~2일)

골든 모델이 완성됐으므로 RTL testbench용 hex 벡터를 생성한다.

```bash
# N=43 ideal-vs-fixed 비교 실행 (벡터 생성 포함)
.venv/bin/python -m sim.python.run_compare_ideal_vs_fixed --num-taps 43

# RTL용 hex 벡터 export
.venv/bin/python -m sim.python.export_rtl_bringup_vectors --num-taps 43
```

생성 대상:

```
sim/vectors/transposed_form/n43/
    input_q15.hex
    expected_fir_q15.hex
    expected_decim_q15.hex
```

완료 기준:
- [ ] hex 벡터 3종 생성 완료
- [ ] 벡터 길이 확인 (input: 8192, fir: 8234, decim: 4117)

---

### Step 2 — N=43 Transposed Form RTL 구현 (약 1~2주)

#### 2-1. 계수 localparam 생성

Python으로 N=43 Q1.15 계수 정수값을 출력해서 Verilog localparam으로 변환한다.

```bash
.venv/bin/python -m sim.python.inspect_kaiser_coeff --num-taps 43
```

#### 2-2. `fir_transposed_n43.v` 구현

```
rtl/transposed_form/fir_transposed_n43.v
```

설계 기준 (`14_transposed_form_rtl_decisions.md`):
- 포트: `clk`, `rst`(active-high), `in_valid`, `in_sample[15:0]`, `out_valid`, `out_sample[15:0]`
- 1 sample/cycle 병렬 처리 (N=43개 MAC 동시)
- 2단계 파이프라인 (Stage1: 곱셈, Stage2: 누산+반올림+포화)
- z[k]: signed 48-bit
- 반올림: ties-away-from-zero
- 포화: 최종 출력 1회

#### 2-3. `fir_decimator_transposed_n43_top.v` 구현

```
rtl/transposed_form/fir_decimator_transposed_n43_top.v
```

기존 `decimator_m2_phase0.v` 재사용. FIR 출력을 decimator에 연결.

#### 2-4. Testbench 및 iverilog 시뮬레이션

```
sim/rtl/tb/transposed_form/
    tb_fir_transposed_n43.v
    tb_fir_decimator_transposed_n43_top.v
```

완료 기준:
- [ ] `tb_fir_transposed_n43` PASS
- [ ] `tb_fir_decimator_transposed_n43_top` PASS

---

### Step 3 — Vivado 합성 및 100MHz 타이밍 클로저 (약 1주)

Vivado 프로젝트 구성:
- Top: `fir_decimator_transposed_n43_top`
- 클럭: Clocking Wizard 100MHz
- Part: Zybo Z7-20

완료 기준:
- [ ] Synthesis/Implementation PASS
- [ ] WNS ≥ 0 @ 100MHz
- [ ] `All user specified timing constraints are met.`
- [ ] 타이밍 위반 시 파이프라인 단계 추가 후 재시도

---

### Step 4 — AXI-Stream 래퍼 구현 (약 2~3주)

```
rtl/transposed_form/fir_decimator_axi_wrapper.v
```

포트:

```verilog
// AXI-Stream Slave (입력)
input  wire        s_axis_tvalid,
output wire        s_axis_tready,
input  wire [15:0] s_axis_tdata,
input  wire        s_axis_tlast,

// AXI-Stream Master (출력)
output wire        m_axis_tvalid,
input  wire        m_axis_tready,
output wire [15:0] m_axis_tdata,
output wire        m_axis_tlast
```

검증 방법:
- BRAM 콜드 데이터로 AXI 인터페이스 동작 먼저 확인
- 이 단계에서 PC Python 오프라인 FFT로 필터 전/후 스펙트럼 확인 가능

완료 기준:
- [ ] AXI-Stream 인터페이스 시뮬레이션 PASS
- [ ] BRAM 콜드 데이터 기준 보드 동작 확인
- [ ] PC Python FFT로 30MHz stopband tone 제거 확인

---

### Step 5 — PS-PL 연동 및 DMA (약 2~4주)

Vivado Block Design:

```
Zynq PS
    → AXI DMA (S2MM: PS→PL 입력, MM2S: PL→PS 출력)
    → FIR Decimator AXI-Stream IP
```

완료 기준:
- [ ] Block Design DRC PASS
- [ ] bare-metal C에서 DMA 송수신 동작 확인
- [ ] PS 생성 멀티톤이 PL 필터 통과 후 PS로 돌아옴

---

### Step 6 — bare-metal C + UART (약 1~2주)

```c
// 멀티톤 생성 (5MHz + 20MHz + 30MHz, Q1.15)
// AXI DMA로 PL 전송 → 필터 출력 수신
// UART로 PC 전송 (필터 전/후 신호 쌍)
```

완료 기준:
- [ ] 멀티톤 생성 및 DMA 송수신 동작
- [ ] UART 출력 PC에서 수신 확인

---

### Step 7 — PC Python FFT 실시간 시각화 (약 1~2주)

시연 시나리오:

```
PS에서 주파수 조합 변경
    → PL FIR Decimation 실시간 처리
    → UART → PC Python FFT 플롯
    → 필터 전/후 스펙트럼 실시간 비교
    → 30MHz stopband tone이 출력에서 제거되는 것 시각적 확인
```

완료 기준:
- [ ] 실시간 스펙트럼 플롯 동작
- [ ] 필터 전/후 비교 시각적으로 명확

---

## 4. 마일스톤 및 일정

| 마일스톤 | 목표 시점 | 내용 |
|---------|-----------|------|
| M1 | 5월 1주차 | N=43 RTL 벡터 생성 완료 |
| M2 | 5월 3주차 | N=43 Transposed Form RTL + iverilog PASS |
| M3 | 6월 1주차 | Vivado 100MHz 타이밍 클로저 |
| **M4 (안전 마감선)** | **6월 말** | **AXI-Stream 래퍼 + BRAM 오프라인 FFT 확인** |
| M5 | 7월 2주차 | PS-PL DMA 연동 완료 |
| M6 | 7월 3주차 | 실시간 시연 파이프라인 완성 |
| M7 | 7월 말 | 발표 준비 + 보고서 완성 |

### Plan A vs Plan B

**Plan A (목표):** Step 1~7 전체 완성 → 실시간 FFT 스펙트럼 시각화 시연

**Plan B (안전 마감):** Step 1~4 완성
- N=43 Transposed Form RTL 동작
- AXI-Stream 래퍼
- BRAM 콜드 데이터 + PC Python 오프라인 FFT 스펙트럼 비교
- "설계 의도가 하드웨어에서 동작함"을 보여줄 수 있는 최소 시연

**M4(6월 말)가 분기점이다.** M4 완성 여부로 Plan A/B를 판단한다.

---

## 5. 변경되지 않은 것

| 항목 | 상태 |
|------|------|
| 필터 스펙 (fp=15MHz, fs=25MHz, As≥60dB) | 유지 |
| N=43 탭 수 | 유지 |
| Q1.15 고정소수점 포맷 | 유지 |
| Python golden → RTL bit-exact 검증 방식 | 유지 |
| 입력 신호 멀티톤 프로파일 (5/20/30 MHz) | 유지 |
| Zybo Z7-20 타겟 보드 | 유지 |
| Kaiser window β=5.653 | 유지 |
| ties-away-from-zero 반올림 | 유지 |
| 48-bit 누산기 | 유지 |
| Decimator 재사용 (decimator_m2_phase0.v) | 유지 |

---

## 6. 디렉토리 구조 현황

```
model/
├── ideal/
│   ├── anti_alias_fir.py              ✅ Direct Form float64
│   ├── decimator.py                   ✅
│   ├── fir_decimator_ideal.py         ✅
│   ├── design_kaiser_coeff.py         ✅
│   ├── gen_multitone.py               ✅
│   └── transposed_form/               ✅
│       ├── __init__.py
│       ├── anti_alias_fir.py
│       └── fir_decimator_transposed_ideal.py
└── fixed/
    ├── decimator.py                   ✅ 공용
    ├── direct_form/                   ✅
    │   ├── anti_alias_fir.py
    │   └── fir_decimator_golden.py
    └── transposed_form/               ✅
        ├── __init__.py
        ├── anti_alias_fir.py
        └── fir_decimator_transposed_golden.py

rtl/
├── direct_form/                       ✅ N=5 bring-up 완료
└── transposed_form/                   ← Step 2에서 생성
    ├── fir_transposed_n43.v
    ├── fir_decimator_transposed_n43_top.v
    ├── fir_decimator_axi_wrapper.v    ← Step 4
    └── constrs/
        └── zybo_n43.xdc

sim/
├── python/test/
│   ├── fixed/
│   │   ├── direct_form/               ✅
│   │   └── transposed_form/           ✅ (28개 테스트 통과)
│   └── ideal/                         ✅
└── vectors/
    ├── direct_form/bringup_n5/        ✅
    └── transposed_form/n43/           ← Step 1에서 생성
```
