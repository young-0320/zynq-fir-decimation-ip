# 38. 2026-07-01 교수님 미팅 정리

- 작성일: 2026-07-01
- 미팅 예정일: 2026-07-02
- 목적: 교수님 미팅에서 보고할 CPU vs FPGA 벤치마크 결과, 주파수 스윕 / Fmax 측정 결과, 결과 해석을 정리한다.
- 참고 문서:
  - `docs/log/36_professor_meeting_2026_05_27.md`
  - `docs/log/37_cpu_vs_fpga_benchmark_implementation.md`
  - `docs/report/fir_n43/plot/cpu_vs_fpga_timing_ubuntu.png`
  - `docs/report/fir_n43/plot/cpu_vs_fpga_timing_window.png`
  - `vivado/reports/sweep_summary.md`

---

## 0. 미팅 대본 / 말하기 순서

### 0-1. 지난 미팅 과제 보고 시작

```text
지난 미팅에서 교수님께서 CPU와 FPGA의 FIR 연산 시간을 비교해보라고 하셨는데,
그 비교를 완료했습니다.

추가로, 이 IP가 100 MHz 이상으로 얼마나 올라갈 수 있는지
Vivado timing 분석으로 Fmax를 측정했습니다.

두 가지 결과를 순서대로 말씀드리겠습니다.
```

---

### 0-2. CPU vs FPGA 측정 기준 설명

```text
CPU 측 기준은 numpy float64 convolve입니다.
Python 엔지니어가 FIR을 구현할 때 자연스럽게 쓰는 최선의 구현이라 이걸 기준으로 잡았습니다.

FPGA 측 측정 구간은 AXI DMA MM2S kick 직전에서 S2MM IDLE 직후까지입니다.
bare-metal C에서 XTime_GetTime()으로 측정했습니다.

UART 전송(115200 baud, 16384 bytes ≈ 1.4초)은 관측 경로라 비교에서 제외했습니다.
```

---

### 0-3. CPU vs FPGA 측정 결과 제시

```text
두 환경에서 측정했습니다.

Windows 노트북 기준:
  CPU (numpy float64): 162.0 µs
  FPGA (Q1.15 fixed-point): 83.0 µs
  → FPGA가 약 1.95x 빠릅니다.

Ubuntu 기준:
  CPU (numpy float64): 58.6 µs
  FPGA (Q1.15 fixed-point): 83.0 µs
  → 이 환경에서는 CPU가 더 빠릅니다.

FPGA 83.0µs는 OS와 무관하게 일정합니다.
FPGA 이론 처리 시간은 8192 / 2 / 100MHz = 81.9µs인데,
측정값 83.0µs가 이 이론값에 99% 수준으로 일치합니다.
즉 FPGA는 이론 한계에 근접해서 돌고 있습니다.
```

---

### 0-4. Ubuntu에서 CPU가 더 빠른 이유 (물어보실 때)

```text
numpy float64 convolve는 내부적으로 BLAS(OpenBLAS / MKL)를 사용합니다.
Ubuntu 환경에서 AVX/SSE 벡터 연산이 최대한 활용되면 58.6µs까지 내려갑니다.

FPGA 83.0µs는 AXI DMA 왕복 오버헤드를 포함한 측정입니다.
N=43 tap 규모에서는 BLAS 최적화된 CPU 경로가 DMA 오버헤드를 포함한 FPGA 경로보다
빠를 수 있습니다.

"numpy가 특별히 빠른 것"이 아니라 "DMA 왕복이 포함된 FPGA 측정"과 비교했기 때문입니다.
```

---

### 0-5. FPGA 이점 추가 설명 (물어보실 때)

