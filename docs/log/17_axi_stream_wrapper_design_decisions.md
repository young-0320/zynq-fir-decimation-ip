# 17. AXI-Stream Wrapper Design Decisions

- 작성일: 2026-05-04
- 단계: 9
- 목적: fir_decimator_transposed_n43_axis_top 구현 전 AXI-Stream 래퍼에 필요한 의사결정 사항을 확정하고 근거를 기록한다
- 선행 문서: `docs/log/16_vivado_timing_closure_transposed_n43.md`

## 1. 배경

Step 4까지 완성된 코어(`fir_decimator_transposed_n43_top`)는 simple valid-pulse 인터페이스를 갖는다.

```
in_valid / in_sample[15:0]   →  입력 샘플 펄스
out_valid / out_sample[15:0] →  출력 샘플 펄스
```

Step 6 PS-PL DMA 연동을 위해 이 코어를 AXI-Stream 인터페이스로 감싸는 래퍼가 필요하다. Xilinx AXI DMA IP(PG021)는 PL 쪽 데이터 포트로 AXI-Stream을 요구한다. AXI-Lite 단독으로는 DMA를 구동할 수 없고, CPU가 매 샘플마다 직접 레지스터를 폴링해야 하므로 50MHz 출력 스트림에서 CPU 부하가 감당 불가능한 수준이 된다.

---

## 2. 의사결정 요약

| 항목 | 결정 |
|---|---|
| 리셋 | 동기 액티브 로우 (`aresetn`) |
| TLAST | 512샘플마다 (`TLAST_N=512` parameter) |
| 백프레셔 | stall (TREADY 기반) |
| 래퍼 구조 | 코어를 포함하는 새 top |
| 모듈명 | `fir_decimator_transposed_n43_axis_top` |
| TDATA 폭 | 16비트 (패딩 없음) |
| S_AXIS_TLAST 입력 | 포트 선언, 내부 로직 미연결 |
| 미사용 신호 | TSTRB/TKEEP/TID/TDEST/TUSER 포함 안 함 |
| 포트 이름 | AXI 관례 (`aclk`, `aresetn`, `*_axis_*`) |
| 출력 버퍼 | depth-3 (reg0/reg1/reg2), `s_axis_tready = !valid2` |

---

## 3. 리셋 방식

**결정**: 동기 액티브 로우 (`aresetn`), 래퍼 내부에서 `rst = ~aresetn`으로 코어에 전달

기존 코어는 비동기 액티브 하이 리셋(`posedge rst`)을 사용한다. AXI 표준 관례는 동기 액티브 로우(`aresetn`)를 요구하며, Vivado IP 패키저가 `aresetn`을 자동으로 리셋 핀으로 인식한다. 코어를 수정하면 기존 TB와 시뮬레이션 자산이 무효화되므로 래퍼 경계에서 극성만 반전하는 방식을 택한다.

코어를 동기 리셋으로 변환하는 작업은 타이밍 영향 분석이 필요한 별도 작업이며 현 단계의 목표와 무관하다.

---

## 4. TLAST 처리

**결정**: M_AXIS 출력에서 512샘플마다 TLAST 펄스 (`TLAST_N = 512`, Verilog parameter)

선택지 비교:

| 방식 | 동작 | 문제 |
|---|---|---|
| 매 샘플 TLAST=1 | 2바이트짜리 DMA 전송 반복 | 전송당 인터럽트 → CPU 폭주 |
| N샘플마다 TLAST | N샘플 블록 단위 전송 | N을 DMA 설정과 맞춰야 함 |
| TLAST 없음 | DMA 단순 모드에서 바이트카운트로만 완료 | Scatter-gather 불가, 카운트 불일치 시 DMA hang |

N=512 선택의 1차 근거는 하드웨어 FFT IP 프레임 크기와의 정합이다. Zybo Z7-20에서 Xilinx FFT IP를 512포인트로 구성하면, FFT IP는 512샘플을 한 프레임으로 처리한다. TLAST가 512번째 샘플에 오지 않으면 FFT IP가 프레임 경계를 인식하지 못한다. N=512는 FFT IP 프레임 크기가 강제하는 값이다.

2차 근거는 수치 검증이다. 시스템 파라미터: Fs=100MHz, M=2이므로 Fs_out=50MHz.

| 항목 | 계산 | 결과 |
|---|---|---|
| 블록 주기 | 512 / 50MHz | 10.24 µs |
| 주파수 분해능 | 50MHz / 512 | 97.6 kHz/bin |
| 패스밴드 내 유효 bin 수 | 15MHz / (50MHz/512) | 154 bins |
| DMA 전송 크기 | 512 × 2 bytes | 1024 bytes |

N=256이면 195kHz/bin으로 분해능이 절반이 되고, N=1024이면 블록 주기가 20.48µs로 두 배가 된다. 512는 분해능·레이턴시·DMA 크기의 균형점이다.

`TLAST_N`을 parameter로 선언하는 이유는 Step 8에서 Python FFT 블록 크기가 바뀔 경우 RTL 재합성 없이 parameter 값 변경만으로 대응하기 위함이다. TLAST 카운터는 M_AXIS 전송(TVALID & TREADY가 동시에 1인 클럭)을 세어 `TLAST_N`번째에 TLAST를 펄스로 내고 0으로 초기화한다.

