# FIR Decimation 프로젝트 워크플로우 v11

- 작성일: 2026-05-07
- 이전 버전: `workflow_v10.md`
- 변경 배경: Step 5~6 완료, Step 7/8 코드 완성 — 보드 연결 후 실보드 검증 절차 정리

---

## 1. v10 대비 변경 사항

| 항목                   | v10     | v11                                         |
| ---------------------- | ------- | ------------------------------------------- |
| Step 5 AXI-Stream 래퍼 | 구현 중 | ✅ 완료                                     |
| Step 6 PS-PL DMA 연동  | 미진행  | ✅ 비트스트림·XSA 생성 완료 (WNS=+1.239ns) |
| Step 7 bare-metal C    | 미진행  | ✅ 코드 완성, 보드 검증 대기                |
| Step 8 PC Python FFT   | 미진행  | ✅ 코드 완성, 보드 검증 대기                |
| 현재 블로커            | —      | 보드(Zybo Z7-20) 물리 연결 필요             |

---

## 2. 현재 상태 요약

**보드가 없으면 더 이상 진행할 수 없는 단계에 진입했다.**

소프트웨어·하드웨어 구현은 모두 완료:

| 항목                        | 경로                                                                                      | 상태              |
| --------------------------- | ----------------------------------------------------------------------------------------- | ----------------- |
| RTL (FIR + AXI-Stream 래퍼) | `rtl/transposed_form/n43/`                                                              | ✅ iverilog PASS  |
| Vivado 비트스트림           | `build/vivado/fir_decimator_trans_n43.runs/impl_1/bd_fir_dma_wrapper.bit` (중간 산출물) | ✅ WNS=+1.239ns   |
| XSA (BSP 소스)              | `build/output/bd_fir_dma_wrapper.xsa`                                                   | ✅ 생성 완료      |
| 펌웨어 C 소스               | `sw/fir_decimator_demo.c`                                                               | ✅ 구현 완료      |
| Vitis 빌드 스크립트         | `vitis/build_fir_decimator_demo.tcl`                                                    | ✅ 경로 수정 완료 |
| PC Python 스크립트          | `sw/fir_decimator_demo.py`                                                              | ✅ 구현 완료      |

---

## 3. 보드 연결 시 진행 순서

### 준비물

| 항목                         | 비고                                                 |
| ---------------------------- | ---------------------------------------------------- |
| Zybo Z7-20 보드              | JP5 점퍼: JTAG 위치 확인                             |
| USB 케이블 1개               | JTAG + UART 겸용 (Digilent USB-UART 브릿지)          |
| Vivado 2024.2 설치된 PC      | `vivado`, `xsct` PATH 필요 (아래 환경 설정 참고) |
| minicom 또는 Python pyserial | UART 수신용                                          |

**환경 설정 (빌드 전 매번, 터미널 세션당 1회)**

```bash
# Linux — 터미널 열 때마다 실행
source <Vivado 설치경로>/settings64.sh
# 예: source ~/Xilinx/Vivado/2024.2/settings64.sh

# Windows — 시작 메뉴 → "Vivado 2024.2 Tcl Shell" 사용
```

---

### Step 7-A: Vitis 빌드 (ELF 생성)

```bash
# build/vitis/ 초기화 후 실행 (재빌드 시에도 동일)
rm -rf build/vitis
vitis -s vitis/build_fir_decimator_demo.py
```

성공 시 ELF 경로:

```
build/output/fir_decimator_demo.elf
```

**완료 기준:** `build/output/fir_decimator_demo.elf` 파일 존재 확인

> 빌드 트러블슈팅 상세 기록 → `docs/log/23_vitis_embedded_build_troubleshooting.md`

---

### Step 7-B: 보드에 비트스트림 + ELF 다운로드

USB 케이블 연결 후 `xsdb`로 FPGA 프로그래밍 및 ELF 다운로드.

```bash
xsdb << 'EOF'
connect
targets -set -filter {name =~ "APU*"}
fpga build/vivado/fir_decimator_trans_n43.runs/impl_1/bd_fir_dma_wrapper.bit
targets -set -filter {name =~ "*A9*#0"}
rst -processor
dow build/output/fir_decimator_demo.elf
con
EOF
```

**DONE LED 점등 확인** — 비트스트림이 FPGA에 올라갔음을 의미.

> `xsdb`는 `/home/young/Xilinx/Vitis/2024.2/bin/xsdb` (PATH에 등록되어 있음)

---

### Step 7-C: UART 동작 확인

**1. UART 포트 확인**

```bash
ls /dev/ttyUSB*
# 보통 /dev/ttyUSB1 (ttyUSB0은 JTAG)
```

**2. minicom 접속**

```bash
minicom -D /dev/ttyUSB1 -b 115200
```

접속 후 아무 출력이 없으면 정상 (명령 대기 상태).

**3. 시나리오 1-1 명령 전송 (happy case)**

