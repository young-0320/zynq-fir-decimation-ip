# 19. PS-PL DMA Integration Design Overview

- 작성일: 2026-05-06
- 단계: 11
- 목적: PS-PL DMA 연동을 위해 Vivado Block Design에서 구성할 IP와 데이터 흐름 정리
- 선행 문서: `docs/log/18_axis_buffer_overflow_fix_and_tb_robustness.md`

## 1. Zynq 구조 개요

Zynq-7000 SoC는 두 영역으로 나뉜다.

- **PS (Processing System)**: ARM Cortex-A9 + DDR3 컨트롤러. C 코드가 실행되는 영역
- **PL (Programmable Logic)**: FPGA 패브릭. 우리가 만든 FIR IP가 올라가는 영역

PS와 PL은 AXI 버스로 연결된다. PS가 PL에게 명령을 내리거나, PL이 PS의 DDR 메모리에 직접 접근하는 경로가 이 버스를 통해 이루어진다.

---

## 2. Block Design에 필요한 IP

### 직접 추가하는 IP (3개)

| IP | 출처 | 역할 |
|---|---|---|
| **ZYNQ7 Processing System** | Xilinx 기본 제공 | ARM 코어, DDR 컨트롤러, HP0 포트 노출 |
| **AXI Direct Memory Access** | Xilinx 기본 제공 | DDR ↔ AXI-Stream 브리지 |
| **fir_decimator_n43_axis** | 우리가 만든 RTL | N=43 FIR 필터 + M=2 데시메이터 |

### Vivado가 자동으로 추가하는 IP (3개, Run Connection Automation 시)

| IP | 역할 |
|---|---|
| **Processor System Reset** | PS 리셋 신호를 PL 클럭 도메인에 동기화 |
| **AXI SmartConnect** | PS GP0 → DMA S_AXI_LITE 제어 경로 인터커넥트 |
| **AXI Interconnect** | DMA M_AXI_MM2S / M_AXI_S2MM → PS HP0 데이터 경로 인터커넥트 (SI=2, MI=1) |

---

## 3. AXI 버스 종류

AXI는 단일 프로토콜이 아닌 계열이다. 이 시스템에서 세 종류가 쓰인다.

| 종류 | 특성 | 이 시스템에서 쓰이는 곳 |
|---|---|---|
| **AXI4-Lite** | 저속, 레지스터 제어용 | PS GP0 → AXI DMA (PS가 DMA에 명령) |
| **AXI4** | 고속, 버스트 메모리 접근 | AXI DMA ↔ PS HP0 (DMA가 DDR 읽기/쓰기) |
| **AXI4-Stream** | 단방향 스트리밍, 주소 없음 | AXI DMA ↔ FIR IP (데이터 이동) |

---

## 4. 포트 연결 구조

```
PS M_AXI_GP0  ──► SmartConnect ──► DMA S_AXI_LITE   (제어)
PS S_AXI_HP0  ◄──────────────────► DMA M_AXI_MM2S   (DDR 읽기)
PS S_AXI_HP0  ◄──────────────────► DMA M_AXI_S2MM   (DDR 쓰기)

DMA M_AXIS_MM2S ──► FIR S_AXIS                       (DDR → FIR)
DMA S_AXIS_S2MM ◄── FIR M_AXIS                       (FIR → DDR)
```

DMA의 AXI-Stream 채널:
- **MM2S** (Memory-Mapped to Stream): DDR에서 읽어 AXI-Stream으로 출력
- **S2MM** (Stream to Memory-Mapped): AXI-Stream을 받아 DDR에 저장

---

## 5. 데이터 흐름

```
① PS (C 코드): 멀티톤 신호 합성
        ↓
② PS: 입력 샘플 배열을 DDR에 저장
        ↓
③ PS: DMA에 전송 명령 (MM2S 시작 주소, 길이)
        ↓
④ DMA MM2S: DDR → AXI-Stream → FIR S_AXIS (입력 전달)
        ↓
⑤ FIR IP: N=43 LPF 필터링 + M=2 데시메이션 (100MHz, 출력 샘플레이트 = 입력의 1/2)
        ↓
⑥ DMA S2MM: FIR M_AXIS → AXI-Stream → DDR (결과 저장)
        ↓
⑦ PS (C 코드): DDR에서 결과 배열 읽기 → UART로 출력
```

