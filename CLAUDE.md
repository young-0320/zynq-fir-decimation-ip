# zynq-axi-fir-decimation-ip — CLAUDE.md

Updated: 2026-05-03
Repository root: `/home/young/dev/10_zynq-fir-decimation-ip`
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

| 항목     | 값                         |
| -------- | -------------------------- |
| Fs_in    | 100 MHz                    |
| Fs_out   | 50 MHz (M=2)               |
| fp       | 15 MHz                     |
| fs       | 25 MHz                     |
| As       | ≥ 60 dB                    |
| N        | 43 (Kaiser window β=5.653) |
| 포맷     | Q1.15 signed 16-bit        |
| FIR 구조 | Transposed Form            |
| 클럭     | 100 MHz (Clocking Wizard)  |

---

## 3. 현재 완료 상태 및 작업 순서

```
Step 1  ✅  N=43 RTL 벡터 생성
Step 2  ✅  fir_transposed_n43.v + TB iverilog PASS
Step 3  ✅  fir_decimator_transposed_n43_top.v + TB PASS (4117 samples)
Step 4  ✅  Vivado 100MHz 타이밍 클로저 WNS=+0.278ns (DSP48=16, LUT=1827)
Step 5  🔄  AXI-Stream 래퍼  ← 현재 / M4 안전 마감선 (6월 말)
Step 6      PS-PL DMA 연동
Step 7      bare-metal C + UART
Step 8      PC Python FFT 실시간 시각화
```

**M4(6월 말)가 분기점.** M4 완성 → Plan A(실시간 시연) 계속. 미완성 → 스코프 재조정.

---

## 4. RTL 설계 확정 사항

근거 문서: `docs/log/14_transposed_form_rtl_decisions.md`

### 파이프라인 구조

```
[Stage 1] in_valid=1
    → h[k] * in_sample  (k=0..42, 43개 병렬) → prod_reg[k] 저장 (signed 48-bit)
    → prod_valid = 1

[Stage 2] prod_valid=1
    → z[k] = prod_reg[k] + z[k+1]  (k=0..41)
      z[42] = prod_reg[42]           ← B안: z[43] 더미 없음
    → round_reg = round(prod_reg[0] + z[1])
      ※ non-blocking 특성상 z[0] 직접 참조 불가 → prod_reg[0]+z[1] 직접 계산
    → round_valid = 1

[Stage 3] round_valid=1
    → out_sample = saturate(round_reg)
    → out_valid = 1
```

### 확정 결정 요약

| 항목        | 결정                                           |
| ----------- | ---------------------------------------------- |
| 처리 구조   | 1 sample/cycle 병렬 (N=43개 MAC 동시)          |
| 파이프라인  | 3단계 (100MHz 타이밍 위반으로 확장)            |
| FIR latency | 3 cycles                                       |
| Top latency | 4 cycles (keep sample 기준)                    |
| z[k] 비트폭 | signed 48-bit (Q2.30)                          |
| prod_reg[k] | signed 48-bit (32-bit 곱 → sign-extend)        |
| 반올림      | ties-away-from-zero, z[0] 출력 1회만           |
| 포화        | 출력 1회 clip(-32768, 32767)                   |
| in_valid=0  | z[k] hold, prod_valid=0, out_valid=0           |
| reset       | active-high, 전체 state 0                      |
| 계수 저장   | localparam 하드코딩 43개                       |
| z[42] 경계  | B안: `z[42] <= prod_reg[42]` (z[43] 더미 없음) |

### 포트 인터페이스

```verilog
input  wire               clk,
input  wire               rst,        // active-high
input  wire               in_valid,
input  wire signed [15:0] in_sample,
output reg                out_valid,
output reg  signed [15:0] out_sample
```

### 누산기 worst-case

```
max|z[k]| ≤ 32,768 × 56,025 = 1,835,827,200  → signed 32-bit 범위 안
RTL은 signed 48-bit 사용 (여유 + DSP48 정렬)
```

### 계수

`rtl/transposed_form/n43/fir_transposed_n43.v` 내 localparam COEFF_0..COEFF_42 참조.

---

## 5. 데모 시나리오 (확정)

| 시나리오 | 방식 | 핵심 |
|----------|------|------|
| 0 — 비교 시연 | PC Python만으로 실행 (보드 불필요) | FIR 없이 다운샘플만 → 앨리어싱 발생 / FIR 적용 → 제거. "왜 필요한가" |
| 1 — 기본 동작 | PS C코드로 고정 멀티톤(5/20/30MHz) 생성 → DMA → PL → UART → PC FFT | "제대로 동작하는가" |
| 2 — 인터랙티브 | 청중이 주파수 지정 → PC Python이 UART로 값 전송 → PS 즉석 생성 → 동일 파이프라인 | "직접 체험" |

