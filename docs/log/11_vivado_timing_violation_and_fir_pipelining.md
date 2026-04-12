# Vivado Timing Violation And FIR Pipelining

- 작성일: 2026-04-12
- 목적: `N=5` bring-up RTL을 Vivado로 올린 뒤 실제 synthesis / implementation 결과에서 확인된 타이밍 위반을 기록하고, 그에 대한 1차 해결 방향으로 `FIR 파이프라이닝`을 채택한 이유를 남긴다.

## 1. 상황 요약

이번 보드 bring-up은 아래 조건으로 진행했다.

- 보드 top: `top_zybo_bringup_n5`
- 입력 클럭: Zybo `sysclk`, `125 MHz`
- 메모리 초기화 파일:
  - `input_q15.hex`
  - `expected_decim_q15.hex`
- build 결과물 경로:
  - `/mnt/workspace/10_zynq-fir-decimation-ip_build/fir_bringup_n5`

시뮬레이션에서는 이미 아래가 PASS한 상태였다.

- `tb_fir_direct_n5`
- `tb_fir_decimator_direct_n5_top`
- `top_zybo_bringup_n5` sanity simulation

즉 문제는 기능 오동작이 아니라, Vivado implementation에서 `125 MHz` 타이밍을 실제로 닫을 수 있는지 여부였다.

## 2. 먼저 해결된 문제: 메모리 초기화 경로 오류

초기 build에서는 `$readmemh`가 `sim/vectors/direct_form/bringup_n5/...` 상대경로를 찾지 못했다.

그 결과 synthesis에서 아래와 같은 경고가 떴다.

- `could not open $readmem data file 'sim/vectors/direct_form/bringup_n5/input_q15.hex'`
- `could not open $readmem data file 'sim/vectors/direct_form/bringup_n5/expected_decim_q15.hex'`

이 상태의 build는 신뢰할 수 없었다. 이유는:

- source ROM이 제대로 초기화되지 않으면 실제 입력 재생 동작이 비정상적일 수 있다.
- checker ROM도 제대로 초기화되지 않으면 false PASS 가능성이 있다.
- 따라서 이 상태에서 timing이 좋아 보여도 그 결과는 의미가 약하다.

이 문제는 `top_zybo_bringup_n5.v`의 기본 파라미터를 파일명만 쓰도록 바꾸고,
Vivado에서 `hex` 파일을 `Memory Initialization Files`로 포함시키는 방식으로 해결했다.

수정 후 synthesis 로그에는 아래가 확인되었다.

- `$readmem data file 'input_q15.hex' is read successfully`
- `$readmem data file 'expected_decim_q15.hex' is read successfully`

즉 현재는 메모리 초기화는 정상이라고 본다.

## 3. 실제로 드러난 문제: 125 MHz 타이밍 위반

메모리 초기화가 정상화된 뒤 implementation timing summary는 아래와 같이 나왔다.

- `WNS = -2.139 ns`
- `TNS = -72.748 ns`
- `WHS = 0.064 ns`
- `THS = 0.000 ns`

해석은 명확하다.

- `setup timing`이 깨졌다.
- `hold timing`은 괜찮다.
- 즉 현재 설계는 `125 MHz`에서 setup closure에 실패한다.

따라서 이 상태로 bitstream을 만들어도, 보드에서 의도한 대로 안정 동작한다고 말할 수 없다.

## 4. worst path가 어디였는가

가장 나쁜 경로는 board checker나 vector source가 아니라, `fir_direct_n5` 내부 accumulate stage에서 나왔다.

리포트 기준 worst path:

- source:
  - `u_fir_decimator_direct_n5_top/u_fir_direct_n5/delay_3_reg[5]`
- destination:
  - `u_fir_decimator_direct_n5_top/u_fir_direct_n5/acc_reg_reg[47]`

경로 성격:

- `delay_3_reg`에서 출발
- `DSP48E1` 곱셈 결과 통과
- `LUT3` 일부 논리 통과
- `CARRY4` 체인 다수 통과
- 최종적으로 `acc_reg`에 도착

리포트에 표시된 주요 수치는 이랬다.

- data path delay: `10.158 ns`
- logic levels: `14`
- 구성: `DSP48E1=1`, `LUT3=2`, `CARRY4=11`

이건 direct-form FIR의 `multiply + wide add` 구간이 아직도 한 stage에 너무 많이 몰려 있다는 뜻이다.

## 5. 왜 checker가 아니라 FIR가 문제인가

구현 중간에는 `tight_setup_hold_pins.txt`에서 `u_bringup_output_checker` 핀도 빡빡하게 보였다.
하지만 routed timing summary의 worst negative slack path는 checker가 아니라 FIR였다.

즉 checker도 이후 정리 대상이 될 수는 있지만,
지금 타이밍 실패를 가장 크게 만드는 1차 원인은 FIR accumulate stage다.

이 판단은 중요하다.

- 메모리 경로만 손보는 것으로는 `125 MHz` closure를 해결할 수 없다.
- 문제의 중심은 실제 데이터패스 연산 경로다.

