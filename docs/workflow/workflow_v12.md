# FIR Decimation 프로젝트 워크플로우 v12

- 작성일: 2026-05-13
- 이전 버전: `workflow_v11.md`
- 변경 배경: JTAG ELF 로딩 최종 실패 → SD카드 부팅으로 전환. Block Design 재생성 후 진행.

---

## 1. v11 대비 변경 사항

| 항목 | v11 | v12 |
|---|---|---|
| 펌웨어 다운로드 방식 | JTAG (`xsdb dow`) | **SD카드 부팅 (BOOT.bin)** |
| 사전 작업 | Vitis ELF 빌드 → xsdb 다운로드 | **BD 재생성 → 비트스트림/XSA 재빌드 → BOOT.bin 생성** |
| 현재 블로커 | 보드 물리 연결 | **SD카드 배송 대기** |
| 진단 변수 | 비트스트림 + ELF + ps7_init 동시 검증 | **ps7_init을 레퍼런스 일치 상태로 고정 후 진행** |

---

## 2. JTAG 폐기 사유 요약

`docs/log/24`, `docs/log/27` 상세 기록. 핵심만:

- DDR 쓰기 시 byte lane 3(DQ[31:24])이 비결정적으로 오염됨 (`0xDEADBEEF` → `0x00ADBEEF` 등)
- OCM(0x00000000) 쓰기는 단일·버스트 모두 완벽 → JTAG/DAP/AXI 무결, 문제는 AXI → DDRC → DDR chip 경로
- 시도해본 모든 우회(burst, dow, mwr+mrd flush, after, pexpect REPL barrier, jtag frequency, board delay 수정, 레퍼런스 ps7_init 적용) 모두 실패
- 미해결 근본 원인 가설 2개 공존:
  1. xsdb JTAG AXI 마스터의 byte[3] 파이프라인 commit 타이밍
  2. DDR PHY byte lane 3 write leveling 마진 부족

---

## 3. SD카드 방향 선택 이유

FSBL(First Stage Boot Loader)이 BOOT.bin 안에서 실행되어:

- DDR을 PS 내부에서 하드웨어적으로 초기화
- 비트스트림을 PL에 로드
- ELF를 DDR로 복사 후 CPU에 점프

→ JTAG 쓰기 경로 완전 우회. byte lane 3 타이밍 문제 영향 없음.

**진단 가치:**

- BD를 깨끗하게 재생성해 ps7_init.tcl이 Digilent 레퍼런스와 일치하는 상태에서 SD 부팅
- 성공 → 프로젝트 완성
- 실패 → ps7_init 변수 통제됐으므로 **HW 결함으로 거의 확정** (보드 교체 검토)

---

## 4. SD카드 도착 후 진행 순서

### Step A: Block Design 재생성

기존 BD는 GUI 캐시 버그로 Preset이 `None` 상태였음 (log 27 Phase 4). 깨끗한 상태로 재생성.

**필수 체크포인트:**

1. 새 Vivado 프로젝트 생성, Zybo Z7-20 보드 파일 타겟 명시
2. Zynq IP 배치 후 GUI 상단의 `Run Block Automation` 배너 강제 실행
   - 이게 보드 파일의 `preset.xml`을 IP 내부로 주입함
3. Zynq IP 더블클릭 → DDR Configuration → **`Board Delay` 컬럼에 0.xxx ns 수치가 채워져 있는지 GUI에서 눈으로 확인** (`0ns` 면 실패)
4. AXI DMA, AXI-Stream FIR, UART1 연결 (기존 `vivado/bd_fir_dma.tcl` 참조)
5. 비트스트림 생성

빌드 명령:

```bash
source ~/Xilinx/Vivado/2024.2/settings64.sh
mkdir -p build/vivado
vivado -mode batch \
  -journal build/vivado/vivado.jou \
  -log build/vivado/vivado.log \
  -source vivado/build_bd_fir_dma.tcl
```

**완료 기준:**

- `build/vivado/fir_decimator_trans_n43.runs/impl_1/bd_fir_dma_wrapper.bit` 존재
- `build/output/bd_fir_dma_wrapper.xsa` 존재

### Step B: ps7_init.tcl 검증

XSA에 동봉된 ps7_init.tcl이 Digilent 공식 Z7-20 레퍼런스와 일치하는지 diff 확인. log 27 Phase 8-2 기준 누락된 항목들이 채워졌는지 확인.

**최소 확인 항목:**

```
0xF8000180  0x00100A20   ← DDRIOB
0xF8000190  0x00100500   ← DDRIOB
mask_delay 0xF8F00200 × 5  ← DDR PHY
```

**DDRC 타이밍 레지스터 5개 값:**

| 레지스터 | 레퍼런스 (Z7-20) |
|---|---|
| `0xF8006004` | `0x00001081` |
| `0xF8006014` | `0x0004281A` |
| `0xF8006018` | `0x44E458D2` |
| `0xF800601C` | `0x720238E5` |
| `0xF8006030` | `0x00040930` |

레퍼런스와 다르면 BD 설정(Preset 누락 또는 보드 파일 미인식)을 의심하고 Step A로 복귀.

### Step C: Vitis ELF 재빌드

새 XSA 기준으로 BSP + ELF 재생성.

```bash
rm -rf build/vitis
vitis -s vitis/build_fir_decimator_demo.py
```

**완료 기준:** `build/output/fir_decimator_demo.elf` 갱신 (mtime이 XSA보다 최신)

