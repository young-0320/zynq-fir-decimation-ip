# 09. Bring-up RTL 운영 규칙 2차 확정

- 작성일: 2026-04-12
- 단계: 5
- 목적: `N=5` direct-form RTL bring-up 구현 전에 운영 계약 10가지를 확정하고, 각 결정에 대한 이유 서술

## 1) 확정된 운영 규칙 10가지

### 1. 포트 인터페이스

bring-up RTL은 최소 streaming 인터페이스를 기준으로 한다.

```verilog
input         clk;
input         rst;
input         in_valid;
input  signed [15:0] in_sample;
output        out_valid;
output signed [15:0] out_sample;
```

이번 bring-up 범위에서는 `ready`, `in_last`, `coeff_load`, `phase_cfg`, AXI-Stream 포트는 두지 않는다.

이렇게 결정한 이유:

- 첫 목표는 AXI-Stream wrapper가 아니라 Python-vs-RTL bit-exact baseline이다.
- 제어 포트를 늘리면 FIR, decimator, top, testbench를 동시에 흔들게 되어 구현 churn이 커진다.
- 최소 포트 집합이 모듈 경계와 검증 범위를 가장 명확하게 만든다.

### 2. reset 규칙

reset 입력은 `rst` active-high로 통일한다. `rst=1`이면 reset 상태다.

reset 시 아래 stateful register는 모두 `0`으로 초기화한다.

- FIR delay registers
- decimator phase state
- `out_valid`
- `out_sample`

bring-up RTL은 `always @(posedge clk or posedge rst)` 형태를 기준으로 한다. 물리 버튼을 실제 보드에서 reset 소스로 쓸 때는 버튼 신호를 DUT에 직접 넣지 않고, debounce + synchronizer를 거친 clean reset net을 `rst`로 넣는다.

FPGA bring-up 데모에서는 별도 `start` 버튼을 두지 않는다. 전원 인가 직후 power-on reset이 끝나면 자동 실행하고, 이후 reset 버튼을 누르면 즉시 초기화되며, 버튼 release가 debounce된 뒤 sample `0`부터 자동 재시작한다.

이렇게 결정한 이유:

- reset 직후 FIR delay line과 decimator phase 상태가 정해져 있지 않으면 첫 샘플부터 golden 비교가 꼬인다.
- active-high `rst`는 현재 세션에서 가장 직관적으로 읽히는 polarity이며, 문서와 구현을 일치시키기 쉽다.
- reset 시 `out_sample=0`으로 고정하면 reset 구간 파형 해석이 단순해진다.
- 실제 FPGA 버튼은 bounce와 비동기 입력 문제가 있으므로, DUT 바깥에서 conditioning을 해야 bring-up 시연까지 안전하게 갈 수 있다.
- bring-up 단계에서 별도 start 버튼을 두지 않으면 top-level 제어가 단순해지고, reset release를 재시작 이벤트로 사용해 데모를 반복하기 쉽다.
- power-on reset 종료 후 자동 실행으로 두면 “전원 인가 후 반드시 버튼을 한 번 더 눌러야 시작”하는 비직관적 UX를 피할 수 있다.

### 3. valid 규칙

bring-up 범위에서는 backpressure를 두지 않고 연속 valid 입력을 가정한다.

- DUT는 `in_ready`를 내보내지 않는다.
- testbench는 실제 입력 구간 동안 `in_valid=1`을 유지한다.
- bubble 없는 연속 스트림을 기본 검증 패턴으로 둔다.

이렇게 결정한 이유:

- 첫 bring-up에서 필요한 것은 흐름 제어 검증이 아니라 datapath의 bit-exact 정합성이다.
- backpressure를 넣으면 DUT와 testbench 양쪽의 상태공간이 불필요하게 커진다.
- 이후 bubble이나 wrapper가 추가되더라도, 현재 core는 단순한 contiguous-input baseline으로 먼저 닫는 편이 디버깅 효율이 높다.

### 4. frame 종료와 tail flush 규칙

full convolution tail은 testbench의 zero padding으로 flush한다.

- `N=5`이므로 실제 입력 `8192`개 뒤에 zero sample `4`개를 `in_valid=1`로 더 넣는다.
- 별도 `in_last` 포트나 internal drain FSM은 이번 bring-up 범위에 두지 않는다.

