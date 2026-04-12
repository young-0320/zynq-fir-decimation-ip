# 10. Bring-up RTL 구현 모듈 설명

- 작성일: 2026-04-12
- 단계: 6
- 목적: 지금까지 구현한 bring-up RTL 모듈을 천천히 읽으면서, 하드웨어가 실제로 어떤 구조로 동작하는지 이해할 수 있도록 설명한다.

## 1) 먼저 큰 그림

현재 bring-up RTL은 두 층으로 나뉜다.

1. **core datapath 층**
   - FIR 필터링과 decimation이라는 본래 신호처리 기능을 수행한다.
2. **board bring-up support 층**
   - 보드 버튼으로 reset을 만들고
   - 입력 벡터를 자동 재생하고
   - 출력이 정답과 일치하는지 스스로 검사하고
   - LED로 상태를 보여 준다.

즉 현재 구현은 단순히 `FIR 코어 하나`만 만든 것이 아니라, 아래와 같은 작은 자동 데모 시스템까지 포함한다.

```text
Zybo clock / reset button
    -> reset_conditioner
    -> bringup_vector_source
    -> fir_decimator_direct_n5_top
         -> fir_direct_n5
         -> decimator_m2_phase0
    -> bringup_output_checker
    -> LED status
```

이 구조를 선택한 이유는 bring-up의 목표가 “RTL 코드를 작성해 보는 것”에서 끝나는 것이 아니라,
**Python golden과 일치하는지 확인된 설계를 실제 FPGA 위에서 자동으로 재생하고 PASS/FAIL까지 볼 수 있게 하는 것**이기 때문이다.

---

## 2) 구현된 모듈 목록

### 2.1 Core datapath 모듈

- `rtl/direct_form/bringup_n5/fir_direct_n5.v`
- `rtl/direct_form/decimator_m2_phase0.v`
- `rtl/direct_form/bringup_n5/fir_decimator_direct_n5_top.v`

### 2.2 Board bring-up support 모듈

- `rtl/direct_form/bringup_n5/reset_conditioner.v`
- `rtl/direct_form/bringup_n5/bringup_vector_source.v`
- `rtl/direct_form/bringup_n5/bringup_output_checker.v`
- `rtl/direct_form/bringup_n5/top_zybo_bringup_n5.v`

### 2.3 Verification testbench 모듈

- `sim/rtl/tb/direct_form/tb_fir_direct_n5.v`
- `sim/rtl/tb/direct_form/tb_fir_decimator_direct_n5_top.v`

---

## 3) Core datapath 모듈 설명

### 3.1 `fir_direct_n5.v`

이 모듈은 `5-tap direct-form FIR`이다. 현재 bring-up에서 가장 핵심인 연산 블록이다.

#### 역할

- 입력 `in_sample`을 한 샘플씩 받아서
- `N=5` coefficient와 곱하고
- 모두 합산한 뒤
- `Q1.15` 형식으로 다시 내보낸다.

이 모듈이 하는 일은 수식으로 쓰면 아래와 같다.

```text
y[n] = h[0]x[n] + h[1]x[n-1] + h[2]x[n-2] + h[3]x[n-3] + h[4]x[n-4]
```

#### 왜 direct-form인가

장기 계획은 transposed form이지만, bring-up 첫 단계에서는 direct-form이 더 읽기 쉽고
Python golden과 1:1로 대응시키기 좋다. 지금은 “최적 구조”보다 “첫 bit-exact baseline”이 더 중요하다.

#### 포트 의미

- `clk`: 연산 기준 클록
- `rst`: active-high reset
- `in_valid`: 현재 cycle의 입력 샘플이 유효한지 표시
- `in_sample`: signed 16-bit Q1.15 입력
- `out_valid`: 현재 cycle의 FIR 출력이 유효한지 표시
- `out_sample`: signed 16-bit Q1.15 출력

#### 내부 상태

이 모듈의 state는 사실상 4개의 delay register이다.

- `delay_1`
- `delay_2`
- `delay_3`
- `delay_4`

현재 입력 샘플 `x[n]`은 포트 `in_sample`로 바로 들어오므로, 내부 register는 `x[n-1]`부터 `x[n-4]`까지만 저장하면 된다.

즉 어떤 시점의 상태를 보면:

- `in_sample` = `x[n]`
- `delay_1` = `x[n-1]`
- `delay_2` = `x[n-2]`
- `delay_3` = `x[n-3]`
- `delay_4` = `x[n-4]`