## 6. 현재 FIR stage 구조와 한계

현재 FIR는 이미 한 차례 파이프라인이 들어간 상태다.

현재 개념적 stage는 아래와 같다.

1. 입력 샘플과 delay tap 저장
2. `multiply + adder tree + acc_reg` 저장
3. `round + saturate + out_sample` 저장

이 구조는 처음의 완전 단일-stage FIR보다 낫지만, `Stage 2`가 여전히 무겁다.
특히 `DSP 결과 -> carry chain -> 48-bit acc_reg` 구간이 `125 MHz`를 버티지 못하고 있다.

즉 "파이프라이닝을 했다"는 사실만으로 충분하지 않았고,
`어디에서 경로를 자르느냐`가 중요하다는 점이 이번 implementation에서 드러났다.

## 7. 1차 해결 방향으로 FIR 파이프라이닝을 채택한 이유

이번 문제를 해결하는 가장 기본적인 방법으로 `FIR 파이프라이닝`을 채택한다.

이 판단의 이유는 아래와 같다.

### 7.1 문제의 위치가 FIR 데이터패스이기 때문이다

worst path가 FIR 내부 accumulate stage에서 나왔으므로,
가장 직접적인 해결도 FIR 내부 stage 분할이어야 한다.

### 7.2 bring-up 목표가 125 MHz 보드 동작 확인이기 때문이다

지금 단계에서 clock constraint를 낮추면 bitstream은 빨리 만들 수 있다.
하지만 그건 `125 MHz sysclk direct-use`라는 현재 bring-up 시연 목표를 약화시킨다.

이번 bring-up은 "일단 돌아가는지"만 보는 게 아니라,
현재 top 구조로 보드에서 실제 동작하는지 보는 단계다.
그래서 먼저 시도할 기본 해법은 주파수를 낮추는 것이 아니라 FIR 자체를 timing-friendly하게 만드는 것이다.

### 7.3 direct-form N=5 범위에서는 가장 단순한 수정이다

구조를 transposed form으로 전환하는 것은 더 큰 방향 전환이다.
반면 현재는 `N=5 bring-up`이고, 먼저 필요한 것은 작은 수정으로 timing을 닫는 것이다.

따라서 현재 범위에서 가장 보수적이고 기본적인 해결은:

- FIR 내부에 pipeline register를 1단 더 추가
- accumulate 경로를 더 짧은 stage 둘로 쪼개기

이다.

## 8. 예상되는 수정 방향

다음 FIR 파이프라인 수정은 아래 방향을 기본안으로 한다.

1. tap register stage
2. multiply 결과와 일부 partial sum을 만드는 stage
3. 더 짧아진 accumulate stage에서 `acc_reg` 저장
4. round / saturate / output stage

핵심은 `DSP -> 긴 carry chain -> acc_reg` 경로를 더 짧게 자르는 것이다.

이렇게 하면 대가도 있다.

- FIR latency가 다시 늘 수 있다.
- top latency도 함께 늘 수 있다.
- spec, decision log, walkthrough, testbench의 latency 설명도 같이 갱신해야 한다.

하지만 timing closure를 위해서는 이 trade-off를 받아들이는 것이 맞다.

## 9. 이번 단계에서 선택하지 않은 대응

이번 문서 시점에서는 아래 대응을 우선안으로 채택하지 않았다.

### 9.1 clock을 낮추는 방법

이 방법은 빠르게 bitstream을 얻는 데는 도움이 될 수 있다.
하지만 현재 bring-up에서 확인하려는 `125 MHz` 보드 동작을 그대로 보여주지는 못한다.

### 9.2 checker/source 문제만 먼저 고치는 방법

checker와 source도 이후 BRAM 유도나 synchronous ROM 구조로 개선할 수 있다.
하지만 현재 worst path는 FIR 쪽이므로, 우선순위는 FIR accumulate stage 파이프라이닝이 맞다.

### 9.3 타이밍 실패 상태로 bi

### tstream을 바로 만들어 보는 방법

setup violation이 있는 bitstream은 보드에서 우연히 보이는 동작이 나와도 신뢰하기 어렵다.
따라서 closure 전 bitstream 시연은 기준 결과로 삼지 않는다.

## 10. 정리

이번 Vivado bring-up에서 얻은 결론은 두 가지다.

1. 메모리 초기화는 현재 정상이다.
   - `$readmemh` 성공 로그로 확인했다.
2. 실제 문제는 `125 MHz`에서 FIR accumulate stage timing이 깨진다는 점이다.

따라서 현재의 기본 해결 방향은:

- `FIR 추가 파이프라이닝`

이다.

이 문서는 "왜 타이밍이 깨졌는지"와 "왜 첫 대응으로 FIR 파이프라인을 더 넣는지"를 기록하는 로그다.
후속 작업에서는 실제 RTL 수정과 그에 따른 latency/spec 업데이트를 이어서 진행한다.
