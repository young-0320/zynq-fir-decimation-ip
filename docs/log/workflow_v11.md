# FIR Decimation 프로젝트 워크플로우 v11

- 작성일: 2026-05-07
- 이전 버전: `workflow_v10.md`
- 변경 배경: Step 5~6 완료, Step 7/8 코드 완성 — 보드 연결 후 실보드 검증 절차 정리

---

## 1. v10 대비 변경 사항

| 항목 | v10 | v11 |
| --- | --- | --- |
| Step 5 AXI-Stream 래퍼 | 구현 중 | ✅ 완료 |
| Step 6 PS-PL DMA 연동 | 미진행 | ✅ 비트스트림·XSA 생성 완료 (WNS=+1.239ns) |
| Step 7 bare-metal C | 미진행 | ✅ 코드 완성, 보드 검증 대기 |
| Step 8 PC Python FFT | 미진행 | ✅ 코드 완성, 보드 검증 대기 |
| 현재 블로커 | — | 보드(Zybo Z7-20) 물리 연결 필요 |

---

## 2. 현재 상태 요약

**보드가 없으면 더 이상 진행할 수 없는 단계에 진입했다.**

소프트웨어·하드웨어 구현은 모두 완료:

| 항목 | 경로 | 상태 |
| --- | --- | --- |
| RTL (FIR + AXI-Stream 래퍼) | `rtl/transposed_form/n43/` | ✅ iverilog PASS |
| Vivado 비트스트림 | `/mnt/workspace/.../bd_fir_dma_wrapper.bit` | ✅ WNS=+1.239ns |
| XSA (BSP 소스) | `/mnt/workspace/.../bd_fir_dma_wrapper.xsa` | ✅ 생성 완료 |
| 펌웨어 C 소스 | `sw/fir_decimator_demo.c` | ✅ 구현 완료 |
| Vitis 빌드 스크립트 | `vitis/build_fir_decimator_demo.tcl` | ✅ 경로 수정 완료 |
| PC Python 스크립트 | `sw/fir_decimator_demo.py` | ✅ 구현 완료 |

---

## 3. 보드 연결 시 진행 순서

### 준비물

| 항목 | 비고 |
| --- | --- |
| Zybo Z7-20 보드 | JP5 점퍼: JTAG 위치 확인 |
| USB 케이블 1개 | JTAG + UART 겸용 (Digilent USB-UART 브릿지) |
| Vivado / Vitis 2024.2 설치된 PC | `/mnt/workspace/` 빌드 산출물 유지 |
| minicom 또는 Python pyserial | UART 수신용 |

---

### Step 7-A: Vitis 빌드 (ELF 생성)

**방법 A — 자동 스크립트 (권장)**

```bash
# 프로젝트 루트에서 실행
xsct vitis/build_fir_decimator_demo.tcl
```

성공 시 ELF 경로:
```
/mnt/workspace/10_zynq-fir-decimation-ip_build/fir_decimator_demo/fir_decimator_demo/Debug/fir_decimator_demo.elf
```

**방법 B — Vitis GUI**

`docs/log/21_vitis_build_and_uart_usage.md` 섹션 2 참고.
요약: XSA 임포트 → 플랫폼 빌드 → 앱 생성 → `sw/fir_decimator_demo.c` 추가 → `-lm` 링크 플래그 추가 → 빌드.

**완료 기준:** `fir_decimator_demo.elf` 파일 생성 확인

---

### Step 7-B: 보드에 비트스트림 + ELF 다운로드

**Vitis GUI:**

```
Run → Run Configurations → Single Application Debug → New
  Bitstream: bd_fir_dma_wrapper.bit
  ELF:       fir_decimator_demo.elf
  → Run
```

**DONE LED 점등 확인** — 비트스트림이 FPGA에 올라갔음을 의미.

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

| 단계 | 확인 항목 | 방법 |
| --- | --- | --- |
| Step 7-A | ELF 생성 | 파일 존재 확인 |
| Step 7-B | DONE LED 점등 | 육안 확인 |
| Step 7-C | binary 응답 수신 | minicom |
| Step 8 mode 0 | 앨리어싱 피크 표시 | Python 그래프 |
| Step 8 mode 1-1 | 30MHz ≥60dB 감쇠 | Python 그래프 |
| Step 8 mode 1-2 | 경계 주파수 동작 | Python 그래프 |

---

## 5. 자주 발생하는 문제

| 증상 | 원인 | 조치 |
| --- | --- | --- |
| minicom 응답 없음 | baud rate 불일치 | C 코드 `UART_BAUD_RATE`와 minicom `-b` 값 일치 확인 |
| minicom 응답 없음 | 비트스트림 미적재 | DONE LED 점등 여부 확인 |
| minicom 응답 없음 | 포트 번호 오류 | `/dev/ttyUSB0` vs `/dev/ttyUSB1` 확인 |
| Python magic 오류 | UART 노이즈 | `uart_recv_result`의 1바이트씩 스캔 로직 동작 확인 |
| Vitis 빌드 오류: `sinf` undefined | `-lm` 누락 | linker flags에 `m` 추가 (로그 21 섹션 2-5 참고) |
| Vitis 빌드 오류: 파일 없음 | 경로 버그 재발 | `vitis/` 스크립트의 `sw/` 경로 확인 |

---

## 6. 마일스톤 현황

| 마일스톤 | 목표 시점 | 내용 | 상태 |
| --- | --- | --- | --- |
| M1 | 5월 1주차 | RTL 검증 환경 구축 | ✅ 완료 |
| M2 | 5월 3주차 | N=43 Transposed Form RTL + iverilog PASS | ✅ 완료 |
| M3 | 6월 1주차 | Vivado 100MHz 타이밍 클로저 | ✅ 완료 |
| **M4 (안전 마감선)** | **6월 말** | **AXI-Stream 래퍼 + PS-PL DMA + 보드 시연** | 🔄 보드 검증 대기 |
| M5 | 7월 2주차 | 실시간 시연 파이프라인 완성 | |
| M6 | 7월 말 | 발표 준비 + 보고서 완성 | |

**M4 판단 기준:** Step 8 mode 1-1 정상 동작 확인 시 M4 완성 → Plan A 계속.
미완성 시 mode 0 (보드 불필요) 결과물로 Plan B 제출.
