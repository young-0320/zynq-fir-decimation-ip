# 09. Bring-up RTL 운영 규칙 1차 확정

- 작성일: 2026-03-31
- 단계: 5
- 목적: `N=5` direct-form RTL bring-up 구현 전에 최소 운영 규칙 1~5를 닫아 구현 churn을 줄인다

## 1) 이번 세션 핵심 결정

1. bring-up RTL은 최소 streaming 인터페이스를 기준으로 본다.
   - 신호 의미는 `clk`, `rst_n`, `in_valid`, `in_sample`, `out_valid`, `out_sample`
   - exact Verilog declaration spelling(`wire/reg/signed` 배치)은 구현 시점으로 미룬다
2. reset 시 stateful register는 모두 `0`으로 초기화한다.
   - FIR delay line
   - decimator phase state
   - `out_valid`
   - 필요 시 `out_sample`
3. bring-up 입력 구간에서는 backpressure를 두지 않고 연속 valid 입력을 가정한다.
   - DUT는 `ready` 신호를 내보내지 않는다
   - testbench는 실제 입력 샘플 구간 동안 `in_valid=1`을 유지한다
4. full-convolution tail은 testbench의 zero padding으로 flush한다.
   - `N=5`이므로 실제 입력 뒤에 `4`개의 zero sample을 `in_valid=1`로 넣는다
   - 별도 `in_last` 또는 internal drain FSM은 이번 bring-up 범위에서 두지 않는다
5. `N=5` FIR coefficient는 `fir_direct_n5.v` 내부에 하드코딩한다.
   - 외부 coefficient load port는 만들지 않는다

## 2) 왜 이렇게 닫았는가

### A. 제어 신호를 줄여 구현과 디버깅을 단순화한다

- 현재 목표는 AXI-Stream wrapper가 아니라 첫 bit-exact baseline이다.
- 따라서 `ready`, `last`, dynamic coefficient load 같은 제어는 지금 넣을 필요가 없다.

### B. full convolution 계약을 RTL에서도 가장 단순하게 재현한다

- Python golden은 입력 범위 밖 샘플을 `0`으로 간주한다.
- 따라서 마지막 입력 뒤 `N-1`개의 zero sample을 넣는 방식이 spec과 정확히 맞는다.
- 이 방식이면 FIR 내부에 별도 tail-drain 제어를 넣지 않아도 된다.

### C. 첫 bring-up에서는 datapath만 검증 대상으로 제한한다

- coefficient를 고정하면 port 수와 초기화 시나리오가 줄어든다.
- 비교 대상도 `input_q15.hex`, `expected_fir_q15.hex`, `expected_decim_q15.hex`로 단순화된다.

## 3) 이번 결정이 바로 반영되는 파일 경로

- `rtl/direct_form/bringup_n5/fir_direct_n5.v`
- `rtl/direct_form/decimator_m2_phase0.v`
- `rtl/direct_form/bringup_n5/fir_decimator_direct_n5.v`
- `sim/vectors/direct_form/bringup_n5/input_q15.hex`
- `sim/vectors/direct_form/bringup_n5/coeff_q15.hex`
- `sim/vectors/direct_form/bringup_n5/expected_fir_q15.hex`
- `sim/vectors/direct_form/bringup_n5/expected_decim_q15.hex`

## 4) 아직 열어 둔 항목

이번 세션에서는 아래 항목을 닫지 않았다.

- arithmetic implementation detail의 RTL 표현 방식
- exact latency contract
- decimator phase state의 cycle-level formal wording
- `out_valid=0`일 때 `out_sample` hold/clear policy
- self-checking testbench 운영 규칙 상세

위 항목은 실제 RTL coding과 testbench 작성 직전에 이어서 닫는다.

## 5) 현재 기준 다음 액션

1. `fir_direct_n5.v`를 full-convolution direct-form FIR로 구현한다.
2. `decimator_m2_phase0.v`를 `M=2`, `phase=0` reusable module로 구현한다.
3. `fir_decimator_direct_n5.v`에서 위 2개를 연결한다.
4. 이후 self-checking testbench에서 `bringup_n5` hex vector로 Python-vs-RTL bit-exact loop를 닫는다.
