# FIR Decimation 프로젝트 워크플로우 v5

- 작성일: 2026-04-12
- 목적: `N=5` direct-form bring-up RTL을 Vivado에 올리고, bitstream 생성과 실제 Zybo 보드 확인까지 재현 가능하게 운영

## 0) 현재 상태 sync

1. `N=5` direct-form bring-up core RTL은 구현 완료 상태다.
2. `top_zybo_bringup_n5.v`와 `zybo_n5.xdc`까지 준비되어 있다.
3. self-checking simulation은 아래 세 경로가 PASS한 상태다.
   - `tb_fir_direct_n5`
   - `tb_fir_decimator_direct_n5_top`
   - `top_zybo_bringup_n5` sanity simulation
4. 현재 보드 데모는 아래 구조를 기준으로 한다.

```text
reset_conditioner
-> bringup_vector_source
-> fir_decimator_direct_n5_top
-> bringup_output_checker
-> LED[3:0]
```

5. 현재 latency 계약은 아래와 같다.
   - FIR latency: `4 cycles`
   - decimator latency: `1 cycle`
   - top latency: `5 cycles`

## 1) 완료 조건 (Definition of Done)

1. Vivado에서 `top_zybo_bringup_n5`를 top으로 설정한 프로젝트가 열린다.
2. RTL source, XDC, memory init hex 파일이 모두 프로젝트에 포함된다.
3. synthesis / implementation / bitstream이 완료된다.
4. bitstream을 Zybo에 다운로드할 수 있다.
5. 보드에서 reset release 후 데모가 자동 실행된다.
6. 정상 동작 시 LED 최종 상태가 `0110`으로 보인다.
7. reset 버튼을 눌렀다가 떼면 sample `0`부터 다시 실행된다.

## 2) Vivado에 올릴 파일

### 2.1 RTL source

- `rtl/direct_form/bringup_n5/fir_direct_n5.v`
- `rtl/direct_form/decimator_m2_phase0.v`
- `rtl/direct_form/bringup_n5/fir_decimator_direct_n5_top.v`
- `rtl/direct_form/bringup_n5/reset_conditioner.v`
- `rtl/direct_form/bringup_n5/bringup_vector_source.v`
- `rtl/direct_form/bringup_n5/bringup_output_checker.v`
- `rtl/direct_form/bringup_n5/top_zybo_bringup_n5.v`

### 2.2 Constraints

- `rtl/direct_form/bringup_n5/constrs/zybo_n5.xdc`

### 2.3 Memory init 파일

- `sim/vectors/direct_form/bringup_n5/input_q15.hex`
- `sim/vectors/direct_form/bringup_n5/expected_decim_q15.hex`

주의:

- 현재 `bringup_vector_source.v`와 `bringup_output_checker.v`는 `$readmemh(...)`를 사용한다.
- 따라서 Vivado 프로젝트에도 위 `hex` 파일이 실제로 들어가 있어야 한다.
- RTL만 넣고 `hex`를 안 넣으면 합성 후 메모리 내용이 비어 있을 수 있다.
- 처음 추가하면 `Unknown`으로 보일 수 있다.
- 이 경우 우클릭 후 `Set File Type -> Memory Initialization Files`로 바꾼다.

## 3) 보드 연결 기준

현재 XDC 기준 연결은 아래와 같다.

- `clk` -> Zybo `sysclk`, `K17`, `125 MHz`
- `reset_btn` -> `btn[0]`, `K18`
- `led[0]` -> running
- `led[1]` -> done
- `led[2]` -> pass
- `led[3]` -> fail

즉 정상 종료 후 기대 LED 상태는:

```text
led[3:0] = 4'b0110
```

의미는:

- `led[0] = 0` : running 아님
- `led[1] = 1` : done
- `led[2] = 1` : pass
- `led[3] = 0` : fail 아님

## 4) Vivado 실행 순서

### 4.1 사전 확인

Vivado에 올리기 전에 아래가 맞는지 먼저 확인한다.

1. 최근 RTL/문서 변경이 커밋되어 있다.
2. 워크트리가 clean이다.
3. self-checking simulation이 PASS 상태다.
4. `top_zybo_bringup_n5.v`가 최상위 보드 top이라는 점이 분명하다.

### 4.2 프로젝트 생성

1. Vivado 실행
2. `Create Project`
3. 프로젝트 이름 예시:
   - `zynq_fir_bringup_n5`