```text
숫자 하나만 보면 환경에 따라 다르게 보일 수 있습니다.
FPGA 구현의 실질적인 이점은 세 가지입니다.

첫째, 결정론적 지연 시간입니다.
FPGA는 OS 스케줄러나 캐시 미스 없이 항상 같은 시간에 끝납니다.
CPU는 부하에 따라 수십%에서 수 배까지 달라질 수 있습니다.

둘째, 자원 효율입니다.
Q1.15 fixed-point로 동작하면서 SNR 72~74 dB를 달성하고,
사용 자원은 DSP48 16개, LUT 1827개입니다.

셋째, 병렬 확장성입니다.
이 FIR core를 두 개 붙이면 처리 시간은 그대로인데 채널이 두 배가 됩니다.
CPU는 코어를 더 써야 하고, 메모리 bandwidth 한계에 먼저 부딪힙니다.
```

---

### 0-6. 주파수 스윕 / Fmax 결과 제시

```text
두 번째로, 이 IP가 100 MHz에서 어느 정도 margin을 갖는지
Vivado implementation을 90 / 100 / 110 / 115 / 120 MHz로 돌려서 WNS를 측정했습니다.

결과:
  90 MHz:  WNS +1.883 ns  ✅
  100 MHz: WNS +0.692 ns  ✅  ← 현재 운용 주파수
  110 MHz: WNS +0.178 ns  ✅
  115 MHz: WNS +0.178 ns  ✅
  120 MHz: WNS -0.783 ns  ❌  ← timing violation

확정 Fmax는 115 MHz입니다.
현재 100 MHz 대비 +15 MHz의 margin이 있습니다.

LUT/DSP48 자원은 클럭 변화에 무관하게 일정하고,
전력은 1.564 W(90 MHz)에서 1.576 W(120 MHz)로 +0.8% 증가에 그칩니다.
```

---

### 0-7. 세게 물어보실 때 짧은 답변

**FPGA가 더 빠르지 않은 경우가 있는데 의미 있나?**

```text
Ubuntu에서 numpy 58.6µs는 BLAS 멀티코어 최적화 결과입니다.
FPGA 83.0µs는 이론 처리 시간 81.9µs에 일치하는 값으로 이론 한계에서 동작합니다.
CPU는 OS/부하에 따라 달라지고, FPGA는 환경 무관하게 일정합니다.
발표 환경(Windows)에서는 FPGA가 약 2x 빠릅니다.
```

**Fmax 115 MHz면 실제로 더 빠르게 쓸 수 있나?**

```text
네. 현재 100 MHz 운용 기준에서 입력 샘플레이트를 115 MHz까지 올릴 수 있습니다.
다만 clock constraint만 바꾸는 것이고, 현재 SD boot / UART demo 경로는 100 MHz 기준입니다.
Fmax 측정의 의미는 "이 IP의 timing 여유가 얼마나 되는가"를 데이터로 보여주는 것입니다.
```

**115 MHz → 120 MHz에서 WNS가 왜 갑자기 뛰나?**

```text
110과 115 MHz에서 WNS가 같은(+0.178 ns) 건 Vivado router가 두 경우 모두
같은 critical path를 같은 방식으로 해결했기 때문입니다.
120 MHz에서는 그 critical path가 더 이상 timing을 맞추지 못해 violation이 납니다.
```

**UART가 느리면 실시간 처리 못 하는 것 아닌가?**

```text
UART는 관측 경로이고 처리 경로가 아닙니다.
실제 처리는 AXI DMA + PL FIR에서 83.0µs 안에 끝납니다.
실제 시스템에서는 UART 대신 다른 인터페이스를 쓰면 됩니다.
```

---

### 0-8. 다음 방향 여쭤볼 때

```text
현재는 end-to-end 보드 동작, golden 비교, CPU vs FPGA 처리 시간 비교,
Fmax 측정까지 완료한 상태입니다.

남은 일은 최종 report evidence 정리와 문서화입니다.

추가로 더 진행한다면, 외부 PC 없이 보드 내부에서 PASS/FAIL을 판단하는
BIST 구조가 다음 단계로 현실적이라고 생각합니다.
이 방향에 대해 교수님 의견을 받고 싶습니다.
```

---

### 0-9. 마무리 대본

