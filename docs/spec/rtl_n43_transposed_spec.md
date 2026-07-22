# N=43 Transposed Form FIR Decimator RTL Spec

- 작성일: 2026-05-07
- 대상: `rtl/transposed_form/` 모듈 전체 (FIR 코어 + 데시메이터 + AXI-Stream 래퍼)
- 용도: 포트 계약, latency, valid 규칙, AXI-Stream 핸드셰이크, TB 검증 기준
- 선행 문서: `docs/spec/fixed_model_spec.md`, `docs/spec/bringup_input_signal_spec.md`
- 설계 근거: `docs/log/14_transposed_form_rtl_decisions.md`, `docs/log/17_axi_stream_wrapper_design_decisions.md`

---

## 0. 현행화 주석 (2026-07-22)

이 스펙은 v1 코어와 초기 래퍼(2026-05-07 시점) 기준이다. 이후 변경 사항은 본문에
소급 반영하지 않고 여기에 요약한다.

1. **v2 코어 추가** — `fir_n43_v2` 계열(4-stage, round 스테이지 분리). FIR latency
   3→4 cycle, top 4→5 cycle. §1~§4의 latency·파이프라인 서술은 v1 기준이다.
   설계 근거 `docs/log/39`, 타이밍 `vivado/reports/sweep_summary_v2.md`.
2. **AXIS 래퍼 2차 수정** — §5(래퍼 valid 규칙)와 §7(핸드셰이크 계약)은 수정 전
   구조(depth-3 버퍼, auto-flush) 기준으로, 현행 RTL과 다르다. 현행 래퍼는
   skid 4칸, flush 제거, `s_axis_tready`에 `| s_axis_tlast` 항 추가(1차 수정,
   `docs/log/42`), 마지막 출력 hold-back(2차 수정, `docs/log/43`~`44`)이다.
   현행 계약의 정의와 검증 기준은 log 43 설계 절과 `sim/`의 `make run_bug` 회귀를
   기준으로 한다.
3. **타이밍 수치** — §1·§11의 WNS/자원은 초기 100 MHz 클로저 시점 값이다. 최신
   Fmax·자원·배포 주파수는 `vivado/reports/sweep_summary.md`/`_v2.md`.

## 1. 시스템 사양

| 항목 | 값 |
|------|----|
| 타겟 보드 | Zybo Z7-20 (xc7z020clg400-1) |
| 클럭 | 100 MHz (PS `FCLK_CLK0`) |
| 입력 샘플 포맷 | Q1.15 (signed 16-bit) |
| 출력 샘플 포맷 | Q1.15 (signed 16-bit) |
| FIR 탭 수 | N = 43 |
| 처리 구조 | 1 sample/cycle 병렬 (N=43 MAC 동시) |
| 디시메이션 계수 | M = 2, phase = 0 |
| 입력 샘플레이트 | 100 MHz |
| 출력 샘플레이트 | 50 MHz |
| Vivado 타이밍 (코어) | WNS = +0.278 ns @ 100 MHz (DSP48=16, LUT=1827) |
| Vivado 타이밍 (BD) | WNS = +1.239 ns @ 100 MHz |

---

## 2. 모듈 계층 구조

```
fir_decimator_n43_axis          ← AXI-Stream 래퍼 (PS-PL 연동 top)
└── fir_decimator_n43           ← FIR + 데시메이터 연결 top
    ├── fir_n43                 ← FIR 코어
    └── decimator_m2_phase0     ← 데시메이터 (공유, direct_form/에 위치)
```

파일 위치:

```
rtl/
├── direct_form/
│   └── decimator_m2_phase0.v           ← fir_n43, direct_form 공유
└── transposed_form/
    └── n43/
        ├── fir_n43.v
        ├── fir_decimator_n43.v
        └── fir_decimator_n43_axis.v
```

---

## 3. 모듈별 포트 계약

### 3.1 `fir_n43` — FIR 코어

```verilog
module fir_n43 (
    input  wire               clk,
    input  wire               rst,
    input  wire               in_valid,
    input  wire signed [15:0] in_sample,
    output reg                out_valid,
    output reg  signed [15:0] out_sample
);
```

