# FIR Decimation 프로젝트 워크플로우 v10

- 작성일: 2026-05-04
- 이전 버전: workflow_v9.md
- 변경 배경: Step 1~4 완료, Step 5 AXI-Stream 래퍼 구현 진입 — 설계 결정사항 반영

---

## 1. v9 대비 변경 사항

| 항목 | v9 | v10 |
|---|---|---|
| Step 1~4 | 진행 중 | 모두 완료 ✅ |
| AXI-Stream 래퍼 모듈명 | `fir_decimator_axi_wrapper.v` | `fir_decimator_transposed_n43_axis_top.v` |
| 래퍼 출력 버퍼 구조 | 미정 | depth-2 레지스터 (reg0/reg1) 확정 |
| TLAST 방식 | 미정 | 512샘플마다, `TLAST_N` parameter |
| 리셋 인터페이스 | 미정 | 동기 액티브 로우 `aresetn` |
| 백프레셔 방식 | 미정 | stall (`s_axis_tready` 기반) |

설계 결정 근거 전문: `docs/log/17_axi_stream_wrapper_design_decisions.md`

---

## 2. 현재 진행 중인 작업 단위

**Step 5 — AXI-Stream 래퍼 구현**

기존 코어(`fir_decimator_transposed_n43_top`)를 수정 없이 포함하는 새 top 모듈을 작성한다.
DMA MM2S → S_AXIS → 코어 → M_AXIS → DMA S2MM 흐름을 완성하는 것이 목표다.

```
DMA MM2S → [S_AXIS] → [FIR+decimator core] → [depth-2 출력 버퍼] → [M_AXIS] → DMA S2MM
              tready                              reg0 / reg1
              제어
```

### 내부 블록 구성

**A. 리셋 변환**
```
wire rst_core = ~aresetn;
```
코어의 비동기 액티브 하이 리셋에 전달.

**B. 입력 핸드셰이크 (S_AXIS → 코어)**
```
s_axis_tready  = !valid2          // reg2 빌 때만 허용
core.in_valid  = s_axis_tvalid && s_axis_tready
core.in_sample = s_axis_tdata
s_axis_tlast   : 포트 선언, 내부 미연결
```

**C. depth-3 출력 버퍼 (코어 → M_AXIS)**
```
reg0 : M_AXIS에 내미는 현재 샘플 (tvalid/tdata 직결)
reg1 : reg0 점유 중 첫 번째 대기 슬롯
reg2 : reg1 점유 중 두 번째 대기 슬롯

out_valid=1, valid0=0                    → reg0 로드
out_valid=1, valid0=1, valid1=0          → reg1 로드
out_valid=1, valid0=1, valid1=1, valid2=0 → reg2 로드
m_axis_tready=1                          → reg0 소비, reg1→reg0, reg2→reg1 이동
s_axis_tready = !valid2
```
depth-3이 필요한 이유: `s_axis_tready = !validN`은 1사이클 지연이 있어 stall 직후 in_valid가 N+1번 새어 들어간다. FIR 3-cycle 파이프라인 + M=2 조합상 이 누출 샘플들이 최대 2개의 decimated 출력을 만들어낸다(T+2, T+4). depth-2는 T+4 출력 시 overflow. depth-3이 safe boundary.

**D. TLAST 카운터**
```
M_AXIS 전송 성사(tvalid & tready)마다 카운터 +1
카운터 == TLAST_N-1 → m_axis_tlast=1, 카운터=0
```

### TB 설계 원칙

기존 `tb_fir_decimator_transposed_n43_top.v`는 `out_valid` 펄스마다 비교한다. AXI 래퍼 TB는 **M_AXIS 핸드셰이크 성사(tvalid & tready가 동시에 1인 클럭)** 시점에만 비교해야 한다. tvalid=1이어도 tready=0이면 전송이 아니므로 인덱스를 올리면 안 된다.

```verilog
// TB 비교 로직 핵심
always @(posedge aclk) begin
    if (m_axis_tvalid && m_axis_tready) begin
        // 이 시점에만 expected_mem[observed_count]와 비교
        // TLAST 검증도 이 시점
    end
end
```

### iverilog 컴파일 명령

```bash
iverilog -o sim_axis_top.out \
    rtl/transposed_form/decimator_m2_phase0.v \
    rtl/transposed_form/n43/fir_transposed_n43.v \
    rtl/transposed_form/n43/fir_decimator_transposed_n43_top.v \
    rtl/transposed_form/n43/fir_decimator_transposed_n43_axis_top.v \
    sim/rtl/tb/transposed_form/tb_fir_decimator_transposed_n43_axis_top.v
vvp sim_axis_top.out
```

기존 TB 컴파일 명령도 경로 변경 반영:
```bash
iverilog -o sim_top.out \
    rtl/transposed_form/decimator_m2_phase0.v \
    rtl/transposed_form/n43/fir_transposed_n43.v \
    rtl/transposed_form/n43/fir_decimator_transposed_n43_top.v \
    sim/rtl/tb/transposed_form/tb_fir_decimator_transposed_n43_top.v
vvp sim_top.out
```

### 현재 단계 완료 기준

- [x] `fir_decimator_transposed_n43_axis_top.v` 작성, iverilog 컴파일 통과
- [x] `tb_fir_decimator_transposed_n43_axis_top.v` TREADY=1 시나리오 — M_AXIS 핸드셰이크 기준 `expected_decim_q15.hex`와 출력 일치
- [x] 백프레셔 시나리오 — TREADY 주기적 LOW 동안 핸드셰이크 카운트 일치
- [x] TLAST 시나리오 — 512·1024번째 핸드셰이크에서 TLAST=1 확인
- [x] aresetn 시나리오 — 리셋 후 버퍼·카운터 초기화 확인

