# FIR Decimation 프로젝트 워크플로우 v13

- 작성일: 2026-05-14
- 이전 버전: `workflow_v12.md`
- 변경 배경: JTAG 폐기 후 SD카드 부팅 준비 전, RTL → 베어메탈 C → BD 순으로 bottom-up 전수 재검증. 마지막 시도.

---

## 1. v12 대비 변경 사항

| 항목 | v12 | v13 |
|---|---|---|
| 시작점 | BD 재생성 (RTL 검증 생략) | **RTL 시뮬레이션 재실행 + 정적 체크** |
| 베어메탈 C | 검토 없음 | **fir_decimator_demo.c 정적 체크 추가** |
| 접근 방식 | 의심 지점 타겟 패치 | **bottom-up 전수 검증 후 진행** |

---

## 2. 검증 대상 파일 목록

| 레이어 | 파일 |
|---|---|
| RTL | `rtl/transposed_form/n43/fir_n43.v` |
| RTL | `rtl/transposed_form/decimator_m2_phase0.v` |
| RTL | `rtl/transposed_form/n43/fir_decimator_n43.v` |
| RTL | `rtl/transposed_form/n43/fir_decimator_n43_axis.v` |
| 베어메탈 C | `sw/fir_decimator_demo.c` |
| BD | Vivado Block Design (Zybo Z7-20 preset) |
| 초기화 | `ps7_init.tcl` (Digilent 레퍼런스와 diff) |

---

## Step A: RTL 시뮬레이션 재실행

```bash
cd /home/young/dev/10_zynq-fir-decimation-ip/sim
make clean
make run_all 2>&1 | tee /tmp/sim_run_all.log
```

각 TB의 **PASS 기준**:

| TB | 검증 내용 | PASS 판단 기준 |
|---|---|---|
| `tb_fir_n43.sv` | fir_n43 단독: 계수·파이프라인·반올림·포화 | `$finish` 정상 도달, 출력 값 오차 ≤ 1 LSB |
| `tb_fir_decimator_n43.sv` | FIR + M=2 데시메이터 체인 | 4117 samples 출력 완료, SNR 기준 통과 |
| `tb_fir_decimator_n43_axis.sv` | AXI-Stream 래퍼: TLAST·Auto-Flush·핸드셰이크 | DMA 1회 전송 시뮬 완료, S2MM TLAST 정상 수신 |

`run_all` 출력에서 `ERROR` / `FAIL` / `mismatch` 문자열이 없어야 함:

```bash
grep -iE "error|fail|mismatch" /tmp/sim_run_all.log
# 출력 없으면 PASS
```

---

## Step B: RTL 정적 체크리스트

시뮬 PASS만으로는 놓칠 수 있는 구조적 결함을 코드 레벨에서 확인.

### B-1. `fir_n43.v`

| 확인 항목 | 기대값 | 확인 방법 |
|---|---|---|
| 계수 대칭성 | `h[k] == h[42-k]` (k=0..20) | 파이썬 또는 눈으로 21쌍 대조 |
| 누적기 폭 | `signed [47:0]` (48-bit, Q2.30) | 선언부 확인 |
| 파이프라인 단수 | 3단 (곱셈→누적→반올림/포화) | always 블록 개수 및 순서 확인 |
| z[42] 처리 | `z[43]` 없이 `prod_reg[42]`만 가산 | B안 주석 + 코드 일치 확인 |
| 반올림 방식 | ties-away-from-zero (Q1.15 하위 15비트) | round_reg 계산식 확인 |
| 포화 범위 | `[-32768, 32767]` | out_sample 클리핑 분기 확인 |
| out_valid 지연 | in_valid 기준 3클럭 후 | TB 파형 또는 코드 레지스터 체인 확인 |

```bash
# 계수 대칭성 빠른 확인 (Python)
python3 -c "
import re
txt = open('rtl/transposed_form/n43/fir_n43.v').read()
nums = re.findall(r'16\'sh([0-9A-Fa-f]+)', txt)
h = [int(x, 16) if int(x,16) < 0x8000 else int(x,16)-0x10000 for x in nums]
assert len(h) == 43, f'계수 개수 오류: {len(h)}'
for k in range(21):
    assert h[k] == h[42-k], f'비대칭: h[{k}]={h[k]} != h[{42-k}]={h[42-k]}'
print('계수 대칭성 OK, 개수 43개 OK')
print('h[0..4]:', h[:5], '  h[21](중앙):', h[21])
"
```

