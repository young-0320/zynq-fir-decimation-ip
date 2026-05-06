# 20. Bare-metal C — fir_decimator_demo.c 설계

- 작성일: 2026-05-06
- 단계: Step 7
- 목적: `ps/fir_decimator_demo.c` 구현 전 설계 사항 정리
- 선행 문서: `docs/log/19_ps_pl_dma_integration_design.md`

---

## 1. 역할

`ps/fir_decimator_demo.c`는 Zynq PS(ARM Cortex-A9)에서 실행되는 bare-metal 애플리케이션이다.

**bare-metal**: OS 없이 ARM 위에서 C 코드가 하드웨어를 직접 제어하는 방식. Linux나 RTOS 없이 레지스터를 직접 읽고 쓴다. Vitis의 "standalone" 도메인이 이에 해당한다.

전체 동작은 다음 루프를 반복한다:

```
① PC(개인 노트북)가 UART로 주파수 명령 전송
        ↓
② PS(ARM): 명령 수신 → 멀티톤 신호 합성 → DDR 메모리 저장
        ↓
③ PS(ARM): DMA에게 명령 → DMA가 DDR의 신호를 FIR IP로 전달
        ↓
④ PL(FPGA): FIR 필터 + M=2 데시메이션 처리
        ↓
⑤ DMA: FIR 출력을 다시 DDR에 저장
        ↓
⑥ PS(ARM): DDR에서 결과 읽기 → UART로 PC에 전송
        ↓
⑦ PC(노트북): 결과 수신 → FFT 계산 → 그래프 표시
        ↓
     (다음 명령 대기, ①로 돌아감)
```

FIR 필터링과 데시메이션은 PL의 `fir_decimator_n43_axis` IP가 담당한다. C 코드는 신호를 준비하고 DMA를 통해 IP에 공급하며 결과를 수집해 PC에 돌려준다.

---

## 2. 파일 위치

```
ps/
└── fir_decimator_demo.c    ← 이 파일 (PS 소프트웨어 소스, repo에 보관)
```

Vitis 작업 시 이 파일을 Vitis 앱 프로젝트의 `src/`에 복사해 빌드한다. Vitis 워크스페이스 자체는 `/mnt/workspace/`에 두고 repo에 포함하지 않는다.

---

## 3. C 코드 내부 상세 구조

### 3-1. 전체 개요

```
fir_decimator_demo.c
│
├── [상수 정의]
│     DMA 주소, 레지스터 오프셋, 버퍼 크기, 프리셋 주파수
│
├── [전역 버퍼]
│     src_buf[8192]   ← 입력 신호 (ARM이 채움)
│     dst_buf[4096]   ← 출력 신호 (DMA가 채움)
│
├── gen_multitone()   ← 멀티톤 신호 합성
├── dma_run()         ← DMA 제어 (전송 + 대기)
├── uart_recv_cmd()   ← PC에서 주파수 명령 수신
├── uart_send_result()← PC로 결과 전송
└── main()            ← 전체 루프 조율
```

---

### 3-2. 상수 정의

```c
#define DMA_BASE    0x40400000   // Block Design에서 할당된 DMA 주소
#define N_IN        8192         // 입력 샘플 수
#define N_OUT       4096         // 출력 샘플 수 (N_IN / 2, M=2 데시메이션)
#define FS_HZ       100000000.0  // 샘플링 주파수 100MHz
#define MAGIC       0xDEADBEEF   // UART 패킷 시작 마커
```

---

### 3-3. 전역 버퍼

```c
static int16_t __attribute__((aligned(32))) src_buf[N_IN];
static int16_t __attribute__((aligned(32))) dst_buf[N_OUT];
```

**왜 전역인가**: bare-metal에서 스택 크기는 수 KB에 불과하다. 8192 × 2 = 16KB짜리 배열을 지역 변수로 선언하면 스택 오버플로가 발생한다. 전역으로 선언하면 BSS 영역(DDR)에 올라간다.

**왜 aligned(32)인가**: Cortex-A9 캐시 라인이 32 bytes다. 캐시 flush/invalidate 시 경계가 정렬되어 있어야 인접한 다른 데이터에 영향을 주지 않는다.