전체 파이프라인: `docs/하드웨어 파이프라인.md` 참고.
처리 방식: 블록 처리. UART로는 주파수 값(숫자 몇 바이트)만 전송, 신호 데이터 아님.

---

## 6. decimator_m2_phase0.v 동작 규칙

재사용 모듈. 동작 규칙을 반드시 준수할 것.

- keep/drop 패턴: reset 후 첫 FIR-valid → keep, 다음 → drop, 이후 반복
- state 전진 조건: FIR-side `in_valid=1`일 때만 phase 토글 (매 클럭이 아님)
- decimator latency: kept FIR sample 기준 1 cycle
- `out_valid=0`일 때 `out_sample`: 이전 값 hold (비교 대상 아님)

---

## 7. 디렉토리 구조

```
rtl/
├── direct_form/
│   ├── bringup_n5/                            ✅ N=5 bring-up 완료
│   └── decimator_m2_phase0.v                  ✅ N=43 재사용
└── transposed_form/n43/
    ├── fir_transposed_n43.v                   ✅
    ├── fir_decimator_transposed_n43_top.v     ✅
    └── constrs/zybo_n43.xdc

sim/
├── python/
│   ├── run_compare_ideal_vs_fixed.py          ✅ --form 인수 지원
│   └── export_rtl_bringup_vectors.py          ✅
├── output/ideal_vs_fixed_trans_n43/           ✅ .npy 벡터
├── vectors/transposed_form/n43/               ✅ hex 벡터 (4종)
└── rtl/tb/transposed_form/
    ├── tb_fir_transposed_n43.v                ✅
    └── tb_fir_decimator_transposed_n43_top.v  ✅

model/
├── ideal/                                     ✅
└── fixed/                                     ✅ (direct_form + transposed_form)

docs/
    study_roadmap.md                               ✅ 단계별 학습 자료 (ZipCPU/Xilinx 문서 링크)
    하드웨어 파이프라인.md                          ✅ 데모 시나리오 0/1/2 및 파이프라인 구조
    summary_design_decisions.md                    ✅ 핵심 설계 결정 요약

docs/log/
    09_bringup_rtl_decisions.md
    13_transposed_form_golden_policy.md
    14_transposed_form_rtl_decisions.md
    15_rtl_vector_pipeline_extension.md
```

생성 벡터 구성:
```
sim/vectors/transposed_form/n43/
    input_q15.hex          (8192 lines)
    coeff_q15.hex          (43 lines)
    expected_fir_q15.hex   (8234 lines = 8192 + 42 flush)
    expected_decim_q15.hex (4117 lines)
```

---

## 8. 코드 스타일 규칙

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
- 로그 헤더 형식:

```markdown
# NN. English Title

- 작성일: YYYY-MM-DD
- 단계: N          ← 이전 로그 단계 +1, "Step N" 형식 쓰지 않음
- 목적: 한 줄 설명 (마침표 없음)
- 선행 문서: `docs/log/NN_*.md`  ← 없으면 생략
```

- 섹션 번호: `## 1)` 형식 사용 (`)` 사용, `.` 아님)
- 섹션 사이 `---` 구분선 사용 안 함
- 마지막 섹션: `## N) 의미` 서술형 — 결론 테이블 쓰지 않음
- 각 결정마다 근거(왜 이렇게 했는가) 포함
- `단계` 값: 직전 로그 +1 (현재 최신 16번 = 단계 8)

---

## 9. 자주 쓰는 명령어

```bash
# pytest 전체
.venv/bin/pytest -q

# 벡터 생성 (2단계)
.venv/bin/python -m sim.python.run_compare_ideal_vs_fixed --num-taps 43 --form transposed
.venv/bin/python -m sim.python.export_rtl_bringup_vectors \
    --num-taps 43 \
    --input-dir sim/output/ideal_vs_fixed_trans_n43 \
    --output-dir sim/vectors/transposed_form/n43

# FIR 단독 시뮬레이션
iverilog -g2012 -Wall -o /tmp/tb_fir.out \
    sim/rtl/tb/transposed_form/tb_fir_transposed_n43.v \
    rtl/transposed_form/n43/fir_transposed_n43.v
vvp /tmp/tb_fir.out

# Top (decimator 포함) 시뮬레이션
iverilog -g2012 -Wall -o /tmp/tb_top.out \
    sim/rtl/tb/transposed_form/tb_fir_decimator_transposed_n43_top.v \
    rtl/transposed_form/n43/fir_transposed_n43.v \
    rtl/transposed_form/n43/fir_decimator_transposed_n43_top.v \
    rtl/direct_form/decimator_m2_phase0.v
vvp /tmp/tb_top.out
```