| 포트 | 방향 | 폭 | 설명 |
|------|------|----|------|
| `clk` | in | 1 | 클럭, 100 MHz |
| `rst` | in | 1 | 비동기 액티브 하이 리셋 |
| `in_valid` | in | 1 | 입력 샘플 유효 |
| `in_sample` | in | 16 | Q1.15 입력 샘플 |
| `out_valid` | out | 1 | 출력 샘플 유효 (registered) |
| `out_sample` | out | 16 | Q1.15 출력 샘플 (registered) |

**내부 주요 신호:**

| 신호 | 폭 | 설명 |
|------|----|------|
| `prod_reg[0:42]` | 48-bit signed | Stage 1 곱셈 결과 레지스터 |
| `z[0:42]` | 48-bit signed | Q2.30 누산 상태 레지스터 |
| `round_reg` | 48-bit signed | Stage 2→3 분리용 반올림 중간 레지스터 |

**파이프라인 3단계:**

```
Stage 1: in_valid=1 → h[k] * in_sample → prod_reg[k]   (k=0..42, 병렬)
Stage 2: prod_reg[k] + z[k+1] → z[k],  round(z[0]) → round_reg
Stage 3: saturate(round_reg) → out_sample,  out_valid=1
```

> 초기 설계는 2단계였으나, Stage 2 critical path(48-bit 덧셈 + round + saturate)가 WNS=−1.155 ns로 위반. round_reg를 삽입해 3단계로 확장 후 WNS=+0.278 ns 달성. `log/16_vivado_timing_closure_transposed_n43.md` 참고.

**계수:**

`localparam signed [15:0] COEFF_k` 하드코딩 (k=0..42). Q1.15 정수값:

```
10, 0, -33, -32, 47, 107, 0, -197, -159, 206,
425, 0, -674, -522, 654, 1336, 0, -2258, -1939, 2995,
9864, 13109, 9864, 2995, -1939, -2258, 0, 1336, 654, -522,
-674, 0, 425, 206, -159, -197, 0, 107, 47, -32,
-33, 0, 10
```

`sum(abs(h_q)) = 56025`, worst-case acc bound = 32768 × 56025 = 1,835,827,200 (signed 32-bit 범위 내).

---

### 3.2 `decimator_m2_phase0` — 데시메이터

```verilog
module decimator_m2_phase0 (
    input  wire               clk,
    input  wire               rst,
    input  wire               in_valid,
    input  wire signed [15:0] in_sample,
    output reg                out_valid,
    output reg  signed [15:0] out_sample
);
```

| 포트 | 방향 | 폭 | 설명 |
|------|------|----|------|
| `clk` | in | 1 | 클럭 |
| `rst` | in | 1 | 비동기 액티브 하이 리셋 |
| `in_valid` | in | 1 | FIR 출력 유효 |
| `in_sample` | in | 16 | FIR 출력 샘플 |
| `out_valid` | out | 1 | 데시메이션 출력 유효 (registered) |
| `out_sample` | out | 16 | 데시메이션 출력 샘플 (registered) |

**동작:**
- `in_valid=1`마다 `keep_next` 토글로 keep/drop 판정
- reset 후 첫 번째 in_valid 샘플: keep (`keep_next` 초기값 = 1)
- keep 샘플은 1 cycle 후 out_valid=1, out_sample에 출력
- in_valid=0이면 `keep_next` hold

---

### 3.3 `fir_decimator_n43` — FIR + 데시메이터 top

```verilog
module fir_decimator_n43 (
    input  wire               clk,
    input  wire               rst,
    input  wire               in_valid,
    input  wire signed [15:0] in_sample,
    output wire               out_valid,
    output wire signed [15:0] out_sample
);
```

`fir_n43` → `decimator_m2_phase0` 직렬 연결. 포트 인터페이스는 `fir_n43`과 동일.

---

### 3.4 `fir_decimator_n43_axis` — AXI-Stream 래퍼