---

### 3-4. `uart_recv_cmd()` — PC에서 주파수 명령 수신

PC(Python)가 보내는 형식:

```
"3 5000000 20000000 30000000\n"
 ^  ↑                        ↑
 |  주파수(Hz), 공백 구분     개행 = 명령 끝
 톤 개수
```

C 코드가 할 일:

1. UART에서 `\n`이 올 때까지 문자를 버퍼에 쌓음
2. `sscanf`로 톤 개수와 주파수 목록 파싱
3. 파싱 결과를 배열로 반환

이 형식을 text로 선택한 이유: 주파수 몇 개 숫자를 보내는 용도라 데이터량이 적고, text는 minicom 등으로 직접 타이핑해서 테스트할 수 있어 디버깅이 편하다.

---

### 3-5. `gen_multitone()` — 멀티톤 신호 합성

```
입력: 주파수 목록(Hz), 톤 개수
출력: src_buf에 Q1.15 int16 샘플 8192개 채움
```

동작:

```
for n in 0..8191:
    x = 0
    for each tone freq f:
        x += amplitude × sin(2π × f/Fs × n)
    src_buf[n] = round(x × 32768)   // float → Q1.15 변환
```

**진폭 결정 규칙**: 합산 클리핑 방지를 위해 `amplitude = 0.9 / 톤개수` 자동 계산.

**Q1.15 변환**:

- Q1.15는 16비트 중 1비트 부호, 15비트 소수부
- float 1.0 → int16 32767
- float -1.0 → int16 -32768
- 변환식: `(int16_t)(x × 32768.0f + 0.5f)` (반올림)

---

### 3-6. `dma_run()` — DMA 제어

DMA는 레지스터에 값을 쓰는 것만으로 동작한다. CPU가 직접 데이터를 옮기지 않는다.

**실행 순서**:

```
① Xil_DCacheFlushRange(src_buf, N_IN×2)
     CPU 캐시 → DDR 반영. DMA가 캐시가 아닌 DDR을 읽어야 하므로.

② S2MM 채널 시작 (수신 준비)
     S2MM_DA      = dst_buf 주소
     S2MM_LENGTH  = N_OUT × 2
     S2MM_DMACR   = 0x1 (RS 비트 세트 → 수신 대기 시작)

③ MM2S 채널 시작 (전송 시작)
     MM2S_SA      = src_buf 주소
     MM2S_LENGTH  = N_IN × 2
     MM2S_DMACR   = 0x1 (RS 비트 세트 → 전송 시작)
     → 이 순간 DMA가 DDR에서 데이터를 읽어 FIR IP로 보내기 시작

④ MM2S 완료 대기: MM2S_DMASR bit1(Idle) = 1이 될 때까지 폴링
⑤ S2MM 완료 대기: S2MM_DMASR bit1(Idle) = 1이 될 때까지 폴링

⑥ Xil_DCacheInvalidateRange(dst_buf, N_OUT×2)
     DMA가 DDR에 쓴 결과를 캐시에서 버림. CPU가 다음에 dst_buf를 읽을 때
     캐시가 아닌 DDR에서 직접 가져오도록.
```

**왜 S2MM를 MM2S보다 먼저 시작하는가**:
FIR IP는 MM2S가 데이터를 보내기 시작하면 즉시 처리해서 출력을 내보낸다. S2MM이 준비되지 않은 상태에서 FIR 출력이 도착하면 데이터가 버려진다. S2MM을 먼저 열어놓고 MM2S를 시작해야 FIR 출력을 한 샘플도 놓치지 않는다.

---

### 3-7. `uart_send_result()` — PC로 결과 전송

PC(Python)가 수신하는 binary 패킷:

```
오프셋   크기    내용
0        4 bytes  magic = 0xDEADBEEF   (패킷 시작 마커)
4        4 bytes  n_samples = 4096     (샘플 수)
8        8192 bytes  int16 × 4096      (필터 출력 데이터)
─────────────────────────────────────
합계     8200 bytes
```

