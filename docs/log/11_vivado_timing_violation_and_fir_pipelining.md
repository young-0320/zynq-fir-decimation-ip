# Vivado Timing Violation And FIR Pipelining

- 작성일: 2026-04-12
- 목적: `N=5` bring-up RTL을 Vivado로 올렸을 때 실제 implementation에서 드러난 타이밍 문제와, 그 문제를 어떤 순서로 해결했는지 기록한다.

## 1. 문제의 출발점

보드 bring-up은 아래 조건으로 진행했다.

- top: `top_zybo_bringup_n5`
- clock: Zybo `sysclk` `125 MHz`
- memory init:
  - `input_q15.hex`
  - `expected_decim_q15.hex`
- build 경로:
  - `/mnt/workspace/10_zynq-fir-decimation-ip_build/fir_bringup_n5`

시뮬레이션은 이미 PASS였다.

- `tb_fir_direct_n5`
- `tb_fir_decimator_direct_n5_top`
- `top_zybo_bringup_n5` sanity simulation

즉 문제는 기능 mismatch가 아니라, **Vivado implementation에서 실제로 `125 MHz`를 닫을 수 있는가**였다.

## 2. 먼저 정리된 선행 이슈: 메모리 초기화 경로

초기 build에서는 `$readmemh`가 `sim/vectors/direct_form/bringup_n5/...` 상대경로를 찾지 못했다.

그 결과 synthesis에서:

- `could not open $readmem data file 'sim/vectors/direct_form/bringup_n5/input_q15.hex'`
- `could not open $readmem data file 'sim/vectors/direct_form/bringup_n5/expected_decim_q15.hex'`

가 발생했다.

이 상태의 build는 신뢰할 수 없었다.

- source ROM이 비정상 초기화되면 실제 입력 재생이 틀어질 수 있다.
- checker ROM이 비정상 초기화되면 false PASS 가능성이 있다.

이 문제는:

- `top_zybo_bringup_n5.v`에서 기본 파일명을 basename으로 바꾸고
- Vivado에서 `hex`를 `Memory Initialization Files`로 포함

하는 방식으로 해결했다.

수정 후 synthesis 로그에는 아래가 확인되었다.

- `$readmem data file 'input_q15.hex' is read successfully`
- `$readmem data file 'expected_decim_q15.hex' is read successfully`

즉 이후 timing 분석은 **정상 memory init 상태의 진짜 build** 기준으로 봐야 한다.

## 3. 첫 번째 실제 timing violation

메모리 초기화가 정상화된 뒤 implementation timing summary는 아래와 같았다.

- `WNS = -2.139 ns`
- `TNS = -72.748 ns`
- `WHS = 0.064 ns`
- `THS = 0.000 ns`

해석:

- `setup timing`이 깨졌다.
- `hold timing`은 괜찮다.
- 따라서 이 상태로는 `125 MHz`에서 안정 동작한다고 볼 수 없다.

## 4. 첫 번째 worst path는 어디였는가

초기 worst path는 board checker가 아니라 `fir_direct_n5` 내부 accumulate stage였다.

리포트 기준:

- source:
  - `u_fir_decimator_direct_n5_top/u_fir_direct_n5/delay_3_reg[5]`
- destination:
  - `u_fir_decimator_direct_n5_top/u_fir_direct_n5/acc_reg_reg[47]`

경로 성격:

- tap register
- DSP multiply
- LUT 일부 논리
- 긴 `CARRY4` 체인
- `acc_reg`

즉 direct-form FIR의 `multiply + wide accumulate` 구간이 한 stage에 너무 무겁게 들어가 있었다.

## 5. 1차 해결: FIR 파이프라인 추가

가장 기본적인 대응은 clock을 낮추는 것이 아니라 **FIR datapath를 파이프라이닝**하는 것이었다.

처음 적용한 구조는 아래였다.

1. tap 저장
2. `5개 multiply` 결과를 product register에 저장
3. wide accumulation 결과를 `acc_reg`에 저장
4. `round + saturate`를 수행해서 `out_sample`에 저장

이 변경으로:

- FIR latency: `2 cycles -> 3 cycles`
- top latency: `3 cycles -> 4 cycles`

가 되었다.