```verilog
module fir_decimator_n43_axis #(
    parameter integer TLAST_N = 512
) (
    input  wire               aclk,
    input  wire               aresetn,

    input  wire               s_axis_tvalid,
    output wire               s_axis_tready,
    input  wire signed [15:0] s_axis_tdata,
    input  wire               s_axis_tlast,

    output wire               m_axis_tvalid,
    input  wire               m_axis_tready,
    output wire signed [15:0] m_axis_tdata,
    output wire               m_axis_tlast
);
```

| 포트 | 방향 | 폭 | 설명 |
|------|------|----|------|
| `aclk` | in | 1 | AXI 클럭, 100 MHz |
| `aresetn` | in | 1 | 동기 액티브 로우 리셋 |
| `s_axis_tvalid` | in | 1 | 슬레이브(입력) 유효 |
| `s_axis_tready` | out | 1 | 슬레이브(입력) 준비 |
| `s_axis_tdata` | in | 16 | Q1.15 입력 샘플 |
| `s_axis_tlast` | in | 1 | 포트 선언만, 내부 로직 미연결 |
| `m_axis_tvalid` | out | 1 | 마스터(출력) 유효 |
| `m_axis_tready` | in | 1 | 마스터(출력) 준비 |
| `m_axis_tdata` | out | 16 | Q1.15 출력 샘플 |
| `m_axis_tlast` | out | 1 | `TLAST_N`번째 전송마다 펄스 |

**파라미터:**

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `TLAST_N` | 512 | M_AXIS TLAST 주기 (샘플 수) |

**s_axis_tlast 미연결 이유:** DMA MM2S가 전송 끝에 TLAST를 보내지만, 코어는 패킷 경계와 무관하게 연속 스트림을 처리한다. 내부 연결 시 파이프라인 상태 소실 위험. 포트 선언만 유지하는 이유는 Vivado IP 패키저 DRC 경고 방지.

---

## 4. Latency 계약

| 블록 | Latency | 기준 |
|------|---------|------|
| `fir_n43` | **3 cycles** | accepted input (in_valid=1인 posedge) 기준 |
| `decimator_m2_phase0` | **1 cycle** | keep 샘플 기준 |
| `fir_decimator_n43` (top) | **4 cycles** | keep 샘플 기준 |

```
accepted input @ cycle t
  → Stage 1 완료 @ t+1   (prod_reg)
  → Stage 2 완료 @ t+2   (z[k] 갱신, round_reg)
  → Stage 3 완료 @ t+3   (out_valid=1, fir_n43 출력)
  → decimator keep @ t+4 (out_valid=1, fir_decimator_n43 출력)
```

drop 샘플: `fir_decimator_n43.out_valid`를 만들지 않음.

**AXI-Stream 래퍼 latency:** 위 4 cycles에 depth-3 출력 버퍼 지연이 추가된다. M_AXIS 전송 성사 시점은 다운스트림(DMA S2MM)의 TREADY에 따라 변동.

---

## 5. Valid 규칙

### 코어 (fir_n43 / fir_decimator_n43)

- **in_valid=1**: 해당 posedge에서 in_sample이 채택됨. 파이프라인 진행.
- **in_valid=0**: `z[k]` hold, `prod_reg` 갱신 없음. 파이프라인 bubble.
- **out_valid=0** 시 `out_sample`: 이전 값 hold. 비교 대상 아님.
- decimator의 `keep_next` 토글: **in_valid=1인 FIR out_valid=1 펄스**를 기준으로 움직임.

### AXI-Stream 래퍼

- **입력 채택 조건**: `s_axis_tvalid & s_axis_tready`가 동시에 1인 posedge
- **출력 전송 성사 조건**: `m_axis_tvalid & m_axis_tready`가 동시에 1인 posedge
- **s_axis_tready**: `!valid1` (depth-3 버퍼의 reg1이 빌 때 허용)
- **백프레셔**: `m_axis_tready=0` → `s_axis_tready=0` → 입력 stall

---

## 6. 리셋 규칙

### fir_n43 / decimator_m2_phase0 / fir_decimator_n43

- **극성**: 비동기 액티브 하이 (`posedge rst`)
- **초기화 대상**:

