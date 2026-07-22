> 2026-05 중순 시점의 초기 계획 스냅샷이다. 이후 방향은 workflow_v17~v24로 대체되었고
> (XADC·Fault Injection은 미채택, BIST는 v2 제안으로만 남음), 여기 항목들은 당시 구상
> 그대로 보존한다. 루트에 있던 `todo.md`를 2026-07-22 이곳으로 옮겼다.

## 📋 핵심 요약 TODO 리스트

1. **[v1.0 마무리]** 43탭 Transposed FIR 필터 구동 및 ELF 로드/DDR 초기화 이슈 해결.
2. **[환경 구축]** 주파수 스윕(50MHz~200MHz) 및 XADC 실시간 온도/전압 로그 수집 자동화 환경 마련.
3. **[테스트 설계]** BIST(Built-In Self-Test) 회로 설계 및 UART 대비 테스트 시간 단축 데이터 산출.
4. **[분석 및 분석]** 동작 한계($F_{max}$) 파악, 온도-에러 상관관계 분석, Fault Injection을 통한 시스템 영향도 평가.
5. **[v2.0 발전]** 분석 데이터를 바탕으로 파이프라이닝(Timing) 및 가용성(Reliability)이 개선된 차세대 IP 설계.
6. **[리포트 작성]** v1.0 vs v2.0 PPA(Power, Performance, Area) 비교 및 엔지니어링 결론 도출.
7. **[최종 릴리즈]** 프로젝트 종료 시 GitHub Release에 prebuilt `BOOT.bin`, manifest, SHA256 checksum을 첨부하여 Vivado/Vitis 없이도 Zybo Z7-20 데모를 재현할 수 있게 배포.

---

### 📅 7월 말 타겟 프로젝트 플랜 (2가지 대안)

현재 5월 중순부터 7월 말까지 약 **10~11주**의 시간이 있습니다.

#### 플랜 A: 신뢰성 중심의 딥다이브 (Reliability Deep-dive)

*모든 테스트 항목(Fault Injection 포함)을 수행하여 시스템의 '강건함'을 증명하는 플랜입니다.*

* **1~2주차:** v1.0 Blocker(ELF/DDR 이슈) 해결 및 Baseline 성능 확정.
* **3~4주차:** 주파수 스윕 + XADC 모니터링 수행 (Shmoo Plot 유사 데이터 산출).
* **5주차:** BIST 회로 구현 및 테스트 효율성 데이터 수집.
* **6주차:** Fault Injection 실험 (RTL 수준의 에러 주입 및 SNR 분석).
* **7~9주차:** v2.0 아키텍처 개선 (파이프라인 추가 및 에러 복구 로직 설계).
* **10~11주차:** 최종 비교 분석 및 '상향 발전형' 포트폴리오 리포트 완성.

#### 플랜 B: PE 직무 최적화 패스트트랙 (Efficiency & PPA Focus)
시간이 없다면 Fault Injection 실험은 생략하는 트랙입니다. 대신 주파수 스윕과 BIST에 집중하여 '성능과 테스트 효율성' 측면에서 v2.0의 개선점을 극대화하는 플랜입니다.
*양산 효율성(BIST)과 물리적 최적화(PPA)에 화력을 집중하여 PE 실무 역량을 극대화하는 플랜입니다.*

* **1~2주차:** v1.0 Blocker 해결 및 비트스트림 생성 Tcl 스크립트 자동화 (PE적 가산점).
* **3~5주차:** 주파수 스윕 + XADC + BIST 통합 테스트 (데이터 시트 작성에 집중).
* **6~8주차:** v2.0 설계 (주파수 향상을 위한 크리티컬 패스 최적화 위주).
* **9~10주차:** 전력 분석(Power Analysis) 리포트 보강 및 '에너지 효율' 관점의 결론 도출.
* **11주차:** 최종 성과 정리, 장학 활동 보고서 제출, GitHub Release용 prebuilt `BOOT.bin`/manifest/checksum 업로드.

