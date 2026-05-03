# 10_zynq-fir-decimation-ip CLAUDE.md

Updated: 2026-05-03
Repository root: `/home/young/dev/10_zynq-fir-decimation-ip`
Branch: `main`
Zybo Z7-20 FPGA에서 동작하는 N=43 Transposed Form FIR 저역통과 필터 + M=2 데시메이터 IP 설계.

Python Q1.15 골든 모델부터 Verilog RTL, Vivado 합성, PS-PL 실시간 FFT 시연까지.

---

## 1. 프로젝트 환경

- 보드: Zybo Z7-20 (Zynq-7000, xc7z020clg400-1)
- 개발 환경: Linux 데스크탑, Vivado 네이티브, Python 3.13, uv 패키지 매니저
- Python 실행: `.venv/bin/python` 또는 `uv run --no-sync python`
- 시뮬레이션: iverilog (`-g2012`) + vvp
- GitHub: young-0320/zynq-axi-fir-decimation-ip
- Vivado 빌드 경로: `/mnt/workspace/10_zynq-fir-decimation-ip_build/`

---

## 2. 필터 스펙 (고정)

| 항목     | 값                          |
| -------- | --------------------------- |
| Fs_in    | 100 MHz                     |
| Fs_out   | 50 MHz (M=2)                |
| fp       | 15 MHz                      |
| fs       | 25 MHz                      |
| As       | ≥ 60 dB                    |
| N        | 43 (Kaiser window β=5.653) |
| 포맷     | Q1.15 signed 16-bit         |
| FIR 구조 | Transposed Form             |
| 클럭     | 100 MHz (Clocking Wizard)   |

---

## 3. 현재 완료 상태

### Python 모델 계층 (전체 완료)

| 파일                                                               | 상태                            |
| ------------------------------------------------------------------ | ------------------------------- |
| `model/ideal/design_kaiser_coeff.py`                             | ✅                              |
| `model/ideal/anti_alias_fir.py`                                  | ✅ Direct Form float64          |
| `model/ideal/transposed_form/anti_alias_fir.py`                  | ✅ Transposed Form float64      |
| `model/fixed/direct_form/anti_alias_fir.py`                      | ✅ Direct Form Q1.15 golden     |
| `model/fixed/transposed_form/anti_alias_fir.py`                  | ✅ Transposed Form Q1.15 golden |
| `model/fixed/transposed_form/fir_decimator_transposed_golden.py` | ✅                              |
| pytest 전체 (28개 포함)                                            | ✅ 전부 통과                    |

### N=5 Direct Form bring-up (전체 완료)

| 항목                                           | 상태                  |
| ---------------------------------------------- | --------------------- |
| `rtl/direct_form/bringup_n5/fir_direct_n5.v` | ✅                    |
| `rtl/direct_form/decimator_m2_phase0.v`      | ✅ (N=43 재사용 예정) |
| iverilog self-checking 시뮬레이션              | ✅ PASS               |
| Vivado 타이밍 클로저 (125MHz, WNS=0.449ns)     | ✅                    |
| Zybo 보드 LED `0110` PASS                    | ✅                    |

```bash
# 1단계: Transposed Form golden 실행 → .npy
.venv/bin/python -m sim.python.run_compare_ideal_vs_fixed \
    --num-taps 43 --form transposed
# → sim/output/ideal_vs_fixed_trans_n43/

# 2단계: .npy → .hex
.venv/bin/python -m sim.python.export_rtl_bringup_vectors \
    --num-taps 43 \
    --input-dir sim/output/ideal_vs_fixed_trans_n43 \
    --output-dir sim/vectors/transposed_form/n43
# → sim/vectors/transposed_form/n43/
```

생성 벡터:

```
sim/vectors/transposed_form/n43/
    input_q15.hex          (8192 lines)
    coeff_q15.hex          (43 lines)
    expected_fir_q15.hex   (8234 lines = 8192 + 42 flush)
    expected_decim_q15.hex (4117 lines)
```

---

## 4. 지금 하고 있는 작업

**N=43 Transposed Form RTL 구현 단계 (Step 2)**

