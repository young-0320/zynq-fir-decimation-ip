# 22. PC Python FFT 시각화 스크립트 설계

- 작성일: 2026-05-06
- 단계: Step 8
- 목적: `sw/fir_decimator_demo.py` 구현 전 설계 사항 정리
- 선행 문서: `docs/log/21_vitis_build_and_uart_usage.md`

---

## 1. 파일 위치

```
sw/
  fir_decimator_demo.c    ← PS(ARM) 펌웨어 (ps/에서 이동)
  fir_decimator_demo.py   ← PC Python 스크립트 (이 문서)
```

`ps/`와 `pc/` 두 폴더로 나누지 않고 `sw/`로 통합한 이유: 파일이 하나씩밖에 없어 폴더 두 개로 나누는 것이 오버헤드. C와 Python은 각각 보드 PS와 PC에서 실행되는 대칭적인 역할이므로 같은 층위에 두는 것이 적합.

---

## 2. 역할

PC에서 실행되는 데모 애플리케이션. 전체 동작:

```
① 사용자(또는 청중)가 주파수 입력
        ↓
② Python: 입력 신호 로컬 생성 → 입력 FFT 즉시 표시
        ↓ UART 전송 ("n f1 f2...\n")
③ PS(C): 신호 생성 → DMA → FIR IP → 결과 전송
        ↓ UART 수신 (binary 패킷)
④ Python: 결과 수신 → 출력 FFT 표시
```

---

## 3. 설정 상수

```python
N_IN    = 8192          # 입력 샘플 수
N_OUT   = 4096          # 출력 샘플 수 (M=2 데시메이션)
FS_HZ   = 100e6         # 입력 샘플링 주파수 (100MHz)
MAGIC   = 0xDEADBEEF    # UART 패킷 동기화 마커
```

---

## 4. FIR 계수

RTL(`rtl/transposed_form/n43/fir_n43.v`)과 동일한 N=43 계수를 하드코딩.
Q15 정수값을 32768로 나눠 float으로 변환:

```python
FIR_COEFFS = np.array([
    10, 0, -33, -32, 47, 107, 0, -197, -159, 206,
    425, 0, -674, -522, 654, 1336, 0, -2258, -1939, 2995,
    9864, 13109, 9864, 2995, -1939, -2258, 0, 1336, 654, -522,
    -674, 0, 425, 206, -159, -197, 0, 107, 47, -32,
    -33, 0, 10
]) / 32768.0
```

RTL과 동일한 계수를 쓰는 이유: scenario 0에서 PC 시뮬레이션 결과가 실제 하드웨어 결과와 동일한 필터 특성을 갖도록 하기 위함.

---

## 5. CLI 인터페이스

```bash
python sw/fir_decimator_demo.py --mode 0
python sw/fir_decimator_demo.py --mode 1-1 --port /dev/ttyUSB1
python sw/fir_decimator_demo.py --mode 1-2 --port /dev/ttyUSB1
python sw/fir_decimator_demo.py --mode 2   --port /dev/ttyUSB1 --baud 115200
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--mode` | (필수) | 0 / 1-1 / 1-2 / 2 |
| `--port` | `/dev/ttyUSB1` | UART 포트 (mode 1/2에서만 사용) |
| `--baud` | `115200` | baud rate, 변경 가능 |

baud rate를 115200으로 기본 설정한 이유: ~710ms 전송 지연이 데모에서 오히려 유리. 결과가 너무 즉각적으로 나타나면 청중이 보드에서 실제 처리가 일어나는 것인지 인식하기 어려움.

---

## 6. 시각화

### 레이아웃

노트북 화면을 좌우로 분할:

```
┌─────────────────┬─────────────────┐
│   입력 신호 FFT  │   출력 신호 FFT  │
│   (로컬 생성)    │   (보드 수신)    │
└─────────────────┴─────────────────┘
```

`plt.subplots(1, 2)` + `plt.ion()` — 창을 닫지 않고 같은 창에서 갱신.

### FFT 표시 규격

| 항목 | 값 |
|------|----|
| y축 | dB (60dB 감쇠를 눈으로 확인하기 위해) |
| x축 범위 | 0~50MHz (입출력 동일) |

x축을 동일하게 맞추는 이유: 입력의 30MHz 피크가 출력에서 사라지는 것을 같은 좌표에서 직접 비교 가능.

출력 신호는 M=2 데시메이션으로 유효 Fs=50MHz → 나이퀴스트 25MHz. 따라서 출력 패널에서 25MHz 이상은 데이터가 없으나 x축은 동일하게 0~50MHz로 표시.

---

## 7. 함수 구조

시나리오별로 함수를 분리해 각자 독립적인 창을 띄운다.

```
fir_decimator_demo.py
│
├── [상수]
│     N_IN, N_OUT, FS_HZ, MAGIC, FIR_COEFFS
│
├── gen_multitone(freqs)
│     C 코드와 동일한 공식으로 입력 신호 생성 (FFT 표시용)
│     amplitude = 0.9 / n_tones, Q1.15 클리핑 없이 float 반환
│
├── uart_send_cmd(ser, freqs)
│     "n f1 f2 ...\n" 포맷으로 전송
│
├── uart_recv_result(ser)
│     magic(0xDEADBEEF) 찾을 때까지 1바이트씩 스캔
│     → n_samples 읽기 → int16 × n_samples 수신
│     ser.timeout=5 설정 — 5초 내 응답 없으면 에러 출력
│
├── plot_fft_pair(ax_l, ax_r, sig_l, sig_r, title_l, title_r)
│     두 신호 FFT 계산 → dB 변환 → 좌우 패널 갱신
│     dB 기준: 입력 최대 피크 = 0dB (상대적 감쇠량이 직접 보임)
│
├── run_scenario0()
│     보드 불필요. 고정 신호: 1-2 주파수 (7/15/25/45MHz)
│     gen_multitone → (좌) 나이브 다운샘플 / (우) FIR_COEFFS convolve+decimate
│     45MHz → 5MHz 앨리어싱이 좌패널에 유령 피크로 나타남
│
├── run_scenario1(freqs, ser)
│     gen_multitone → uart_send_cmd → uart_recv_result → plot_fft_pair
│     좌: 입력 FFT / 우: 출력 FFT
│
├── run_interactive(ser)
│     루프: 주파수 입력(input()) → run_scenario1 → plt.ion()으로 같은 창 갱신
│
└── main()
      argparse 파싱 → 모드별 분기
```

---

## 8. 의존성

```
pyserial   UART 통신
numpy      FFT, 신호 생성, 계수 연산
matplotlib 시각화
```

---

## 9. 데시메이션과 FFT 주파수 범위

FFT는 시간 영역 신호를 주파수 영역으로 변환하는 알고리즘(Fast Fourier Transform).

주파수 범위 결정:

```
입력 Fs = 100MHz
  → 나이퀴스트: 샘플링 주파수의 절반까지만 표현 가능
  → 입력 FFT 범위: 0~50MHz

M=2 데시메이션: 2샘플 중 1샘플 취함 → 출력 Fs = 50MHz
  → 나이퀴스트 재적용
  → 출력 FFT 범위: 0~25MHz
```

두 번의 ÷2가 모두 나이퀴스트에서 오는 것처럼 보이지만 다른 이유:
- 첫 번째: 100MHz 샘플링으로 표현 가능한 최대 주파수 = 50MHz
- 두 번째: 데시메이션으로 샘플링 주파수 자체가 50MHz로 감소 → 그 절반 = 25MHz