| 신호 | 리셋 값 |
|------|---------|
| `z[k]` (k=0..42) | 0 |
| `prod_reg[k]` (k=0..42) | 0 |
| `round_reg` | 0 |
| `out_valid` | 0 |
| `out_sample` | 0 |
| `keep_next` (decimator) | 1 (reset 후 첫 샘플 keep) |

### fir_decimator_n43_axis

- **극성**: 동기 액티브 로우 (`aresetn`)
- 래퍼 내부에서 `rst_core = ~aresetn`으로 변환해 코어에 전달
- **초기화 대상 추가**:

| 신호 | 리셋 값 |
|------|---------|
| `valid0/valid1/valid2` | 0 |
| `data0/data1/data2` | 0 |
| TLAST 카운터 | 0 |

---

## 7. AXI-Stream 핸드셰이크 계약

### 출력 버퍼 (depth-3)

```
reg0 (data0/valid0): M_AXIS에 내미는 현재 샘플
reg1 (data1/valid1): reg0 점유 시 대기 슬롯 1
reg2 (data2/valid2): reg1 점유 시 대기 슬롯 2
```

백프레셔 임계: `s_axis_tready = !valid1`

> `valid1/valid2`는 registered 신호이므로 stall이 1사이클 늦게 전파된다. 이 지연 동안 in_valid가 1회 누출되고, FIR 3-cycle 파이프라인 + M=2 조합으로 최대 1개의 decimated 출력이 발생한다. `~valid1`으로 트리거하면 valid2가 해당 출력을 흡수해 오버플로 없음. (`~valid2`로 트리거 시 DROP 발생.)

### TLAST 카운터

- M_AXIS 전송 성사(`m_axis_tvalid & m_axis_tready`)마다 카운터 +1
- 카운터 == `TLAST_N-1` → `m_axis_tlast=1`, 카운터 = 0

---

## 8. 수치 계약 (arithmetic)

| 항목 | 계약 |
|------|------|
| 입력/계수 포맷 | Q1.15, signed 16-bit |
| 내부 곱셈 결과 | Q2.30, signed 48-bit (sign-extend) |
| 누산기 (`z[k]`) | signed 48-bit |
| 반올림 | ties-away-from-zero (Q2.30 → Q1.15) |
| 포화 | clip(−32768, 32767), 출력 1회만 |
| 중간 overflow 처리 | 없음 (wide accumulator로 exact 누산) |

---

## 9. TB 규칙 및 검증 기준

### 9.1 벡터 파일

| 파일 | 내용 |
|------|------|
| `sim/vectors/transposed_form/n43/input_q15.hex` | Q1.15 입력 (8192샘플) |
| `sim/vectors/transposed_form/n43/expected_fir_q15.hex` | `fir_n43` 기대 출력 (8234샘플 = 8192 + 42) |
| `sim/vectors/transposed_form/n43/expected_decim_q15.hex` | `fir_decimator_n43` 기대 출력 (4117샘플) |

벡터 생성:
```bash
# golden 출력 생성
python -m sim.python.run_compare_ideal_vs_fixed --num-taps 43 --form transposed

# hex 변환
python -m sim.python.export_rtl_bringup_vectors \
    --num-taps 43 \
    --input-dir sim/output/ideal_vs_fixed_trans_n43 \
    --output-dir sim/vectors/transposed_form/n43
```

### 9.2 입력 구동 규칙

- 실제 입력 8192샘플 뒤 **zero 42개**를 in_valid=1로 추가 전송 (full convolution tail flush)
- 이유: N=43이면 tail = N-1 = 42. FIR 내부 pipeline을 drain해야 expected_fir_q15.hex 전체를 수신 가능

### 9.3 비교 규칙

- **fir_n43 TB**: `out_valid=1`인 posedge에서만 `expected_fir_q15.hex`와 비교
- **fir_decimator_n43 TB**: `out_valid=1`인 posedge에서만 `expected_decim_q15.hex`와 비교
- **AXI-Stream TB**: **`m_axis_tvalid & m_axis_tready`가 동시에 1인 posedge**에서만 비교

  > tvalid=1이어도 tready=0이면 전송 미성사 → 비교 금지, 카운터 증가 금지.