③~⑥ 구간에서 PS는 명령만 내리고, 실제 데이터 이동은 DMA가 CPU 없이 독립적으로 처리한다. 이것이 DMA를 쓰는 이유다.

---

## 6. FIR IP 삽입 방법: Module Reference

커스텀 IP를 Block Design에 넣는 방법은 두 가지다.

- **IP Packaging**: RTL을 `component.xml` + 메타데이터로 포장해 Vivado IP 카탈로그에 등록. Xilinx의 AXI DMA나 ZYNQ7 PS가 이 방식으로 배포된다. 다른 프로젝트에서도 카탈로그 검색으로 재사용 가능.
- **Module Reference**: RTL 파일을 프로젝트 소스에 추가하고, Block Design에서 `Add Module`로 직접 참조. 포장 과정 없음.

IP Packaging의 메타데이터 작성과 인터페이스 선언은 **여러 프로젝트에서 재사용할 때** 그 비용을 회수한다. 이 FIR IP는 이 Block Design 하나에서만 쓰이고, AXI-Stream 인터페이스도 이미 RTL에 구현되어 있다. 포장이 기능을 추가하지 않는 상황에서 IP Packaging은 오버헤드만 된다.

이 프로젝트는 Module Reference를 쓴다. 프로젝트에 포함된 RTL 소스:

- `rtl/transposed_form/n43/fir_decimator_n43_axis.v` ← Block Design에 삽입되는 최상위
- `rtl/transposed_form/n43/fir_decimator_n43.v`
- `rtl/transposed_form/n43/fir_n43.v`
- `rtl/transposed_form/decimator_m2_phase0.v`

---

## 7. 진행 순서

### 7-1. Vivado 프로젝트 생성
RTL 소스 4개 포함, Board: Zybo Z7-20 선택.

### 7-2. Create Block Design
이름: `bd_fir_dma`. Directory: Local to Project, Source Set: Design Sources 기본값 유지.

### 7-3. ZYNQ7 Processing System 추가 및 설정

캔버스 우클릭 → Add IP → `zynq` 검색 → ZYNQ7 Processing System 추가.
블록 더블클릭 → Re-customize IP에서 두 가지 설정.

**HP0 포트 활성화**
`PS-PL Configuration → HP Slave AXI Interface → S AXI HP0 Interface` 체크.

HP(High Performance) 포트는 PL이 PS의 DDR에 직접 접근하는 경로다. 기본적으로 비활성화되어 있다. DMA는 PL에 위치하고, DDR은 PS 영역에 있다. DMA가 DDR을 읽고 쓰려면 이 포트가 열려있어야 한다. GP(General Purpose) 포트는 PS→PL 방향 마스터 포트라서 이 용도로 쓸 수 없다.

**FCLK_CLK0 100MHz 확인**
`Clock Configuration → PL Fabric Clocks → FCLK_CLK0` 가 100MHz인지 확인.

FCLK_CLK0는 PS가 PL 전체에 공급하는 클럭이다. FIR IP는 Step 4에서 100MHz 기준으로 타이밍 클로저를 검증했다 (WNS=+0.278ns). PL 클럭이 이 주파수와 일치해야 타이밍이 보장된다.

### 7-4. AXI DMA 추가 및 설정
Add IP → `axi dma` 검색 → AXI Direct Memory Access 추가.
블록 더블클릭 → Re-customize IP에서 세 가지 확인.

**상단 공통 설정**

| 항목 | 값 | 설명 |
|---|---|---|
| Enable Scatter Gather Engine | 해제 | Simple DMA 모드. Scatter Gather는 디스크립터 체인을 메모리에 구성하고 C 코드에서 Buffer Descriptor 링을 직접 설정해야 한다. 연속 배열 하나를 전송하는 이 구조에선 시작 주소와 길이만 넘기는 Simple DMA로 충분하다 |
| Enable Micro DMA | 해제 | 기능 제한된 경량 DMA. 해당 없음 |
| Enable Multi Channel Support | 비활성 | Scatter Gather 전용. 해당 없음 |
| Enable Control/Status Stream | 비활성 | Scatter Gather 전용. 해당 없음 |
| Width of Buffer Length Register | 14 bits | 최대 전송 크기 2¹⁴ = 16KB. 4117샘플 × 2bytes ≈ 8KB이므로 충분 |
| Address Width | 32 bits | Zynq-7000은 32비트 주소 체계 |

