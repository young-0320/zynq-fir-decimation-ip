# 16. Vivado Timing Closure — N=43 Transposed Form

- 작성일: 2026-05-03
- 단계: Step 3
- 목적: N=43 Transposed Form `fir_decimator_transposed_n43_top`을 Vivado 100 MHz 기준으로 합성/구현했을 때 발생한 두 가지 문제와 해결 과정을 기록한다.

선행 문서:
- `docs/log/14_transposed_form_rtl_decisions.md` — 파이프라인 설계 결정
- `docs/log/11_vivado_timing_violation_and_fir_pipelining.md` — N=5 Direct Form 타이밍 위반 해결 사례

---

## 1. 빌드 환경 및 구성

### 대상 소스

| 파일 | 역할 |
|------|------|
| `rtl/transposed_form/n43/fir_transposed_n43.v` | N=43 Transposed Form FIR (2단계 파이프라인 초기) |
| `rtl/transposed_form/n43/fir_decimator_transposed_n43_top.v` | FIR + decimator_m2_phase0 연결 top |
| `rtl/direct_form/decimator_m2_phase0.v` | M=2 phase=0 decimator |
| `rtl/transposed_form/n43/constrs/zybo_n43.xdc` | 100 MHz 클럭 제약 |

### XDC 클럭 제약

이 단계에서는 보드 물리 핀 제약 없이 `clk` 포트에 100 MHz를 직접 선언했다.

```xdc
create_clock -period 10.000 -name clk [get_ports clk]
```

보드 sysclk(125 MHz, K17 핀)과 Clocking Wizard를 사용하는 구조는 Step 4 AXI-Stream 래퍼 단계에서 구성한다. 이 단계는 IP 코어의 타이밍 검증이 목적이므로 port clock 직접 선언이 표준적인 방법이다.

### TCL 빌드 스크립트

`vivado/build_fir_transposed_n43.tcl`에 프로젝트 생성, 합성, 구현, 타이밍/리소스 리포트 생성을 자동화했다.

```bash
# repo root에서 실행
vivado -mode batch -source vivado/build_fir_transposed_n43.tcl
```

---

## 2. 문제 1: board_part 미설치로 인한 즉시 종료

### 증상

TCL에 아래 한 줄이 있었다.

```tcl
set_property board_part digilentinc.com:zybo-z7-20:part0:1.1 [current_project]
```

실행 직후 Vivado가 에러를 내고 종료됐다.

```
ERROR: [Board 49-71] The board_part definition was not found for
digilentinc.com:zybo-z7-20:part0:1.1. The project's board_part property was
not set, but the project's part property was set to xc7z020clg400-1.
```

### 원인

빌드 머신에 Digilent board repository가 설치되어 있지 않아 board_part 정의를 찾지 못했다.

### 해결

`set_property board_part` 한 줄 제거. `create_project` 에 이미 `-part xc7z020clg400-1`가 지정되어 있으므로 타이밍 클로저에 board_part는 불필요하다.

```tcl
# 제거 전
set_property board_part digilentinc.com:zybo-z7-20:part0:1.1 [current_project]
set_property target_language Verilog [current_project]

# 제거 후
set_property target_language Verilog [current_project]
```

---

## 3. 문제 2: WNS = −1.155 ns (타이밍 위반)

### 증상

board_part 문제 해결 후 합성/구현까지 완료됐지만 타이밍이 깨졌다.

```
WNS = -1.155 ns   (required 10.000 ns, arrived 11.155 ns)
```

### Critical path 분석

Vivado timing summary의 worst path:

```
Source:      u_fir_transposed_n43/z_reg[1][6]/C
Destination: u_fir_transposed_n43/out_sample_reg[12]/D
Data Path Delay: 11.075 ns
Logic Levels:    23  (CARRY4=17  LUT1=2  LUT2=1  LUT3=1  LUT4=1  LUT5=1)
```

Stage 2 안에서 아래 연산이 하나의 클럭 사이클에 들어가 있었다.

```
z_reg[1]
  → prod_reg[0] + z[1]    (48-bit 덧셈, ~6 CARRY4)
  → |value|               (48-bit 조건부 negate, CARRY4 chain)
  → + ROUND_BIAS          (48-bit 덧셈, CARRY4 chain)
  → >> 15                 (wiring, free)
  → 조건부 negate         (16-bit)
  → saturate              (비교 + mux)
  → out_sample_reg
```

17개 CARRY4 체인이 11.075 ns로 100 MHz 클럭 주기(10 ns)를 넘겼다.

### DSP48 = 0 오독

TCL 쿼리 결과로 `DSP48 used = 0`이 터미널에 찍혔다.

