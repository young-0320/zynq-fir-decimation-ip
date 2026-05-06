# 21. Vitis 빌드 및 UART 사용법

- 작성일: 2026-05-06
- 단계: Step 7
- 목적: `sw/fir_decimator_demo.c` 빌드 절차 및 UART 테스트 방법 정리
- 선행 문서: `docs/log/20_baremetal_c_fir_dma.md`

---

## 1. 필요한 것

| 항목 | 내용 |
|---|---|
| Vitis 2024.2 | 빌드 도구 (Vivado와 함께 설치됨) |
| XSA 파일 | `/mnt/workspace/10_zynq-fir-decimation-ip_build/fir_decimator_trans_n43/bd_fir_dma_wrapper.xsa` |
| C 소스 | `sw/fir_decimator_demo.c` |
| Zybo Z7-20 보드 | USB 케이블 1개 (프로그래밍 + UART 겸용) |
| PC | Python 없이도 minicom으로 기본 동작 확인 가능 |

---

## 2. Vitis 프로젝트 생성

### 2-1. Vitis 실행

```bash
vitis &
```

워크스페이스 경로: `/mnt/workspace/10_zynq-fir-decimation-ip_vitis`

### 2-2. 플랫폼 생성 (XSA → BSP)

```
File → New → Platform Project
  Platform name: fir_dma_platform
  XSA: bd_fir_dma_wrapper.xsa 선택
  OS: standalone
  CPU: ps7_cortexa9_0
  → Finish
```

플랫폼 빌드:
```
Project Explorer에서 fir_dma_platform 우클릭 → Build Project
```

BSP가 생성되면서 `xparameters.h`, `xil_cache.h`, `xuartps.h` 등이 자동으로 만들어진다.

### 2-3. 애플리케이션 프로젝트 생성

```
File → New → Application Project
  Platform: fir_dma_platform 선택
  Application name: fir_decimator_demo
  Domain: standalone_ps7_cortexa9_0
  Template: Empty Application (C)
  → Finish
```

### 2-4. C 소스 파일 추가

```
Project Explorer → fir_decimator_demo → src 우클릭
  → Import Sources
  → sw/fir_decimator_demo.c 선택
```

또는 직접 복사:
```bash
cp /home/young/dev/10_zynq-fir-decimation-ip/sw/fir_decimator_demo.c \
   /mnt/workspace/10_zynq-fir-decimation-ip_vitis/fir_decimator_demo/src/
```

### 2-5. math 라이브러리 링크 설정

`sinf()`, `roundf()` 사용으로 `-lm` 플래그가 필요하다.

```
fir_decimator_demo 우클릭 → Properties
  → C/C++ Build → Settings
  → ARM v7 gcc linker → Libraries
  → Libraries(+) → m 추가
  → Apply and Close
```

### 2-6. 빌드

```
Project Explorer → fir_decimator_demo 우클릭 → Build Project
```

성공 시: `fir_decimator_demo/Debug/fir_decimator_demo.elf` 생성

---

## 3. 보드에 다운로드

### 3-1. 비트스트림 + ELF 동시 다운로드

```
Run → Run Configurations → Single Application Debug
  → New Configuration
  Bitstream: bd_fir_dma_wrapper.bit (Vivado 빌드 결과)
  ELF: fir_decimator_demo.elf
  → Run
```

또는 Vitis 상단 툴바 → Debug 버튼.

보드 PROG 스위치가 JTAG 모드인지 확인 (JP5 점퍼: JTAG 위치).

---

## 4. UART 연결

### 4-1. 포트 확인

```bash
ls /dev/ttyUSB*
# 예: /dev/ttyUSB1
```

### 4-2. minicom 접속

```bash
minicom -D /dev/ttyUSB1 -b 115200
```

접속 후 보드가 명령을 기다리는 상태 (아무 출력 없음 = 정상).

---

## 5. UART 프로토콜 사용법

### PC → PS 명령 형식

```
<톤개수> <주파수1(Hz)> <주파수2(Hz)> ... <주파수N(Hz)>
```

명령을 입력하고 Enter를 누르면 PS가 처리 후 binary 결과를 돌려준다.

### 시나리오 1-1 명령 (happy case)

```
3 5000000 20000000 30000000
```

- 3개 톤: 5MHz (통과), 20MHz (전이대역), 30MHz (차단)
- 진폭 자동 계산: 0.9 / 3 = 0.3

### 시나리오 1-2 명령 (edge case)

```
4 7000000 15000000 25000000 45000000
```

- 4개 톤: 7MHz (통과), 15MHz (fp 경계), 25MHz (fs 경계), 45MHz (차단)
- 진폭 자동 계산: 0.9 / 4 = 0.225

### 시나리오 2 — 임의 주파수

```
2 10000000 35000000
```

- 2개 톤: 10MHz (통과), 35MHz (차단)
- 진폭: 0.9 / 2 = 0.45

### 주의사항

| 항목 | 제한 |
|---|---|
| 최대 톤 개수 | 8개 |
| 주파수 범위 | 1MHz ~ 49MHz (Fs=100MHz 기준 Nyquist=50MHz 미만) |
| 50MHz 사용 불가 | sin(πn) = 0, 신호 없음 |

---

## 6. PS → PC 수신 패킷 구조

minicom에서는 binary 데이터가 깨진 문자로 보인다. 실제 데이터 확인은 Step 8 Python 코드로 파싱하거나 아래 Python 스니펫으로 빠르게 확인 가능하다.

```python
import serial
import struct
import numpy as np

ser = serial.Serial('/dev/ttyUSB1', baudrate=115200)

# 명령 전송
ser.write(b'3 5000000 20000000 30000000\n')

# magic 수신
magic = struct.unpack('<I', ser.read(4))[0]
assert magic == 0xDEADBEEF, f"sync error: {magic:#x}"

# 샘플 수 수신
n = struct.unpack('<I', ser.read(4))[0]

# 샘플 수신
data = np.frombuffer(ser.read(n * 2), dtype=np.int16)
print(f"수신 샘플 수: {len(data)}")
print(f"최대값: {data.max()}, 최소값: {data.min()}")
```

---

## 7. 테스트 가능 범위

| 항목 | 방법 | 보드 필요 |
|---|---|---|
| 컴파일 오류 확인 | Vitis 빌드 | 불필요 |
| UART 명령 파싱 | minicom에서 직접 타이핑 | 필요 |
| DMA 동작 | binary 수신 후 샘플 수 확인 | 필요 |
| 필터 동작 | Python FFT → 주파수 성분 확인 | 필요 |

호스트 Linux에서 소스만으로는 컴파일조차 불가능하다. `xil_cache.h`, `xuartps.h`, `xparameters.h`는 Vitis BSP가 생성하는 파일이기 때문이다.

---

## 8. 자주 발생하는 문제

### 명령을 보냈는데 응답이 없음

- baud rate 불일치 확인 (`UART_BAUD_RATE` 상수와 minicom `-b` 값이 같아야 함)
- 비트스트림이 보드에 올라갔는지 확인 (DONE LED 점등)
- UART 포트 번호 확인 (`/dev/ttyUSB0` vs `/dev/ttyUSB1`)

### magic 값이 틀림

- UART 노이즈 또는 수신 타이밍 오차
- Python 스크립트에서 magic을 찾을 때까지 1바이트씩 스캔하는 로직 추가 필요 (Step 8에서 처리)

### 빌드 오류: `sinf` undefined reference

- `-lm` 링크 플래그 추가 여부 확인 (2-5 참고)
