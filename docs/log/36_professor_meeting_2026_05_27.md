# 36. 2026-05-27 교수님 미팅 정리

- 작성일: 2026-05-26
- 미팅 예정일: 2026-05-27
- 목적: 교수님 미팅에서 보고할 현재 상태, 주요 디버깅 결과, v2.0 확장 방향, 실제 말하기 대본을 정리한다.
- 참고 문서:
  - `docs/workflow/workflow_v7.md`
  - `docs/log/12_project_direction_change.md`
  - `docs/log/32_smoke_pass_after_dma_length_width_fix.md`
  - `docs/log/35_report_evidence_review_and_v16_status.md`
  - `docs/report/fir_n43/summary/scenario1_1.md`
  - `docs/report/fir_n43/summary/scenario1_2.md`

---

## 0. 미팅 대본 / 말하기 순서

이 섹션은 교수님이 프로젝트를 "FIR RTL 단일 구현"으로 기억하고 있을 가능성에 대비한 실제 말하기 순서다. 자세한 스펙, 수치, 디버깅 근거는 뒤 섹션을 보면서 설명한다.

### 0-1. 시작 30초

```text
교수님, 먼저 프로젝트 범위를 다시 짧게 말씀드리겠습니다.

처음에는 FIR 필터 RTL 구현처럼 보일 수 있는데,
현재는 단순히 FIR core 하나를 Verilog로 만든 수준에서 끝난 것이 아니라
실제 Zynq 보드에서 PS와 PL을 연결해 동작시키는 end-to-end FIR decimation system으로 확장했습니다.

즉 FIR RTL은 전체 시스템의 핵심 datapath이고,
제가 이번에 만든 것은 DSP 사양 정의부터 Python fixed-point golden model,
RTL 구현, AXI-Stream wrapper, Vivado block design, AXI DMA/DDR 연동,
Vitis bare-metal app, SD boot, UART, PC FFT/metric report까지 이어지는 검증 flow입니다.
```

핵심은 미팅 초반에 "FIR 필터 하나 구현"이 아니라 "board-level end-to-end system"으로 프레임을 다시 잡는 것이다.

### 0-2. 지금 뭐가 됐는지 물으시면

```text
현재는 fir_n43 기준으로 실제 보드 경로가 동작합니다.

흐름은 PC Python에서 UART로 tone 명령을 보내면,
PS bare-metal C app이 입력 multitone을 DDR에 만들고,
AXI DMA MM2S가 그 데이터를 PL의 FIR/decimator로 보냅니다.

PL에서 처리된 출력은 AXI DMA S2MM으로 다시 DDR에 저장되고,
PS가 그 결과를 UART packet으로 PC에 보내면,
PC Python이 FFT를 그리고 fixed-point golden model과 수치 비교를 합니다.
```

짧게 줄이면:

```text
PC -> UART -> PS C app -> AXI DMA -> PL FIR/decimator -> DMA -> UART -> PC FFT/report까지 연결했습니다.
```

### 0-3. FIR RTL 말고 뭐가 추가됐는지 물으시면

```text
단순 FIR RTL이면 input vector를 넣고 Verilog simulation에서 expected output과 비교하면 끝납니다.

그런데 이번 프로젝트에서는 그 RTL을 실제 보드 시스템 안에 넣었습니다.
그래서 AXI-Stream의 TVALID/TREADY/TLAST,
DMA의 MM2S/S2MM 전송,
DDR buffer와 cache flush/invalidate,
FSBL과 BOOT.bin,
bare-metal C app,
UART capture,
PC-side FFT와 metric report까지 모두 연결했습니다.

그래서 프로젝트의 깊이는 FIR 수식 하나보다,
fixed-point DSP model과 RTL을 맞추고,
그 RTL을 실제 Zynq PS-PL-DMA 시스템에서 재현 가능하게 검증한 데 있습니다.
```

강조할 최종 표현:

```text
제가 보여드리고 싶은 성과는 "FIR 필터 하나를 만들었다"가 아니라,
"FIR decimation IP를 실제 Zynq 시스템 안에 넣고 보드에서 재현 가능하게 검증하는 end-to-end flow를 만들었다"는 점입니다.
```

### 0-4. 스펙과 보드 검증 결과로 넘어가는 말