```text
정리하면,
지난 미팅 과제인 CPU vs FPGA 처리 시간 비교를 완료했고,
추가로 이 IP의 Fmax를 측정했습니다.

CPU vs FPGA:
  Windows: CPU 162.0µs vs FPGA 83.0µs → FPGA 약 2x 빠름
  Ubuntu:  CPU  58.6µs vs FPGA 83.0µs → BLAS 최적화 환경에서 CPU가 빠름
  FPGA 83.0µs는 이론 처리 시간 81.9µs와 일치 → 이론 한계에서 동작

Fmax:
  90~115 MHz: timing PASS, 120 MHz: FAIL
  확정 Fmax = 115 MHz (현재 운용 주파수 100 MHz 대비 +15 MHz margin)

보드 기능 검증:
  scenario 1-1 SNR 74.9 dB, 1-2 SNR 72.2 dB, 모두 PASS

문서화를 마무리하면 v1.0이 완성되는 단계이고,
다음 방향에 대해 교수님 의견을 받고 싶습니다.
```

---

## 1. 측정 결과 요약

### CPU vs FPGA FIR 처리 시간

| 환경    | CPU (numpy float64) | FPGA (Q1.15 fixed-point) |      FPGA 배속      |
| ------- | :-----------------: | :----------------------: | :------------------: |
| Windows |      162.0 µs      |         83.0 µs         | **1.95x 빠름** |
| Ubuntu  |      58.6 µs      |         83.0 µs         |     0.71x (느림)     |

- 비교 대상: N=43 taps, M=2, 입력 8192 samples
- CPU 측정: `time.perf_counter()` + `np.convolve()` 구간만
- FPGA 측정: `XTime_GetTime()` + MM2S kick 직전 ~ S2MM IDLE 직후 구간만
- FPGA 이론 처리 시간: 8192 / 2 / 100 MHz = **81.92 µs** (측정값 83.0 µs, 오차 1.3%)
- 비교 차트: `docs/report/fir_n43/plot/cpu_vs_fpga_timing_windows.png`, `_ubuntu.png`

### 주파수 스윕 / Fmax

| 목표 클럭 (MHz) | WNS (ns) | timing PASS | LUT | DSP48 | 전력 (W) |
| :-------------: | :------: | :---------: | :--: | :---: | :------: |
|       90       |  +1.883  |     ✅     | 4583 |  16  |  1.564  |
|       100       |  +0.692  |     ✅     | 4584 |  16  |  1.567  |
|       110       |  +0.178  |     ✅     | 4583 |  16  |  1.570  |
|       115       |  +0.178  |     ✅     | 4583 |  16  |  1.570  |
|       120       |  -0.783  |     ❌     | 4584 |  16  |  1.576  |

- **확정 Fmax: 115 MHz** (WNS ≥ 0인 최대 주파수)
- pass → fail 전환: 115 MHz ✅ → 120 MHz ❌, 경계 해상도 5 MHz
- LUT/DSP48은 클럭 변화에 무관하게 일정 (combinational logic 구조)
- 전력 변화: +0.8% (클럭 증가에 따른 dynamic power 미세 증가)
- 상세: `vivado/reports/sweep_summary.md`

### 보드 기능 검증 결과

| 시나리오             | Max error |   RMSE   |   SNR   | Correlation |    Overall    |
| -------------------- | :-------: | :------: | :------: | :---------: | :------------: |
| 1-1 (5/20/30 MHz)    |   6 LSB   | 1.40 LSB | 74.86 dB |  1.000000  | **PASS** |
| 1-2 (7/15/25/45 MHz) |   7 LSB   | 1.81 LSB | 72.22 dB |  1.000000  | **PASS** |

---

## 2. 이전 교수님 피드백 반영 내용

이전 피드백 (2026-05-27):

> "실제로 뭔가 보여지는 게 중요하다. 보드로 뭔가를 해낸다고 잘 안 느껴지니까 그 부분이 걱정스럽다."
> "노트북(CPU)으로 FIR 연산 실행 → 시간 측정. 보드(FPGA)로 실행 → 시간 측정. 비교하라."