### B-2. `decimator_m2_phase0.v`

| 확인 항목 | 기대값 |
|---|---|
| 리셋 후 `keep_next` | `1` (첫 샘플이 phase 0) |
| 출력 조건 | `in_valid & keep_next`일 때만 `out_valid = 1` |
| `keep_next` 토글 | `in_valid` 매 클럭마다 반전 |

### B-3. `fir_decimator_n43.v`

| 확인 항목 | 기대값 |
|---|---|
| 계층 순서 | `in → fir_n43 → decimator_m2_phase0 → out` (FIR 먼저, 다운샘플 나중) |
| `in_valid` 전달 | 최상위 `in_valid`가 `fir_n43.in_valid`에 직결 (전체 입력 샘플이 FIR 통과) |
| `fir_out_valid` 전달 | `fir_n43.out_valid` → `decimator.in_valid` |
| `out_valid` 비율 | 입력 N 샘플 → 출력 N/2 샘플 |

### B-4. `fir_decimator_n43_axis.v`

| 확인 항목 | 기대값 |
|---|---|
| `s_axis_tready` 식 | `core_ready & ~flush_active` |
| `core_in_valid` 식 | `(s_axis_tvalid & s_axis_tready) \| (flush_active & core_ready)` |
| `core_in_sample` | flush 중 `16'sd0`, 정상 시 `s_axis_tdata` |
| `target_out_cnt` 계산 | `s_axis_tlast` 시점 `(in_cnt + 1) >> 1` (in_cnt는 tlast 포함 카운트) |
| Skid buffer 깊이 | 3단 (`valid1, valid2, valid3`) |
| TLAST 동기화 | `tlast0, tlast1, tlast2` 데이터와 동일 타이밍 진행 |
| `waiting_for_last_out` 해제 | `out_cnt == target_out_cnt`이고 `core_ready`일 때 |

---

## Step C: 베어메탈 C 코드 체크리스트 (`fir_decimator_demo.c`)

### C-1. DMA 주소 및 크기

| 항목 | 기대값 | 확인 방법 |
|---|---|---|
| `DMA_BASE` | `0x40400000` | BD `assign_bd_address` 결과와 일치 확인 |
| `N_IN` | `8192` | 입력 버퍼 크기 = MM2S LENGTH = 8192 × 2 = 16384 bytes |
| `N_OUT` | `4096` | 출력 버퍼 크기 = S2MM LENGTH = 4096 × 2 = 8192 bytes |
| `MM2S_LENGTH` 레지스터 값 | `8192 * 2 = 16384` | `dma_run()` 내 `N_IN * sizeof(int16_t)` 확인 |
| `S2MM_LENGTH` 레지스터 값 | `4096 * 2 = 8192` | `dma_run()` 내 `N_OUT * sizeof(int16_t)` 확인 |

### C-2. DMA 초기화 순서

PG021 기준 올바른 순서:

```
1. MM2S_DMACR bit[2] = 1  →  전체 코어 soft reset
2. MM2S_DMACR bit[2] == 0 대기  (self-clearing)
3. S2MM 먼저 arm: S2MM_DMACR.RS=1, S2MM_DA=dst, S2MM_LENGTH=N_OUT*2
4. MM2S 시작: MM2S_DMACR.RS=1, MM2S_SA=src, MM2S_LENGTH=N_IN*2
```

`sw/fir_decimator_demo.c`의 `dma_run()` 코드가 위 순서와 정확히 일치하는지 확인. **S2MM arm 전에 MM2S를 시작하면 데드락 발생.**

### C-3. 캐시 일관성

| 항목 | 위치 | 기대 동작 |
|---|---|---|
| `Xil_DCacheFlushRange(src_buf, ...)` | DMA TX 직전 | CPU가 DDR에 쓴 src_buf를 DMA가 올바르게 읽음 |
| `Xil_DCacheInvalidateRange(dst_buf, ...)` | DMA RX 완료 후 | DMA가 DDR에 쓴 dst_buf를 CPU가 캐시 stale 없이 읽음 |