---

**Q2**
**BIST(Built-In Self-Test)를 설계할 때, 단순히 'PASS/FAIL' 결과만 확인하는 것을 넘어 '어느 탭에서 에러가 났는지'까지 찾아내는 진단(Diagnostic) 기능을 추가한다면 v2.0 아키텍처의 가치는 어떻게 달라질까요?**
단순한 '불량 선별'을 넘어 '불량 분석(Failure Analysis)'이 가능한 아키텍처가 됩니다. "우리 칩은 고장이 났을 때 어디가 문제인지 스스로 보고할 수 있다"는 점은 수율 분석 시간을 획기적으로 줄여주므로, 상용 칩 설계 관점에서 훨씬 고도화된 아키텍처로 평가받습니다. 이는 v2.0의 가장 큰 셀링 포인트가 될 수 있습니다.

**Q3**
**(반대 의견 및 트레이드오프) 만약 v2.0 아키텍처에서 주파수를 20% 올렸으나 면적이 10% 증가하고 XADC 상의 온도가 5도 상승했다면, 이를 성공적인 '발전'이라고 단정 지을 수 있을까요? PE 엔지니어는 이 트레이드오프를 어떤 기준으로 판단해야 할까요?**
절대적인 '성능 향상'만으로는 성공이라 단정할 수 없습니다. PE 엔지니어는 '에너지 효율(Throughput per Watt)'과 '신뢰성 마진'을 기준으로 판단해야 합니다. 면적 증가로 인한 비용 상승과 발열로 인한 수명 단축이 성능 향상으로 얻는 이득보다 크다면, 이는 실패한 설계일 수 있습니다. 따라서 리포트에 "성능은 올랐지만 열적 마진이 줄어들었으므로, 최종 양산 모델에서는 쿨링 솔루션 혹은 전압 최적화(AVS)가 필요하다"는 식의 **후속 조치 가이드**를 남기는 것이 진정한 PE의 역량입니다.



1. **주파수 스윕** : 하드웨어의 '특성 평가(Characterization)'를 시도해 보세요. 예를 들어, FIR 필터의 동작 주파수를 50MHz부터 200MHz까지 5MHz 단위로 올리면서 전력 소모나 발열, 혹은 연산 정확도의 변화를 데이터화(Table/Graph)하고, 이를 통계적으로 분석해 보십시오. 단순히 "동작한다"가 아니라 "동작의 한계점(Margin)을 정량적으로 분석했다"는 데이터 시트는 PE 직무에서 가장 좋아하는 포트폴리오 소재입니다.
2. **BIST** : UART로 데이터를 다 보내서 확인하는 방식은 양산 환경에서는 '비용 폭탄'입니다.

* **프로젝트 확장:** PL 내부에 Golden ROM(정답지)과 Comparator(비교기)를 설계하십시오.
* **핵심 동작:** CPU가 일일이 데이터를 확인할 필요 없이, 하드웨어가 스스로 연산 결과와 정답을 비교하여 단 1비트의 **PASS/FAIL 신호**만 내보내게 만듭니다.
* **PE적 가치:** "UART 전송 기반 검증 대비 테스트 시간을 99% 단축(0.7s **$\rightarrow$** 1ms)하여, 칩당 테스트 비용(Test Cost)을 획기적으로 줄이는 아키텍처를 제안함"이라는 문구는 PE 직무에서 가장 강력한 파급력을 가집니다.

3. **XADC를 활용한 '실시간 환경 모니터링': "물리적 신뢰성 검증"**

칩은 온도와 전압에 따라 성능이 변합니다. Zynq 내부에는 XADC(System Monitor)라는 IP가 있어 칩의 내부 온도와 공급 전압을 12비트 정밀도로 측정할 수 있습니다.