**Read Channel (MM2S) — DDR → FIR 방향**

| 항목 | 값 | 설명 |
|---|---|---|
| Number of Channels | 1 | 채널 하나면 충분 |
| Memory Map Data Width | 32 | DDR(HP0) 쪽 버스 폭. 32비트 표준 |
| Stream Data Width | **16** | FIR `s_axis_tdata` 폭과 일치해야 한다. 불일치 시 데이터 정렬이 깨짐 |
| Max Burst Size | 16 | DDR 읽기 시 한 번에 전송할 최대 beat 수. 기본값으로 충분 |
| Allow Unaligned Transfers | 해제 | 16비트 샘플은 정렬 보장됨 |

**Write Channel (S2MM) — FIR → DDR 방향**

| 항목 | 값 | 설명 |
|---|---|---|
| Number of Channels | 1 | 채널 하나면 충분 |
| Memory Map Data Width | 32 (AUTO) | DDR 쪽 버스 폭. Read Channel과 동일 |
| Stream Data Width | **16 (MANUAL)** | FIR `m_axis_tdata` 폭과 일치해야 한다 |
| Max Burst Size | 16 | DDR 쓰기 시 한 번에 전송할 최대 beat 수 |
| Allow Unaligned Transfers | 해제 | 정렬 보장됨 |

**하단**

| 항목 | 값 | 설명 |
|---|---|---|
| Enable Single AXI4 Data Interface | AUTO/해제 | MM2S와 S2MM이 DDR 포트를 각각 따로 사용. 동시 읽기+쓰기 가능 |

### 7-5. FIR Module Reference 추가
캔버스 우클릭 → `Add Module` → `fir_decimator_n43_axis` 선택.

### 7-6. Run Connection Automation
캔버스 상단 배너 클릭. 목록에 나타나는 항목 2개와 의미:

| 항목 | 연결되는 경로 | 설명 |
|---|---|---|
| axi_dma_0 → S_AXI_LITE | PS GP0 → SmartConnect → DMA S_AXI_LITE | PS가 DMA 레지스터에 명령을 쓰는 제어 경로 |
| processing_system7_0 → S_AXI_HP0 | DMA M_AXI_MM2S/S2MM → PS HP0 | DMA가 DDR을 읽고 쓰는 데이터 경로 |

모두 체크하고 OK. Vivado가 SmartConnect, Processor System Reset을 자동 생성하고 클럭/리셋도 배선한다.

FIR의 AXI-Stream 포트(S_AXIS, M_AXIS)는 이 목록에 나타나지 않는다. Vivado가 DMA의 어느 채널을 FIR의 어느 포트에 연결할지 자동으로 판단하지 못하기 때문이다. 다음 단계에서 수동으로 연결한다.

### 7-7. AXI-Stream 수동 연결
Run Connection Automation 이후 DMA ↔ FIR 간 AXI-Stream 포트는 미연결 상태다. 수동으로 연결:

| DMA 포트 | FIR 포트 | 방향 |
|---|---|---|
| M_AXIS_MM2S | S_AXIS | DMA → FIR (입력) |
| S_AXIS_S2MM | M_AXIS | FIR → DMA (출력) |

캔버스에서 포트 끝점을 드래그해 연결하거나, 포트 위에서 우클릭 → `Make Connection`으로 연결한다.

### 7-8. Validate Design
캔버스 상단 체크 아이콘. 포트 미연결, 클럭 도메인 불일치 등 오류 확인.

### 7-9. Generate Bitstream
Synthesize → Implement → Generate Bitstream.

### 7-10. Export Hardware
File → Export Hardware → `.xsa` 파일 생성. Vitis에서 C 코드 작성 시 사용 (Step 7).

---

## 8. 트러블슈팅

### Bug 1: 클럭 미연결

**증상:** Validate Design에서 `[BD 41-758] /axi_dma_0/m_axi_s2mm_aclk is not connected to a valid clock source`

**원인:** Run Connection Automation이 DMA의 `m_axi_s2mm_aclk`를 자동 연결하지 않았다. `s_axi_lite_aclk`, `m_axi_mm2s_aclk`도 동일하게 미연결 상태일 수 있다.

