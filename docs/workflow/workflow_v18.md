# FIR Decimation Project Workflow v18

- Date: 2026-06-29
- Previous: `docs/workflow/workflow_v17.md`
- Purpose: 2026-05-27 교수님 미팅 피드백 반영. CPU(노트북) vs FPGA(보드) FIR 처리 시간 비교.
- Feedback source: `docs/log/36_professor_meeting_2026_05_27.md` 섹션 10

---

## 1. 배경

교수님 피드백:

> "실제로 뭔가 보여지는 게 중요하다. 보드로 뭔가를 해낸다고 잘 안 느껴진다."

요청 사항:
1. 노트북(CPU)으로 FIR 연산 실행 → 시간 및 자원 기록
2. 보드(FPGA)로 FIR 연산 실행 → 시간 측정 → 비교 분석

---

## 2. 설계 결정 사항

### 2-1. CPU 벤치마크 기준: numpy float64

`run_fir_decimator_transposed_golden()`은 RTL bit-exact Python loop이다. RTL 동작을 에뮬레이션하기 위해 의도적으로 sample 단위 sequential loop로 구현되어 있어 CPU의 장점(vectorization)을 전혀 사용하지 않는다. 이를 CPU 벤치마크로 쓰면 "Python loop vs FPGA" 비교가 된다.

**numpy float64 FIR**을 CPU 기준으로 사용한다. Python 엔지니어가 자연스럽게 작성할 최선의 구현이다. 발표 시 "numpy float64 기준"임을 명시한다.

```python
x_f64 = input_q15.astype(np.float64) / 32768.0
h_f64 = FIR_COEFFS_Q15.astype(np.float64) / 32768.0
y = np.convolve(x_f64, h_f64)[::2]  # FIR + M=2 decimation
```

### 2-2. FPGA 타이밍 측정 범위: MM2S kick → S2MM IDLE

`dma_run()` 전체를 감싸면 안 된다. 내부에 UART debug print(D0~D6, dma_dump_status)가 8개 있고, 115200 baud에서 한 줄이 2~3ms이므로 ~82µs의 실제 처리 시간을 수십 배 왜곡한다.

**타이밍 구간: MM2S_LENGTH 쓰기(kick) 직전 ~ S2MM IDLE 확인 직후.**

DMA를 측정 범위에 포함하는 이유: DMA는 FPGA 솔루션의 데이터 경로 일부이며, numpy가 input array를 캐시에서 로드하는 시간에 대응된다. 이 수준이 CPU 타이밍과 비교 가능한 최소 단위이다.

타이머는 `dma_run()` 내부에 배치하고, `dma_run()` 시그니처를 변경해 측정값을 반환한다:
```c
static int dma_run(u32 *out_elapsed_us);
```

### 2-3. capture.py 반환 타입: Q15CaptureResult

`FIR_TIME_US:XXX` 라인은 UART byte stream 안에서 magic bytes 직전에 위치한다. `uart_recv_result_q15()` 내부에서만 파싱 가능하므로 timing과 signal 수신은 물리적으로 결합되어 있다.

- **q15 경로**: `Q15CaptureResult(samples, board_time_us)` NamedTuple 반환. timing이 필요한 코드가 이 경로를 사용한다.
- **float 경로**: `uart_recv_result()`, `capture_output_float()`는 `.samples`만 꺼내 float 변환 후 반환. timing이 불필요한 FFT viewer가 이 경로를 사용한다.

---

## 3. 현재 상태 확인

| 항목 | 상태 | 위치 |
| --- | --- | --- |
| 입력 vs 출력 FFT 나란히 비교 시각화 | **이미 구현됨** | `sw/fir_decimator_report.py` `_save_fft_png()` |
| CPU FIR 연산 로직 (numpy float64) | **없음** | 추가 필요 |
| CPU 처리 시간 측정 | **없음** | 추가 필요 |
| 보드 FIR 연산 로직 | **이미 있음** | `dma_run()` in `sw/fir_decimator_demo.c:135` |
| 보드 처리 시간 측정 | **없음** | 추가 필요 |
| CPU vs FPGA 비교 출력 | **없음** | 추가 필요 |

---

## 4. 시나리오별 영향 범위