**왜 binary인가**: 4096개 int16을 text(예: "-1234\n")로 보내면 약 60,000 bytes. binary는 8192 bytes. 921600 baud에서 binary는 90ms, text는 650ms. 데모 반응성 차이가 크다.

**왜 magic이 필요한가**: UART는 바이트 스트림이라 패킷 경계가 없다. 노이즈나 타이밍 오차로 PC가 패킷 중간부터 수신을 시작할 수 있다. magic 값(0xDEADBEEF)을 찾아 패킷 시작 위치를 동기화한다.

---

### 3-8. `main()` — 전체 루프

```c
int main(void) {
    uart_init(921600);

    while (1) {
        float freqs[8];
        int n_tones = uart_recv_cmd(freqs);   // PC에서 명령 수신

        gen_multitone(freqs, n_tones, src_buf);  // 신호 합성
        dma_run();                                // DMA 실행
        uart_send_result(dst_buf, N_OUT);         // 결과 전송
    }
}
```

루프를 도는 이유: 시나리오 2(인터랙티브)에서 청중이 주파수를 바꿀 때마다 새로 처리해야 하기 때문이다. 시나리오 1(고정 프리셋)도 PC Python이 명령을 보내는 구조이므로 동일하게 처리된다.

---

## 4. 신호 프리셋

### 시나리오 1-1 (happy case)

| 파라미터     | 값                       |
| ------------ | ------------------------ |
| 입력 샘플 수 | 8192                     |
| 출력 샘플 수 | 4096                     |
| 톤           | 5MHz / 20MHz / 30MHz     |
| 진폭         | 0.3 균등 (합산 최대 0.9) |

| 톤    | 필터 영역 | 예상 결과    |
| ----- | --------- | ------------ |
| 5MHz  | 통과대역  | 원형 유지    |
| 20MHz | 전이대역  | 부분 감쇠    |
| 30MHz | 저지대역  | ≥ 60dB 감쇠 |

### 시나리오 1-2 (edge case)

| 파라미터     | 값                                  |
| ------------ | ----------------------------------- |
| 입력 샘플 수 | 8192                                |
| 출력 샘플 수 | 4096                                |
| 톤           | 7MHz / 15MHz / 25MHz / 45MHz        |
| 진폭         | 0.225 균등 (= 0.9/4, 합산 최대 0.9) |

| 톤    | 필터 영역       | 예상 결과                                |
| ----- | --------------- | ---------------------------------------- |
| 7MHz  | 통과대역        | 원형 유지                                |
| 15MHz | fp 경계값       | 리플 범위 내 통과                        |
| 25MHz | fs 경계값       | ≥ 60dB 감쇠 (양자화로 ±수dB 오차 가능) |
| 45MHz | 저지대역 깊숙이 | ≥ 60dB 감쇠                             |

**50MHz를 쓰지 않는 이유**: Fs=100MHz에서 50MHz는 나이퀴스트 주파수다. `sin(2π × 50MHz/100MHz × n) = sin(πn) = 0` — 초기 위상 0이면 모든 샘플이 0이다. 신호가 없는 것과 같아 의미 없다.

---

## 5. DMA 레지스터 맵

DMA 기저주소: `0x40400000` (`bd_fir_dma.tcl` `assign_bd_address` 기준)

AXI DMA Simple 모드 레지스터 (PG021 기준):

### MM2S (DDR → FIR 방향)

| 오프셋 | 이름        | 용도                                |
| ------ | ----------- | ----------------------------------- |
| 0x00   | MM2S_DMACR  | 제어: bit0=RS(Run/Stop), bit2=Reset |
| 0x04   | MM2S_DMASR  | 상태: bit1=Idle, bit12=IOC_Irq      |
| 0x18   | MM2S_SA     | 전송 시작 주소 (src_buf 물리 주소)  |
| 0x28   | MM2S_LENGTH | 전송 바이트 수 (N_IN × 2 = 16384)  |

### S2MM (FIR → DDR 방향)

| 오프셋 | 이름        | 용도                               |
| ------ | ----------- | ---------------------------------- |
| 0x30   | S2MM_DMACR  | 제어: bit0=RS, bit2=Reset          |
| 0x34   | S2MM_DMASR  | 상태: bit1=Idle, bit12=IOC_Irq     |
| 0x48   | S2MM_DA     | 수신 시작 주소 (dst_buf 물리 주소) |
| 0x58   | S2MM_LENGTH | 수신 바이트 수 (N_OUT × 2 = 8192) |