#### coefficient

현재 coefficient는 하드코딩되어 있다.

- `88`
- `7069`
- `18455`
- `7069`
- `88`

이 값은 실수 계수를 Q1.15 정수로 양자화한 것이다. bring-up에서는 coefficient load port를 두지 않고
이 숫자들을 고정함으로써 회로와 검증 경로를 최대한 단순하게 했다.

#### 산술 흐름

산술은 아래 순서로 진행된다.

1. 16-bit 입력과 16-bit coefficient를 곱한다.
2. 각 곱셈 결과는 `Q2.30`으로 해석한다.
3. 다섯 개 product를 48-bit로 sign-extend 해서 더한다.
4. 누산 결과를 `Q2.30 -> Q1.15`로 반올림한다.
5. 최종 결과만 `[-32768, 32767]`로 saturation 한다.
6. 그 값을 `out_sample`에 저장한다.

핵심은 **중간에 saturation이나 wrap을 하지 않는 것**이다. Python golden도 넓은 누산 후 마지막에만 반올림과 saturation을 하기 때문에,
RTL도 같은 순서를 따라야 bit-exact로 맞는다.

#### 반올림 방식

반올림은 `ties-away-from-zero`다.

의미는 아래와 같다.

- `+0.5`는 `+1`로 감
- `-0.5`는 `-1`로 감

이 규칙은 Python model의 `_round_shift_ties_away_from_zero`와 맞추기 위해 명시적으로 구현했다.

#### reset 시 동작

`rst=1`이면:

- delay register 모두 `0`
- `out_valid = 0`
- `out_sample = 0`

즉 reset이 끝난 뒤 첫 valid 입력은 새 스트림의 첫 샘플로 처리된다.

#### valid 시 동작

- `in_valid=1`이면
  - 현재 입력과 저장된 delay들을 이용해 FIR 출력을 계산
  - `out_valid=1`
  - 다음 cycle을 위해 delay register를 한 칸씩 shift
- `in_valid=0`이면
  - `out_valid=0`
  - `out_sample`은 이전 값을 hold

#### latency

이 모듈은 registered output이므로:

- 입력 accepted 기준
- FIR output은 `1 cycle` 뒤에 나온다.

즉 `in_valid=1`로 받은 샘플이 same-cycle combinational path로 바로 나가는 것이 아니라,
다음 clock edge에서 `out_valid/out_sample`로 나타난다.

---

### 3.2 `decimator_m2_phase0.v`

이 모듈은 `M=2`, `phase=0` decimator이다.

#### 역할

FIR 출력이 매 cycle valid로 들어올 때마다:

- 첫 번째는 keep
- 두 번째는 drop
- 세 번째는 keep
- 네 번째는 drop

이 패턴으로 절반만 통과시킨다.

즉 Python의 `x[0::2]`와 같은 동작을 RTL state machine으로 구현한 것이다.

#### 중요한 오해 하나

이 decimator는 **두 샘플을 모아서 새로운 계산을 하는 블록이 아니다.**
그저 “들어오는 샘플 중 어떤 것을 통과시키고 어떤 것을 버릴지”를 결정하는 selector이다.

그래서 첫 출력 생성을 위해 FIR 샘플 두 개를 모두 기다릴 필요가 없다.

#### 내부 상태

state는 `keep_next` 한 비트뿐이다.

- `keep_next = 1`이면 다음 valid 샘플을 통과
- `keep_next = 0`이면 다음 valid 샘플을 버림

reset 시 `keep_next=1`로 시작하므로, 첫 FIR-valid sample은 keep된다.

#### reset 시 동작

`rst=1`이면:

- `keep_next=1`
- `out_valid=0`
- `out_sample=0`

#### valid 시 동작

- `in_valid=1`이고 `keep_next=1`
  - `out_valid=1`
  - `out_sample=in_sample`
  - 다음에는 drop하도록 `keep_next` 토글

- `in_valid=1`이고 `keep_next=0`
  - `out_valid=0`
  - `out_sample`은 hold
  - 다음에는 keep하도록 `keep_next` 토글

- `in_valid=0`
  - `out_valid=0`
  - 상태는 그대로 유지

#### 왜 valid가 중요하나

이 모듈은 매 clock마다 상태가 움직이는 것이 아니라 **`in_valid=1`일 때만** 상태가 움직인다.
이게 중요하다. 나중에 bubble이 생기더라도 decimation phase가 깨지지 않기 때문이다.

#### latency

