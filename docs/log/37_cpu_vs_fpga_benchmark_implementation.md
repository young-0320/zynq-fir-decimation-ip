# 37. CPU vs FPGA FIR 처리 시간 비교 구현

- 작성일: 2026-06-29
- 선행 문서:
  - `36_professor_meeting_2026_05_27.md`
  - `../workflow/workflow_v18.md`

---

## 배경

교수님 피드백: "실제로 뭔가 보여지는 게 중요하다. 보드로 뭔가를 해낸다고 잘 안 느껴진다."

CPU(노트북) vs FPGA(보드) FIR 처리 시간 비교 기능을 추가했다.

---

## 설계 결정 사항

### CPU 벤치마크 기준: numpy float64

`run_fir_decimator_transposed_golden()`은 RTL bit-exact Python loop이다. CPU의 vectorization을 의도적으로 사용하지 않아 "Python loop vs FPGA" 비교가 되어버린다.

numpy float64 FIR을 CPU 기준으로 선택했다. Python 엔지니어가 자연스럽게 작성할 최선의 구현이며, 발표 시 "numpy float64 기준"임을 명시한다.

```python
x_f64 = input_q15.astype(np.float64) / 32768.0
h_f64 = FIR_COEFFS_Q15.astype(np.float64) / 32768.0
y = np.convolve(x_f64, h_f64)[::2]
```

### FPGA 타이밍 측정 범위: MM2S kick → S2MM IDLE

`dma_run()` 전체를 감싸면 내부 UART debug print(D0~D6)가 115200 baud에서 한 줄에 2~3ms씩, 총 ~20ms 이상의 오버헤드를 유발한다. 실제 FPGA 처리 시간(~82µs)을 수백 배 왜곡한다.

타이머를 `dma_run()` 내부에 배치하고 kick 직전~S2MM IDLE 직후만 측정한다. DMA는 FPGA 솔루션의 데이터 경로 일부이며 numpy의 캐시 로드에 대응하는 구간이므로 포함한다.

`dma_run()` 시그니처 변경: `static int dma_run(u32 *out_elapsed_us)`

### capture.py 반환 타입: Q15CaptureResult

`FIR_TIME_US:XXX` 라인은 UART byte stream에서 magic bytes 직전에 위치한다. `uart_recv_result_q15()` 내부에서만 파싱 가능하므로 timing과 signal 수신은 물리적으로 결합되어 있다.

- q15 경로: `Q15CaptureResult(samples, board_time_us)` NamedTuple 반환
- float 경로: `.samples`만 꺼내 float 변환 후 반환 (기존 타입 유지)

FFT viewer 등 float 경로를 쓰는 기존 코드에 영향 없다.

### CPU 벤치마크는 시나리오와 무관

FIR 연산량은 `len(x) × len(h) = 8192 × 43`으로 고정이다. 시나리오가 바꾸는 것은 입력 주파수(값)이고, `np.convolve`의 연산 시간은 값에 무관하다. FPGA도 동일하다. 따라서 비교 차트는 시나리오 FFT plot과 분리된 독립 파일로 산출한다.

---

## 변경된 파일

### `sw/cpu_benchmark.py` (신규)

- numpy float64 FIR 벤치마크
- CV 수렴 루프 (min 30회, max 500회, CV < 2%) + 배치 측정(10회씩)으로 Windows OS jitter 희석
- Windows 환경에서 CV가 수렴하지 않는 경우가 많음. median을 비교 기준으로 사용
- `--port COM3` 옵션으로 보드에 자동 커맨드 전송 및 `FIR_TIME_US` 실측값 수신
- `--board-time-us` 옵션으로 수동 입력 fallback 유지 (두 옵션 mutually exclusive)
- 비교 표 + 바 차트를 `docs/report/fir_n43/plot/cpu_vs_fpga_timing.png`로 저장

```bash
# 자동 (보드 연결 시)
uv run python sw/cpu_benchmark.py --port COM3

# 수동 fallback
uv run python sw/cpu_benchmark.py --board-time-us 95

# CPU 벤치마크만
uv run python sw/cpu_benchmark.py
```

### `sw/fir_decimator_capture.py` (수정)

- `Q15CaptureResult(samples, board_time_us)` NamedTuple 추가
- `uart_recv_result_q15()`: `FIR_TIME_US:XXX` 라인 파싱, `Q15CaptureResult` 반환
- `capture_output_q15()`: `Q15CaptureResult` 반환
- `uart_recv_result()`, `capture_output_float()`: `.samples`만 꺼내 기존 float 반환 타입 유지

### `sw/test/test_fir_decimator_capture.py` (수정)

- `uart_recv_result_q15()` 반환값 `.samples` 사용으로 변경 (4개 테스트)
- `test_uart_recv_result_q15_parses_fir_time_us` 추가
- `test_uart_recv_result_q15_ignores_malformed_fir_time_us` 추가
- 36 passed

### `sw/fir_decimator_demo.c` (수정)

- `#include "xtime_l.h"` 추가
- `uart_putu32()` 헬퍼 추가 (xil_printf 의존성 없이 uint32 출력)
- `dma_run()` 시그니처 변경: `static int dma_run(u32 *out_elapsed_us)`
- 타이머 구간: MM2S_LENGTH 쓰기(kick) 직전 ~ S2MM IDLE 직후
- 타이밍 구간 내 UART debug print 전부 제거
- `main()`: 성공 시 `FIR_TIME_US:%u\r\n` 출력 (magic bytes 직전)
- 에러 시 FIR_TIME_US 출력 없음

### `docs/workflow/workflow_v18.md` (업데이트)

- 섹션 2 (설계 결정 사항) 신규 추가
- 섹션 번호 오류 수정 (Section 5 중복 → 6, 7, 8, 9, 10으로 정리)
- 작업 순서에 capture.py 수정 단계 추가

---

## 완료 확인

Vitis 재빌드 및 BOOT.bin 재생성 완료. SD카드 교체 후 보드에서 `FIR_TIME_US:XXX` UART 수신 확인 완료. `cpu_benchmark.py` 실행으로 CPU vs FPGA 비교 표 및 바 차트(`docs/report/fir_n43/plot/cpu_vs_fpga_timing.png`) 산출 완료.