**Buffer Length Register 한계**: 14-bit → 최대 16384 bytes.

- MM2S: 8192 × 2 = 16384 bytes → 정확히 한계값
- S2MM: 4096 × 2 = 8192 bytes → 여유 있음

---

## 6. UART 통신 프로토콜

Baud rate: **921600** (115200 대비 8배 빠름. Zybo USB-UART 브릿지 지원 범위 내)

### PC → PS (명령)

```
형식: "<n> <f1> <f2> ... <fn>\n"
예시: "3 5000000 20000000 30000000\n"
```

- text 형식, 개행(`\n`)으로 명령 끝 표시
- 톤 개수 제한: 최대 8개 (합산 진폭이 1.0 미만으로 유지되는 범위)

### PS → PC (결과)

```
[ 0xDE 0xAD 0xBE 0xEF ]  4 bytes  magic (패킷 동기화 마커)
[ n_samples: uint32   ]  4 bytes  샘플 수
[ int16 × n_samples   ]  n×2 bytes 필터 출력
```

- binary 형식, little-endian (ARM Cortex-A9 = x86 모두 little-endian)
- 총 전송량: 8200 bytes, 921600 baud 기준 약 90ms

---

## 7. 캐시 관리

Zynq-7000 bare-metal은 L1/L2 캐시가 활성화된다. DMA는 캐시를 거치지 않고 DDR에 직접 접근한다.

```
CPU가 src_buf에 씀 → 캐시에만 반영, DDR은 아직 구버전
                   → Flush 해야 DDR에 반영됨 → DMA가 올바른 데이터 읽음

DMA가 dst_buf에 씀 → DDR에 직접 씀, 캐시는 구버전
                   → Invalidate 해야 캐시 버림 → CPU가 DDR에서 올바른 데이터 읽음
```

| 시점         | 함수                                             | 대상      |
| ------------ | ------------------------------------------------ | --------- |
| MM2S 시작 전 | `Xil_DCacheFlushRange(src_buf, N_IN×2)`       | 입력 버퍼 |
| S2MM 완료 후 | `Xil_DCacheInvalidateRange(dst_buf, N_OUT×2)` | 출력 버퍼 |

두 함수 모두 `xil_cache.h` (Vitis standalone BSP 포함).

---

## 8. UART 기초 개념

### Baud rate란

UART가 데이터를 전송하는 속도. 단위는 bps(bits per second).

UART는 데이터 1바이트를 전송할 때 실제로 10비트를 사용한다 (8N1 프레임):

```
[스타트 비트 1개] [데이터 8비트] [스톱 비트 1개] = 10비트 / 1바이트
```

따라서 실효 전송량 = baud rate ÷ 10:

```
115200 baud → 11,520 bytes/s ≈ 11 KB/s
921600 baud → 92,160 bytes/s ≈ 90 KB/s
```

4096샘플 × 2byte = 8192byte 전송 시:
- 115200 baud: 약 710ms (느림, 데모에서 체감)
- 921600 baud: 약 90ms (빠름, 데모에서 반응 즉각적)

이 프로젝트는 921600 baud를 사용한다.

### BSP(Board Support Package)란

Vitis에서 XSA 파일로 플랫폼을 생성하면 BSP가 자동으로 만들어진다. BSP는 하드웨어에 맞춰 자동 생성되는 드라이버 및 설정 모음이다.

```
XSA (하드웨어 정보)
    ↓ Vitis 플랫폼 생성
BSP 생성됨:
  ├── xparameters.h      하드웨어 주소/상수 자동 정의
  ├── xil_cache.h        캐시 제어 API
  ├── xuartps.h          UART 드라이버
  ├── 기본 UART baud rate: 115200  ← 이 값이 BSP 기본값
  └── ... 기타 드라이버들
```

**BSP Settings**: Vitis GUI에서 플랫폼의 BSP 설정을 바꿀 수 있는 메뉴. 기본 UART baud rate, 스택/힙 크기 등을 수정할 수 있다.