### 9.4 AXI-Stream TB 시나리오

| 시나리오 | 내용 | 완료 기준 |
|----------|------|-----------|
| TREADY=1 | m_axis_tready 항상 1 | 4117 샘플 bit-exact 일치 |
| 백프레셔 | m_axis_tready 30% 확률 | 핸드셰이크 카운트 4117 일치 |
| TLAST | TREADY=1 | 512·1024번째 전송에서 m_axis_tlast=1 확인 |
| aresetn | 리셋 재인가 후 재시작 | 버퍼·카운터 초기화, 이후 출력 정상 |

### 9.5 워치독

- `fir_n43 TB`: in_valid 또는 out_valid 없이 1000 cycle 초과 시 FATAL
- `axis TB`: M_AXIS 전송 성사 없이 1000 cycle 초과 시 deadlock FATAL

### 9.6 PASS/FAIL 기준

- 모든 expected 샘플을 mismatch 없이 소비 → PASS
- mismatch 1개라도 발생 → FAIL (sample index, actual, expected 출력)
- drain 구간 내 expected 수 미달 → FAIL

---

## 10. 시뮬레이션 빌드 명령

프로젝트 루트에서 실행:

```bash
# 전체 빌드
make -C sim all

# 전체 실행
make -C sim run_all
```

개별 타겟:

```bash
# fir_n43 단독
iverilog -g2012 -o sim/build/tb_fir_n43.out \
    sim/rtl/tb/transposed_form/tb_fir_n43.sv \
    rtl/transposed_form/n43/fir_n43.v
vvp sim/build/tb_fir_n43.out

# fir_decimator_n43 (FIR + decimator)
iverilog -g2012 -o sim/build/tb_fir_decimator_n43.out \
    sim/rtl/tb/transposed_form/tb_fir_decimator_n43.sv \
    rtl/direct_form/decimator_m2_phase0.v \
    rtl/transposed_form/n43/fir_n43.v \
    rtl/transposed_form/n43/fir_decimator_n43.v
vvp sim/build/tb_fir_decimator_n43.out

# fir_decimator_n43_axis (AXI-Stream 래퍼 포함)
iverilog -g2012 -o sim/build/tb_fir_decimator_n43_axis.out \
    sim/rtl/tb/transposed_form/tb_fir_decimator_n43_axis.sv \
    rtl/direct_form/decimator_m2_phase0.v \
    rtl/transposed_form/n43/fir_n43.v \
    rtl/transposed_form/n43/fir_decimator_n43.v \
    rtl/transposed_form/n43/fir_decimator_n43_axis.v
vvp sim/build/tb_fir_decimator_n43_axis.out
```

---

## 11. Vivado 합성 결과

| 항목 | 값 |
|------|----|
| 대상 클럭 | 100 MHz (10 ns period) |
| WNS (코어 standalone) | +0.278 ns |
| WNS (Block Design, PS-PL 전체) | +1.239 ns |
| DSP48 | 16 |
| LUT | 1827 |
| Vivado 버전 | 2024.2 |

Vivado 빌드 재현:
```bash
vivado -mode batch -source vivado/fir_n43/build_fir_transposed_n43.tcl
```

Block Design 재현:
```bash
# Vivado TCL Console에서:
source vivado/fir_n43/bd_fir_dma.tcl
```

---

## 12. 구현 체크리스트

- [X] `fir_n43.v` — iverilog PASS, bit-exact golden 일치 (8234샘플)
- [X] `fir_decimator_n43.v` — iverilog PASS, bit-exact golden 일치 (4117샘플)
- [X] `fir_decimator_n43_axis.v` — iverilog PASS (TREADY=1, 백프레셔, TLAST, aresetn 4시나리오)
- [X] Vivado 100 MHz 타이밍 클로저 WNS=+0.278 ns
- [X] Block Design DRC PASS, 비트스트림 생성 완료 WNS=+1.239 ns
- [ ] 실보드 UART 동작 확인 (보드 대기)
- [ ] Python FFT 시각화 30 MHz ≥ 60 dB 감쇠 확인 (보드 대기)