keep되는 샘플은 registered output을 거쳐 `1 cycle` 뒤에 나온다.

---

### 3.3 `fir_decimator_direct_n5_top.v`

이 모듈은 core datapath의 내부 top이다.

#### 역할

아래 두 모듈을 단순히 직렬 연결한다.

- `fir_direct_n5`
- `decimator_m2_phase0`

즉 이 모듈 자체는 복잡한 제어를 추가하지 않는다. 역할은 “이번 bring-up DUT를 하나의 top으로 묶는 것”이다.

#### 데이터 흐름

```text
in_valid/in_sample
    -> FIR
    -> FIR out_valid/out_sample
    -> Decimator
    -> out_valid/out_sample
```

#### 왜 따로 top을 두는가

- testbench에서 DUT를 하나로 잡기 쉬움
- 나중에 board top에서 core를 한 번에 인스턴스화하기 쉬움
- FIR와 decimator의 경계는 유지하면서도 “현재 bring-up용 신호처리 체인”을 하나의 블록으로 다룰 수 있음

#### top-level latency

현재 구조에서는:

- FIR = `1 cycle`
- Decimator = `1 cycle`

이므로 keep되는 샘플 기준 top latency는 `2 cycles`다.

---

## 4) Board bring-up support 모듈 설명

### 4.1 `reset_conditioner.v`

이 모듈은 보드 버튼 입력을 clean active-high `rst`로 바꾸는 역할을 한다.

#### 왜 필요한가

보드 버튼은:

- clock와 비동기이고
- 기계적 bounce가 있고
- 전원 인가 직후 상태도 바로 믿기 어렵다.

버튼 신호를 DUT에 직접 넣으면 상태가 불안정해질 수 있으므로, 그 앞에 conditioning 블록이 필요하다.

#### 이 모듈이 하는 세 가지

1. **동기화**
   - `sync_0`, `sync_1` 두 단계 register로 버튼 입력을 clock domain에 동기화한다.

2. **debounce**
   - 버튼이 release된 뒤 일정 시간 안정적으로 유지될 때만 reset을 풀어 준다.

3. **power-on reset**
   - bitstream 로드 직후 몇 cycle 동안 자동으로 reset을 유지한다.

#### 중요한 동작 철학

이 모듈은 reset을 아래처럼 다룬다.

- assert는 즉시
- release는 debounce 후

즉 버튼이 눌리면 reset은 바로 올라간다.
반대로 버튼을 뗐다고 해서 바로 내려가지 않고, 일정 시간 안정적일 때만 reset을 해제한다.

이 방식이 reset 버튼으로는 가장 자연스럽다.

#### 왜 이렇게 했는가

초기 시도에서는 눌림과 release를 완전히 대칭으로 debounce하려고 했는데,
그 경우 “전원 인가 때 버튼을 계속 누르고 있으면 reset이 잠깐 풀리는 구간”이 생길 수 있었다.
그래서 reset 버튼다운 동작으로 수정했다.

#### 현재 파라미터 의미

- `DEBOUNCE_COUNT_MAX`
  - 버튼 release를 인정하기 전에 기다릴 cycle 수
  - 현재 125 MHz 기준 약 10 ms 설정

- `POWER_ON_RESET_CYCLES`
  - 전원 인가 직후 자동 reset을 유지할 cycle 수

- `BUTTON_ACTIVE_HIGH`
  - 버튼 polarity를 바꾸기 위한 파라미터

#### 현재 bring-up에서의 의미

지금 구조는 “start 버튼”이 따로 없다.

- 전원 인가
- power-on reset 유지
- power-on reset 종료
- 자동 실행 시작

그리고 나중에 사용자가 reset 버튼을 누르면:

- 즉시 초기화
- 버튼을 떼고 debounce가 끝나면
- sample 0부터 자동 재시작

즉 reset release가 사실상 run enable 역할을 한다.

---

### 4.2 `bringup_vector_source.v`

이 모듈은 보드에서 입력 벡터를 자동으로 재생하는 source이다.

#### 역할

- `input_q15.hex`를 ROM처럼 읽는다.
- reset이 풀리면 sample `0`부터 출력한다.
- 총 `8192`개의 실제 입력을 출력한다.
- 그 뒤 zero `4`개를 flush 용도로 추가 출력한다.
- 끝나면 `done=1`을 유지한다.

#### 왜 필요하나

현재 bring-up은 ADC나 PS-PL streaming 없이 먼저 닫기로 했다.
따라서 보드 위에서 DUT를 실제로 돌려보려면, 내부에서 테스트 입력을 공급하는 source가 필요하다.