### Step D: BOOT.bin 생성

`bootgen`으로 FSBL + 비트스트림 + ELF를 하나의 BOOT.bin으로 패키징.

```bash
cd /home/young/dev/10_zynq-fir-decimation-ip
bootgen -arch zynq -image build/output/fir_decimator_demo.bif \
        -o build/output/BOOT.bin -w on
```

`fir_decimator_demo.bif` 내용 참조:

```
//arch = zynq; split = false; format = BIN
the_ROM_image:
{
    [bootloader]<FSBL.elf 경로>
    <bd_fir_dma_wrapper.bit 경로>
    <fir_decimator_demo.elf 경로>
}
```

**완료 기준:** `build/output/BOOT.bin` 생성, mtime이 ELF/XSA보다 최신

### Step E: SD카드 준비

1. SD카드를 **FAT32**로 포맷 (32GB 이하 권장, 64GB 이상은 exFAT 기본이라 별도 포맷 필요)
2. `build/output/BOOT.bin` 한 파일만 SD 루트에 복사
3. 다른 파일은 둬도 무방 (Zynq BootROM은 BOOT.bin만 읽음)

### Step F: 보드 부팅 및 검증

1. **JP5 점퍼를 SD 위치로 이동** (현재 JTAG → SD)
2. SD카드 삽입
3. USB 케이블 연결 (UART용)
4. 전원 공급
5. **DONE LED 점등 확인** (FSBL이 비트스트림 로드 완료)
6. UART 응답 확인:
   ```bash
   minicom -D /dev/ttyUSB1 -b 115200
   # minicom에서 입력: 3 5000000 20000000 30000000
   # binary 응답 수신 확인
   ```
7. Python FFT 검증:
   ```bash
   python sw/fir_decimator_demo.py --mode 1-1 --port /dev/ttyUSB1
   ```

**완료 기준:**

- [ ] DONE LED 점등
- [ ] minicom에서 명령 입력 후 binary 응답 수신
- [ ] Python 그래프에서 30MHz 피크가 출력 FFT에서 ≥60dB 감쇠

---

## 5. 단계별 완료 기준 요약

| 단계 | 확인 항목 | 방법 |
|---|---|---|
| Step A | BD 비트스트림 + XSA 생성 | 파일 존재 + Vivado WNS 양수 |
| Step B | ps7_init.tcl 레퍼런스 일치 | diff 명령 |
| Step C | ELF 갱신 | 파일 mtime |
| Step D | BOOT.bin 생성 | 파일 존재 |
| Step E | SD에 BOOT.bin 적재 | `ls /mnt/sd` |
| Step F-1 | FPGA 부팅 성공 | DONE LED |
| Step F-2 | 펌웨어 실행 | UART 응답 |
| Step F-3 | DSP 정상 동작 | Python FFT 그래프 |

---

## 6. 실패 시 분기 (HW 결함 판정 기준)

| Step F 결과 | 해석 | 다음 액션 |
|---|---|---|
| DONE LED 점등 안 됨 | FSBL이 비트스트림 로드 실패 | BOOT.bin 재생성, .bif 경로 확인 |
| DONE LED ✅ but UART 무응답 | FSBL → ELF 점프 실패 또는 펌웨어 hang | UART 포트 확인, ELF 재빌드, FSBL 로그 확인 (FSBL_DEBUG_INFO 빌드) |
| UART 응답 ✅ but 데이터 깨짐 | DDR에서 ELF/heap 손상 추정 | **HW 결함 가능성 농후 — 보드 교체 검토** |
| 시나리오 1-1 통과 | M4 완성, Plan A 계속 | Step 8 시나리오 1-2 진행 |

**HW 결함 확정 조건:** Step A~D가 ps7_init 레퍼런스 일치 상태에서 완료되었음에도 Step F가 실패하면 Zybo Z7-20 보드의 DDR 또는 DDRIOB 회로 결함을 강하게 의심해야 함. 다른 Z7-20 보드 + 동일 BOOT.bin으로 교차 검증 필요.

---

## 7. 마일스톤 현황

| 마일스톤 | 목표 시점 | 내용 | 상태 |
|---|---|---|---|
| M1 | 5월 1주차 | RTL 검증 환경 구축 | ✅ 완료 |
| M2 | 5월 3주차 | N=43 Transposed Form RTL + iverilog PASS | ✅ 완료 |
| M3 | 6월 1주차 | Vivado 100MHz 타이밍 클로저 | ✅ 완료 |
| **M4 (안전 마감선)** | **6월 말** | **AXI-Stream 래퍼 + PS-PL DMA + 보드 시연** | 🔄 SD카드 부팅 검증 대기 |
| M5 | 7월 2주차 | 실시간 시연 파이프라인 완성 | — |
| M6 | 7월 말 | 발표 준비 + 보고서 완성 | — |

---

## 8. 참고 문서

- `docs/log/24_jtag_download_troubleshooting.md` — JTAG 시도 1차 트러블슈팅 기록
- `docs/log/26_vivado_rebuild_ddr_misconfiguration_and_axi_stream_interface.md` — Vivado 재빌드 / DDR 미설정 이슈
- `docs/log/27_ddr_msb_corruption_investigation.md` — JTAG byte[3] 오염 근본 원인 조사 (Phase 1~9, 최종 SD 전환 결정)
- `docs/workflow/workflow_v11.md` — JTAG 방식 워크플로우 (폐기)