두 호출 모두 `dma_run()` 내에 있고, **flush는 DMA 시작 전, invalidate는 IDLE 확인 후**에 위치해야 함.

### C-4. UART 프로토콜 일관성

Python 스크립트(`sw/fir_decimator_demo.py`)의 송수신 형식과 C 코드의 형식이 일치하는지:

| 방향 | C 코드 형식 | Python 기대 형식 |
|---|---|---|
| PC → PS | `"<n> <f1> <f2> ... <fn>\n"` (text) | `f"{n_tones} {' '.join(str(f) for f in freqs)}\n"` |
| PS → PC | `[0xDEADBEEF 4B][N_OUT 4B][int16 × N_OUT]` (binary LE) | magic=0xDEADBEEF, n=N_OUT, data=N_OUT samples |

---

## Step D: Block Design 재생성

기존 BD는 GUI 캐시 버그로 Preset `None` 상태였음(log 27 Phase 4). 깨끗하게 재생성.

```bash
source ~/Xilinx/Vivado/2024.2/settings64.sh
mkdir -p build/vivado
vivado -mode batch \
  -journal build/vivado/vivado.jou \
  -log build/vivado/vivado.log \
  -source vivado/build_bd_fir_dma.tcl
```

**필수 GUI 체크포인트** (배치 모드로 확인 불가, Vivado GUI에서 확인):

1. Zynq IP 배치 직후 상단 녹색 배너 `Run Block Automation` 클릭 (보드 파일 preset.xml 주입)
2. Zynq IP 더블클릭 → DDR Configuration → `Board Delay` 컬럼에 소수점 수치(예: `0.244 ns`) 채워져 있는지 확인 (`0 ns`이면 실패 → BD 폐기 후 재시작)
3. DDR 파트: `MT41K256M16 RE-125` (Z7-20)
4. AXI-Stream 연결: 번들 단위 연결(`M_AXIS ↔ S_AXIS_S2MM`), 개별 신호 연결 금지

**Tcl 검증 명령** (Vivado Tcl console에서):

```tcl
get_property CONFIG.PCW_UIPARAM_DDR_PARTNO [get_bd_cells /processing_system7_0]
# 기대값: MT41K256M16 RE-125

get_property CONFIG.PCW_UIPARAM_DDR_BUS_WIDTH [get_bd_cells /processing_system7_0]
# 기대값: 32 Bit
```

**완료 기준:**
- `build/vivado/fir_decimator_trans_n43.runs/impl_1/bd_fir_dma_wrapper.bit` 존재
- `build/output/bd_fir_dma_wrapper.xsa` 존재
- Vivado WNS ≥ 0

---

## Step E: ps7_init.tcl 검증

XSA에 동봉된 ps7_init.tcl이 Digilent 공식 Z7-20 레퍼런스와 일치하는지 확인.

```bash
# 현재 생성된 ps7_init.tcl
PROJ_INIT="build/output/bd_fir_dma_wrapper.xsa"  # 압축 해제 후 경로 확인 필요
# 또는
PROJ_INIT="build/vivado/fir_decimator_trans_n43.runs/impl_1/ps7_init.tcl"

# Digilent 레퍼런스 (저장된 위치 기준)
REF_INIT="<레퍼런스 ps7_init.tcl 경로>"

diff "$REF_INIT" "$PROJ_INIT" | grep -E "^[<>].*0xF800|mask_delay|DDRIOB"
```

**log 27 Phase 8-2 기준 확인 항목:**

| 항목 | 레퍼런스 값 | 누락 시 결과 |
|---|---|---|
| `0xF8000180 0x00100A20` | DDRIOB 설정 | DDR I/O 버퍼 미설정 |
| `0xF8000190 0x00100500` | DDRIOB 설정 | DDR I/O 버퍼 미설정 |
| `mask_delay 0xF8F00200` (5개) | DDR PHY 타이밍 딜레이 | write leveling 미보정 |
| `0xF8006004 = 0x00001081` | DDRC CAS latency | 타이밍 오설정 |
| `0xF8006014 = 0x0004281A` | DDRC tRCD 등 | 타이밍 오설정 |
| `0xF8006018 = 0x44E458D2` | DDRC tRP 등 | 타이밍 오설정 |
| `0xF800601C = 0x720238E5` | DDRC 타이밍 | 타이밍 오설정 |
| `0xF8006030 = 0x00040930` | DDRC refresh | 타이밍 오설정 |