```text
기본 DSP 스펙은 입력 100 MHz, decimation factor M=2, 출력 50 MHz입니다.
passband는 15 MHz까지, stopband는 25 MHz 이상이고,
목표 감쇠는 60 dB입니다.

Kaiser window 기반으로 N=43 tap을 선택했고,
고정소수점은 Q1.15 signed 16-bit입니다.
RTL 구조는 timing을 고려해 transposed form으로 잡았습니다.
```

이후 섹션 1의 스펙 표를 보여준다.

```text
보드 검증은 scenario 1-1과 1-2로 확인했습니다.
두 경우 모두 board output을 Python fixed-point golden model과 비교했고,
sample-domain 기준으로 PASS입니다.
```

이후 섹션 4의 수치를 보여준다.

### 0-5. 20 MHz bin 공유를 설명해야 할 때

```text
Scenario 1-1에서 조심해야 할 점이 하나 있습니다.

출력 sampling rate가 50 MHz라 출력 FFT의 유효 범위는 0~25 MHz입니다.
이때 입력 30 MHz tone은 decimation 후 50 - 30 = 20 MHz로 alias될 수 있습니다.

그런데 scenario 1-1에는 원래 20 MHz transition tone도 들어 있습니다.
그래서 출력 FFT의 20 MHz bin에는 20 MHz transition tone과 30 MHz stopband tone의 영향이 같이 보일 수 있습니다.

따라서 scenario 1-1은 board와 golden이 잘 일치한다는 증거로는 좋지만,
30 MHz stopband 단독 감쇠를 설명하는 데에는 조심해야 합니다.

stopband alias suppression을 더 명확히 보여주는 것은 scenario 1-2의 45 MHz tone입니다.
```

짧게 말하면:

```text
1-1은 board-vs-golden 일치성 확인용으로 보고,
stopband alias 억제 설명은 1-2를 중심으로 하겠습니다.
```

### 0-6. 디버깅 이야기를 꺼낼 때

```text
가장 큰 bring-up 이슈는 AXI DMA MM2S timeout이었습니다.

처음에는 FIR RTL이나 AXI-Stream handshake 문제처럼 보였습니다.
그래서 FIR를 제거한 단순 AXIS debug path와 smoke-test까지 만들어서
어느 boundary에서 문제가 생기는지 분리했습니다.

결론적으로 FIR datapath 문제가 아니라 AXI DMA length field 설정 문제였습니다.
입력이 8192 samples이고 sample이 int16이라 MM2S 전송 길이가 16384 bytes였는데,
AXI DMA 기본 length width가 14-bit라 최대 16383 bytes까지만 표현 가능했습니다.
딱 1 byte 초과한 셈입니다.

Vivado BD Tcl에서 c_sg_length_width를 23-bit로 늘린 뒤
SD boot + DMA + UART 경로가 통과했습니다.
```

JTAG/DDR 이슈는 다음처럼 짧게 말한다.

```text
추가로 JTAG/XSDB direct DDR write 경로에서는 byte lane 3 MSB 오염이 관찰됐습니다.
그래서 최종 검증 경로는 JTAG direct DDR write가 아니라
FSBL을 거치는 SD boot 경로로 고정했습니다.
현재 신뢰 기준은 SD boot + AXI DMA + UART입니다.
```

### 0-7. v2 방향을 여쭤볼 때

```text
현재 v1.0은 end-to-end 보드 동작과 golden 비교 evidence까지 확보한 상태입니다.

남은 일은 report evidence를 정리하고,
demo command와 PASS 기준을 문서화하는 것입니다.

그 다음 v2.0으로 확장한다면,
제가 보기에는 BIST와 frequency sweep이 가장 현실적인 방향입니다.
이 부분에 대해 교수님 의견을 받고 싶습니다.
```

BIST 설명:

```text
BIST는 Built-In Self-Test입니다.
외부 PC가 모든 출력 샘플을 받아서 비교하는 것이 아니라,
하드웨어 내부에 test vector와 comparator를 넣어서
회로가 스스로 PASS/FAIL을 판단하게 만드는 구조입니다.

현재 v1은 UART로 출력 4096 samples를 PC에 보내고,
PC Python이 golden과 비교합니다.

v2에서 BIST를 넣으면,
PL 내부 BRAM에 input vector와 expected output vector를 저장하고,
controller가 FIR에 입력을 넣은 뒤,
comparator가 실제 출력과 golden을 cycle-by-cycle 비교합니다.

그 결과로 PASS/FAIL, error count, first mismatch index 정도만 PS나 UART로 보고하면 됩니다.
```