---

## 5. 다음 작업 순서

### Step 1~4 — 완료 ✅

| 단계 | 내용 | 결과 |
|---|---|---|
| Step 1 | N=43 RTL 벡터 생성 | ✅ |
| Step 2 | `fir_transposed_n43.v` + TB iverilog PASS | ✅ |
| Step 3 | `fir_decimator_transposed_n43_top.v` + TB PASS (4117 샘플) | ✅ |
| Step 4 | Vivado 100MHz 타이밍 클로저 WNS=+0.278ns | ✅ |

---

### Step 5 — AXI-Stream 래퍼 구현 ✅

```
rtl/transposed_form/n43/fir_decimator_transposed_n43_axis_top.v
sim/rtl/tb/transposed_form/tb_fir_decimator_transposed_n43_axis_top.v
```

구현 순서:
1. 모듈 skeleton — 포트 선언 + parameter + 코어 instantiate, iverilog 컴파일 통과
2. 리셋 변환 + 입력 핸드셰이크
3. depth-2 출력 버퍼 (reg0/reg1 로직)
4. TLAST 카운터
5. TB 작성 — TREADY=1 회귀 검증
6. 백프레셔 / TLAST / aresetn 시나리오 추가

---

### Step 6 — PS-PL DMA 연동

Vivado Block Design: Zynq PS + AXI DMA IP + FIR AXI-Stream IP 연결.

완료 기준:
- [ ] Block Design DRC PASS
- [ ] bare-metal C DMA 송수신 동작 확인

---

### Step 7 — bare-metal C + UART

완료 기준:
- [ ] 멀티톤 생성 및 DMA 송수신 동작
- [ ] UART 출력 PC 수신 확인

---

### Step 8 — PC Python FFT 실시간 시각화

시연 목표: 30MHz stopband tone이 필터 후 출력에서 제거되는 것을 실시간 스펙트럼으로 확인.

완료 기준:
- [ ] 실시간 스펙트럼 플롯 동작
- [ ] 필터 전/후 비교 시각적으로 명확

---

## 6. 마일스톤 및 일정

| 마일스톤 | 목표 시점 | 내용 | 상태 |
|---|---|---|---|
| M1 | 5월 1주차 | RTL 검증 환경 구축 (hex 벡터 생성) | ✅ 완료 |
| M2 | 5월 3주차 | N=43 Transposed Form RTL + iverilog PASS | ✅ 완료 |
| M3 | 6월 1주차 | Vivado 100MHz 타이밍 클로저 | ✅ 완료 |
| **M4 (안전 마감선)** | **6월 말** | **AXI-Stream 래퍼 + BRAM 오프라인 FFT 확인** | 🔄 진행 중 |
| M5 | 7월 2주차 | PS-PL DMA 연동 완료 | |
| M6 | 7월 3주차 | 실시간 시연 파이프라인 완성 | |
| M7 | 7월 말 | 발표 준비 + 보고서 완성 | |

**M4(6월 말)가 분기점이다.** M4 완성 여부로 Plan A/B를 판단한다.

### Plan A vs Plan B

**Plan A (목표):** Step 1~8 전체 완성 → 실시간 FFT 스펙트럼 시각화 시연

**Plan B (안전 마감):** Step 1~5 완성
- N=43 Transposed Form RTL 동작 확인
- AXI-Stream 래퍼
- BRAM 콜드 데이터 + PC Python 오프라인 FFT 스펙트럼 비교

---

## 7. 변경되지 않은 것

| 항목 | 상태 |
|---|---|
| 필터 스펙 (fp=15MHz, fs=25MHz, As≥60dB) | 유지 |
| N=43 탭 수 | 유지 |
| Q1.15 고정소수점 포맷 | 유지 |
| Python golden → RTL bit-exact 검증 방식 | 유지 |
| 입력 신호 멀티톤 프로파일 (5/20/30 MHz, 8192샘플) | 유지 |
| Zybo Z7-20 타겟 보드 | 유지 |
| Kaiser window β=5.653 | 유지 |
| ties-away-from-zero 반올림 | 유지 |
| 48-bit 누산기 | 유지 |
| Decimator 재사용 (decimator_m2_phase0.v) | 유지 |

---

## 8. 디렉토리 구조 현황

```
rtl/
├── direct_form/                            ✅ N=5 bring-up 완료
└── transposed_form/
    └── n43/
        ├── constrs/                        ✅
        ├── fir_transposed_n43.v            ✅ Step 2
        ├── fir_decimator_transposed_n43_top.v  ✅ Step 3
        └── fir_decimator_transposed_n43_axis_top.v  ← Step 5에서 생성

sim/
├── python/                                 ✅
├── output/                                 ✅
└── vectors/
    ├── direct_form/                        ✅
    └── transposed_form/n43/               ✅ Step 1

sim/rtl/tb/
├── direct_form/                            ✅
└── transposed_form/
    ├── tb_fir_transposed_n43.v            ✅ Step 2
    ├── tb_fir_decimator_transposed_n43_top.v  ✅ Step 3
    └── tb_fir_decimator_transposed_n43_axis_top.v  ← Step 5에서 생성

docs/log/
├── ...
├── 17_axi_stream_wrapper_design_decisions.md  ✅ Step 5 설계 결정
└── workflow_v10.md                            ✅ 현재 문서
```