완료 체크:

- [X] `rtl/transposed_form/n43/fir_transposed_n43.v` 구현
- [ ] iverilog 문법 체크 통과
- [ ] `tb_fir_transposed_n43.v` 작성
- [ ] iverilog self-checking 시뮬레이션 PASS
- [ ] `fir_decimator_transposed_n43_top.v` 구현
- [ ] `tb_fir_decimator_transposed_n43_top.v` PASS
- [ ] Vivado 100MHz 타이밍 클로저 (WNS ≥ 0)

---

## 5. RTL 설계 확정 사항

근거 문서: `docs/log/14_transposed_form_rtl_decisions.md`

### 파이프라인 구조

```
[Stage 1] in_valid=1
    → h[k] * in_sample  (k=0..42, 43개 병렬)
    → prod_reg[k] 저장  (signed 48-bit)
    → prod_valid = 1

[Stage 2] prod_valid=1
    → z[k] = prod_reg[k] + z[k+1]  (k=0..41)
      z[42] = prod_reg[42]           ← 경계: z[43] 없음, 곱셈 결과만 (B안)
    → out_sample = saturate(round(prod_reg[0] + z[1]))
      ※ non-blocking 특성상 z[0] 직접 참조 불가 → prod_reg[0]+z[1] 직접 계산
    → out_valid = 1
```

### 확정 결정 요약

| 항목        | 결정                                            |
| ----------- | ----------------------------------------------- |
| 처리 구조   | 1 sample/cycle 병렬 (N=43개 MAC 동시)           |
| 파이프라인  | 2단계 초기, 타이밍 위반 시 3단계로 확장         |
| FIR latency | 2 cycles                                        |
| Top latency | 3 cycles (keep sample 기준)                     |
| z[k] 비트폭 | signed 48-bit (Q2.30)                           |
| prod_reg[k] | signed 48-bit (32-bit 곱 → sign-extend)        |
| 반올림      | ties-away-from-zero, z[0] 출력 1회만            |
| 포화        | 출력 1회 clip(-32768, 32767)                    |
| in_valid=0  | z[k] hold, prod_valid=0, out_valid=0            |
| reset       | active-high, 전체 state 0                       |
| 계수 저장   | localparam 하드코딩 43개                        |
| z[42] 경계  | B안:`z[42] <= prod_reg[42]` (z[43] 더미 없음) |

### 포트 인터페이스

```verilog
input  wire               clk,
input  wire               rst,        // active-high
input  wire               in_valid,
input  wire signed [15:0] in_sample,
output reg                out_valid,
output reg  signed [15:0] out_sample
```

### N=43 계수 (Q1.15 정수값)