Frequency sweep 설명:

```text
두 번째 방향은 frequency sweep입니다.

현재는 100 MHz 기준으로 동작을 확인했는데,
100, 125, 150 MHz처럼 clock point를 올려가면서
Vivado timing의 WNS/TNS와 실제 board output correctness를 같이 보는 방식입니다.

이렇게 하면 이 IP가 단순히 동작한다는 것에서 끝나지 않고,
어느 주파수까지 timing margin을 갖는지,
어디서 깨지는지,
v2 구조가 v1보다 Fmax나 timing margin을 개선했는지 데이터로 말할 수 있습니다.
```

교수님께 드릴 질문:

```text
남은 기간을 고려하면,
저는 BIST로 testability를 보강하고,
frequency sweep으로 timing margin을 정량화하는 조합이 가장 현실적이라고 생각합니다.
교수님께서는 v2 방향으로 이 조합이 적절하다고 보시는지 여쭤보고 싶습니다.
```

### 0-8. 세게 물으실 때 짧은 답변

**결국 FIR 필터 하나 만든 것 아닌가?**

```text
FIR core는 핵심 datapath이지만, 현재 결과물은 그 core를 실제 Zynq 시스템에 통합해 보드에서 검증하는 flow입니다.
단순 RTL simulation이 아니라 PS에서 데이터를 만들고, DMA로 PL에 보내고, PL 결과를 다시 DDR/UART/PC로 가져와 golden과 비교합니다.
```

**UART로 보는 건 너무 느리지 않나?**

```text
맞습니다. UART는 처리 경로가 아니라 관측/데모 경로입니다.
실제 처리는 AXI DMA와 PL FIR에서 수행되고,
UART는 결과를 PC로 가져와 FFT와 metric report를 만들기 위한 evidence capture 경로입니다.
그래서 v2에서는 BIST로 UART 의존도를 줄이는 방향을 생각하고 있습니다.
```

**reset 없이 scenario를 연속 실행 못 하는 건 문제 아닌가?**

```text
현재 v1의 신뢰 가능한 절차는 scenario마다 board reset 후 실행하는 것입니다.
AXI DMA reset은 firmware에서 수행하지만,
PL/FIR/AXIS 전체를 board reset과 동일하게 초기화하는 software-controlled reset은 아직 부족합니다.
제품화 수준으로 가려면 이 부분은 v2에서 보완할 수 있습니다.
```

**JTAG 문제가 남아 있는데 괜찮나?**

```text
최종 검증 경로를 JTAG direct DDR write가 아니라 SD boot로 고정했기 때문에 v1 evidence에는 영향이 없습니다.
오히려 JTAG 경로의 신뢰성 문제를 분리했고,
FSBL을 거치는 SD boot + DMA + UART 경로를 기준 경로로 정했습니다.
```

**BIST가 v2라고 부를 만큼 의미 있나?**

```text
네. 단순 기능 추가가 아니라 검증 방식이 외부 PC 기반에서 on-chip self-test로 바뀝니다.
PASS/FAIL, error count, first mismatch index를 하드웨어가 직접 내면 testability와 test time 관점에서 발전입니다.
```

### 0-9. 마무리 대본

```text
정리하면,
교수님 피드백 이후 단순 LED 기반 시연에서 벗어나
N=43 transposed-form FIR decimator를 실제 Zynq PS-PL-DMA-UART 시스템에 통합했습니다.

현재 SD boot 기준으로 실제 보드에서 scenario 1-1과 1-2가 동작하고,
Python fixed-point golden과 수치적으로 비교되는 evidence까지 확보했습니다.

이제 v1.0은 report evidence와 문서화를 정리하면 되는 단계이고,
v2.0은 BIST를 통한 자체 검증 구조와 frequency sweep을 통한 timing margin 측정 방향으로 확장하는 것이 좋을지
교수님 의견을 받고 싶습니다.
```

---

## 1. 기본 하드웨어 / DSP 스펙