| 시나리오 | 보드 연결 | 펌웨어 변경 영향 | capture.py 변경 영향 |
| --- | --- | --- | --- |
| Scenario 0 | 없음 (PC only) | **없음** | **없음** |
| Scenario 1-1 | 있음 | **있음** — `FIR_TIME_US:XXX` UART 추가 출력 | **있음** — 해당 라인 파싱 필요 |
| Scenario 1-2 | 있음 | **있음** — 동일 | **있음** — 동일 |
| Scenario 2 | 있음 | **있음** — 동일 | **있음** — 동일 |
| cpu_benchmark.py | 없음 | **없음** — 독립 실행 도구 | **없음** |

`fir_decimator_capture.py` 수정 시 `FIR_TIME_US:` 라인 파싱이 기존 동작을 깨지 않아야 한다.
Scenario 1-1, 1-2, 2는 타이밍 값을 받아도 기존 FFT/메트릭 흐름에 영향이 없어야 한다.

---

## 5. 작업 1: CPU 벤치마크 스크립트

**파일:** `sw/cpu_benchmark.py` (신규)

**할 일:**

1. 입력 신호: Scenario 1-2 고정 (7/15/25/45 MHz, 8192 samples, Q1.15). `fir_decimator_metrics.generate_fixed_reference()`로 생성.
2. FIR 연산: numpy float64 FIR.
   ```python
   x_f64 = input_q15.astype(np.float64) / 32768.0
   h_f64 = FIR_COEFFS_Q15.astype(np.float64) / 32768.0
   y = np.convolve(x_f64, h_f64)[::2]
   ```
3. `time.perf_counter()`로 연산 구간만 측정한다.
4. `psutil.cpu_percent()`로 CPU 사용률을 캡처한다.

**반복 횟수 결정:**

- 워밍업 10회 실행 후 측정 시작 (JIT/캐시 안정화)
- 변동 계수(CV = std / mean)가 2% 이하가 될 때까지 반복
- 최소 30회, 최대 500회

**출력 형식:**

```
=== CPU FIR Benchmark ===
Input:  8192 samples, Scenario 1-2 (7/15/25/45 MHz)
Filter: N=43 taps, M=2 decimation, numpy float64

Runs: XXX (CV converged < 2%)
  Mean:  XXX us
  Min:   XXX us
  Max:   XXX us
  Std:   XXX us
  CV:    X.X %
  Throughput: XXX M samples/sec

CPU usage: XX %
```

---

## 6. 작업 2: 보드 타이머 삽입

**파일:** `sw/fir_decimator_demo.c` (수정)

**할 일:**

타이머를 `dma_run()` 내부 MM2S kick ~ S2MM IDLE 구간에 배치한다. 타이밍 구간 내의 UART debug print(D4/ST4, D5/ST5, D6/ST6)를 타이밍 구간 밖으로 이동한다.

`dma_run()` 시그니처 변경:
```c
static int dma_run(u32 *out_elapsed_us);
```

C 코드 변경 (dma_run 내부):
```c
#include "xtime_l.h"

// S2MM 설정 (기존 동일)
DMA_REG(S2MM_DMACR) = DMA_RS_BIT;
DMA_REG(S2MM_DA)    = (uint32_t)(UINTPTR)dst_buf;
DMA_REG(S2MM_LENGTH) = N_OUT * sizeof(int16_t);

// MM2S 설정 후 kick 직전 타이머 시작
DMA_REG(MM2S_DMACR) = DMA_RS_BIT;
DMA_REG(MM2S_SA)    = (uint32_t)(UINTPTR)src_buf;

XTime tStart, tEnd;
XTime_GetTime(&tStart);
DMA_REG(MM2S_LENGTH) = N_IN * sizeof(int16_t);  /* kick: 타이밍 시작 */

// MM2S poll (status interval print 제거)
t = DMA_POLL_TIMEOUT;
while (!(DMA_REG(MM2S_DMASR) & DMA_IDLE_BIT)) {
    if (--t == 0) { dma_dump_status("MM2STO"); return 1; }
}

// S2MM poll (status interval print 제거)
t = DMA_POLL_TIMEOUT;
while (!(DMA_REG(S2MM_DMASR) & DMA_IDLE_BIT)) {
    if (--t == 0) { dma_dump_status("S2MMTO"); return 2; }
}
XTime_GetTime(&tEnd);  /* 타이밍 종료 */

*out_elapsed_us = (u32)((tEnd - tStart) * 1000000ULL / COUNTS_PER_SECOND);

Xil_DCacheInvalidateRange((UINTPTR)dst_buf, N_OUT * sizeof(int16_t));
return 0;
```

