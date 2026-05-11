# 25. AXI-Stream TLAST 데드락 및 파이프라인 잔여 데이터 트러블슈팅

- 작성일: 2026-05-11
- 목표: DMA S2MM(수신) 채널 타임아웃 오류(Python 응답 없음) 원인 분석 및 해결
- 상태: 🔄 보드 동작 확인 전

---

## 배경

`24_jtag_download_troubleshooting.md`에서 DMA soft reset 누락 문제를 해결하고 `fir_decimator_demo.py`를 실행했으나, `TimeoutError: 보드 응답 없음` 에러가 발생했다. DMA 송신(MM2S)은 정상 완료되는 것으로 보이나, 수신(S2MM) 채널이 패킷 완료 신호를 받지 못하고 무한 대기(Hang) 상태에 빠진 것이 문제의 시발점이라고 생각된다.

---

## 문제 1: S2MM 타임아웃 (하드코딩된 TLAST 카운터)

**증상**
C 코드에서 `N_OUT=4096` 크기로 수신을 대기하지만 DMA가 끝나지 않음. Python 스크립트 역시 UART 패킷(Magic word)을 영원히 기다리다 Timeout 처리됨.

**원인 (하드웨어 제어권 결함)**
`fir_decimator_n43_axis.v` 내부의 `TLAST_N` 파라미터가 `4096`으로 하드코딩되어 있었다.

1. DMA(MM2S)가 8192개의 입력 샘플을 다 보내고 전송을 끊음(`s_axis_tvalid = 0`).
2. FIR 코어는 파이프라인 구조(Transposed form)이므로, 마지막 데이터가 데시메이션 처리를 거쳐 출력되기까지 수십 클럭의 지연(Latency)이 존재함.
3. 데이터 공급이 끊기자 파이프라인 컨베이어 벨트가 멈추며, 마지막 출력 샘플들이 IP 내부에 갇혀버림(Starvation).
4. 출력 카운터가 `4096`에 도달하지 못해(4094~4095에서 정지) `m_axis_tlast`를 내보내지 않음.
5. S2MM 채널은 TLAST도 없고 요청한 4096개 데이터도 안 들어오니 영구 데드락(Deadlock)에 빠짐.

**해결**
독재적인 내부 카운터를 삭제하고 마스터(DMA)의 TLAST에 순응하는 **동적 카운터(Dynamic Counter)** 구조로 RTL 래퍼를 전면 재설계.

- 변경 후: 마스터가 보내는 `s_axis_tlast`를 감지하여 들어온 입력 개수(`in_cnt`)를 파악하고, 데시메이션 비율(M=2)에 맞춰 동적으로 목표 출력 개수(`target_out_cnt`)를 계산.

---

## 문제 2: 파이프라인 데이터 갇힘(Starvation) 해소

**증상**
동적 카운터 방식을 적용하더라도, 입력 데이터가 끊긴 시점에서 파이프라인 내부에 남아있는(In-flight) 데이터를 밀어낼 동력이 없으면 여전히 출력이 나오지 않음.

**원인**
ADC 연속 스트리밍 환경과 달리, 본 프로젝트는 Python에서 지정한 8192개 데이터만 블록 단위(Batch)로 쏘고 멈추는 데모 환경임. 패킷 전송 후 파이프라인을 비워주지 않으면 데드락과 런타임 상태 오염이 발생함.

**해결**
RTL 래퍼 내부에 **Auto-Flush 상태 머신** 도입.

1. `s_axis_tlast`가 감지되면 `waiting_for_last_out` 상태로 진입.
2. 외부에서 더 이상 새로운 패킷이 섞여 들어오지 못하도록 `s_axis_tready`를 강제로 `0`으로 차단 (Backpressure).
3. IP 코어의 데이터 입력 포트에 0(Dummy Data)을 강제로 주입하여 파이프라인 내부를 계속 밀어냄.
4. `target_out_cnt`만큼의 출력이 밖으로 모두 빠져나오는 순간 `m_axis_tlast`를 동기화하여 출력하고 Flush 상태 종료.

---

## 최종 수정된 RTL 구조 요약 (`fir_decimator_n43_axis.v`)

1. **상태 레지스터 추가**: `in_cnt`, `out_cnt`, `target_out_cnt`, `waiting_for_last_out`
2. **Auto-Flush 다중화기(MUX)**:
   ```verilog
   assign s_axis_tready = core_ready & ~flush_active;
   wire core_in_valid  = (s_axis_tvalid & s_axis_tready) | (flush_active & core_ready);
   wire [15:0] core_in_sample = flush_active ? 16'sd0 : s_axis_tdata;
   ```


3. **TLAST 파이프라인 동기화** : Depth-3 스키드 버퍼(Skid buffer)에 `tlast0, tlast1, tlast2` 레지스터를 추가하여 데이터와 TLAST 신호가 동일한 타이밍에 m_axis로 방출되도록 구현.

---

## 핵심 교훈

1. **AXI-Stream IP는 패킷의 끝(TLAST) 처리가 생명이다.** 하드코딩된 길이로 블록을 임의로 자르는 방식은 실시간 스트리밍(무한 데이터) 환경에서나 쓸 수 있으며, 범용 래퍼는 반드시 마스터의 `s_axis_tlast` 신호에 동적으로 대응(Propagation)해야 한다.
2. **배치 처리(Batch processing) 시 파이프라인 지연(Latency)은 찌꺼기를 남긴다.** 데이터가 끊겼을 때 내부 레지스터를 스스로 비워내는(Flush) 구조가 없으면 시스템은 반드시 멈춘다.
3. **더미 데이터 주입의 트레이드오프 수용.** Auto-Flush로 인한 0 주입은 4096개 출력의 마지막 20여 개 샘플에 과도 응답(Transient) 찌그러짐을 유발하지만, 데모 시나리오의 핵심인 FFT 스펙트럼(주파수 분석) 결과에는 수학적/시각적 영향을 미치지 않으므로 최적의 타협점이다.

