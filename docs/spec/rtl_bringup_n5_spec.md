1. 포트 인터페이스
   왜 필요한가: 모듈 경계를 고정해야 FIR, decimator, top, testbench를 동시에 흔들지 않습니다.
   추천: bring-up에서는 최소 포트만 둡니다.

  input         clk;
  input         rst;       // active-high reset. 1일 때 리셋
  input         in_valid;
  input  signed [15:0] in_sample;
  output        out_valid;
  output signed [15:0] out_sample;

  지금은 ready, in_last, coeff_load, phase_cfg 같은 포트는 넣지 않는 걸 추천합니다. 이유는
  control 복잡도만 늘고 bring-up 목적에는 필요가 없기 때문입니다.

2. reset 규칙
   시작 안정화/abort용도
   왜 필요한가: FIR delay line, decimator phase 상태가 reset 직후 어떻게 시작하는지 안 정하면 첫 샘플부터 비교가 꼬입니다.

   추천: `rst` active-high로 통일하고, reset 시 내부 state 전부 0으로 클리어합니다.

- FIR delay registers = 0
- decimator phase counter = 0
- out_valid = 0
- out_sample = 0

  bring-up에서는 `always @(posedge clk or posedge rst)` 형태로 가면 충분합니다.
  단, 물리 버튼을 실제 보드에서 reset 소스로 쓸 때는 버튼 신호를 DUT의 `rst`에 직접 연결하지 않고,
  debounce + synchronizer를 거친 clean reset net을 `rst`로 넣는 것을 권장합니다.

  FPGA bring-up 데모의 실행 제어는 아래처럼 고정합니다.

- 별도 `start` 버튼은 두지 않습니다.
- 전원 인가 직후에는 `reset_conditioner.v`가 power-on reset을 일정 cycle 동안 유지합니다.
- power-on reset이 해제되면 데모는 sample index `0`부터 자동으로 실행을 시작합니다.
- 사용자가 reset 버튼을 누르면 시스템은 즉시 reset 상태로 들어갑니다.
- 사용자가 reset 버튼을 떼면, release가 debounce된 뒤 reset이 해제되고 데모는 다시 sample index `0`부터 자동 실행됩니다.

  즉 현재 bring-up 구조에서 run 시작 이벤트는 “버튼을 눌렀을 때”가 아니라 “reset이 최종 해제되었을 때”입니다.
  전원 인가 후 반드시 버튼을 한 번 눌러야 시작하는 구조는 아닙니다. power-on reset 종료 후에는 자동 실행됩니다.

3. valid 규칙
   왜 필요한가: 데이터가 “매 클럭 유효한지”를 명확히 해야 sample counting과 decimation counting이
   맞습니다.
   추천: bring-up에선 backpressure 없음, input은 연속 valid로 가정합니다.

- DUT는 in_ready를 내보내지 않음
- testbench는 실제 입력 구간 동안 in_valid=1 유지
- bubble 없는 연속 스트림으로 검증

  중요한 건 decimator counter는 매 클럭이 아니라 in_valid=1인 입력 샘플 수를 기준으로 움직여야
  한다는 점입니다. 이렇게 해야 나중에 bubble이 생겨도 구조가 안 깨집니다.

4. frame 종료와 tail flush 규칙
   왜 필요한가: fixed spec은 full convolution tail 포함이라서, 마지막 입력 뒤에도 FIR 출력이 N-1
   개 더 나와야 합니다. 이걸 처리하는 방식이 없으면 Python golden과 길이가 안 맞습니다.
   추천: bring-up에서는 testbench가 zero padding으로 flush하는 방식을 추천합니다.

  즉 N=5이면:

- 실제 입력 8192개를 넣고
- 그 뒤에 0을 4개 더 in_valid=1로 넣습니다

  이 방식을 추천하는 이유:
- in_last 포트가 필요 없음
- FIR 내부 drain FSM이 필요 없음
- 수학적으로도 입력 밖은 0이라는 full convolution 정의와 정확히 맞음
- testbench가 가장 단순해짐

  이게 bring-up용으로는 제일 좋습니다.

5. coefficient 공급 방식
   왜 필요한가: FIR 계수를 어디서 가져올지 안 정하면 FIR 모듈 구조가 계속 흔들립니다.
   추천: bring-up N=5에서는 FIR 내부 localparam 하드코딩이 가장 좋습니다.

  현재 계수는:

- 88
- 7069
- 18455
- 7069
- 88

  이유:
- 포트 수가 줄어듦
- testbench가 단순해짐
- bit-exact 기준이 흔들리지 않음

  나중에 generic FIR이나 coefficient reload가 필요할 때만 바꾸면 됩니다.