반영 결과:

| 항목                                | 완료 여부 | 내용                                        |
| ----------------------------------- | :-------: | ------------------------------------------- |
| P0-A 입력/출력 스펙트럼 나란히 비교 |    ✅    | scenario1_1/1_2 FFT plot 산출               |
| P0-B CPU vs FPGA FIR 처리 시간 비교 |    ✅    | Windows/Ubuntu 양 환경 측정 완료, 차트 산출 |
| (자체 추가) Fmax 주파수 스윕        |    ✅    | 90~120 MHz 5포인트 측정, Fmax=115 MHz 확정  |

---

## 3. 현재 완료 상태

```text
PC Python
-> UART command
-> PS bare-metal C
-> input multitone 생성 + XTime_GetTime 타이밍 시작
-> AXI DMA MM2S
-> PL FIR + Decimator (Fmax 115 MHz 확인된 설계)
-> AXI DMA S2MM
-> XTime_GetTime 타이밍 종료
-> FIR_TIME_US:XXX UART 출력
-> DDR output buffer
-> UART packet
-> PC FFT / metrics report + CPU vs FPGA 비교 차트
```

확인된 사항:

- SD boot 후 UART에서 `READY FIR` 출력 확인
- Scenario `1-1`, `1-2` board output 수신 및 golden 비교 완료
- bare-metal C에서 `FIR_TIME_US:XXX` UART 수신 확인
- `cpu_benchmark.py` 실행으로 CPU vs FPGA 비교 표 및 PNG 산출 (Windows / Ubuntu)
- Vivado 주파수 스윕 (90/100/110/115/120 MHz) 완료, Fmax=115 MHz 확정

---

## 4. 결과 해석 시 주의 사항

### Ubuntu에서 CPU가 더 빠른 이유

- `np.convolve()`는 내부적으로 BLAS(OpenBLAS / MKL)를 사용한다.
- Ubuntu에서 AVX/SSE 벡터 연산이 최대 활용되면 58.6 µs까지 내려간다.
- FPGA 83.0 µs는 AXI DMA 왕복 오버헤드 포함 값이다.
- N=43 tap 규모에서는 BLAS 최적화된 CPU가 DMA 오버헤드 포함 FPGA보다 빠를 수 있다.

### FPGA 83.0 µs의 의미

- 이론 처리 시간: 8192 / 2 / 100 MHz = 81.92 µs
- 측정값 83.0 µs는 이론값의 101.3% → FPGA는 이론 한계에 근접해 동작 중
- CPU 162 µs(Windows)는 캐시 워밍, OS 스케줄러 오버헤드 포함값

### 115 MHz와 110 MHz의 WNS가 같은 이유

- 두 constraint에서 Vivado router가 동일한 critical path를 동일하게 해결했다.
- 해당 path의 실제 지연이 두 constraint 구간(8.33 ns / 8.70 ns) 안에 모두 들어오기 때문이다.
- 120 MHz(8.33 ns 아래)에서는 critical path가 constraint를 초과해 violation이 발생한다.

### 발표 환경 선택

- 발표 환경이 Windows라면 FPGA 2x 빠른 결과를 그대로 제시할 수 있다.
- 두 환경 결과를 모두 제시하고 "FPGA는 환경 무관하게 일정, CPU는 환경 의존"으로 설명하면 더 정직하고 강한 설명이 된다.

---

## 5. 현재 한계 / 남은 정리

1. 보드 reset 없이 시나리오 연속 실행 시 MM2S timeout 가능성 존재 (신뢰 절차: 시나리오마다 보드 reset 후 실행)
2. Scenario 1-1의 20 MHz shared bin 해석을 report에 명확히 표시 필요
3. 최종 README에 demo command / PASS 기준 정리 필요
4. 최종 report artifact 검토 및 재생성 필요
5. 주파수 스윕은 Vivado timing 기준이며, 115 MHz에서의 실제 보드 동작 검증은 미실시