| 항목               | 내용                                         |
| ------------------ | -------------------------------------------- |
| Target board       | Zybo Z7-20, Zynq-7000                        |
| 설계 대상          | FIR Low-pass Filter + M=2 Decimator          |
| FIR 구조           | N=43 Transposed Form FIR                     |
| 입력 샘플링 주파수 | 100 MHz                                      |
| 출력 샘플링 주파수 | 50 MHz                                       |
| Decimation factor  | M = 2                                        |
| 통과대역           | 0 ~ 15 MHz                                   |
| 천이대역           | 15 ~ 25 MHz                                  |
| 차단대역           | 25 MHz 이상                                  |
| 목표 감쇠          | As >= 60 dB                                  |
| 계수 설계          | Kaiser window, beta = 5.653                  |
| Fixed-point format | Q1.15 signed 16-bit input/coefficient/output |
| RTL 검증 기준      | Python fixed-point golden model과 비교       |
| 시스템 인터페이스  | AXI-Stream wrapper                           |
| PS-PL 연결         | AXI DMA simple mode, HP0 DDR                 |
| Software           | Vitis bare-metal C                           |
| PC 연동            | UART 115200 + Python FFT viewer/report       |

---

## 2. 이전 교수님 피드백 반영 내용

이전 피드백:

> "시연이 약하다. 너무 간단하다. 발전된 모듈이 필요하다."

이에 따라 기존 방향을 수정했다.

기존 방향:

```text
N=5 bring-up
-> BRAM 기반 입력
-> LED PASS/FAIL 확인
```

변경 후 방향:

```text
N=43 Transposed FIR
-> AXI-Stream wrapper
-> Zynq PS + AXI DMA
-> bare-metal C
-> SD boot
-> UART
-> PC Python FFT 시각화 및 golden 비교
```

즉, 단순 RTL 시뮬레이션이나 LED 확인이 아니라, 실제 보드에서 PS-PL-DMA-UART까지 연결되는 end-to-end 시연 구조로 확장했다.

---

## 3. 현재 완료 상태

현재 `fir_n43` 기준으로 다음 경로가 동작한다.

```text
PC Python
-> UART command
-> PS bare-metal C
-> input multitone 생성
-> AXI DMA MM2S
-> PL FIR + Decimator
-> AXI DMA S2MM
-> DDR output buffer
-> UART packet
-> PC FFT / metrics report
```

확인된 사항:

- SD boot 후 UART에서 `READY FIR` 출력 확인
- Scenario `1-1`, `1-2`에서 board output 수신 확인
- PC FFT plot 생성 확인
- Board output과 Python fixed-point golden model 비교 완료
- Report artifact로 PNG / JSON / Markdown summary 생성 가능

---

## 4. 보드 검증 결과

### Scenario 1-1

입력 tone:

```text
5 MHz, 20 MHz, 30 MHz
```

의미:

- 5 MHz: passband
- 20 MHz: transition band
- 30 MHz: stopband

결과:

| 항목             |        값 |
| ---------------- | --------: |
| Overall          |      PASS |
| 비교 샘플 수     |      4096 |
| Max error        |     6 LSB |
| RMSE             | 1.403 LSB |
| SNR              | 74.863 dB |
| Correlation      |  1.000000 |
| Saturation count |         0 |

주의할 점:

- 출력 샘플링 주파수는 50 MHz이므로 출력 FFT 유효 범위는 0~25 MHz이다.
- 30 MHz 입력 tone은 decimation 후 `50 - 30 = 20 MHz`로 alias될 수 있다.
- 따라서 20 MHz transition tone과 30 MHz stopband tone이 출력 FFT의 20 MHz bin을 공유한다.
- 이 시나리오는 board와 golden이 잘 일치한다는 증거로는 좋지만, 30 MHz stopband 단독 감쇠를 설명할 때는 조심해야 한다.

### Scenario 1-2

입력 tone:

```text
7 MHz, 15 MHz, 25 MHz, 45 MHz
```

의미:

- 7 MHz: passband
- 15 MHz: passband edge
- 25 MHz: stopband edge / output Nyquist edge
- 45 MHz: deep stopband

결과:

| 항목             |        값 |
| ---------------- | --------: |
| Overall          |      PASS |
| 비교 샘플 수     |      4096 |
| Max error        |     7 LSB |
| RMSE             | 1.805 LSB |
| SNR              | 72.216 dB |
| Correlation      |  1.000000 |
| Saturation count |         0 |

특히 45 MHz tone은 출력에서 5 MHz로 alias될 수 있는데, FIR가 이를 약 64 dB 수준으로 억제하는 결과를 확인했다.

따라서 stopband alias suppression을 설명할 때는 Scenario 1-2가 더 명확하다.

---

