# 24. JTAG 다운로드 / 펌웨어 실행 트러블슈팅

- 작성일: 2026-05-08
- 목표: xsdb로 Zybo Z7-20에 비트스트림 + ELF 다운로드 후 펌웨어 실행
- 상태: 🔄 진행 중 (UART 응답 확인 단계)

---

## 배경

ELF 빌드 완료(`23_vitis_embedded_build_troubleshooting.md`) 후 보드에 올리는 과정.
`xsdb`는 Xilinx JTAG 디버거. FSBL 없이 JTAG 직접 부팅이므로 ps7_init.tcl로
DDR/PLL/MIO를 수동 초기화해야 한다.

실행 명령:

```bash
xsdb vitis/download_and_run.tcl
```

---

## 문제 1: `Memory write error — Cannot access DDR`

**증상**

```
Memory write error at 0x100000. Cannot access DDR: the controller is held in reset.
```

`dow` 명령으로 ELF 다운로드 시 발생.

**원인**
JTAG 부팅 시 DDR 컨트롤러가 초기화되지 않은 상태. `fpga` 명령이 FPGA만 프로그래밍하고 PS는 건드리지 않는다.

**해결**
비트스트림 프로그래밍 후, CPU 리셋 전에 ps7_init.tcl 실행:

```tcl
targets -set -filter {name =~ "*A9*#0"}
rst -processor -clear-registers
source $PS7_INIT
ps7_init
ps7_post_config
```

---

## 문제 2: `dow` 및 `mwr` 연속 실행 시 MSB(byte 3) 오염

**증상**
`dow` 또는 연속 `mwr`로 DDR에 쓴 후 `mrd`로 읽으면 대부분 워드의 MSB가 다르다.

```tcl
mwr 0x100000 0x11111111
mwr 0x100004 0x22222222
mwr 0x100008 0x33333333
mwr 0x10000C 0x44444444
mrd 0x100000 4
# 100000: F2111111   ← byte3=F2 (stale), 비정상
# 100004: F2222222   ← byte3=F2 (stale), 비정상
# 100008: F2333333   ← byte3=F2 (stale), 비정상
# 10000C: 44444444   ← 정상 (마지막 mwr)
```

결과: CPU 부팅 즉시 SVC exception (PC=0x8) crash. 벡터 테이블이 오염됐기 때문.

**원인 (JTAG write buffer 파이프라인 버그)**
xsdb의 JTAG AXI 마스터가 `mwr`을 파이프라인 처리. byte 3(MSB)는 다음 JTAG 커맨드가
시작될 때 flush된다. 연속 `mwr` 시 마지막 워드만 정상, 나머지는 직전 워드의 byte 3을 유지.
`dow` 내부도 동일 버그.

**해결: mwr 후 mrd로 강제 flush**
`vitis/gen_mwr_tcl.py` 작성: ELF PT_LOAD 세그먼트의 각 32비트 워드마다 `mwr + mrd` 쌍 생성.
`mrd`가 next JTAG command로 작동해 직전 `mwr`의 byte 3을 flush.

```python
cmds.append(f"mwr 0x{addr:08X} 0x{word:08X}")
cmds.append(f"mrd 0x{addr:08X} 1")  # JTAG write buffer flush
```

`build/output/load_elf.tcl` (~13,700개 mwr+mrd 쌍)을 `download_and_run.tcl`에서 `source`.

**검증 (power cycle 후)**

```tcl
mwr 0x100000 0xAAAAAAAA; mrd 0x100000 1  # → AAAAAAAA ✓
mwr 0x100004 0xBBBBBBBB; mrd 0x100004 1  # → BBBBBBBB ✓
mwr 0x100008 0xCCCCCCCC; mrd 0x100008 1  # → CCCCCCCC ✓
mwr 0x10000C 0xDDDDDDDD; mrd 0x10000C 1  # → DDDDDDDD ✓
```

---

## 문제 3: L2 캐시 stale 데이터로 mrd 오독

**증상**
mwr+mrd flush 적용 후에도 `mrd` 결과가 이상하게 보이는 경우 있음.

**원인**
L2 캐시(PL310, 0xF8F02000)에 이전 펌웨어의 stale 데이터 잔존. `mrd`가 DDR 대신 L2 캐시를 읽을 수 있음.