```
3 5000000 20000000 30000000
```

보드가 응답하면 minicom에 binary 데이터가 깨진 문자로 표시됨 → 정상. 내용은 Step 8에서 Python으로 파싱.

**완료 기준:** minicom에서 명령 입력 후 binary 응답 수신 확인

---

### Step 8: PC Python FFT 시각화

**Step 7-C UART 동작 확인 후 진행.**

**시나리오 0 — 보드 없이 동작 확인 (사전 검증용)**

```bash
python sw/fir_decimator_demo.py --mode 0
```

PC 로컬에서 naive downsample vs FIR decimation 비교 그래프 표시.
45MHz → 5MHz 앨리어싱이 왼쪽 패널에 보이면 정상.

**시나리오 1-1 — 실보드 happy case**

```bash
python sw/fir_decimator_demo.py --mode 1-1 --port /dev/ttyUSB1
```

기대 결과:

- 좌 패널(입력 FFT): 5MHz / 20MHz / 30MHz 피크 3개
- 우 패널(출력 FFT): 5MHz만 남고 30MHz는 ≥60dB 감쇠

**시나리오 1-2 — 경계값 확인**

```bash
python sw/fir_decimator_demo.py --mode 1-2 --port /dev/ttyUSB1
```

기대 결과:

- 7MHz 유지, 15MHz 리플 범위 내 통과, 25/45MHz ≥60dB 감쇠

**완료 기준:**

- [ ] 30MHz 피크가 출력 FFT에서 ≥60dB 감쇠로 시각적 확인
- [ ] 5MHz 피크가 출력 FFT에 유지

---

## 4. 단계별 완료 기준 요약

| 단계            | 확인 항목          | 방법           |
| --------------- | ------------------ | -------------- |
| Step 7-A        | ELF 생성           | 파일 존재 확인 |
| Step 7-B        | DONE LED 점등      | 육안 확인      |
| Step 7-C        | binary 응답 수신   | minicom        |
| Step 8 mode 0   | 앨리어싱 피크 표시 | Python 그래프  |
| Step 8 mode 1-1 | 30MHz ≥60dB 감쇠  | Python 그래프  |
| Step 8 mode 1-2 | 경계 주파수 동작   | Python 그래프  |

---

## 5. 자주 발생하는 문제

| 증상                               | 원인              | 조치                                                    |
| ---------------------------------- | ----------------- | ------------------------------------------------------- |
| minicom 응답 없음                  | baud rate 불일치  | C 코드 `UART_BAUD_RATE`와 minicom `-b` 값 일치 확인 |
| minicom 응답 없음                  | 비트스트림 미적재 | DONE LED 점등 여부 확인                                 |
| minicom 응답 없음                  | 포트 번호 오류    | `/dev/ttyUSB0` vs `/dev/ttyUSB1` 확인               |
| Python magic 오류                  | UART 노이즈       | `uart_recv_result`의 1바이트씩 스캔 로직 동작 확인    |
| Vitis 빌드 오류: `sinf` undefined  | `-lm` 누락        | `app.set_app_config(key="USER_LINK_LIBRARIES", values=["m"])` 확인 |
| Vitis 빌드 오류: 파일 없음          | 경로 버그 재발    | `vitis/build_fir_decimator_demo.py` 의 `SRC` 경로 확인 |
| `xuartps.h` not found              | BD에서 UART1 비활성 | `bd_fir_dma.tcl` UART 설정 확인 후 Vivado 재빌드 |
| `XPAR_XUARTPS_1_DEVICE_ID` 미선언  | 신 BSP는 단일 UART → index 0 | `fir_decimator_demo.c` 의 `UART_DEVICE_ID` 를 `0` 으로 수정 |
| Lopper 오류 또는 미설치             | Vitis Embedded Development 미설치 또는 pip 설치 실패 | 로그 23 참고 |

---

## 6. 마일스톤 현황

| 마일스톤                   | 목표 시점        | 내용                                              | 상태              |
| -------------------------- | ---------------- | ------------------------------------------------- | ----------------- |
| M1                         | 5월 1주차        | RTL 검증 환경 구축                                | ✅ 완료           |
| M2                         | 5월 3주차        | N=43 Transposed Form RTL + iverilog PASS          | ✅ 완료           |
| M3                         | 6월 1주차        | Vivado 100MHz 타이밍 클로저                       | ✅ 완료           |
| **M4 (안전 마감선)** | **6월 말** | **AXI-Stream 래퍼 + PS-PL DMA + 보드 시연** | 🔄 보드 검증 대기 |
| M5                         | 7월 2주차        | 실시간 시연 파이프라인 완성                       |                   |
| M6                         | 7월 말           | 발표 준비 + 보고서 완성                           |                   |

**M4 판단 기준:** Step 8 mode 1-1 정상 동작 확인 시 M4 완성 → Plan A 계속.
미완성 시 mode 0 (보드 불필요) 결과물로 Plan B 제출.