#### 내부 상태

- `input_mem`
  - `input_q15.hex`를 읽어 저장하는 메모리

- `sample_idx`
  - 현재 몇 번째 샘플을 내보내는지 추적

- `replay_active`
  - 현재 재생 중인지 표시

- `running`, `done`
  - 바깥에서 상태를 보기 위한 status

#### 동작 순서

reset이 풀린 뒤 첫 active 구간에:

1. `replay_active=1`
2. `out_valid=1`
3. `out_sample=input_mem[0]`

그 다음 cycle부터는 `sample_idx`를 증가시키면서:

- `0 ~ 8191`: 실제 입력 샘플
- `8192 ~ 8195`: zero flush 샘플

을 순서대로 출력한다.

모든 샘플을 다 내보내면:

- `out_valid=0`
- `running=0`
- `done=1`

이 된다.

#### 왜 zero flush까지 여기서 넣나

시뮬레이션에서 이미 full convolution tail을 맞추기 위해 zero `4`개를 넣기로 했고,
보드 데모도 같은 기준을 따라야 checker가 Python golden과 동일한 길이를 비교할 수 있다.

즉 source가 zero flush까지 책임지는 것이 전체 시스템 관점에서 가장 자연스럽다.

---

### 4.3 `bringup_output_checker.v`

이 모듈은 DUT 출력이 정답과 일치하는지 보드 안에서 자동으로 판단한다.

#### 역할

- `expected_decim_q15.hex`를 읽는다.
- DUT의 `out_valid/out_sample`을 받는다.
- `out_valid=1`일 때만 expected와 비교한다.
- mismatch가 나오면 `fail`
- 끝까지 다 맞으면 `pass`
- 검사 종료를 `done`으로 표시한다.

#### 왜 필요한가

보드에서는 시뮬레이션처럼 터미널에 mismatch 로그를 쏟아내기 어렵다.
그래서 비교 로직 자체를 RTL로 넣고, 최종 결과만 `pass/fail`로 보이게 해야 한다.

#### 내부 상태

- `expected_mem`
  - golden decimated output 저장

- `observed_count`
  - 지금까지 valid 출력 샘플을 몇 개 받았는지

- `drain_count`
  - source가 끝난 뒤 얼마나 더 기다렸는지

- `done`, `pass`, `fail`, `mismatch_seen`
  - 최종 상태 latch

#### 비교 규칙

- `in_valid=1`인 cycle만 비교
- `observed_count`번째 expected sample과 현재 `in_sample` 비교

만약:

- 값이 다르면
  - 즉시 `done=1`
  - `fail=1`
  - `mismatch_seen=1`

- expected 길이보다 더 많은 출력이 나오면
  - 역시 `fail`

#### drain timeout이 필요한 이유

source는 자기 샘플을 다 내보낸 뒤 `source_done=1`이 된다.
하지만 DUT와 decimator에는 pipeline latency가 있으므로,
source가 끝났다고 해서 checker도 즉시 끝낼 수는 없다.

그래서 `source_done=1` 뒤에도 일정 cycle을 더 기다린다.

그 기간 안에:

- expected sample을 정확히 다 받으면 `pass`
- 다 못 받으면 `fail`

로 처리한다.

즉 checker는 mismatch뿐 아니라 **출력 부족**도 잡아낸다.

---

### 4.4 `top_zybo_bringup_n5.v`

이 모듈은 실제 Zybo 보드에 올릴 최상위 top이다.

#### 역할

앞에서 만든 support/core 모듈을 모두 연결해 하나의 보드 데모 시스템으로 만든다.

연결 구조는 아래와 같다.

```text
clk, reset_btn
    -> reset_conditioner
    -> rst

rst
    -> bringup_vector_source
    -> fir_decimator_direct_n5_top
    -> bringup_output_checker

checker status
    -> LED
```

#### 포트

- `clk`
  - Zybo의 system clock
- `reset_btn`
  - reset 버튼 입력
- `led[3:0]`
  - 상태 표시용 출력

#### 내부 연결

- `reset_conditioner`가 clean `rst` 생성
- `bringup_vector_source`가 DUT 입력 생성
- `fir_decimator_direct_n5_top`이 실제 필터/decimation 수행
- `bringup_output_checker`가 DUT 출력 검사

#### LED 의미

현재 LED 매핑은 아래와 같다.