**해결:** DMA의 모든 aclk 포트(`s_axi_lite_aclk`, `m_axi_mm2s_aclk`, `m_axi_s2mm_aclk`)를 PS의 `FCLK_CLK0`에 수동 연결.

---

### Bug 2: DRC NSTD-1 (I/O Standard 미지정)

**증상:**
```
[DRC NSTD-1] Unspecified I/O Standard: 39 out of 39 logical ports use I/O standard value 'DEFAULT'
Problem ports: m_axis_tdata[15:0], s_axis_tdata[15:0], aclk, aresetn, ...
```

**원인:** Vivado BD에서 포트를 드래그할 때 다른 IP의 포트 위에 정확히 올려놓지 않고 빈 캔버스에 drop하면, Vivado가 자동으로 "Make External"을 실행해 외부 포트(FPGA 물리 핀)를 생성한다. FIR의 AXI-Stream 포트들이 DMA 내부 연결이 아닌 FPGA 핀으로 노출된 것이다.

**해결:**
1. TCL 콘솔에서 `get_bd_ports *`로 외부 포트 존재 확인
2. 잘못 생성된 외부 포트 삭제
3. FIR 포트를 DMA 포트 위에 정확히 드래그해서 내부 연결로 재연결
4. 포트 드래그 시 반드시 대상 IP 포트 위에서 초록 체크가 나타날 때 drop

---

### Bug 3: 합성 Top 오류 + XDC 충돌

**증상:** 비트스트림 생성 시 DRC NSTD-1 에러가 지속됨. 합성 로그에 `synth_design -top fir_decimator_n43_axis`가 찍히고, `zybo_n43.xdc`의 `clk` 포트 미매칭 CRITICAL WARNING 발생.

**원인:** 두 가지가 겹쳤다.
- 합성 top이 `bd_fir_dma_wrapper`가 아닌 `fir_decimator_n43_axis`로 설정되어 Block Design을 무시하고 FIR RTL을 standalone top으로 합성
- Step 4에서 쓰던 `zybo_n43.xdc`가 프로젝트에 남아있어 `clk` 포트 제약이 충돌

**해결:**
```tcl
set_property top bd_fir_dma_wrapper [current_fileset]
```
Sources → Constraints → `zybo_n43.xdc` 우클릭 → `Disable File`

---

## 10. Block Design TCL 추출 및 재현

Block Design은 Vivado 프로젝트 파일(.xpr) 안에만 존재한다. 프로젝트가 유실되거나 다른 환경에서 재현해야 할 때를 대비해 `write_bd_tcl`로 Block Design 전체를 TCL 파일로 추출해 레포에 보관한다.

### 추출 명령

Block Design이 열린 상태에서 Vivado TCL Console에서 실행:

```tcl
write_bd_tcl -force /home/young/dev/10_zynq-fir-decimation-ip/vivado/bd_fir_dma.tcl
```

추출 결과: `vivado/bd_fir_dma.tcl`

### 포함 내용

`write_bd_tcl`이 추출하는 정보:
- 모든 IP VLNV (버전 포함: `processing_system7:5.5`, `axi_dma:7.1` 등)
- IP 파라미터 설정 전체 (SG=0, stream width=16 등)
- 모든 배선 연결 (AXI, AXI-Stream, 클럭, 리셋)
- 주소 할당 (`assign_bd_address`)
- 마지막에 `validate_bd_design` 자동 호출

### 재현 방법

다른 머신에서 Block Design을 재현하려면:

1. Vivado 2024.2 + Zybo Z7-20 보드 파일 설치
2. RTL 소스 4개가 포함된 Vivado 프로젝트 생성 (7-1 참고)
3. Vivado TCL Console에서:

```tcl
source vivado/bd_fir_dma.tcl
```

RTL 소스 없이 sourcing하면 `fir_decimator_n43_axis` 모듈을 찾지 못해 실패한다.

---

## 9. 의미

Step 5까지는 PL 단독으로 동작하는 IP를 만드는 작업이었다. Step 6부터는 PS와 PL이 함께 동작하는 시스템을 구성한다. Block Design은 Verilog를 직접 쓰는 것이 아니라 IP 간 연결을 정의하는 작업이다. 우리가 만든 FIR IP는 이 시스템에서 AXI-Stream 데이터를 받아 필터링하는 하나의 블록으로 동작한다.
