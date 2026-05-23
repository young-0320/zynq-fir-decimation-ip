# TODO / 학습 정리

## 1. 하드웨어 특성 평가(Characterization) 보완

하드웨어의 특성 평가를 시도해 보세요. 단, 특성 평가는 단순히 FIR 필터의 동작 주파수를 50 MHz부터 200 MHz까지 올리면서 pass/fail만 보는 작업이 아니다. 주파수 sweep은 여러 평가 축 중 하나이며, 최종 목표는 "동작한다"가 아니라 "어떤 조건에서 어느 정도의 margin을 가지고 동작하는지"를 데이터화하는 것이다.

평가 결과는 Table/Graph 형태로 정리하고, 가능하면 각 항목의 측정 조건, 반복 횟수, pass/fail 기준, 관찰된 failure mode를 함께 기록한다. 이런 데이터 시트는 PE 직무에서 특히 좋은 포트폴리오 소재가 된다.

권장 평가 축:

- Frequency/timing margin: 클럭 주파수 sweep, WNS/TNS, setup/hold 통과 여부, Fmax 추정, critical path 변화.
- Functional correctness: Python golden 대비 RTL/보드 출력의 bit-exact 여부, max error, MSE, SNR, 1 LSB 이내 오차율.
- DSP response: passband 유지, stopband attenuation, alias suppression, decimation 전후 FFT/PSD 비교, 경계 주파수 입력의 동작.
- Throughput/latency: 1 sample/cycle 달성 여부, FIR/decimator/top latency, DMA 전송 시간, UART 전송 시간, end-to-end 처리 시간.
- AXI-Stream robustness: backpressure 조건에서 데이터 drop 없음, TLAST 위치 정확성, TVALID/TREADY stall 상황, reset recovery.
- DMA/DDR/system path: MM2S/S2MM timeout 여부, DMA length 설정별 동작, cache flush/invalidate 영향, DDR buffer 정합성.
- Resource/PPA: LUT, FF, BRAM, DSP48 사용량, clock 변경 또는 파이프라인 추가 전후 resource/timing tradeoff.
- Power/thermal: 가능하면 보드 전력, regulator 온도, FPGA/보드 표면 온도, 장시간 반복 실행 안정성.
- Boot/reproducibility: JTAG/SD boot별 성공률, DONE LED, UART READY, BOOT.bin 재생성 절차, XSA/bit/ELF/FSBL 산출물 일관성.

최소 산출물 예시:

| 평가 축 | 측정 항목 | 기준 | 결과 | 로그/증거 |
| --- | --- | --- | --- | --- |
| Timing | 100/125/150 MHz WNS | WNS >= 0 | TBD | Vivado timing summary |
| Correctness | max error / SNR | <= 1 LSB or 기준 SNR 이상 | TBD | Python golden 비교 |
| DSP | 30 MHz attenuation | >= 60 dB | TBD | FFT/PSD plot |
| AXIS | random TREADY backpressure | drop 없음, TLAST 1회 | TBD | RTL TB PASS |
| DMA | 8192 input / 4096 output transfer | timeout 없음 | TBD | UART trace / Python run |

## 2. 이 프로젝트에서 핵심적으로 이해해야 할 이론

### 2.1 AXI-Stream 통신 프로토콜

- 실제 데이터 beat는 `TVALID && TREADY`인 clock edge에서만 전송된다.
- `TVALID=1`이고 `TREADY=0`이면 `TDATA`, `TLAST` 등 payload는 유지되어야 한다.
- `TREADY`는 downstream backpressure이고, `TLAST`는 packet/frame boundary다.
- 이 프로젝트의 S2MM timeout, TLAST deadlock, auto-flush, skid buffer 문제는 모두 AXI-Stream 계약 위반 또는 packet boundary 처리와 연결된다.
- 핵심 질문: "언제 샘플 하나가 실제로 이동했는가?", "stall 중 어떤 상태가 고정되어야 하는가?", "마지막 샘플의 TLAST는 데이터와 같은 beat에 붙어 나가는가?"

### 2.2 PC -> PS -> PL 데이터 흐름과 버스 구조

- PC Python은 UART로 명령을 보낸다.
- PS bare-metal C app은 명령을 받아 입력 신호를 만들고 DDR buffer에 저장한다.
- PS는 AXI-Lite/MMIO로 AXI DMA register를 설정한다.
- AXI DMA MM2S는 DDR의 입력 buffer를 읽어 AXI-Stream으로 PL FIR에 보낸다.
- PL FIR/decimator는 AXI-Stream 입력을 처리해 AXI-Stream 출력으로 돌려준다.
- AXI DMA S2MM은 PL 출력을 DDR output buffer에 쓴다.
- PS는 output buffer를 읽어 UART binary packet으로 PC에 전송하고, PC Python은 FFT/plot으로 결과를 확인한다.
- cache flush/invalidate는 필수다. DMA는 CPU cache가 아니라 DDR을 직접 보므로, PS가 쓴 입력은 flush해야 하고 DMA가 쓴 출력은 invalidate해야 한다.