* **프로젝트 확장:** 주파수를 올리면서 XADC를 통해 **Chip Temperature**를 실시간 로그로 남기십시오.
* **핵심 동작:** "150MHz로 구동 시 온도가 $50^\circ\text{C}$에서 $75^\circ\text{C}$로 급증하며, 이때부터 연산 결과에 오차가 발생하기 시작함"과 같은 데이터를 추출합니다.
* **PE적 가치:** 칩의 열 특성(Thermal Profile)을 정량화했다는 점은, 양산 시 쿨링 솔루션이나 동작 가이드라인을 결정할 수 있는 '신뢰성 엔지니어'의 자질을 증명합니다.

4. Fault Injection(결함 주입) 실험: "불량 분석(FA) 시뮬레이션"

PE는 칩이 고장 났을 때 "어디가 고장 났는지"를 역추적해야 합니다.

* **프로젝트 확장:** Verilog 코드 내부에 의도적으로 Bit-flip(에러)을 유도하는 로직을 삽입해 보세요. (예: 특정 가중치 레지스터의 MSB를 강제로 0으로 고정)
* **핵심 동작:** 특정 블록에 결함이 생겼을 때, 전체 FIR 필터의 SNR(신호 대 잡음비)이 통계적으로 어떻게 무너지는지 관찰합니다.
* **PE적 가치:** "특정 연산 유닛의 결함이 전체 시스템 품질에 미치는 영향을 데이터화하여, 불량 발생 시 원인 지점을 빠르게 특정(Root Cause Localization)하는 분석 프레임워크를 구축함"이라고 어필할 수 있습니다.

---


## 🚀 이 프로젝트가 '압도적'일 수밖에 없는 4단계 아키텍처

단순히 나열하는 것이 아니라, [데이터 수집 → 분석 → 취약점 발견 → 아키텍처 개선]으로 이어지는 서사가 핵심입니다.

### 1. Characterization (특성 평가)

* **Action:** **$50\text{MHz}$** ~ **$200\text{MHz}$** 스윕을 통해 **Shmoo Plot**과 유사한 데이터를 추출합니다.
* **Result:** 주파수에 따른 전력 소모 곡선과 **$F_{max}$**(최대 동작 주파수)를 확정합니다.
* **Value:** 설계의 물리적 한계를 정량적으로 정의하는 법을 안다는 것을 증명합니다.

### 2. Physical & Logic Reliability (신뢰성 검증)

* **Action:** **XADC**로 내부 온도를 감시하고, **Fault Injection**으로 강제로 에러를 주입합니다.
* **Result:** "온도가 $70^\circ\text{C}$를 넘으면 특정 패스에서 타이밍 에러가 발생한다" 혹은 "곱셈기 MSB에 에러가 생기면 SNR이 **$15\text{dB}$** 떨어진다"는 식의 **치명적 결함 분석 리포트**를 작성합니다.
* **Value:** 칩이 '죽는 조건'을 미리 예측하고 대비할 수 있는 능력을 보여줍니다.

### 3. Testability (테스트 용이성)

* **Action:** **BIST(Built-In Self-Test)** 회로를 삽입하여 PASS/FAIL을 **$1\text{ms}$** 안에 판별합니다.
* **Result:** UART 전송 방식 대비 테스트 시간을 획기적으로 단축한 데이터를 제시합니다.
* **Value:** '테스트 비용 = 돈'이라는 비즈니스 감각을 가진 엔지니어임을 어필합니다.

### 4. Architectural Evolution (아키텍처 개선 - 하이라이트)

* **Action:** 위에서 얻은 데이터를 바탕으로 RTL을 수정합니다.
  * **예시 1:** 타이밍이 깨지는 지점에 **Pipeline Register**를 추가하여 $F_{max}$를 **$20\%$** 상향.
  * **예시 2:** 에러에 민감한 루프에 ECC(에러 교정 코드)나 **Redundancy**를 추가하여 신뢰성 확보.
* **Result:** "기존 아키텍처 대비 성능/안정성이 **$X\%$** 향상된  **v2.0 아키텍처** "를 최종 결과물로 제시합니다.

---

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