**해결**
ELF 로드 직전 L2 전체 무효화 (PL310 Invalidate by Way):

```tcl
mwr 0xF8F0277C 0x0000FFFF
after 200
```

---

## 문제 4: `AP transaction timeout` — 이전 펌웨어 실행 중 재다운로드 시도

**증상**

```
Memory write error at 0xE0001034. AP transaction timeout
```

보드 전원 재공급 없이 `download_and_run.tcl` 재실행 시 ps7_init 중 UART1 레지스터 접근에서 타임아웃.

**원인**
이전 세션에서 `con`으로 실행된 펌웨어가 DMA/UART 레지스터를 점유한 채 무한 루프 중.
`rst -processor`로 halt 시도해도 stuck된 CPU는 halt 불가 ("Cannot halt processor core, timeout").

**해결**
**전원 재공급(power cycle) 필수.** 소프트 리셋만으로 복구 불가.

---

## 문제 5: DMA soft reset 누락으로 DMA 폴링 무한 대기

**증상**
다운로드 후 `con`으로 실행. Python/minicom에서 UART 응답 없음.
`TimeoutError: 보드 응답 없음`

**원인**
`dma_run()`에서 soft reset 없이 DMA RUN/STOP bit만 세웠다.
전원 인가 직후 DMA 상태가 불확실하면 IDLE bit이 영원히 세워지지 않음.

**해결 1차 시도 (잘못됨)**

```c
// S2MM 리셋 후 설정, 다시 MM2S 리셋 → S2MM 설정이 날아감
dma_reset_channel(S2MM_DMACR, ...);  // 전체 코어 리셋
DMA_REG(S2MM_DA) = ...;
dma_reset_channel(MM2S_DMACR, ...);  // 전체 코어 다시 리셋 → S2MM DA/LENGTH 클리어됨!
```

**핵심 함정 (PG021)**: `DMACR[2]` (reset bit)는 MM2S/S2MM 양쪽 모두 **전체 DMA 코어**를 리셋한다.
채널별 독립 리셋 없음.

**해결 2차 (올바름): 코어 1회 리셋 후 양쪽 채널 설정**

```c
DMA_REG(MM2S_DMACR) = (1u << 2);               // 전체 코어 리셋
while (DMA_REG(MM2S_DMACR) & (1u << 2));        // self-clearing 대기

DMA_REG(S2MM_DMACR) = DMA_RS_BIT;              // S2MM 먼저 arm
DMA_REG(S2MM_DA)     = (uint32_t)(UINTPTR)dst_buf;
DMA_REG(S2MM_LENGTH) = N_OUT * sizeof(int16_t);

DMA_REG(MM2S_DMACR) = DMA_RS_BIT;              // MM2S 시작
DMA_REG(MM2S_SA)     = (uint32_t)(UINTPTR)src_buf;
DMA_REG(MM2S_LENGTH) = N_IN * sizeof(int16_t);
```

적용 후 `download_and_run.tcl` 정상 완료. Python 응답 여부 검증 진행 중.

---

## 현재 상태 (2026-05-08)

- mwr+mrd flush 방식으로 DDR 로딩 정상 확인 ✅
- DMA soft reset 1회 리셋 방식으로 수정 ✅
- xsdb 다운로드 완료 ✅
- **Python `TimeoutError` 재현 중** — UART 응답 미확인 🔄
  - TLAST_N=512 (설계 결정: 512샘플 패킷, DMA는 8패킷 연속 수신으로 4096샘플 완성)
  - DMA가 문제인지 UART가 문제인지 미분리

---

## 핵심 교훈

1. **JTAG 부팅 시 ps7_init.tcl 필수.** 없으면 DDR 접근 불가.
2. **xsdb `dow`/연속 `mwr`은 MSB를 오염시킨다.** 각 mwr 직후 mrd로 flush해야 한다.
3. **AXI DMA soft reset은 전체 코어 리셋이다.** 두 채널 설정 전 딱 한 번만 리셋해야 한다.
4. **이전 펌웨어가 실행 중이면 재다운로드 불가.** 전원 재공급 필수.
5. **DMA soft reset 없이 RUN/STOP을 세우면 DMA가 완료되지 않는다.**