6. arithmetic 규칙
   왜 필요한가: 이 부분이 Python golden과 한 비트라도 어긋나면 검증이 실패합니다.
   추천: 아래를 그대로 고정합니다.

- input/coeff: signed 16-bit Q1.15
- product: signed Q2.30
- rounding: round-to-nearest, ties-away-from-zero
- saturation: 최종 출력 저장 시점 1회만
- intermediate wrap/saturation 없음
- accumulator 폭은 먼저 수식적 worst-case bound로 최소 요구 폭을 계산한 뒤, 실제 RTL 구현 폭을 별도로 고정합니다.

  `N=5` bring-up 계수의 현재 Q1.15 정수값은 아래와 같습니다.
- 88
- 7069
- 18455
- 7069
- 88

  계수 절대값 합은:

$$
\sum |h_q[k]| = 88 + 7069 + 18455 + 7069 + 88 = 32769
$$

  입력 샘플의 worst-case magnitude는 signed Q1.15 기준:

$$
\max |x_q| = 32768
$$

  따라서 한 출력 샘플의 누산 worst-case bound는:

$$
\max |acc| \le \max |x_q| \cdot \sum |h_q[k]| = 32768 \cdot 32769 = 1{,}073{,}774{,}592
$$

  이 값은 signed 31-bit 양수 최대값 `2^{30}-1 = 1,073,741,823`은 넘고, signed 32-bit 범위 안에는 들어갑니다.
  따라서 `N=5` bring-up direct-form FIR의 accumulator 최소 요구 폭은 signed `32-bit`입니다.

  그럼에도 bring-up RTL 구현 폭은 signed `48-bit`로 고정하는 것을 추천합니다. 이유는:

- 최소 요구 폭보다 넉넉해서 구현/디버깅 중 안전 여유가 큼
- 이후 tap 확장이나 구조 수정 시 accumulator 폭 재검토 부담이 줄어듦
- Xilinx `DSP48` datapath 폭과 정렬하기 쉬워 구현이 단순함
- Python golden이 intermediate wrap/saturation 없는 wide accumulation을 기준으로 하므로, RTL도 넓게 두는 편이 bit-exact 검증에 유리함

  여기서 핵심은 “산술 시프트에 기대지 말고 rounding 규칙을 명시적으로 구현”하는 겁니다. 그래야
  Python과 정확히 맞추기 쉽습니다.

7. latency 규칙
   왜 필요한가: testbench가 언제부터 기대값과 비교해야 하는지 정해야 합니다.
   추천: 각 블록의 출력은 registered output으로 둡니다. 여기서 registered output이란
   `out_valid`, `out_sample`이 조합 논리로 즉시 변하는 것이 아니라, clock edge에서 register에
   저장되어 갱신되는 출력을 뜻합니다. 이 방식을 쓰면 타이밍을 맞추기 쉽고, 파형이 깔끔하며,
   testbench가 단순해지고, 블록 경계도 명확해집니다.

- input accept 기준:

  - `rst=0`인 상태에서 `posedge clk`에 `in_valid=1`이면 DUT가 입력 샘플 1개를 accepted한 것으로 봅니다.
- FIR:

  - 입력 1개를 accepted할 때마다 FIR 출력 샘플 1개를 생성합니다.
  - FIR 출력은 registered output으로 두고, accepted input 기준 FIR latency는 `2 cycles`로 고정합니다.
  - direct-form bring-up RTL은 입력 tap 저장 stage와 wide accumulate stage, 그리고 최종 round/saturate 출력 stage를 분리합니다.
  - 구체적으로는 `multiply + adder tree` 결과를 accumulator register에 한 번 저장하고, 그 다음 cycle에 round/saturate를 거쳐 최종 `out_sample`을 만듭니다.
- decimator:

  - decimator는 FIR 출력 2개를 모아서 계산하는 블록이 아니라, FIR valid가 들어올 때마다 현재 phase state로 keep/drop를 즉시 판정하는 selector 블록으로 둡니다.
  - 따라서 첫 출력 생성을 위해 FIR 출력 2개를 모두 기다릴 필요는 없습니다.
  - phase=0에서는 reset 후 첫 번째 FIR-valid 샘플을 keep하고, 두 번째를 drop하고, 이후 keep/drop을 반복합니다.
  - keep된 FIR 샘플은 decimator output register를 거쳐 다음 cycle에 출력되며, kept FIR sample 기준 decimator latency는 `1 cycle`로 고정합니다.