효과는 컸다. 가장 큰 accumulate-stage 위반은 줄었고, 이후 timing bottleneck은 checker와 FIR 마지막 stage 쪽으로 이동했다.

## 6. 2차 정리: board shell을 timing-friendly하게 재구성

첫 번째 FIR 파이프라인 뒤에는 checker 쪽이 빡빡하게 보였다.
그래서 board bring-up shell도 더 timing-friendly하게 바꿨다.

적용한 변경은 두 가지다.

1. `bringup_vector_source`
   - ROM을 BRAM-friendly하게 유도
2. `bringup_output_checker`
   - expected ROM을 synchronous read로 바꾸고
   - DUT sample과 expected sample을 register에 잡은 뒤
   - 다음 cycle에 비교하도록 변경

이 변경 후 synthesis 리포트에서는 `RAMB36E1 = 4`가 잡혔다.
즉 source/checker memory가 LUT ROM에 머무르지 않고 실제 BRAM 자원을 쓰게 되었다.

이 단계 뒤 routed timing은 크게 좋아졌지만, 아직 작은 setup violation이 남았다.

- `WNS = -0.117 ns`
- `TNS = -0.461 ns`

그리고 이 시점의 worst path는 다시 FIR 마지막 stage였다.

- source:
  - `u_fir_decimator_direct_n5_top/u_fir_direct_n5/acc_reg_reg[0]`
- destination:
  - `u_fir_decimator_direct_n5_top/u_fir_direct_n5/out_sample_reg[12]`

즉 이제는 `acc_reg -> round/saturate -> out_sample` 경로가 마지막 병목이었다.

## 7. 최종 해결: FIR 마지막 stage도 한 번 더 분리

남은 문제는 아주 명확했다.

- `accumulate`는 이미 register로 분리됐지만
- `round + saturate`는 아직 한 stage에 남아 있었다

그래서 FIR에 register를 하나 더 추가해서 최종 구조를 아래처럼 만들었다.

1. tap 저장
2. product register
3. `acc_reg` 저장
4. `round_reg` 저장
5. saturation 후 `out_sample` 저장

즉 `accumulate -> round -> saturate`로 다시 나눈 것이다.

이 변경 후 latency 계약은 최종적으로:

- FIR latency: `4 cycles`
- decimator latency: `1 cycle`
- top latency: `5 cycles`

가 되었다.

## 8. 최종 결과

최종 routed timing summary는 아래와 같다.

- `WNS = 0.449 ns`
- `TNS = 0.000 ns`
- `WHS = 0.072 ns`
- `THS = 0.000 ns`

즉:

- setup timing 통과
- hold timing 통과
- `125 MHz` bring-up timing closure 달성

리포트 문구도:

- `All user specified timing constraints are met.`

로 바뀌었다.

최종 worst setup path는 여전히 FIR 내부였지만, 이제 slack이 양수다.

- source:
  - `u_fir_decimator_direct_n5_top/u_fir_direct_n5/prod_0/CLK`
- destination:
  - `u_fir_decimator_direct_n5_top/u_fir_direct_n5/acc_reg_reg[45]/D`
- slack:
  - `0.449 ns`

## 9. 의미

이번 과정의 핵심은 이렇다.

- initial problem은 “단순히 Vivado가 까다롭다”가 아니라
  **실제 datapath stage가 `125 MHz`에 비해 너무 길었다**는 것이다.
- 가장 기본적인 대응은 예상대로 **FIR 파이프라이닝**이었다.
- 그러나 bring-up shell도 실제 build에선 timing에 영향을 주므로,
  source/checker도 BRAM-friendly synchronous 구조로 정리하는 것이 유효했다.
- 최종 closure는
  - FIR accumulate 경로 절단
  - checker/source memory 경로 정리
  - FIR round/saturate 경로 추가 절단
  의 조합으로 달성되었다.

## 10. 현재 결론

현재 `N=5` bring-up design은:

- local RTL regression PASS
- board-top sanity simulation PASS
- Vivado synthesis/implementation PASS
- `125 MHz` timing closure PASS

상태다.

즉 이제는 bitstream 생성과 실제 Zybo 보드 다운로드를 진행해도 되는 수준까지 왔다.