```verilog
// 음수는 -16'sdXXX 형태로 써야 함 (16'sd-XXX 는 문법 오류)
localparam signed [15:0] COEFF_0  =  16'sd10;   localparam signed [15:0] COEFF_1  =  16'sd0;
localparam signed [15:0] COEFF_2  = -16'sd33;   localparam signed [15:0] COEFF_3  = -16'sd32;
localparam signed [15:0] COEFF_4  =  16'sd47;   localparam signed [15:0] COEFF_5  =  16'sd107;
localparam signed [15:0] COEFF_6  =  16'sd0;    localparam signed [15:0] COEFF_7  = -16'sd197;
localparam signed [15:0] COEFF_8  = -16'sd159;  localparam signed [15:0] COEFF_9  =  16'sd206;
localparam signed [15:0] COEFF_10 =  16'sd425;  localparam signed [15:0] COEFF_11 =  16'sd0;
localparam signed [15:0] COEFF_12 = -16'sd674;  localparam signed [15:0] COEFF_13 = -16'sd522;
localparam signed [15:0] COEFF_14 =  16'sd654;  localparam signed [15:0] COEFF_15 =  16'sd1336;
localparam signed [15:0] COEFF_16 =  16'sd0;    localparam signed [15:0] COEFF_17 = -16'sd2258;
localparam signed [15:0] COEFF_18 = -16'sd1939; localparam signed [15:0] COEFF_19 =  16'sd2995;
localparam signed [15:0] COEFF_20 =  16'sd9864; localparam signed [15:0] COEFF_21 =  16'sd13109;
localparam signed [15:0] COEFF_22 =  16'sd9864; localparam signed [15:0] COEFF_23 =  16'sd2995;
localparam signed [15:0] COEFF_24 = -16'sd1939; localparam signed [15:0] COEFF_25 = -16'sd2258;
localparam signed [15:0] COEFF_26 =  16'sd0;    localparam signed [15:0] COEFF_27 =  16'sd1336;
localparam signed [15:0] COEFF_28 =  16'sd654;  localparam signed [15:0] COEFF_29 = -16'sd522;
localparam signed [15:0] COEFF_30 = -16'sd674;  localparam signed [15:0] COEFF_31 =  16'sd0;
localparam signed [15:0] COEFF_32 =  16'sd425;  localparam signed [15:0] COEFF_33 =  16'sd206;
localparam signed [15:0] COEFF_34 = -16'sd159;  localparam signed [15:0] COEFF_35 = -16'sd197;
localparam signed [15:0] COEFF_36 =  16'sd0;    localparam signed [15:0] COEFF_37 =  16'sd107;
localparam signed [15:0] COEFF_38 =  16'sd47;   localparam signed [15:0] COEFF_39 = -16'sd32;
localparam signed [15:0] COEFF_40 = -16'sd33;   localparam signed [15:0] COEFF_41 =  16'sd0;
localparam signed [15:0] COEFF_42 =  16'sd10;
```

### 누산기 worst-case

```
max|z[k]| ≤ 32,768 × 56,025 = 1,835,827,200  → signed 32-bit 범위 안
RTL은 signed 48-bit 사용 (여유 + DSP48 정렬)
```

---

## 6. 디렉토리 구조

```
rtl/
├── direct_form/               ✅ N=5 bring-up 완료
│   ├── bringup_n5/
│   └── decimator_m2_phase0.v  ← N=43에서 재사용
└── transposed_form/
    └── n43/
        ├── fir_transposed_n43.v               ✅ 구현 완료
        ├── fir_decimator_transposed_n43_top.v ← 다음 작업
        └── constrs/zybo_n43.xdc

sim/
├── python/
│   ├── run_compare_ideal_vs_fixed.py  ✅ --form 인수 추가됨
│   └── export_rtl_bringup_vectors.py  ✅
├── output/
│   └── ideal_vs_fixed_trans_n43/      ← 벡터 생성 후 여기 생김
├── vectors/
│   └── transposed_form/n43/           ← hex 벡터 생성 후 여기 생김
└── rtl/tb/
    └── transposed_form/
        ├── tb_fir_transposed_n43.v               ← 작성 필요
        └── tb_fir_decimator_transposed_n43_top.v ← 작성 필요

model/
├── ideal/
│   ├── design_kaiser_coeff.py  ✅
│   └── transposed_form/        ✅
└── fixed/
    ├── direct_form/             ✅
    └── transposed_form/         ✅

docs/log/
    09_bringup_rtl_decisions.md       ← N=5 bring-up 운영 규칙
    13_transposed_form_golden_policy.md
    14_transposed_form_rtl_decisions.md
    15_rtl_vector_pipeline_extension.md
```

---

## 7. 코드 스타일 규칙

### Verilog

```verilog
`timescale 1ns / 1ps
`default_nettype none
// ... 모듈 내용
`default_nettype wire
```

- reset: `always @(posedge clk or posedge rst)`
- 출력 레지스터: `output reg`
- signed 명시: `signed [47:0]`, `signed [15:0]`

### Python

- type hint 필수, docstring 필수
- 기존 `model/` 구조 패턴 유지

### 문서

- `docs/log/NN_*.md` 형식, 제목 영어, 본문 한국어
- 커밋: conventional commits (feat/fix/test/docs/refactor)

---

## 8. 전체 작업 순서

```
Step 1  ✅  N=43 RTL 벡터 생성
Step 2  🔄  fir_transposed_n43.v + testbench + iverilog PASS  ← 현재
Step 3      Vivado 100MHz 타이밍 클로저
Step 4      AXI-Stream 래퍼                    ← M4 안전 마감선 (6월 말)
Step 5      PS-PL DMA 연동
Step 6      bare-metal C + UART
Step 7      PC Python FFT 실시간 시각화
```

**M4(6월 말)가 분기점.** M4 완성 → Plan A(실시간 시연) 계속. 미완성 → 스코프 재조정.

---

## 9. 자주 쓰는 명령어

```bash
# pytest 전체
.venv/bin/pytest -q

