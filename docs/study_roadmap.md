# 프로젝트 완수를 위한 학습 로드맵

단계별로 필요한 시점에만 학습. 앞 단계 지식을 미리 쌓을 필요 없음.

---

## Step 5 — AXI-Stream 래퍼 (지금)

### AXI-Stream 프로토콜 (TVALID / TREADY / TDATA)

| 자료 | 링크 | 핵심 내용 |
|------|------|-----------|
| ZipCPU — Learning AXI: Where to start? | https://zipcpu.com/blog/2022/05/07/learning-axi.html | 입문 가이드, 읽는 순서 안내 |
| ZipCPU — AXI Handshaking Rules | https://zipcpu.com/blog/2021/08/28/axi-rules.html | TVALID/TREADY 악수 규칙 6개, 핵심 |

| ZipCPU — AXI Stream is broken | https://zipcpu.com/blog/2022/02/23/axis-abort.html | FIFO + 백프레셔 패턴 실습 |

**최소 학습량:** 위 세 글 순서대로 읽으면 래퍼 구현 가능.

**추가 학습**
| ZipCPU — skidbuffe | https://zipcpu.com/blog/2019/05/22/skidbuffer.html | 데이터 처리량을 위해서 필요. 지금은 오버엔지니어링일 수 있음 |
---

## Step 6 — Vivado Block Design + PS-PL DMA 연동

### Vivado IP Integrator (Block Design)

| 자료 | 링크 | 핵심 내용 |
|------|------|-----------|
| Xilinx UG994 | xilinx.com 검색: "UG994" | Vivado IP Integrator 공식 가이드 |
| Digilent Zybo Z7 튜토리얼 | digilent.com/reference/programmable-logic/zybo-z7 | 보드 기준 Block Design 예제 |

### AXI DMA IP

| 자료 | 링크 | 핵심 내용 |
|------|------|-----------|
| Xilinx PG021 | xilinx.com 검색: "PG021" | AXI DMA 동작 원리, 레지스터, 설정법 전부 |

### Zynq PS-PL 연결 구조 (HP 포트, 클럭, AXI Interconnect)

| 자료 | 링크 | 핵심 내용 |
|------|------|-----------|
| Xilinx UG585 | xilinx.com 검색: "UG585" | Zynq-7000 TRM, PS-PL 인터페이스 챕터 참고 |

---

## Step 7 — bare-metal C + UART

### Vitis / Xilinx SDK 환경

| 자료 | 링크 | 핵심 내용 |
|------|------|-----------|
| Xilinx UG1400 | xilinx.com 검색: "UG1400" | Vitis 환경 세팅, 프로젝트 생성 |
| Vitis 설치 내 예제 | `{Vitis 설치경로}/data/embeddedsw/XilinxProcessorIPLib/drivers/` | XAxiDma, XUartPs 드라이버 예제 |

### XAxiDma C 드라이버

| 자료 | 링크 | 핵심 내용 |
|------|------|-----------|
| PG021 드라이버 섹션 | 위 PG021 동일 문서 | API 함수 목록, 초기화 순서 |
| Xilinx GitHub 예제 | github.com/Xilinx/embeddedsw — `XilinxProcessorIPLib/drivers/axidma` | 실제 C 코드 예제 |

---

## Step 8 — PC Python FFT 시각화

### Python 라이브러리

| 자료 | 핵심 내용 |
|------|-----------|
| `pyserial` 공식 문서 | UART 수신: `serial.read()` |
| `numpy.fft.fft` | FFT 계산 |
| `matplotlib.pyplot` | 실시간 스펙트럼 플롯 |

이 단계는 이미 Python에 익숙하면 문서 안 읽어도 됨.

---

## 참고: 이미 완료된 사전 지식

- Verilog RTL 설계 (모듈, always 블록, 파이프라인)
- Q1.15 고정소수점 연산
- Kaiser window FIR 필터 이론
- Vivado 합성/구현, 타이밍 클로저