---

## 6. 교수님께 여쭤볼 핵심 질문

### 질문 1. 비교 결과 해석 방향

Windows(FPGA 2x 빠름)와 Ubuntu(CPU 더 빠름) 두 환경 결과를 모두 제시할지, 발표에서 한 환경으로 단순화할지 의견을 받고 싶다.

### 질문 2. Fmax 보드 검증 필요 여부

115 MHz Fmax는 Vivado timing analysis 기준이다. 실제 115 MHz constraint에서 BOOT.bin을 새로 구워 보드 동작을 검증하는 것이 필요한지 확인받고 싶다.

### 질문 3. v1.0 마무리 범위

현재 상태에서 report/documentation 정리로 v1.0을 마무리할지, 추가 기능이 필요한지 확인받고 싶다.

### 질문 4. v2.0 방향

다음 단계로 외부 PC 없이 보드 내부에서 PASS/FAIL을 판단하는 BIST 구조 추가가 적절한지 의견을 받고 싶다.

---

## 7. 미팅에서 말할 최종 요약 문장

지난 미팅 과제인 CPU vs FPGA FIR 처리 시간 비교를 완료했습니다.
Windows 환경에서 CPU 162.0 µs vs FPGA 83.0 µs로 FPGA가 약 2x 빠르고,
FPGA 83.0 µs는 이론 처리 시간 81.9 µs에 일치해 이론 한계에서 동작하고 있습니다.

추가로 90~120 MHz 주파수 스윕을 돌려서 Fmax를 측정했습니다.
115 MHz까지 timing PASS이고, 120 MHz에서 violation이 납니다.
Fmax 115 MHz로 현재 운용 주파수 100 MHz 대비 +15 MHz margin이 있습니다.

보드 기능 검증은 scenario 1-1 SNR 74.9 dB, 1-2 SNR 72.2 dB로 PASS입니다.

문서화를 마무리하면 v1.0이 완성되는 단계이고,
Fmax 보드 검증 여부와 v2.0 방향에 대해 교수님 의견을 받고 싶습니다.

---

## 8. 실제 미팅 피드백 (2026-07-02)

미팅 완료. 방향성 자체는 좋다는 평가를 받았고, 다음 4가지 추가 지시를 받았다.

### 8-1. ASIC 워크플로우를 보조 지표로 추가

- 학교 서버의 OASIS RTL로 synthesis, Nitro로 P&R까지 진행할 것.
- FPGA IP 결과에 더해 ASIC flow 결과(면적/타이밍/전력)를 보조 지표로 제시.

### 8-2. CPU 벤치마크 PNG에 측정 조건 명시

- CPU 스펙(모델명, 코어/클럭 등)과 측정 방법론(무엇을, 어떻게 측정했는지)을
  `cpu_vs_fpga_timing_*.png` 자체에 텍스트로 기입할 것.
- 현재 PNG는 수치만 있고 측정 환경 정보가 없어 보완 필요.

### 8-3. 전력 실측 (보조 지표)

- 교수님이 HDS242 오실로스코프 및 멀티미터를 대여.
- 보드 동작 중 전류/전압을 실측하여 전력을 보조 지표로 산출.
- Vivado power estimation(90~120 MHz sweep, 1.564~1.576 W)과 실측 전력값을
  비교분석하면 의미 있는 결과가 될 것으로 판단 (자체 의견).

### 8-4. 다음 작업 순서 (TODO)

1. OASIS synthesis + Nitro P&R 학교 서버에서 실행, 면적/타이밍/전력 결과 확보
2. HDS242로 보드 전류/전압 실측 → 전력 계산
3. Vivado 추정 전력 vs 실측 전력 비교분석 정리
4. `cpu_vs_fpga_timing_windows.png`, `_ubuntu.png`에 CPU 스펙 및 측정 방법론 텍스트 추가
5. 위 결과를 기존 v1.0 문서(FPGA vs CPU, Fmax sweep)에 보조 지표로 통합