4. Target device/board:
   - Zybo Z7 board preset 또는 정확한 part 선택

보드 preset이 있다면 보드 preset을 쓰는 편이 편하다.

### 4.3 RTL source 추가

1. `Add Sources`
2. 위 RTL source 7개를 모두 추가
3. source tree에서 `top_zybo_bringup_n5`를 top module로 설정

확인 포인트:

- top을 `fir_decimator_direct_n5_top`로 잘못 잡으면 안 된다.
- 실제 bitstream top은 `top_zybo_bringup_n5`다.

### 4.4 Constraint 추가

1. `Add Constraints`
2. `rtl/direct_form/bringup_n5/constrs/zybo_n5.xdc` 추가

확인 포인트:

- 다른 Zybo 템플릿 XDC를 동시에 넣지 않는다.
- 현재 bring-up top 포트명은 `clk`, `reset_btn`, `led[3:0]`이다.

### 4.5 Memory init 파일 추가

1. 프로젝트에 아래 파일을 추가한다.
   - `sim/vectors/direct_form/bringup_n5/input_q15.hex`
   - `sim/vectors/direct_form/bringup_n5/expected_decim_q15.hex`
2. Vivado가 이 파일들을 source set에 포함하고 있는지 확인한다.

이 단계는 중요하다.
현재 ROM은 handwritten RTL + `$readmemh` 방식이라, bitstream 생성 시 init 파일이 누락되면
보드에서는 source/checker 메모리가 모두 0 또는 비정상 내용이 될 수 있다.

### 4.6 Synthesis

1. `Run Synthesis`
2. 완료 후 아래를 확인한다.
   - syntax/elaboration error 없음
   - top module 인식 정상
   - 심각한 memory init warning 없는지 확인

확인 포인트:

- `$readmemh` 관련 warning
- inferred ROM/BRAM 관련 warning
- unconnected port warning

### 4.7 Implementation

1. `Run Implementation`
2. 완료 후 timing summary 확인

현재 구조는:

- 보드 clock `125 MHz`
- period `8.00 ns`

즉 WNS/TNS를 확인해서 timing closure가 되는지 본다.

핵심 체크:

- WNS >= 0
- 심각한 hold violation 없는지

### 4.8 Bitstream 생성

1. `Generate Bitstream`
2. bitstream 생성 완료 후 hardware manager로 이동

### 4.9 보드 다운로드

1. Zybo 보드 전원 연결
2. JTAG 연결
3. `Open Hardware Manager`
4. `Open Target`
5. device 선택
6. bitstream program

## 5) 보드에서 동작이 맞는지 확인하는 방법

이 단계가 가장 중요하다. 단순히 “bitstream이 올라갔다”가 아니라, 현재 의도한 bring-up flow가
실제로 실행되는지 확인해야 한다.

### 5.1 전원 인가 직후 기대 동작

현재 reset/start 정책은:

- power-on reset 후 자동 실행
- 별도 start 버튼 없음
- reset 버튼을 누르면 즉시 초기화
- reset 버튼 release 후 debounce 뒤 자동 재실행

즉 전원 인가 후 사용자는 반드시 버튼을 먼저 누를 필요가 없다.

기대 시퀀스:

1. bitstream 다운로드 직후 잠깐 reset 상태
2. 자동 실행 시작
3. running LED가 켜질 수 있음
4. 일정 시간 뒤 done/pass 상태로 종료

### 5.2 LED로 확인하는 방법

현재 가장 직접적인 확인 방법은 LED다.

#### 정상 동작

최종 LED 상태:

```text
0110
```

즉:

- `running=0`
- `done=1`
- `pass=1`
- `fail=0`

이 상태면:

- source가 끝까지 재생되었고
- DUT 출력이 `expected_decim_q15.hex`와 일치했고
- checker가 mismatch 없이 종료했다는 뜻이다.

#### 비정상 동작 예시

- `1000` 또는 `0001`

  - fail이 켜진 경우
  - 출력 mismatch, extra output, 또는 drain timeout failure 가능성
- `0000` 상태에 멈춤

  - reset이 안 풀렸거나
  - top이 아예 실행되지 않았거나
  - bitstream/programming/XDC/top 설정 문제일 수 있음
- `0001`이 아니라 `1000`처럼 보이는지 여부는 보드 LED ordering을 육안으로 다시 확인

### 5.3 reset 버튼으로 확인하는 방법

버튼 테스트는 매우 중요하다.

