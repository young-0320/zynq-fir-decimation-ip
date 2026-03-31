1. 포트 집합
   왜 필요한가: 모듈 경계를 고정해야 FIR, decimator, top, testbench를 동시에 흔들지 않습니다.
   추천: bring-up에서는 최소 포트만 둡니다.

  input         clk;
  input         rst_n;
  input         in_valid;
  input  signed [15:0] in_sample;
  output        out_valid;
  output signed [15:0] out_sample;

  지금은 ready, in_last, coeff_load, phase_cfg 같은 포트는 넣지 않는 걸 추천합니다. 이유는
  control 복잡도만 늘고 bring-up 목적에는 필요가 없기 때문입니다.

2. reset 규칙
   왜 필요한가: FIR delay line, decimator phase 상태가 reset 직후 어떻게 시작하는지 안 정하면 첫
   샘플부터 비교가 꼬입니다.
   추천: rst_n active-low, reset 시 내부 state 전부 0으로 클리어합니다.

- FIR delay registers = 0
- decimator phase counter = 0
- out_valid = 0
- out_sample = 0 또는 hold, 둘 중 하나로 통일

  bring-up에서는 always @(posedge clk or negedge rst_n) 형태로 가면 충분합니다.

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
- accumulator는 bring-up이라도 넉넉하게 48-bit signed 추천

  여기서 핵심은 “산술 시프트에 기대지 말고 rounding 규칙을 명시적으로 구현”하는 겁니다. 그래야
  Python과 정확히 맞추기 쉽습니다.

7. latency 규칙
   왜 필요한가: testbench가 언제부터 기대값과 비교해야 하는지 정해야 합니다.
   추천: 각 블록의 출력은 registered output으로 두는 걸 추천합니다.

- FIR: 입력 1개 받을 때 출력 1개 생성
- decimator: FIR valid 2개 중 1개만 통과
- top: FIR 뒤 decimator를 직렬 연결

  여기서 더 중요한 추천은 정확한 cycle count보다 out_valid를 기준으로 비교하는 겁니다.
  즉 testbench는:

- out_valid==1인 샘플만 카운트
- 그때의 out_sample만 golden hex와 비교

  이렇게 하면 latency 한두 사이클 문제로 테스트가 불필요하게 복잡해지지 않습니다.

8. decimator phase 규칙
   왜 필요한가: phase=0의 의미를 RTL state machine에서 확정해야 Python의 x[0::2]와 정확히 맞습니
   다.
   추천: reset 후 첫 번째 in_valid 샘플을 통과시키고, 그 다음 valid는 버리고, 그 다음을 통과시키
   는 방식으로 갑니다.

  즉 keep/drop 패턴은:

- keep
- drop
- keep
- drop

  그리고 이 토글은 in_valid=1일 때만 움직이게 하세요.

9. invalid cycle에서 out_sample 의미
   왜 필요한가: 파형을 볼 때 헷갈릴 수 있습니다.
   추천: 의미 있는 건 out_valid뿐이라고 두는 게 좋습니다.

- out_valid=0일 때 out_sample은 compare 대상 아님
- 구현은 hold 해도 되고 0으로 넣어도 됨
- bring-up에선 hold가 제일 단순합니다

  즉 testbench는 out_valid가 0이면 무조건 무시하면 됩니다.

10. testbench 규칙
    왜 필요한가: RTL 구현 규칙과 testbench 규칙이 같이 닫혀야 bit-exact loop가 닫힙니다.
    추천:

- FIR testbench:
  - input_q15.hex 입력
  - 마지막에 zero 4개 flush
  - expected_fir_q15.hex와 비교
- Top testbench:
  - 같은 입력과 같은 flush
  - expected_decim_q15.hex와 비교
- 비교 기준:
  - out_valid 기준 샘플 index 증가
  - mismatch 발생 시 sample index, actual, expected 출력

  bring-up용으로 내가 추천하는 최종 규칙 세트

1. 포트는 clk/rst_n/in_valid/in_sample/out_valid/out_sample만 둡니다.
2. ready, last, AXI-Stream, coefficient port는 넣지 않습니다.
3. FIR 계수는 fir_direct_n5.v 내부 하드코딩합니다.
4. testbench가 마지막 실제 입력 뒤에 zero 4개를 넣어 tail을 flush합니다.
5. decimator는 m=2, phase=0 고정으로 만듭니다.
6. decimator state는 in_valid일 때만 진행합니다.
7. 비교는 cycle absolute timing보다 out_valid 기준으로 합니다.
8. arithmetic은 Python golden과 동일하게 Q2.30 -> Q1.15, ties-away-from-zero, final saturation
   1회로 갑니다.

  한 줄로 요약하면, bring-up에서는 제어 신호를 최소화하고, testbench가 frame/tail을 책임지고,
  DUT는 순수 streaming datapath만 구현하는 방식이 가장 좋습니다.

  원하면 다음 답변에서 이 규칙을 기준으로
  fir_direct_n5.v, decimator_m2_phase0.v, fir_decimator_direct_n5.v
  각 모듈의 포트/내부 동작 spec을 바로 써드리겠습니다.