## 5. 주요 디버깅 / Bring-up 이슈

### AXI DMA MM2S timeout 원인

처음에는 FIR RTL 또는 AXI-Stream handshake 문제처럼 보였지만, smoke-test를 통해 원인을 분리했다.

핵심 원인:

```text
N_IN = 8192 samples
sample width = int16 = 2 bytes
MM2S_LENGTH = 8192 * 2 = 16384 bytes
```

그런데 AXI DMA 기본 length field width가 14-bit였다.

```text
14-bit 최대 표현값 = 2^14 - 1 = 16383 bytes
필요한 전송 길이 = 16384 bytes
```

즉, 입력 DMA 전송 길이가 기본 설정 한계를 정확히 1 byte 초과했다.

조금 더 풀어 쓰면:

```text
16383 = 0x3FFF = 14-bit로 표현 가능
16384 = 0x4000 = 15번째 bit가 필요함
```

14-bit length field는 bit `[13:0]`까지만 의미가 있는데, `0x4000`은 그 바깥 bit가 켜진 값이다. 그래서 DMA가 이 전송 길이를 정상적인 byte count로 처리하지 못했고, MM2S transfer가 완료되지 않은 채 software timeout으로 관찰되었다.

해결:

```tcl
CONFIG.c_sg_length_width {23}
```

이 설정을 Vivado BD Tcl에 추가하여 DMA length field를 23-bit로 확장했고, 이후 SD boot + DMA + UART 경로가 통과했다.

### JTAG / DDR MSB 오류

JTAG `dow` / XSDB direct DDR write 경로에서 byte lane 3 MSB 오염이 관찰되었다.

따라서 최종 검증 경로는 JTAG direct DDR write가 아니라 다음으로 고정했다.

```text
SD boot
-> FSBL
-> bitstream
-> bare-metal ELF
-> AXI DMA
-> UART
```

이 내용은 단순 실패 사례가 아니라, 최종적으로 어떤 경로를 신뢰할 수 있는지 판단한 bring-up 결과로 설명한다.

---

## 6. 현재 한계 / 남은 정리

현재 기능 자체는 동작하지만, 다음 항목은 아직 정리 대상이다.

1. Scenario별 report artifact 최종 재생성 및 검토
2. README에 최종 demo command / PASS 기준 정리
3. 보드 reset 없이 `1-1` 후 `1-2`를 연속 실행하면 MM2S timeout이 날 수 있음
4. 현재 신뢰 가능한 데모 절차는 scenario마다 board reset 후 실행하는 방식
5. Scenario 1-1의 shared output bin 해석을 report에 명확히 표시해야 함

---

## 7. 교수님께 여쭤볼 핵심 질문

### 질문 1. v1.0 마무리 범위

현재 v1.0은 end-to-end 보드 동작과 golden 비교 evidence까지 확보했다.

확인받고 싶은 점:

- 이 상태에서 report/documentation 정리를 우선해 v1.0을 마무리할지
- 아니면 추가 기능을 더 넣어야 할지

### 질문 2. v2.0 확장 방향

남은 기간에 v2.0을 진행한다면 후보는 다음과 같다.

#### 방향 A: BIST

Built-In Self-Test 구조를 추가한다.

현재 방식:

```text
보드 출력 전체를 UART로 PC에 보내고
PC Python이 golden과 비교
```

BIST 방식:

```text
PL 내부에서 test input 생성
-> FIR 처리
-> PL 내부 golden 또는 signature와 비교
-> PASS/FAIL, error count, first mismatch index만 출력
```

장점:

- 외부 PC 의존도 감소
- 테스트 시간 감소
- 양산 테스트 / PE 직무 관점에서 의미 있음
- 단순 시연이 아니라 testability 개선으로 설명 가능

#### 방향 B: Frequency Sweep / Fmax 측정

현재 100 MHz 동작을 기준으로, 더 높은 주파수에서 timing과 기능이 어디까지 버티는지 측정한다.

예시:

```text
100 MHz
125 MHz
150 MHz
175 MHz
200 MHz
```

측정 항목:

- WNS / TNS
- implementation 성공 여부
- board output correctness
- SNR / max error
- failure point

장점:

- FIR IP의 timing margin을 데이터화 가능
- v1과 v2 비교에서 성능 향상 수치로 사용 가능
- PPA 관점의 포트폴리오 소재가 됨

#### 방향 C: XADC / 온도 모니터링