```tcl
# 잘못된 필터 — 결과 항상 0
set dsp_count [llength [get_cells -hierarchical -filter {PRIMITIVE_TYPE =~ DSP*}]]
```

실제 `report_utilization` 파일을 확인하면:

```
| DSPs           |   16 |
|   DSP48E1 only |   16 |
```

처음부터 16개의 DSP48이 추론되어 있었다. TCL 필터 문법(`PRIMITIVE_TYPE`)이 틀렸던 것이며, 올바른 필터는 `REF_NAME =~ DSP48*`이다.

43개 계수 중 DSP48이 16개인 이유:

- 8개 계수가 0 (k=1,6,11,16,26,31,36,41) → 곱셈 불필요
- 소계수(±10, ±32, ±33, ±47 등)는 Vivado가 shift-and-add로 더 효율적으로 구현
- 대계수(±674 이상)만 DSP48에 할당

타이밍 위반의 원인은 DSP48 미사용이 아니라 Stage 2의 누산+반올림+포화 경로 전체가 한 사이클에 너무 길게 들어간 것이다.

### 해결: 3단계 파이프라인으로 확장

`docs/log/14_transposed_form_rtl_decisions.md`에 사전 결정된 방침:

> 타이밍 위반 시 Stage 2를 → round_reg 저장 + sat 출력으로 분리 → 3단계

이에 따라 `fir_transposed_n43.v`를 수정했다.

**변경 전 (2단계):**

```
Stage 1: in_valid → prod_reg[k] 저장, prod_valid
Stage 2: prod_valid → z[k] 갱신 + round(prod_reg[0]+z[1]) + saturate → out_sample, out_valid
```

**변경 후 (3단계):**

```
Stage 1: in_valid → prod_reg[k] 저장, prod_valid
Stage 2: prod_valid → z[k] 갱신 + round(prod_reg[0]+z[1]) → round_reg, round_valid
Stage 3: round_valid → saturate(round_reg) → out_sample, out_valid
```

핵심은 `round_reg`라는 48-bit 레지스터를 추가해서 반올림 연산 결과를 Stage 2와 Stage 3 사이에서 잘라낸 것이다. Stage 3은 `saturate`만 수행하므로 경로가 매우 짧다.

```verilog
// Stage 2 (변경 후)
always @(posedge clk or posedge rst) begin
    if (prod_valid) begin
        z[0]  <= prod_reg[0] + z[1];
        // ... z[1]~z[42] 갱신 ...
        round_reg   <= round_q2_30_to_q1_15(prod_reg[0] + z[1]);
        round_valid <= 1'b1;
    end else begin
        round_valid <= 1'b0;
    end
end

// Stage 3 (신규)
always @(posedge clk or posedge rst) begin
    if (round_valid) begin
        out_sample <= saturate_to_q1_15(round_reg);
        out_valid  <= 1'b1;
    end else begin
        out_valid <= 1'b0;
    end
end
```

---

## 4. 수정 후 검증

### iverilog 재검증

3단계 파이프라인으로 수정 후 FIR latency가 3 cycles로 늘어났지만 testbench는 `out_valid` 기준 비교이므로 latency 변화와 무관하게 동일하게 동작한다.

```
PASS tb_fir_transposed_n43:              observed 8234 samples
PASS tb_fir_decimator_transposed_n43_top: observed 4117 samples
```

### Vivado 재빌드 결과

```
WNS = +0.278 ns  ✅
```

리소스:

| 항목 | 값 | Util% |
|------|----|-------|
| Slice LUTs | 1827 | 3.43% |
| Slice Registers | 2113 | 1.99% |
| DSP48E1 | 16 | 7.27% |

---

## 5. Latency 재조정

3단계 전환에 따라 `docs/log/14_transposed_form_rtl_decisions.md`의 latency 계약을 갱신한다.

| 블록 | 2단계 (초기) | 3단계 (확정) |
|------|------------|------------|
| FIR latency | 2 cycles | 3 cycles |
| Decimator latency | 1 cycle | 1 cycle |
| Top latency | 3 cycles | 4 cycles |

---

## 6. 결론

| 항목 | 결과 |
|------|------|
| board_part 에러 | `set_property board_part` 제거로 해결 |
| WNS = −1.155 ns | round_reg 스테이지 추가로 3단계 확장 |
| iverilog 재검증 | FIR 8234 + decimator 4117 samples PASS |
| 최종 WNS | **+0.278 ns (100 MHz 클로저 성공)** |
| DSP48 | 16개 (Vivado 상수 곱셈 최적화) |

N=43 Transposed Form IP 코어의 100 MHz 타이밍 클로저가 완료됐다. 다음 단계는 AXI-Stream 래퍼 구현이다.