- top:

  - `FIR -> Decimator`를 직렬 연결합니다.
  - 따라서 phase=0에서 첫 번째 keep 샘플 경로는 `accepted input @ cycle t -> FIR output @ t+2 -> decimator output @ t+3`가 됩니다.
  - 즉 keep되는 샘플에 대해서는 accepted input 기준 top latency를 `3 cycles`로 둡니다.
  - drop되는 샘플은 top-level `out_valid`를 만들지 않습니다.

  이 규칙을 정하더라도 bring-up testbench의 1차 비교 기준은 absolute cycle보다 `out_valid`입니다.
  즉 testbench는:
- out_valid==1인 샘플만 카운트
- 그때의 out_sample만 golden hex와 비교
- absolute cycle timing은 참고 정보로만 보고, pass/fail의 1차 기준은 `out_valid`에 실린 샘플 순서와 값으로 둡니다.

  이렇게 하면 latency 한두 사이클 문제로 테스트가 불필요하게 복잡해지지 않습니다.

8. decimator phase 규칙
   왜 필요한가: phase=0의 의미를 RTL state machine에서 확정해야 Python의 x[0::2]와 정확히 맞습니다.
   추천: reset 후 첫 번째 FIR-valid 샘플을 통과시키고, 그 다음 FIR-valid 샘플은 버리고, 그 다음을
   다시 통과시키는 방식으로 갑니다.

  즉 keep/drop 패턴은:

- keep
- drop
- keep
- drop

  그리고 이 토글은 FIR-side valid=1일 때만 움직이게 하세요.

9. invalid cycle에서 out_sample 의미
   왜 필요한가: 파형을 볼 때 헷갈릴 수 있습니다.
   추천: 의미 있는 건 out_valid뿐이라고 두는 게 좋습니다.

- out_valid=0일 때 out_sample은 compare 대상 아님
- 구현은 hold 
- bring-up에선 hold가 제일 단순합니다

  즉 testbench는 out_valid가 0이면 무조건 무시하면 됩니다. -> 어차피 무시하는 값이니 굳이 0으로 바꿀 필요가 없다

10. testbench 규칙
    왜 필요한가: RTL 구현 규칙과 testbench 규칙이 같이 닫혀야 bit-exact loop가 닫힙니다.
    추천: bring-up testbench는 self-checking 방식으로 고정합니다.

- FIR testbench:

  - DUT는 `fir_direct_n5.v`
  - `sim/vectors/direct_form/bringup_n5/input_q15.hex`를 입력으로 사용합니다.
  - 실제 입력 `8192`개를 넣은 뒤, zero sample `4`개를 `in_valid=1`로 더 넣어 full-convolution tail을 flush합니다.
  - 출력은 `sim/vectors/direct_form/bringup_n5/expected_fir_q15.hex`와 비교합니다.
- Top testbench:

  - DUT는 `fir_decimator_direct_n5_top.v`
  - 같은 `input_q15.hex`와 같은 zero-4 flush 규칙을 사용합니다.
  - 출력은 `sim/vectors/direct_form/bringup_n5/expected_decim_q15.hex`와 비교합니다.
- 입력 구동 규칙:

  - reset 해제 후 실제 입력 구간과 flush 구간에서는 `in_valid=1`을 유지합니다.
  - bring-up 범위에서는 bubble 없는 연속 스트림을 기본 입력 패턴으로 둡니다.
- 비교 규칙:

  - testbench는 `out_valid=1`인 cycle에서만 출력 샘플 index를 증가시킵니다.
  - `out_valid=1`인 cycle의 `out_sample`만 golden hex의 현재 expected sample과 비교합니다.
  - `out_valid=0`인 cycle은 비교 대상에서 제외합니다.
- mismatch 보고 규칙:

  - mismatch 발생 시 최소한 `sample index`, `actual`, `expected`를 출력합니다.
  - 가능하면 해당 cycle count도 함께 출력합니다.
- 종료 / pass-fail 규칙:

  - 모든 expected sample을 mismatch 없이 소비하면 PASS입니다.
  - mismatch가 하나라도 발생하면 FAIL입니다.
  - 입력 종료 후 충분한 drain cycle 안에 expected sample 수를 모두 받지 못해도 FAIL입니다.

## 11. Bring-up RTL 모듈 집합

이 문서는 `N=5` direct-form bring-up의 구현 범위를 정의하는 primary source of truth다. 따라서
“어떤 RTL/Verilog 모듈을 이번 bring-up 범위에서 반드시 구현할 것인가”도 이 문서에 고정한다.

### 11.1 Core datapath 모듈

아래 3개는 첫 Python-vs-RTL bit-exact baseline과 이후 FPGA bring-up 데모에 공통으로 필요한 필수
core 모듈이다.