주파수 또는 반복 실행 조건에 따라 Zynq 내부 온도 변화를 측정한다.

장점:

- 물리적 신뢰성 관점 추가
- PE 직무와 연결 가능

단점:

- 측정 환경 변수 많음
- BIST / Fmax보다 우선순위는 낮아 보임

#### 방향 D: Fault Injection

RTL 내부에 의도적인 bit-flip 또는 coefficient fault를 넣고 출력 SNR 변화를 분석한다.

장점:

- failure analysis 관점에서 강한 주제
- 고급 포트폴리오 소재

단점:

- 범위가 커질 수 있음
- 현재 단계에서는 후순위가 안전함

---

## 8. 제안하는 v2.0 우선순위

개인적으로는 다음 조합이 가장 현실적이다.

```text
1순위: BIST
2순위: Frequency Sweep / Fmax 측정
3순위: XADC 온도 로그
4순위: Fault Injection
```

추천 v2.0 목표:

```text
v1.0:
PC UART 기반 end-to-end FIR decimation demo

v2.0:
PL 내부 BIST + 주파수 sweep을 통해
testability와 timing margin을 정량화한 개선형 FIR IP
```

---

## 9. 미팅에서 말할 최종 요약 문장

교수님 피드백 이후 단순 LED 기반 시연에서 벗어나, N=43 Transposed FIR를 AXI-Stream으로 감싸고 Zynq PS, AXI DMA, bare-metal C, UART, PC FFT viewer까지 연결한 end-to-end 보드 검증 구조를 만들었습니다.

현재 SD boot 기준으로 실제 보드에서 scenario 1-1과 1-2가 동작하고, Python fixed-point golden과 비교했을 때 각각 SNR 74.86 dB, 72.22 dB 수준으로 일치합니다.

Bring-up 중 AXI DMA length width 문제와 JTAG DDR write MSB 오염 문제를 분리했고, 최종 신뢰 경로는 SD boot + AXI DMA + UART로 고정했습니다.

이제 v1.0은 report evidence와 문서화를 마무리하면 되는 단계이고, v2.0은 BIST를 통한 자체 검증 구조와 frequency sweep을 통한 timing margin 측정 방향으로 확장하는 것이 좋을지 교수님 의견을 받고 싶습니다.

---

## 10. 실제 미팅 피드백 (2026-05-27)

미팅에서 교수님이 주신 실제 피드백은 다음과 같다.

### 교수님 지시 사항

1. **보드 없이 노트북(CPU)만으로 동일한 FIR 연산 실행** → 걸린 시간 및 사용 자원 기록
2. **보드(FPGA)로 FIR 연산 실행** → 걸린 시간 측정 → 노트북과 비교 분석

### 교수님이 강조하신 핵심

> "실제로 뭔가 보여지는 게 중요하다."
> "보드로 뭔가를 해낸다고 잘 안 느껴지니까 그 부분이 걱정스럽다."

현재 데모는 보드가 동작한다는 사실은 보여주지만, 보드를 쓰는 이유(CPU 대비 이점)가 시각적으로 드러나지 않는다는 우려다.

### 반영 방향 (v18 작업 목록)

교수님 피드백을 두 가지 P0 작업으로 반영한다.

| 항목 | 내용 | 커버하는 피드백 |
| --- | --- | --- |
| P0-A | 입력 vs 출력 스펙트럼 나란히 비교 시각화 | "보여지는 게 중요하다" — FIR가 무엇을 하는지 직관적으로 보임 |
| P0-B | CPU(노트북) vs FPGA(보드) FIR 처리 시간 비교 | 노트북/보드 시간 측정 및 비교 분석 직접 요청 |

상세 구현 계획은 `docs/workflow/workflow_v18.md` 참조.

### 비교 시 주의 사항

총 경로 시간(UART 포함)으로 비교하면 FPGA가 더 느리게 나온다.

```
UART 115200bps, 16384 bytes 전송 ≈ 1.4초
NumPy FIR 연산 ≈ 수십 마이크로초
```

UART는 결과 관측 경로이지 처리 경로가 아니다. 비교 기준은 FIR 연산 시간만으로 한정한다.

- CPU 측: `time.perf_counter()`로 NumPy FIR 연산 구간만 측정
- FPGA 측: bare-metal C에서 DMA MM2S 시작 → S2MM 완료 구간만 `XTime_GetTime()`으로 측정