**S_AXIS_TLAST 입력**: DMA MM2S가 전송 끝에 TLAST를 보내지만, 코어는 패킷 경계와 무관하게 연속 스트림을 처리한다. TLAST를 받아 코어를 리셋하면 파이프라인 상태가 날아가 다음 패킷 첫 샘플들이 오염되고, 무시하면 연결 자체가 무의미하다. 따라서 내부 로직에는 연결하지 않는다. 단, 포트 선언은 유지해야 한다. Vivado IP 패키저가 `s_axis_tlast` 없이는 AXI-Stream 인터페이스가 불완전하다고 판단하고, Block Design에서 DMA의 M_AXIS_MM2S_TLAST 핀이 연결처를 찾지 못해 DRC 경고가 발생하기 때문이다.

---

## 5. 백프레셔

**결정**: stall — M_AXIS_TREADY가 0이면 S_AXIS_TREADY도 0으로 내려 입력을 멈춤

데이터 유실과 실시간성 저하 중 무엇이 더 큰 손실인가를 기준으로 판단한다. FIR 출력 샘플이 유실되면 FFT 결과에 위상 불연속과 스펙트럼 아티팩트가 발생하며 복구 수단이 없다. 반면 stall로 인한 레이턴시 증가는 DMA 버퍼 크기(512샘플 = 10.24µs)로 흡수된다.

AXI-Stream 명세에서 TREADY=0으로 인한 일시 정지는 정상 동작으로 정의되어 있다. DMA는 이 동작을 기본으로 가정하고 설계된다.

출력 버퍼는 reg0/reg1/reg2 depth-3 구조다. stall 조건은 `s_axis_tready = !valid2`이다.

`valid2`는 등록된(registered) 신호이므로 stall이 1사이클 늦게 전파된다. 이 지연 동안 in_valid가 최대 3번 새어 들어가고, FIR 3-cycle 파이프라인 + M=2 조합상 그 중 최대 2개가 decimated 출력으로 emerge한다. depth-3이 이를 모두 수용하는 최소 크기다.

```
valid2=1 (reg2 꽉 참)
    → S_AXIS_TREADY = 0
    → 새 샘플 진입 차단
    → 파이프라인 잔류 샘플은 reg0/reg1/reg2가 흡수
```

---

## 6. TDATA 폭

**결정**: 16비트, 패딩 없음

AXI-Stream 명세는 TDATA를 8의 배수 비트로 요구한다. 샘플 포맷 Q1.15는 부호 있는 16비트 2의 보수 정수이며, 16 = 2×8이므로 명세를 그대로 만족한다.

비트 배치는 TDATA[15:0] = sample[15:0]로 직접 대응된다. 부호 비트(MSB)는 TDATA[15]에, 소수부 최하위 비트는 TDATA[0]에 위치한다. DMA가 메모리에 쓸 때 little-endian 기준으로 하위 바이트(TDATA[7:0])가 낮은 주소에 저장되며, Python에서 `np.frombuffer(..., dtype=np.int16)`으로 바로 읽으면 부호와 스케일이 자동으로 맞는다.

32비트로 패딩하지 않는 이유는 두 가지다. 첫째, DMA 전송 크기가 두 배로 늘어나 메모리 대역폭이 낭비된다. 둘째, Python에서 `dtype=np.int32`로 읽은 뒤 상위 16비트를 버리는 변환 코드가 추가로 필요해진다.

---

## 7. 래퍼 구조와 모듈명

**결정**: 새 파일 `fir_decimator_transposed_n43_axis_top.v`가 기존 코어를 instantiate, 기존 파일 수정 없음

기존 코어를 직접 수정하면 Step 4까지 검증된 TB(`tb_fir_decimator_transposed_n43_top.v`)와 시뮬레이션 벡터가 무효화된다. 래퍼를 별도 파일로 분리하면 코어 단독 TB는 그대로 유지되고, 래퍼에 대한 AXI-Stream TB를 독립적으로 추가할 수 있다.

모듈명 `fir_decimator_transposed_n43_axis_top`은 기존 패턴(`fir_decimator_transposed_n43_top`)에 `_axis`만 추가한 것이다. Vivado IP 패키저는 top 모듈 이름을 IP 이름으로 사용하므로, 인터페이스 종류가 이름에 명시되는 편이 IP 카탈로그에서 구분하기 쉽다.

포트 이름은 AXI 관례를 따른다.

```
aclk, aresetn
s_axis_tvalid, s_axis_tready, s_axis_tdata[15:0], s_axis_tlast
m_axis_tvalid, m_axis_tready, m_axis_tdata[15:0], m_axis_tlast
```

Vivado IP 패키저가 `aclk`/`aresetn`/`*_axis_*` 패턴을 자동으로 인터페이스로 인식한다. Step 6 Block Design에서 수동 포트 매핑 없이 자동 연결이 가능해진다.

---

## 8. 이 결정들이 갖는 의미

각 결정은 독립적인 편의 선택이 아니라 Step 6, 7, 8의 동작 요구사항이 역방향으로 투영된 제약이다. 리셋을 `aresetn`으로 맞추지 않으면 Vivado Block Design에서 PS 리셋 신호와 수동 연결해야 한다. TLAST를 FFT IP 프레임 크기와 맞추지 않으면 Step 8 Python 시각화가 위상이 어긋난 FFT 결과를 만든다. 백프레셔 stall이 없으면 DMA 버퍼 언더런 시 FFT 입력 데이터가 오염된다. TDATA를 16비트로 유지하지 않으면 Python 수신 코드에 불필요한 변환이 생긴다. 이 문서의 결정들은 전체 파이프라인이 처음부터 올바르게 맞물리기 위한 사전 계약이다.
