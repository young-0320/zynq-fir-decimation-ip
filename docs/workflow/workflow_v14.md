
# FIR Decimation 프로젝트 워크플로우 v14

- 작성일: 2026-05-21
- 이전 버전: `workflow_v13.md`
- 변경 배경: v13의 bottom-up 검증 흐름은 유지하되, SD카드 부팅 전환 과정에서 발견된 **산출물 이름 불일치**, **XSA/FSBL DDR 초기화값 불일치**, **BIF 경로 비재현성**, **Vitis 빌드 스크립트 누락**을 먼저 정리한다.

---

## 1. v13 대비 변경 사항

| 항목 | v13 | v14 |
|---|---|---|
| BD 이름 | 암묵적으로 `bd_fir_dma` 기대 | **`bd_fir_dma`를 canonical name으로 고정** |
| XSA 검증 | 파일 존재 + ps7_init diff | **XSA 내부 `ps7_init.tcl` 직접 검사** |
| Vitis 빌드 | `vitis/build_fir_decimator_demo.py` 실행 전제 | **스크립트 존재/복구를 필수 조건으로 명시** |
| FSBL 검증 | BOOT.bin 생성 후 실패 시 의심 | **FSBL `ps7_init.c` DDR 값까지 사전 확인** |
| BIF | `build/output/fir_decimator_demo.bif` 사용 | **repo-root 기준 고정 경로만 허용** |
| JTAG | 폐기 결정 | **메인 workflow에서 완전히 제외** |

---

## 2. 현재 정체 원인 요약

현재 문제는 RTL 필터 수학이나 AXI-Stream 래퍼 자체보다, **SD 부팅용 산출물 체인이 하나의 하드웨어 기준으로 재생성되지 않는 것**이다.

| 문제 | 영향 | 판정 |
|---|---|---|
| `db_fir_dma` / `bd_fir_dma` 혼재 | Vivado wrapper/XSA 경로가 엇갈림 | 빌드 재현성 문제 |
| `db_fir_dma_wrapper.xsa` 내부 DDR 값이 구형 계열 | FSBL이 잘못된 DDR init으로 빌드될 수 있음 | SD 부팅 검증 신뢰도 저하 |
| `vitis/build_fir_decimator_demo.py` 누락 | ELF/FSBL 재생성 절차가 문서와 불일치 | 즉시 수정 필요 |
| `untitled.bif` + Vitis 내부 경로 | BOOT.bin 재생성이 IDE 상태에 의존 | 즉시 수정 필요 |

`db`/`bd` 이름 자체는 보드 동작의 본질 문제가 아니다. 그러나 스크립트와 문서가 서로 다른 이름을 기대하면 같은 소스에서 같은 BOOT.bin을 다시 만들 수 없으므로, v14에서는 `bd_fir_dma`로 통일한다.

---

## 3. Canonical 산출물

모든 단계는 repo root(`/home/young/dev/10_zynq-fir-decimation-ip`)에서 실행한다.

| 산출물 | canonical 경로 |
|---|---|
| Vivado bitstream | `build/output/bd_fir_dma_wrapper.bit` |
| Vivado XSA | `build/output/bd_fir_dma_wrapper.xsa` |
| FSBL ELF | `build/output/fsbl.elf` |
| App ELF | `build/output/fir_decimator_demo.elf` |
| BIF | `build/output/fir_decimator_demo.bif` |
| Boot image | `build/output/BOOT.bin` |

Vitis IDE가 만든 `untitled.bif`, `db_fir_dma_wrapper.xsa`, `_ide/bitstream/...` 경로는 임시 산출물로만 취급한다. BOOT.bin 입력으로 직접 사용하지 않는다.

---

## Step A: 작업트리와 이름 정리

### A-1. 작업트리 확인

```bash
git status --short
```

현재 변경사항이 있으면 어떤 파일이 의도된 변경인지 먼저 확인한다. 기존 사용자 변경을 되돌리지 않는다.

### A-2. BD 이름 통일

`bd_fir_dma`를 유일한 design name으로 사용한다.

확인 대상:

```bash
rg -n "db_fir_dma|bd_fir_dma|set design_name|make_wrapper|get_files .*\\.bd|write_hw_platform" vivado
```

기대 상태:

| 파일 | 기대값 |
|---|---|
| `vivado/bd_fir_dma.tcl` | `set design_name bd_fir_dma` |
| `vivado/build_bd_fir_dma.tcl` | `get_files bd_fir_dma.bd` |
| `vivado/build_bd_fir_dma.tcl` | top = `bd_fir_dma_wrapper` |
| `vivado/build_bd_fir_dma.tcl` | XSA = `build/output/bd_fir_dma_wrapper.xsa` |

완료 기준:

```bash
rg -n "db_fir_dma" vivado vitis README.md CLAUDE.md
# 출력 없음
```

---

## Step B: RTL / C 정적 기준 유지

v13의 RTL/C 검증 기준은 그대로 유지한다.

### B-1. RTL 시뮬레이션

```bash
cd /home/young/dev/10_zynq-fir-decimation-ip/sim
make clean
make run_all 2>&1 | tee /tmp/sim_run_all.log
grep -iE "error|fail|mismatch" /tmp/sim_run_all.log
```

완료 기준: 마지막 `grep` 출력 없음.

### B-2. 핵심 코드 체크포인트

| 레이어 | 확인 항목 |
|---|---|
| `fir_decimator_n43_axis.v` | dynamic TLAST + auto-flush 유지 |
| `tb_fir_decimator_n43_axis.sv` | 마지막 입력에서만 `s_axis_tlast`, 출력 4096번째에서만 `m_axis_tlast` |
| `sw/fir_decimator_demo.c` | DMA reset 1회 → S2MM arm → MM2S start |
| `sw/fir_decimator_demo.py` | C UART 프로토콜과 magic/n/data 형식 일치 |

---

## Step C: Vivado 재빌드

기존 `build/output/db_fir_dma_wrapper.xsa`는 사용하지 않는다. 이름 정리 후 새로 생성한다.

```bash
source ~/Xilinx/Vivado/2024.2/settings64.sh
mkdir -p build/vivado build/output
vivado -mode batch \
  -journal build/vivado/vivado.jou \
  -log build/vivado/vivado.log \
  -source vivado/build_bd_fir_dma.tcl
```

완료 기준:

```bash
test -f build/output/bd_fir_dma_wrapper.xsa
test -f build/output/bd_fir_dma_wrapper.bit
test ! -f build/output/db_fir_dma_wrapper.xsa
```

Vivado가 bitstream을 `impl_1`에만 만들면 `build_bd_fir_dma.tcl`에서 `build/output/bd_fir_dma_wrapper.bit`로 복사하도록 보강한다.

---

## Step D: XSA 내부 검증

파일명만 믿지 말고 XSA 내부를 직접 확인한다.

### D-1. XSA 파일 목록

```bash
unzip -l build/output/bd_fir_dma_wrapper.xsa
```

기대 항목:

| 파일 | 기대 |
|---|---|
| `bd_fir_dma_wrapper.bit` | 존재 |
| `bd_fir_dma.hwh` | 존재 |
| `ps7_init.tcl` | 존재 |
| `ps7_init.c` | 존재 |

`db_fir_dma_wrapper.bit`, `db_fir_dma.hwh`가 나오면 Step A/C 실패로 간주한다.

### D-2. DDR part / bus width / board delay

```bash
unzip -p build/output/bd_fir_dma_wrapper.xsa bd_fir_dma.hwh \
  | rg -n "PCW_UIPARAM_DDR_PARTNO|PCW_UIPARAM_DDR_BUS_WIDTH|PCW_UIPARAM_DDR_BOARD_DELAY"
```

기대값:

| 항목 | 기대값 |
|---|---|
| DDR part | `MT41K256M16 RE-125` |
| DDR bus width | `32 Bit` |
| Board delay | `0.221`, `0.222`, `0.217`, `0.244` 계열의 non-zero 값 |

### D-3. ps7_init DDR 레지스터

```bash
unzip -p build/output/bd_fir_dma_wrapper.xsa ps7_init.tcl \
  | rg -n "F8000180|F8000190|F8006004|F8006014|F8006018|F800601C|F8006030|mask_delay"
```

기대값:

| 레지스터 | 기대값 |
|---|---|
| `0xF8000180` | `0x00100A20` |
| `0xF8000190` | `0x00100500` |
| `0xF8006004` | `0x00001081` / `0x00081081` 계열 |
| `0xF8006014` | `0x0004281A` |
| `0xF8006018` | `0x44E458D2` |
| `0xF800601C` | `0x720238E5` |
| `0xF8006030` | `0x00040930` |
| `mask_delay 0xF8F00200` | 여러 번 존재 |

다음 값이 보이면 실패:

```text
0x00001082
0x0004285B
0x44E458D3
0x7282BCE5
0x00040B30
```

---

## Step E: Vitis 빌드 스크립트 복구 및 ELF/FSBL 재생성

`vitis/build_fir_decimator_demo.py`는 source-controlled 파일이어야 한다. Vitis IDE journal이나 `build/vitis/_ide/...`에 의존하지 않는다.

### E-1. 스크립트 필수 역할

`vitis/build_fir_decimator_demo.py`는 다음을 수행해야 한다.

| 단계 | 요구사항 |
|---|---|
| 입력 XSA | `build/output/bd_fir_dma_wrapper.xsa` |
| workspace | `build/vitis` |
| platform | `fir_decimator_pf` |
| app | `fir_decimator_demo` |
| source | `sw/fir_decimator_demo.c` |
| link | `-lm` |
| output copy | `build/output/fir_decimator_demo.elf` |
| FSBL copy | `build/output/fsbl.elf` |

### E-2. 실행

```bash
rm -rf build/vitis
vitis -s vitis/build_fir_decimator_demo.py
```

완료 기준:

```bash
test -f build/output/fir_decimator_demo.elf
test -f build/output/fsbl.elf
test build/output/fir_decimator_demo.elf -nt build/output/bd_fir_dma_wrapper.xsa
test build/output/fsbl.elf -nt build/output/bd_fir_dma_wrapper.xsa
```

### E-3. FSBL ps7_init.c 검증

FSBL은 XSA의 `ps7_init.c`를 컴파일해 들어가므로, Vitis workspace 안의 FSBL 소스도 확인한다.

```bash
rg -n "00001082|00001081|0004285B|0004281A|44E458D3|44E458D2|7282BCE5|720238E5|00040B30|00040930" \
  build/vitis/fir_decimator_pf/zynq_fsbl/ps7_init.c
```

완료 기준:

- `00001081`, `0004281A`, `44E458D2`, `720238E5`, `00040930` 계열이 보임
- `00001082`, `0004285B`, `44E458D3`, `7282BCE5`, `00040B30` 계열이 보이지 않음

---

## Step F: BIF 고정

`build/output/fir_decimator_demo.bif`는 repo root에서 실행하는 `bootgen` 기준 상대 경로만 사용한다.

```text
the_ROM_image:
{
    [bootloader]build/output/fsbl.elf
    build/output/bd_fir_dma_wrapper.bit
    build/output/fir_decimator_demo.elf
}
```

금지:

| 금지 경로 | 이유 |
|---|---|
| `build/output/untitled.bif` | Vitis IDE 임시 이름 |
| `build/vitis/.../_ide/bitstream/...` | IDE workspace 상태 의존 |
| absolute path | repo 이동 시 재현 불가 |
| `db_fir_dma_wrapper.*` | canonical name 불일치 |

완료 기준:

```bash
test -f build/output/fir_decimator_demo.bif
rg -n "untitled|_ide|db_fir_dma|/home/" build/output/fir_decimator_demo.bif
# 출력 없음
```

---

## Step G: BOOT.bin 생성

```bash
bootgen -arch zynq \
  -image build/output/fir_decimator_demo.bif \
  -o build/output/BOOT.bin -w on
```

완료 기준:

```bash
test -f build/output/BOOT.bin
test build/output/BOOT.bin -nt build/output/fsbl.elf
test build/output/BOOT.bin -nt build/output/bd_fir_dma_wrapper.bit
test build/output/BOOT.bin -nt build/output/fir_decimator_demo.elf
```


### G-1. C 파일만 바뀐 경우 fast rebuild

`sw/fir_decimator_demo.c`만 수정한 경우에는 Vivado hardware와 Vitis platform을 다시 만들지 않고, 기존 `build/vitis` workspace를 재사용해 app ELF와 BOOT.bin만 다시 만든다.

```bash
vitis/rebuild_boot_image.sh
```

SD카드까지 바로 갱신하려면:

```bash
vitis/rebuild_boot_image.sh --sd-mount /mnt/223F-CE51
```

이 스크립트는 다음을 수행한다.

| 단계 | 산출물 |
|---|---|
| C source copy | `build/vitis/fir_decimator_demo/fir_decimator_demo.c` |
| app rebuild | `build/vitis/fir_decimator_demo/build/fir_decimator_demo.elf` |
| output copy | `build/output/fsbl.elf`, `build/output/bd_fir_dma_wrapper.bit`, `build/output/fir_decimator_demo.elf` |
| BIF regenerate | `build/output/fir_decimator_demo.bif` |
| bootgen | `build/output/BOOT.bin` |

주의: 이 fast rebuild는 hardware/BD 변경을 반영하지 않는다. `vivado/bd_fir_dma.tcl`, RTL, XSA, bitstream이 바뀐 경우에는 Step A부터 다시 수행해야 한다.

---

## Step H: SD카드 부팅 및 UART 검증

JTAG `dow` / `mwr` / `download_and_run.py`는 사용하지 않는다.

1. SD카드 FAT32 포맷
2. `build/output/BOOT.bin`만 SD 루트에 복사
3. JP5 점퍼를 SD 위치로 변경
4. SD 삽입, USB 연결, 전원 인가
5. DONE LED 확인
6. UART 확인

```bash
ls /dev/ttyUSB*
minicom -D /dev/ttyUSB1 -b 115200
```

기대:

```text
READY
```

명령 입력:

```text
3 5000000 20000000 30000000
```

Python FFT:

```bash
python sw/fir_decimator_demo.py --mode 1-1 --port /dev/ttyUSB1
```

---

## 실패 시 분기

| 실패 위치 | 해석 | 다음 액션 |
|---|---|---|
| Step A | 이름 혼재 | `bd_fir_dma`로 Tcl/문서/스크립트 통일 |
| Step C | XSA/bit 미생성 | Vivado log에서 BD 이름, board_part, wrapper 경로 확인 |
| Step D | XSA 내부 DDR 값 구형 | BD preset/board automation 재적용 후 XSA 재생성 |
| Step E | Vitis 빌드 실패 | `vitis/build_fir_decimator_demo.py` API/경로 확인 |
| Step E-3 | FSBL DDR 값 구형 | Vitis workspace 삭제 후 corrected XSA로 platform 재생성 |
| Step F | BIF가 IDE/absolute path 포함 | BIF 생성 로직 수정 |
| Step G | BOOT.bin 미생성 | BIF 경로/파일 존재 확인 |
| Step H DONE LED 없음 | FSBL 또는 bitstream 로드 실패 | BOOT.bin 입력 3개 파일 재확인 |
| Step H UART 무응답 | ELF 점프 실패 또는 펌웨어 hang | FSBL debug build, UART 포트, DMA polling 상태 확인 |
| UART 응답 but FFT 이상 | RTL/DMA/DDR 런타임 문제 | v13 Step A~C와 C 코드 DMA 상태 재점검 |

---

## 완료 기준 요약

| 항목 | Pass 기준 |
|---|---|
| 이름 | active script에 `db_fir_dma` 없음 |
| RTL/C | v13 정적 기준 유지, `make run_all` PASS |
| XSA | `bd_fir_dma_wrapper.xsa` 내부 이름/DDR 값 일치 |
| Vitis | corrected XSA로 FSBL + app ELF 재생성 |
| BIF | repo-root 상대 경로, IDE/absolute path 없음 |
| BOOT | `BOOT.bin`이 FSBL/bit/ELF보다 최신 |
| 보드 | DONE LED + UART `READY` + Python FFT 확인 |

---

## 참고 문서

- `docs/workflow/workflow_v13.md` — bottom-up 검증 기준
- `docs/workflow/workflow_v12.md` — SD카드 부팅 전환 원본
- `docs/log/23_vitis_embedded_build_troubleshooting.md` — Vitis 2024.2 빌드 이슈
- `docs/log/24_jtag_download_troubleshooting.md` — JTAG 다운로드 폐기 근거
- `docs/log/27_ddr_msb_corruption_investigation.md` — DDR byte lane 오염 조사 및 SD 전환 결론
- `docs/log/28_axis_tb_update_for_log25_rtl_redesign.md` — AXI-Stream TB 업데이트