### 2.3 Boot 종류와 산출물 관계

- JTAG FPGA programming은 PL bitstream을 올리는 작업이고, PS DDR/PLL/MIO 초기화와는 별개다.
- JTAG ELF download는 `ps7_init` 이후 DDR에 ELF를 써서 ARM을 실행하는 흐름이다. 이 프로젝트에서는 JTAG DDR write byte lane 오염 문제 때문에 신뢰 경로에서 제외했다.
- SD boot는 `BOOT.bin = FSBL + bitstream + application ELF` 흐름이다.
- FSBL은 XSA에서 나온 PS7 초기화 정보를 사용해 DDR/clock/MIO를 초기화하고, bitstream과 app을 순서대로 로드한다.
- XSA, HWH, bitstream, FSBL, ELF, BIF, BOOT.bin의 관계를 설명할 수 있어야 한다.

### 2.4 오류가 발생한 지점과 원인 분리법

- UART timeout은 UART 자체 문제일 수도 있고, 보드 app이 DMA timeout에 걸려 응답을 못 한 것일 수도 있다.
- MM2S timeout은 DDR -> DMA -> AXI-Stream source 방향 문제를 의심한다.
- S2MM timeout은 PL output, TLAST, output length, backpressure, DMA receive path를 우선 의심한다.
- JTAG DDR byte[3] 오염은 PL FIR RTL과 분리해서 봐야 한다. 이 경로는 AXI-Stream wrapper를 거치지 않는다.
- smoke-test는 FIR를 제거하고 DMA/DDR/UART/Python 경로만 검증하기 위한 원인 분리 장치다.
- 핵심 사고방식은 "전체가 안 된다"가 아니라 "어느 boundary까지는 증명되었고, 다음 boundary에서 깨지는가"를 자르는 것이다.

### 2.5 Fixed-point DSP / FIR / Decimation

- Decimation 전에는 anti-alias FIR가 필요하다. 출력 샘플링 주파수가 낮아지면 Nyquist 한계도 낮아지기 때문이다.
- Kaiser window, tap 수, transition band, stopband attenuation 관계를 이해해야 한다.
- `N=43`은 멀티톤 하나의 결과가 아니라 coefficient frequency response의 worst-case stopband 기준으로 선택된 tap 수다.
- `Q1.15` 입력/계수, `Q2.30` 곱셈, wide accumulator, rounding, saturation 정책이 Python golden과 RTL bit-exact 비교의 기준이다.
- 주파수 응답만 보지 말고 time-domain 오차, fixed-point quantization error, SNR/MSE/max error도 함께 봐야 한다.

### 2.6 RTL timing / 검증 이론

- WNS가 음수면 지정 clock period 안에 combinational path가 닫히지 않는다는 뜻이다.
- Pipeline을 추가하면 latency는 늘지만 critical path가 짧아져 Fmax/timing margin이 좋아진다.
- DSP48 사용량, LUT/FF 증가, latency 증가를 timing closure와 함께 tradeoff로 봐야 한다.
- Testbench는 RTL의 현재 계약을 검증해야 의미가 있다. RTL이 dynamic TLAST/auto-flush로 바뀌었으면 TB도 그 계약을 검증해야 한다.
- backpressure, input bubble, reset recovery는 AXI-Stream IP의 무결성을 확인하는 핵심 시나리오다.

## 3. 최종 정리 방향

이 프로젝트를 제대로 이해했다는 기준은 다음 질문에 답할 수 있는지로 잡는다.

- PC에서 보낸 명령이 어떤 버스와 buffer를 거쳐 PL FIR까지 도달하는가?
- AXI-Stream에서 실제 전송이 성립하는 조건은 무엇인가?
- DMA가 timeout될 때 MM2S/S2MM 각각 어떤 지점을 의심해야 하는가?
- 왜 JTAG boot 경로를 버리고 SD boot로 전환했는가?
- `N=43`, `Q1.15`, rounding/saturation 정책은 어떤 근거로 정했는가?
- Timing violation을 pipeline으로 해결하면 latency/resource/throughput이 어떻게 바뀌는가?
- 주파수 응답 외에 어떤 지표로 하드웨어 IP의 특성을 평가할 수 있는가?