- `led[0] = running`
- `led[1] = done`
- `led[2] = pass`
- `led[3] = fail`

즉 정상 종료 후 PASS면 LED는 `0110`이 된다.

#### `demo_running` 계산

`demo_running = (~rst) & (~checker_done)` 으로 두었다.

의미는 단순하다.

- reset 상태가 아니고
- 아직 checker가 끝나지 않았으면
- 지금 데모가 돌고 있다고 본다.

---

## 5) Testbench 모듈 설명

### 5.1 `tb_fir_direct_n5.v`

이 testbench는 FIR core만 단독으로 검증한다.

#### 하는 일

- `input_q15.hex`를 읽는다.
- 샘플 `8192`개를 넣는다.
- zero `4`개를 flush로 더 넣는다.
- `expected_fir_q15.hex`와 비교한다.

#### 비교 방식

- `out_valid=1`일 때만 sample index 증가
- 그때의 `out_sample`만 golden과 비교
- mismatch가 나면 즉시 FAIL

즉 absolute cycle보다 valid sample ordering을 기준으로 검증한다.

---

### 5.2 `tb_fir_decimator_direct_n5_top.v`

이 testbench는 전체 datapath top을 검증한다.

#### 하는 일

- 같은 입력과 같은 zero flush를 사용
- DUT는 `fir_decimator_direct_n5_top`
- 비교 대상은 `expected_decim_q15.hex`

이 벤치가 PASS한다는 것은:

- FIR 산술
- decimator keep/drop 규칙
- top-level 연결

이 모두 Python golden과 일치한다는 뜻이다.

---

## 6) 전원 인가부터 PASS까지 실제 동작 순서

현재 보드 데모의 실제 시간 순서를 글로 쓰면 아래와 같다.

1. 전원 인가 또는 bitstream 로드
2. `reset_conditioner`가 power-on reset 유지
3. power-on reset 종료
4. `bringup_vector_source`가 sample `0`부터 재생 시작
5. 샘플이 `fir_decimator_direct_n5_top`으로 들어감
6. FIR가 anti-alias filtering 수행
7. decimator가 `keep/drop` 수행
8. decimated output이 `bringup_output_checker`로 감
9. checker가 `expected_decim_q15.hex`와 비교
10. 모두 맞으면 `done=1`, `pass=1`, `fail=0`
11. LED는 `0110`

사용자가 reset 버튼을 누르면 위 과정이 중간에 끊기고 다시 초기 상태로 간다.
버튼을 떼고 debounce가 끝나면, 다시 sample `0`부터 위 순서가 반복된다.

---

## 7) XDC와 실제 보드 연결

현재 보드 연결은 `rtl/direct_form/bringup_n5/constrs/zybo_n5.xdc`에 반영돼 있다.

- `clk` -> Zybo `sysclk`
- `reset_btn` -> `btn[0]`
- `led[0]` -> running
- `led[1]` -> done
- `led[2]` -> pass
- `led[3]` -> fail

클럭은 `125 MHz` system clock을 그대로 사용한다.
현재 bring-up의 목적은 “100 MHz system 설계의 완전한 타이밍 실험”이 아니라,
**보드에서 자동 데모가 돌고 PASS/FAIL이 분명히 보이는 baseline을 닫는 것**이므로
PLL/MMCM 없이 direct-use로 단순화했다.

---

## 8) 이 구현에서 의도적으로 단순화한 부분

현재 구현은 bring-up용이므로 일부러 넣지 않은 것들이 있다.

- AXI-Stream wrapper 없음
- `ready` 없음
- `in_last` 없음
- coefficient reload 없음
- PS-PL 제어 없음
- DMA 없음
- ILA는 아직 optional

즉 현재 구조는 “가장 작은 self-running hardware demo”를 목표로 한 것이다.

---

## 9) 현재 구현의 의미

이번 단계에서 확보한 것은 단순히 `.v` 파일 몇 개가 아니다.

1. Python golden과 bit-exact로 맞는 core datapath baseline
2. self-checking simulation baseline
3. reset / vector replay / output checking까지 포함한 FPGA demo shell
4. 실제 Zybo top과 XDC 매핑

즉 이제 프로젝트는 “문서만 있는 상태”가 아니라, **실제로 합성 가능한 bring-up RTL 시스템**을 가진 상태다.

다음 단계는 Vivado에서:

- top 지정
- XDC 적용
- synthesis
- implementation
- bitstream

을 수행해 실제 보드에서 LED 상태를 확인하는 것이다.