- `rtl/direct_form/bringup_n5/fir_direct_n5.v`
  - `N=5` direct-form FIR core
  - Q1.15 input/coefficient, Q2.30 product, ties-away-from-zero rounding, final saturation 정책 구현
- `rtl/direct_form/decimator_m2_phase0.v`
  - `M=2`, `phase=0` decimator core
  - FIR-side valid마다 keep/drop를 판정하는 selector block
- `rtl/direct_form/bringup_n5/fir_decimator_direct_n5_top.v`
  - `FIR -> Decimator` 연결용 top-level datapath wrapper
  - bring-up DUT의 대표 top으로 사용

### 11.2 Simulation testbench 모듈

아래 2개는 self-checking RTL simulation을 위한 필수 testbench 모듈이다.

- `sim/rtl/tb/direct_form/tb_fir_direct_n5.v`
  - `input_q15.hex`와 `expected_fir_q15.hex`를 사용해 FIR core를 검증
- `sim/rtl/tb/direct_form/tb_fir_decimator_direct_n5_top.v`
  - `input_q15.hex`와 `expected_decim_q15.hex`를 사용해 top-level datapath를 검증

### 11.3 FPGA bring-up 데모 모듈

이번 bring-up의 목표는 시뮬레이션 통과에서 끝나지 않고 실제 Zybo FPGA 데모까지 가는 것이다.
따라서 아래 보조 모듈도 이번 구현 범위에 포함한다.

- `rtl/direct_form/bringup_n5/reset_conditioner.v`
  - 보드 reset 버튼 입력을 debounce + synchronizer 처리하여 clean active-high `rst`를 생성
  - reset assert는 즉시, reset release는 debounce 후에만 반영
  - power-on reset 종료 후 별도 start 버튼 없이 자동 실행되도록 run control 기준 신호 제공
- `rtl/direct_form/bringup_n5/bringup_vector_source.v`
  - `input_q15.hex`를 내부 memory에 preload하고, contiguous `in_valid` 스트림으로 DUT에 공급
  - 실제 입력 `8192`개 뒤 zero `4`개 flush까지 포함해 구동
- `rtl/direct_form/bringup_n5/bringup_output_checker.v`
  - `expected_decim_q15.hex`를 내부 memory에 preload하고, DUT 출력과 self-checking 비교
  - 최소한 `done`, `pass`, `fail`, `mismatch_seen` 성격의 상태 출력을 제공
- `rtl/direct_form/bringup_n5/top_zybo_bringup_n5.v`
  - Zybo 보드 데모용 최상위 top
  - `reset_conditioner`, `bringup_vector_source`, `fir_decimator_direct_n5_top`, `bringup_output_checker`를 연결
  - LED 또는 동등한 단순 status output으로 `running/done/pass/fail`를 외부에서 확인 가능하게 함
  - 별도 start 버튼 없이, power-on reset 해제 또는 reset 버튼 release 후 자동 실행

### 11.3.1 FPGA bring-up run-control 규칙

보드 데모용 bring-up은 “시작 버튼”이 있는 구조가 아니라 “reset release 후 자동 실행” 구조로 고정합니다.

- 보드 system clock은 Zybo의 입력 system clock을 직접 사용합니다.
- `reset_conditioner.v`는 power-on reset과 버튼 reset을 하나의 clean active-high `rst`로 합칩니다.
- `rst=1` 동안 `bringup_vector_source`, DUT, `bringup_output_checker`는 모두 초기 상태를 유지합니다.
- `rst=0`이 되는 첫 동작 구간부터 `bringup_vector_source`가 sample `0`부터 contiguous stream을 재생합니다.
- 데모 실행 중 reset 버튼을 누르면 전체 체인이 즉시 초기 상태로 돌아갑니다.
- reset 버튼을 떼면 debounce된 release 뒤에 다시 sample `0`부터 자동 실행됩니다.

이 규칙의 목적은 control path를 최소화하면서도, 전원 인가 직후 자동 실행과 사용자의 명확한 재시작 동작을 동시에 보장하는 것입니다.

### 11.4 이번 범위에서 제외하는 항목

아래 항목은 현재 `N=5` bring-up 범위에 넣지 않는다.

- AXI-Stream wrapper
- PS-PL integration
- AXI DMA
- bare-metal C control path
- generic-`N` parameterization
- dynamic coefficient load
- separate coefficient ROM

현재 `N=5` bring-up에서는 FIR coefficient를 core 내부 하드코딩으로 두므로, board demo를 위해 별도
coefficient loader 모듈을 만들지 않는다.

### 11.5 Optional debug 항목

ILA 같은 FPGA debug IP는 bring-up 디버깅에 유용할 수 있지만, tool-generated artifact이므로 이번
handwritten required module set에는 포함하지 않는다.