# 계수 확인
.venv/bin/python -m sim.python.inspect_kaiser_coeff --num-taps 43

# 벡터 생성
.venv/bin/python -m sim.python.run_compare_ideal_vs_fixed --num-taps 43 --form transposed
.venv/bin/python -m sim.python.export_rtl_bringup_vectors \
    --num-taps 43 \
    --input-dir sim/output/ideal_vs_fixed_trans_n43 \
    --output-dir sim/vectors/transposed_form/n43

# iverilog 시뮬레이션
iverilog -g2012 -Wall -o /tmp/tb_fir.out \
    sim/rtl/tb/transposed_form/tb_fir_transposed_n43.v \
    rtl/transposed_form/n43/fir_transposed_n43.v
vvp /tmp/tb_fir.out

# top testbench (decimator 포함)
iverilog -g2012 -Wall -o /tmp/tb_top.out \
    sim/rtl/tb/transposed_form/tb_fir_decimator_transposed_n43_top.v \
    rtl/transposed_form/n43/fir_transposed_n43.v \
    rtl/transposed_form/n43/fir_decimator_transposed_n43_top.v \
    rtl/direct_form/decimator_m2_phase0.v
vvp /tmp/tb_top.out
```

---

## 10. 참고: N=5 Direct Form bring-up 기술 사항

새 RTL 작성 시 참고용. 이 섹션의 내용은 변경하지 말 것.

### 입력 신호 프로파일

| 항목    | 값                     |
| ------- | ---------------------- |
| 파형    | 3-tone sine (결정론적) |
| 샘플 수 | 8192                   |
| 주파수  | 5 MHz, 20 MHz, 30 MHz  |
| 진폭    | 0.3, 0.3, 0.3          |
| 위상    | 0, 0, 0                |
| 헤드룸  | 0.1                    |
| 양자화  | tone 합산 후 1회       |

### N=5 FIR 파이프라인 (4단계가 된 이유)

초기 3단계 설계에서 `acc_reg → round/saturate → out_sample` 경로 125MHz 타이밍 위반.
round register 스테이지 추가해 4단계로 분리 후 WNS=0.449ns 클로저.

```
Stage 1: tap reg 저장
Stage 2: 5개 곱셈 → prod_reg[k] 저장
Stage 3: prod_reg 합산 → acc_reg 저장
Stage 4: round → round_reg, saturate → out_sample
```

N=43 Transposed Form은 carry chain이 없으므로 2단계로 시작.
타이밍 위반 시 round_reg 분리해서 3단계로 확장.

### decimator_m2_phase0.v 동작 규칙

- keep/drop 패턴: reset 후 첫 FIR-valid → keep, 다음 → drop, 이후 반복
- state 전진 조건: FIR-side `in_valid=1`일 때만 phase 토글 (매 클럭이 아님)
- decimator latency: kept FIR sample 기준 1 cycle
- `out_valid=0`일 때 `out_sample`: 이전 값 hold (비교 대상 아님)

### N=5 Vivado 프로젝트 경로

```
프로젝트: /mnt/workspace/10_zynq-fir-decimation-ip_build/fir_bringup_n5/fir_bringup_n5.xpr
타이밍:   /mnt/workspace/10_zynq-fir-decimation-ip_build/fir_bringup_n5/
          fir_bringup_n5.runs/impl_1/top_zybo_bringup_n5_timing_summary_routed.rpt
결과:     WNS=0.449ns  TNS=0.000ns  WHS=0.072ns  THS=0.000ns
```

```

```
