# 16. Vivado Timing Closure — N=43 Transposed Form

- 작성일: 2026-05-03
- 단계: 8
- 목적: N=43 Transposed Form을 Vivado 100 MHz 기준으로 합성/구현할 때 발생한 두 문제와 해결 과정을 기록한다
- 선행 문서: `docs/log/14_transposed_form_rtl_decisions.md`, `docs/log/11_vivado_timing_violation_and_fir_pipelining.md`

## 1) 빌드 구성

대상 소스는 아래 세 파일이다.

- `rtl/transposed_form/n43/fir_transposed_n43.v`
- `rtl/transposed_form/n43/fir_decimator_transposed_n43_top.v`
- `rtl/direct_form/decimator_m2_phase0.v`

XDC에는 100 MHz 클럭 제약 하나만 선언했다.

```xdc
create_clock -period 10.000 -name clk [get_ports clk]
```

보드 sysclk(125 MHz, K17 핀) + Clocking Wizard 구조는 Step 4 AXI-Stream 래퍼 단계에서 구성한다. 이 단계의 목적은 IP 코어의 타이밍 검증이므로 port clock 직접 선언이 표준적인 방법이다.

빌드는 `vivado/build_fir_transposed_n43.tcl`로 자동화했다. 합성, 구현, 타이밍/리소스 리포트 생성까지 한 번에 수행한다.

## 2) 문제 1: board_part 미설치로 인한 즉시 종료

TCL 스크립트 첫 실행에서 Vivado가 즉시 에러로 종료됐다.

```
ERROR: [Board 49-71] The board_part definition was not found for
digilentinc.com:zybo-z7-20:part0:1.1.
```

원인은 빌드 머신에 Digilent board repository가 설치되어 있지 않은 것이었다. 타이밍 클로저 단계에서 board_part는 불필요하다. `create_project`에 `-part xc7z020clg400-1`이 이미 직접 지정되어 있으므로 `set_property board_part` 한 줄을 제거하는 것으로 해결됐다.

## 3) 문제 2: WNS = −1.155 ns 타이밍 위반

board_part 문제 해결 후 합성/구현은 완료됐지만 타이밍이 깨졌다.

```
WNS = -1.155 ns   (required 10.000 ns, arrived 11.155 ns)
```

## 4) Critical path 분석

Vivado timing summary의 worst path:

```
Source:      u_fir_transposed_n43/z_reg[1][6]/C
Destination: u_fir_transposed_n43/out_sample_reg[12]/D
Data Path Delay: 11.075 ns
Logic Levels:    23  (CARRY4=17  LUT1=2  LUT2=1  LUT3=1  LUT4=1  LUT5=1)
```

Stage 2 안에서 아래 연산 전체가 한 사이클에 들어가 있었다.

```
z_reg[1]
  → prod_reg[0] + z[1]    (48-bit 덧셈)
  → |value|               (48-bit 조건부 negate, CARRY4 chain)
  → + ROUND_BIAS          (48-bit 덧셈, CARRY4 chain)
  → >> 15                 (wiring, free)
  → 조건부 negate         (16-bit)
  → saturate              (비교 + mux)
  → out_sample_reg
```

17개 CARRY4 체인이 11.075 ns로 100 MHz 클럭 주기(10 ns)를 넘겼다.

## 5) DSP48 카운트 오독

TCL 실행 중 `DSP48 used = 0`이 터미널에 찍혔다.

```tcl
# 잘못된 필터 (결과 항상 0)
set dsp_count [llength [get_cells -hierarchical -filter {PRIMITIVE_TYPE =~ DSP*}]]
```

실제 `report_utilization` 파일을 열면 처음부터 DSP48이 16개였다.

```
| DSP48E1 only |   16 |
```

올바른 TCL 필터는 `REF_NAME =~ DSP48*`이다. 타이밍 위반의 원인은 DSP48 미사용이 아니라 Stage 2의 누산+반올림+포화 경로 전체가 한 사이클에 너무 길게 들어간 것이다.

참고로 43개 계수 중 DSP48이 16개인 이유는 다음과 같다. 계수 중 8개(k=1,6,11,16,26,31,36,41)가 0이라 곱셈 자체가 사라지고, 소계수(±10, ±32, ±33, ±47 등)는 Vivado가 shift-and-add로 구현하는 편이 더 효율적이기 때문이다. ±674 이상의 대계수에만 DSP48이 배정됐다.

## 6) 해결: round_reg 스테이지 추가 (3단계 확장)

`docs/log/14_transposed_form_rtl_decisions.md`에 사전 결정된 방침을 그대로 적용했다.

> 타이밍 위반 시 Stage 2를 → round_reg 저장 + sat 출력으로 분리 → 3단계

```
변경 전 (2단계)
  Stage 1: in_valid → prod_reg[k], prod_valid
  Stage 2: prod_valid → z[k] 갱신 + round + saturate → out_sample, out_valid

변경 후 (3단계)
  Stage 1: in_valid → prod_reg[k], prod_valid
  Stage 2: prod_valid → z[k] 갱신 + round → round_reg, round_valid
  Stage 3: round_valid → saturate(round_reg) → out_sample, out_valid
```

`round_reg`(48-bit)를 추가해서 반올림 연산 결과를 Stage 2와 3 사이에서 잘랐다. Stage 3은 saturate 비교+mux만 수행하므로 경로가 매우 짧다. 이 분리로 critical path가 두 사이클로 나뉘어 여유가 생겼다.

FIR latency가 2 cycles → 3 cycles로 늘어나고 top latency는 3 cycles → 4 cycles로 재조정된다. testbench는 `out_valid` 기준 비교이므로 latency 변화에 무관하게 동일하게 동작한다.

## 7) 수정 후 결과

iverilog 재검증:

```
PASS tb_fir_transposed_n43:               observed 8234 samples
PASS tb_fir_decimator_transposed_n43_top: observed 4117 samples
```

Vivado 재빌드:

```
WNS = +0.278 ns  (100 MHz 클로저 성공)
```

리소스: Slice LUTs 1827 (3.43%), Registers 2113 (1.99%), DSP48E1 16 (7.27%).

## 8) 의미

이번 단계에서 확인된 핵심은 두 가지다.

첫째, Transposed Form은 Direct Form과 달리 z[k] 업데이트 경로에 carry chain이 없지만, 반올림 함수(절댓값 + ROUND_BIAS 덧셈 + 조건부 negate)가 48-bit 연산을 두 번 연달아 수행하기 때문에 단일 사이클에 넣으면 100 MHz에서 충분히 위반이 발생한다. N=5 Direct Form의 경험(문서 11번)과 다른 경로이지만 근본적인 대응 방법(경로 중간에 레지스터 삽입)은 동일했다.

둘째, Vivado의 상수 계수 곱셈 최적화 결과를 TCL로 직접 쿼리할 때는 필터 문법을 주의해야 한다. `report_utilization` 파일을 읽는 것이 더 신뢰성 있다.

N=43 Transposed Form IP 코어의 100 MHz 타이밍 클로저가 완료됐다. 다음 단계는 AXI-Stream 래퍼 구현이다.