diff 결과가 위 항목에서 불일치하면 BD 재생성 실패(Step D)로 간주 → Step D 재시도.

---

## Step F: Vitis ELF 재빌드

새 XSA 기준으로 BSP + ELF 재생성.

```bash
rm -rf build/vitis
vitis -s vitis/build_fir_decimator_demo.py
```

**완료 기준:**
- `build/output/fir_decimator_demo.elf` 존재
- mtime이 `build/output/bd_fir_dma_wrapper.xsa`보다 최신

---

## Step G: BOOT.bin 생성

```bash
bootgen -arch zynq \
        -image build/output/fir_decimator_demo.bif \
        -o build/output/BOOT.bin -w on
```

`fir_decimator_demo.bif` 확인:

```
the_ROM_image:
{
    [bootloader]<FSBL.elf 경로>
    <bd_fir_dma_wrapper.bit 경로>
    <fir_decimator_demo.elf 경로>
}
```

**완료 기준:** `build/output/BOOT.bin` 생성, mtime이 ELF보다 최신.

---

## Step H: SD카드 부팅 및 검증

1. SD카드 FAT32 포맷 (`sudo mkfs.fat -F 32 /dev/sdX1`)
2. `build/output/BOOT.bin` 만 SD 루트에 복사
3. **JP5 점퍼를 SD 위치로 변경** (현재 JTAG)
4. SD 삽입, USB 연결, 전원 인가

**DONE LED 점등 확인 (FSBL 완료)**:

```bash
# UART 포트 확인
ls /dev/ttyUSB*

# UART 연결
minicom -D /dev/ttyUSB1 -b 115200
# 기대: "READY\r\n" 출력
# 이후 입력: "3 5000000 20000000 30000000"
# 기대: binary 응답 (0xDEADBEEF 시작)
```

**Python FFT 검증:**

```bash
python sw/fir_decimator_demo.py --mode 1-1 --port /dev/ttyUSB1
```

---

## 단계별 완료 기준 요약

| Step | Pass 기준 |
|---|---|
| A (시뮬) | `make run_all` 출력에 ERROR/FAIL/mismatch 없음 |
| B (RTL 정적) | 4개 파일 체크리스트 전 항목 ✅ |
| C (C 코드 정적) | DMA 순서, 캐시, UART 형식 모두 ✅ |
| D (BD) | .bit + .xsa 존재, WNS≥0, Board Delay 수치 채워짐 |
| E (ps7_init) | diff 결과 DDRIOB·mask_delay·DDRC 5개 레퍼런스 일치 |
| F (ELF) | .elf mtime > .xsa mtime |
| G (BOOT.bin) | .bin 존재, mtime > .elf mtime |
| H (부팅) | DONE LED + UART "READY" + Python FFT ≥60dB 감쇠 |

---

## 실패 시 분기

| Step H 결과 | 해석 | 다음 액션 |
|---|---|---|
| DONE LED 없음 | FSBL 비트스트림 로드 실패 | BOOT.bin 재생성, .bif 경로 확인 |
| DONE LED ✅, UART 무응답 | ELF 점프 실패 또는 펌웨어 hang | FSBL_DEBUG_INFO 빌드 후 UART 로그 확인 |
| UART ✅, FFT 결과 이상 | DDR 런타임 불안정 또는 DMA 오류 | Step A~E 재점검 |
| Step A~E 전부 ✅임에도 H 실패 | **HW 결함 거의 확정** | 다른 Z7-20 보드 + 동일 BOOT.bin 교차 검증 |
| 전 단계 통과 | **M4 완성** | Step 8 시나리오 1-2 진행 |

---

## 참고 문서

- `docs/log/24` — JTAG 다운로드 트러블슈팅
- `docs/log/25` — AXI-Stream TLAST 데드락
- `docs/log/26` — DDR 파트 오설정 / AXI-Stream 인터페이스 연결 규칙
- `docs/log/27` — DDR MSB 오염 근본 원인 조사 (최종 미해결)
- `docs/workflow/workflow_v12.md` — SD카드 부팅 워크플로우 원본