#### 기대 동작

1. 정상 PASS 후 LED `0110`
2. reset 버튼 누름
   - 즉시 reset 상태로 들어감
3. reset 버튼 release
   - debounce 뒤 sample `0`부터 자동 재시작
4. 다시 최종 LED `0110`

이게 되면 아래가 같이 검증된다.

- `reset_conditioner` 동작
- source state reset
- DUT state reset
- checker state reset
- auto-run flow

### 5.4 시간이 너무 짧아 LED 변화가 안 보일 때

현재 벡터 재생은 `8192 + 4`개 샘플이다.
125 MHz에서 실행 시간이 매우 짧기 때문에, running 상태를 눈으로 길게 보기 어려울 수 있다.

이 경우 확인 포인트는:

- 최종 상태가 `0110`인지
- reset 버튼으로 반복 재실행이 되는지

즉 running LED의 “순간적인 점등” 자체보다, 최종 `done/pass/fail` 상태와 reset 반복성이 더 중요한 검증 포인트다.

## 6) 보드 동작이 제대로 안 보일 때의 점검 순서

문제가 생기면 아래 순서로 점검한다.

1. **top 설정 확인**

   - Vivado top이 `top_zybo_bringup_n5`인지
2. **XDC 확인**

   - `clk`, `reset_btn`, `led[3:0]`가 현재 top 포트명과 정확히 맞는지
3. **hex 파일 포함 여부 확인**

   - `input_q15.hex`
   - `expected_decim_q15.hex`
   - Vivado project source에 실제 포함됐는지
4. **timing summary 확인**

   - timing failure로 동작이 불안정하지 않은지
5. **reset polarity 확인**

   - `btn[0]`이 현재 보드에서 눌렀을 때 active-high처럼 들어오는지
6. **LED polarity/ordering 확인**

   - 원하는 LED가 실제 같은 번호 위치에 연결됐는지
7. **simulation 재확인**

   - board top sanity가 PASS 상태인지

## 7) 필요하면 추가하면 좋은 확인 수단

현재는 LED만으로도 PASS/FAIL을 볼 수 있다. 하지만 더 확실히 보고 싶으면 아래를 고려할 수 있다.

### 7.1 ILA 추가

관측하면 좋은 신호:

- `rst`
- `source_valid`
- `source_done`
- `dut_out_valid`
- `checker_done`
- `checker_pass`
- `checker_fail`

이렇게 하면 보드에서 실제로:

- reset이 언제 풀리는지
- source가 언제 시작/종료하는지
- DUT 출력이 나오고 있는지
- checker가 왜 끝났는지

를 cycle-level로 확인할 수 있다.

### 7.2 source/checker를 느리게 만드는 debug build

사람이 눈으로 running LED를 보기 어렵다면, debug branch에서는:

- source 사이에 divider를 두거나
- source를 1 sample / many cycles로 느리게 재생하거나
- done 전에 pause를 길게 넣는 방식

도 가능하다.

다만 현재 기본 bring-up 본선은 “최종 PASS/FAIL 자동 판단”이 목적이므로, 우선순위는 낮다.

## 8) 이 워크플로우의 핵심 철학

이번 v5는 단순히 Vivado 버튼을 누르는 순서만 정한 것이 아니다.
핵심은 아래 두 가지다.

1. **Vivado에서 재현 가능하게 같은 구조를 올릴 것**

   - top/XDC/hex 파일을 빠뜨리지 않기
2. **보드에서 의도한 동작을 명확한 관측값으로 확인할 것**

   - 최종 LED `0110`
   - reset release 후 자동 실행
   - reset 반복 시 재시작 가능

즉 “bitstream 생성 성공”이 완료 조건이 아니라,
**실제 보드에서 PASS 상태를 확실히 읽을 수 있을 때** 이번 bring-up이 닫힌다.

## 9) v5 단계의 다음 액션

v5 단계에서 실제로 해야 할 일은 아래 순서다.

1. Vivado 프로젝트 생성
2. RTL/XDC/hex source 추가
3. top 설정
4. synthesis
5. implementation
6. bitstream 생성
7. 보드 다운로드
8. LED `0110` 확인
9. reset 버튼 재실행 확인
10. 필요 시 ILA로 추가 확인

이 단계가 끝나면 `N=5 bring-up RTL`은 문서/시뮬레이션/보드 동작까지 한 번의 폐루프로 닫히게 된다.