`main()`에서:
```c
u32 elapsed_us = 0;
int err = dma_run(&elapsed_us);
if (err) {
    /* ERR:<n>\r\n 출력 후 continue */
}
xil_printf("FIR_TIME_US:%lu\r\n", elapsed_us);  /* magic bytes 직전 */
uart_send_result();
```

에러 시 `FIR_TIME_US:` 출력 없음.

**Python 측 파싱 (`sw/fir_decimator_capture.py` 수정):**

```python
from typing import NamedTuple

class Q15CaptureResult(NamedTuple):
    samples: npt.NDArray[np.int16]
    board_time_us: int | None
```

`uart_recv_result_q15()`:
- `FIR_TIME_US:XXX` 라인 감지 시 값 파싱, `board_time_us`에 저장
- 반환 타입: `Q15CaptureResult`

`capture_output_q15()`:
- 반환 타입: `Q15CaptureResult` (board_time_us 포함)

`uart_recv_result()`, `capture_output_float()`:
- 내부에서 `.samples`만 꺼내 처리
- 반환 타입 유지: `npt.NDArray[np.float64]`

테스트 수정 범위: `test_fir_decimator_capture.py`에서 `uart_recv_result_q15()` 반환값을 직접 ndarray로 사용하는 4개 테스트 → `.samples` 사용으로 변경. `board_time_us` 파싱 테스트 추가.

---

## 7. 작업 3: 비교 출력

**파일:** `sw/cpu_benchmark.py`에 포함

CPU 벤치마크 실행 후 보드 타이밍 결과를 인자로 받아 비교 표와 바 차트를 출력한다.

기존 scenario 1-1, 1-2 FFT plot은 건드리지 않는다. 비교 차트는 별도 파일로만 저장한다.

**터미널 출력 형식:**

```
=== CPU vs FPGA Comparison ===
Input: 8192 samples, N=43 FIR, M=2 decimation

                   CPU (laptop)         FPGA (board)
Implementation:    numpy float64        Q1.15 fixed-point
Processing time:   XXX us               XXX us
Throughput:        XXX M samp/s         XXX M samp/s
Speedup:           1x                   Xx

Resources:
  CPU:   1 core, XX% usage
  FPGA:  16 DSP48, 1827 LUT (Vivado utilization report 기준)
```

바 차트는 `docs/report/fir_n43/plot/cpu_vs_fpga_timing.png`에 독립적으로 저장한다.

---

## 8. 작업 순서

```
1. sw/cpu_benchmark.py 작성 (보드 불필요)
   → verify: 30회 이상 실행 후 평균 처리 시간 숫자 출력 확인

2. sw/fir_decimator_capture.py 수정 (Q15CaptureResult)
   → verify: 기존 테스트 통과 + board_time_us 파싱 테스트 통과

3. sw/fir_decimator_demo.c 수정 (XTime 타이머)
   → verify: 보드 UART에서 FIR_TIME_US:XXX 라인 수신 확인
   → 주의: Vitis 재빌드 및 BOOT.bin 재생성 필요

4. cpu_benchmark.py에 비교 표 및 바 차트 추가
   → verify: 두 수치 모두 있을 때 비교 결과 출력/저장 확인
```

작업 1, 2는 보드 없이 바로 가능하다.
작업 3은 Vitis 재빌드 및 BOOT.bin 재생성이 필요하다.

---

## 9. 완료 기준

| 기준 | 확인 방법 |
| --- | --- |
| CPU 처리 시간이 수치로 출력됨 | `cpu_benchmark.py` 실행 결과 |
| 보드 처리 시간이 UART로 수신됨 | `FIR_TIME_US:` 라인 확인 |
| CPU vs FPGA 비교 표와 바 차트가 생성됨 | 두 수치 확보 후 출력/저장 |

---

## 10. v17과의 관계

v17(characterization, BIST, frequency sweep)은 v18 이후에 진행한다.
v18은 교수님 피드백 반영에만 집중한다.