기본값(115200)을 BSP Settings에서 921600으로 바꾸는 대신, C 코드 안에서 `XUartPs_SetBaudRate()` API로 직접 설정한다. 이렇게 하면 BSP 설정에 의존하지 않아 다른 환경에서도 재현성이 보장된다.

---

## 9. C 코드와 FPGA가 소통하는 원리

### 메모리 맵 I/O (MMIO)

ARM CPU는 32비트 주소 공간(4GB)을 갖는다. 이 주소 공간 안에 DDR 메모리뿐 아니라 FPGA의 IP 레지스터도 함께 배치된다.

```
주소 공간:
0x00000000 ~ 0x1FFFFFFF  →  DDR 메모리 (512MB, 실제 데이터 저장)
           ...
0x40400000               →  AXI DMA 레지스터  ← FPGA 안에 있음
           ...
```

ARM이 `0x40400000`에 값을 쓰면 DDR이 아니라 **DMA 컨트롤러 레지스터에 쓰는 것**이다. 이것이 MMIO(메모리 맵 I/O)다. CPU 입장에서는 메모리 쓰기와 구별이 없다.

C 코드에서는 이렇게 표현한다:

```c
volatile uint32_t *reg = (volatile uint32_t *)0x40400000;
*reg = 0x1;  // DMA 시작 — 실제로는 레지스터에 쓰는 것
```

### 전체 소통 경로

C 코드는 FIR IP와 직접 대화하지 않는다. DMA를 통해 간접적으로 연결된다.

```
[ARM C 코드]
    │
    │  ① MMIO로 DMA 레지스터에 명령 작성
    │     (src_buf 주소, 전송 바이트 수, 시작 비트)
    ▼
[AXI DMA]  ←── PS GP0 버스로 연결 (SmartConnect 경유)
    │
    │  ② DMA가 DDR에서 데이터를 읽음
    │     (HP0 버스로 연결, AXI Interconnect 경유)
    ▼
[DDR: src_buf]  →  DMA가 읽어서 AXI-Stream으로 변환
    │
    │  ③ AXI-Stream으로 FIR IP에 전달
    ▼
[FIR IP (FPGA)]  필터링 + 데시메이션 처리
    │
    │  ④ AXI-Stream으로 DMA에 결과 전달
    ▼
[AXI DMA]  →  AXI-Stream을 다시 DDR에 저장
    │
    │  ⑤ DMA가 DDR에 결과 씀
    ▼
[DDR: dst_buf]  →  ARM C 코드가 읽어서 UART로 전송
```

### 핵심 정리

- **C 코드 ↔ DMA**: MMIO (레지스터 읽기/쓰기)
- **DMA ↔ DDR**: HP0 AXI 버스 (고속 메모리 접근)
- **DMA ↔ FIR IP**: AXI-Stream (데이터 스트리밍)
- **C 코드 ↔ FIR IP**: 직접 통신 없음. DDR을 공유 메모리로 사용해 간접 통신

C 코드가 FIR IP의 존재를 "모르는" 것처럼 동작해도 되는 이유가 이것이다. C는 DMA에게 "이 주소에서 저 주소로 보내라"고만 하면 나머지는 하드웨어가 처리한다.

---

## 10. 구현 검증 기준

| 항목                     | 확인 방법                                      |
| ------------------------ | ---------------------------------------------- |
| DMA MM2S 완료            | MM2S_DMASR bit1(Idle) = 1 폴링 확인            |
| DMA S2MM 완료            | S2MM_DMASR bit1(Idle) = 1 폴링 확인            |
| UART 수신 (PC→PS)       | minicom에서 직접 명령 타이핑 후 응답 확인      |
| UART 송신 (PS→PC)       | magic 0xDEADBEEF + n=4096 확인                 |
| 필터 동작 (시나리오 1-1) | Python FFT → 5MHz 존재, 30MHz ≥ 60dB 감쇠    |
| 필터 동작 (시나리오 1-2) | Python FFT → 7MHz 존재, 25/45MHz ≥ 60dB 감쇠 |