이렇게 결정한 이유:

- Python golden은 입력 범위 밖 샘플을 `0`으로 간주하는 full convolution 계약을 사용한다.
- 마지막 입력 뒤 `N-1`개 zero sample을 넣는 방식이 이 계약과 정확히 맞는다.
- 이 방식이면 frame 종료 제어를 위해 DUT 내부에 별도 FSM을 추가할 필요가 없다.
- testbench가 가장 단순하고, Python vector와 RTL 동작의 대응도 가장 직접적이다.

### 5. coefficient 공급 방식

`N=5` FIR coefficient는 `fir_direct_n5.v` 내부에 하드코딩한다.

현재 Q1.15 coefficient 정수값은 아래와 같다.

- `88`
- `7069`
- `18455`
- `7069`
- `88`

이번 bring-up에서는 외부 coefficient load port를 두지 않는다.

이렇게 결정한 이유:

- coefficient를 고정하면 포트 수와 초기화 시나리오가 줄어든다.
- testbench와 board bring-up 경로가 단순해진다.
- 현재 목표는 generic FIR이 아니라 첫 bit-exact baseline이므로, coefficient programmability는 지금 우선순위가 아니다.

### 6. arithmetic 규칙

산술 정책은 아래와 같이 고정한다.

- input/coeff: signed 16-bit `Q1.15`
- product: signed `Q2.30`
- rounding: `round-to-nearest, ties-away-from-zero`
- saturation: 최종 출력 저장 시점 1회만 적용
- intermediate wrap/saturation 없음

누산기 폭은 먼저 수식적 worst-case bound로 최소 요구 폭을 계산하고, 실제 RTL 구현 폭을 별도로 정한다.

`N=5` coefficient 정수값의 절대값 합은:

$$
\sum |h_q[k]| = 88 + 7069 + 18455 + 7069 + 88 = 32769
$$

입력 샘플의 worst-case magnitude는:

$$
\max |x_q| = 32768
$$

따라서 한 출력 샘플의 누산 worst-case bound는:

$$
\max |acc| \le 32768 \cdot 32769 = 1{,}073{,}774{,}592
$$

이 값은 signed `31-bit` 양수 최대값은 넘고 signed `32-bit` 범위 안에는 들어간다. 따라서 `N=5` bring-up direct-form FIR의 accumulator 최소 요구 폭은 signed `32-bit`다. 다만 실제 bring-up RTL 구현 폭은 signed `48-bit`로 고정한다.

이렇게 결정한 이유:

- rounding이나 saturation 위치가 Python golden과 한 비트라도 어긋나면 RTL 비교가 깨진다.
- accumulator 최소 요구 폭은 근거 없는 감이 아니라 worst-case 수식으로 닫아야 한다.
- 그럼에도 실제 구현을 `48-bit`로 두면 안전 여유가 크고, 향후 tap 확장 시 재검토 부담이 줄어든다.
- Xilinx `DSP48` datapath 폭과 정렬하기 쉬워 구현이 단순해진다.
- Python golden도 intermediate wrap/saturation 없는 wide accumulation을 기준으로 하므로, RTL도 넓게 두는 편이 bit-exact 검증에 유리하다.

### 7. latency 규칙

각 블록의 출력은 registered output으로 둔다. 즉 `out_valid`, `out_sample`은 조합 논리로 즉시 변하는 것이 아니라 clock edge에서 register에 저장되어 갱신된다.

입력 accept 기준은 다음과 같다.

- `rst=0`인 상태에서 `posedge clk`에 `in_valid=1`이면 입력 샘플 1개를 accepted한 것으로 본다.

latency는 아래와 같이 고정한다.

- FIR latency: accepted input 기준 `2 cycles`
- decimator latency: kept FIR sample 기준 `1 cycle`
- top latency: keep되는 sample에 대해 accepted input 기준 `3 cycles`

phase=0에서 첫 번째 keep sample 경로는 아래와 같다.

```text
accepted input @ cycle t
-> FIR output @ t+2
-> decimator output @ t+3
```

drop되는 샘플은 top-level `out_valid`를 만들지 않는다.

이렇게 결정한 이유:

- registered output은 타이밍을 맞추기 쉽고, 파형과 블록 경계가 깔끔하다.
- 현재 direct-form FIR에서는 `multiply + adder tree` 뒤에 accumulator register를 한 번 두고, 다음 stage에서 round/saturate를 수행하도록 파이프라인을 넣었다.
- 이로 인해 FIR latency는 1 cycle 늘었지만, 가장 긴 arithmetic 경로가 잘려 bring-up 타이밍 여유가 좋아진다.
- 현재 decimator는 FIR 출력 2개를 모아서 계산하는 블록이 아니라, FIR valid마다 keep/drop를 즉시 판정하는 selector이므로 첫 출력 생성을 위해 두 샘플을 모두 기다릴 필요가 없다.
- exact cycle contract는 문서에 남기되, testbench pass/fail은 `out_valid` 기준 비교로 두는 편이 불필요한 복잡도를 줄인다.

### 8. decimator phase 규칙

`M=2`, `phase=0` decimator는 reset 후 첫 번째 FIR-valid 샘플을 keep하고, 두 번째를 drop하고, 이후 keep/drop을 반복한다.

즉 keep/drop 패턴은 아래와 같다.

- keep
- drop
- keep
- drop

decimator phase state는 FIR-side valid=`1`일 때만 진행한다.

이렇게 결정한 이유:

- Python golden의 decimator 기준은 `x[phase::m]`이며, `phase=0`이면 첫 번째 샘플부터 유지한다.
- decimator state가 valid sample 기준이 아니라 매 clock 기준으로 움직이면 bubble이나 reset 이후 정합성이 깨질 수 있다.
- keep/drop 규칙을 cycle-level로 닫아야 RTL state machine과 Python golden의 의미가 정확히 일치한다.

### 9. invalid cycle에서 out_sample 의미

`out_valid`가 `out_sample`의 유효성을 결정하는 유일한 기준이다.

- `out_valid=0`일 때 `out_sample`은 compare 대상이 아니다.
- bring-up RTL에서는 invalid cycle 동안 `out_sample`이 이전 register 값을 hold하도록 둔다.

이렇게 결정한 이유:

- invalid cycle의 `out_sample`을 의미 있는 데이터로 해석하면 파형과 testbench가 모두 혼란스러워진다.
- `hold`는 별도 clear 제어가 필요 없어서 구현이 가장 단순하다.
- testbench가 어차피 `out_valid=0` cycle을 무시하므로, invalid cycle에 굳이 `0`을 강제로 써 넣을 기능적 이점이 없다.

### 10. testbench 규칙

bring-up testbench는 self-checking 방식으로 고정한다.

FIR testbench 규칙:

- DUT는 `fir_direct_n5.v`
- 입력은 `input_q15.hex`
- 실제 입력 `8192`개 뒤에 zero `4`개를 `in_valid=1`로 더 넣어 tail을 flush
- 출력은 `expected_fir_q15.hex`와 비교

Top testbench 규칙:

- DUT는 `fir_decimator_direct_n5_top.v`
- 같은 `input_q15.hex`와 같은 zero-4 flush 규칙 사용
- 출력은 `expected_decim_q15.hex`와 비교

공통 비교 규칙:

- testbench는 `out_valid=1`인 cycle에서만 출력 sample index를 증가시킨다
- `out_valid=1`인 cycle의 `out_sample`만 golden hex와 비교한다
- `out_valid=0`인 cycle은 비교 대상에서 제외한다
- mismatch 발생 시 최소한 `sample index`, `actual`, `expected`를 출력한다
- 가능하면 cycle count도 함께 출력한다
- 모든 expected sample을 mismatch 없이 소비하면 PASS다
- mismatch가 하나라도 발생하면 FAIL이다
- 입력 종료 후 충분한 drain cycle 안에 expected sample 수를 모두 받지 못해도 FAIL이다

이렇게 결정한 이유:

- RTL 구현 규칙과 testbench 규칙이 같이 닫혀야 첫 Python-vs-RTL bit-exact loop가 닫힌다.
- 이미 생성된 golden vector를 그대로 사용하면 시뮬레이션과 FPGA bring-up의 기준이 흔들리지 않는다.
- `out_valid` 기준 비교는 absolute cycle alignment 문제로 testbench가 불필요하게 복잡해지는 것을 막아 준다.
- mismatch 보고 형식을 고정해야 디버깅이 재현 가능하고 빨라진다.
