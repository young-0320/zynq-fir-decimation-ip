# 24. JTAG 다운로드 / 펌웨어 실행 트러블슈팅

- 작성일: 2026-05-08
- 목표: xsdb로 Zybo Z7-20에 비트스트림 + ELF 다운로드 후 펌웨어 실행
- 상태: ❌ JTAG ELF 로딩 미완 — byte[3] 오염 미해결, SD카드 부팅으로 전환 (→ `27_ddr_msb_corruption_investigation.md` 최종 결론)

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

## 문제 6: sourced 모드에서 시간 기반 flush 실험 — 전부 실패

**증상**
`gen_mwr_tcl.py`로 생성한 .tcl 파일에 `mwr + mrd`, `mwr + after 1`, `mwr + after 0` 등 다양한 flush 삽입을 시도. 결과:

| 방법 | 결과 |
|------|------|
| `mrd 0x{same_addr} 1` | byte3 여전히 오염 |
| `after 1` (1 ms) | byte3가 0xEA 대신 `0x00`으로 flush됨 |
| `after 0` | byte3뿐 아니라 bytes 0~2까지 전부 0x00 |
| `mrd 0xF8000000 1` (다른 주소) | sourced 모드 배치 처리로 효과 없음 |

**근본 원인 — REPL barrier 메커니즘 규명**

xsdb의 JTAG AXI 마스터는 `mwr` 실행 즉시 bytes 0~2를 전송하지만, byte3(MSB)는 내부 파이프라인 버퍼에 hold한다.
byte3가 commit되는 조건은 **"xsdb가 stdin에서 다음 명령을 기다리며 블로킹할 때"**다.

- 인터랙티브 REPL에서는 사용자가 Enter를 누르기 전까지 blocking → byte3 flush 완료 → 다음 명령 처리.
- sourced 모드(`xsdb script.tcl`, `source file.tcl`)는 xsdb parser가 파일 버퍼에서 직접 읽어 stdin blocking이 없음. `mrd`나 `after`를 삽입해도 같은 실행 컨텍스트에서 연속 파싱 → barrier 없음.
- `after 1`(1ms)은 오히려 xsdb idle timeout을 트리거해 byte3를 `0x00`으로 자동 flush한다 (데이터가 아닌 null 값).

**결론: sourced 모드에서는 어떤 flush 삽입도 REPL barrier를 재현할 수 없다.**

**해결: pexpect로 REPL barrier를 소프트웨어적으로 재현**

pexpect가 PTY를 에뮬레이션하면 xsdb는 인터랙티브 터미널로 인식한다.
각 `mwr` 직후 `xsdb.expect('xsdb%')` 호출 → xsdb가 실제로 stdin blocking → JTAG subsystem이 byte3 commit → 프롬프트 출력 순서가 보장됨.

```python
xsdb = pexpect.spawn('xsdb', encoding='utf-8', timeout=60)
for addr, word in words:
    xsdb.sendline(f"mwr 0x{addr:08X} 0x{word:08X}")
    xsdb.expect('xsdb%')   # ← 이 blocking이 인터랙티브 REPL과 동일한 barrier
    xsdb.buffer = ''
```

`searchwindowsize=500` 설정으로 누적 버퍼 검색을 최근 500자로 제한 → 장시간 실행 시 메모리 누적 방지.

---

## 문제 7: mwr silent failure — all-zeros를 byte3 버그로 오진

**증상**
pexpect 방식으로 13,769 words "완료" 후 `mrd 0x100000 4` 결과:

```
100000: 00000000
100004: 00000000
100008: 00000000
10000C: FF000000
```

문제 2(byte3 버그)의 증상(`100000: 00000031`, byte3만 0x00)과 완전히 다른 패턴.

**두 실패 모드의 구별법**

| 패턴 | 의미 |
|------|------|
| `0x000000XX` — 하위 3바이트만 정상 | 쓰기 성공, byte3 flush 실패 |
| `0x00000000` — 전체 0 | 쓰기 자체 실패, DDR 접근 불가 |

**원인**
이전 `con` 세션으로 CPU가 실행 중인 상태에서 전원 재공급 없이 재실행. `ps7_init` 중 UART1 레지스터(`0xE0001034`) 접근에서 AP transaction timeout 발생 → 이후 모든 `mwr`이 xsdb 내부에서 에러를 출력하지만, 스크립트 루프가 `xsdb.before`를 `buffer = ''`로 버려서 에러를 전혀 감지하지 못함 → 13,769회 "완료"처럼 보이지만 실제로는 전부 실패.

**해결 1: ELF 로딩 전 DDR write-readback 점검**

```python
cmd(xsdb, "mwr 0x100000 0xDEADBEEF")
out = cmd(xsdb, "mrd 0x100000 1")
if "DEADBEEF" not in out.upper():
    sys.exit("DDR 접근 실패 — 전원 재공급 후 재시도")
```

이 패턴으로 DDR 접근 불가를 13,769회 낭비 없이 즉시 감지한다.

**해결 2: mwr output 모니터링**

xsdb는 `mwr` 성공 시 아무 출력도 하지 않는다. 출력이 있으면 에러다.

```python
out = xsdb.before.strip()
if out:   # 빈 문자열이 아니면 에러 메시지
    print(f"[경고] mwr 0x{addr:08X}: {out}")
```

초반 N개 + 에러 발생 시 항상 출력하도록 설정하면 silent failure를 조기에 포착한다.


## Zynq-7000 JTAG ELF 다운로드 트러블슈팅 리포트

### [Phase 1] 하드웨어 레벨: 명령어 유실 발생

* **원인** : XSDB 네이티브 명령어 `dow` 사용 시, 메모리 첫 주소(`0x100000`)의 MSB(byte 3)가 `0xEA` 대신 `0x00`으로 기록됨.
* **가설** : 고속 Bulk 전송 시 USB-JTAG 브릿지(FTDI)의 FIFO 버퍼가 오버런(Overrun)되거나 트랜잭션 경계에서 데이터 플러시(Flush) 타이밍이 어긋남.
* **해결 방식** : 바이너리를 워드 단위로 쪼개어 `mwr` 명령어로 개별 전송하도록 우회.

### [Phase 2] OS 인터페이스 레벨: 파이프 데드락

* **원인** : Python `subprocess.PIPE`를 이용한 자동화 시 스크립트가 초기화 단계에서 무한 대기함.
* **가설** : `xsdb`가 비대화형(Non-interactive) 환경임을 감지하고 블록 버퍼링(Block Buffering)을 수행하여 프롬프트를 내보내지 않음. 부모-자식 프로세스 간 교착 상태 발생.
* **해결 방식** : 가상 터미널(PTY)을 에뮬레이션하는 `pexpect` 라이브러리를 도입하여 대화형 환경 강제 구현.

### [Phase 3] 통신 성능 레벨: IPC 병목 지옥

* **원인** : ELF 데이터(약 13,000 words) 다운로드에 10분 이상의 시간 소요 (약 19 words/s).
* **가설** : 워드 하나당 `Python ↔ XSDB` 간의 문자열 송수신 및 컨텍스트 스위칭 오버헤드가 하드웨어 전송 속도보다 수백 배 큼.
* **해결 방식** : 128개 워드를 하나로 묶어 전송하는 **Chunking(블록 쓰기)** 기법 적용.

### [Phase 4] 커널 버퍼 레벨: PTY 입력 오버플로우

* **원인** : Chunking 적용 후 약 14%(2048 words) 지점에서 전송이 멈추는 현상 발생.
* **가설** : 리눅스 커널의 PTY 입력 큐(약 4KB~8KB)가 가득 찼으나, XSDB 파서가 이를 소화하는 속도가 파이썬의 타이핑 속도를 따라가지 못해 커널 레벨에서 블로킹됨.
* **해결 방식** : 텍스트 통신을 최소화하기 위해 모든 `mwr` 명령을 담은 **임시 .tcl 파일을 생성**하고, XSDB에서 `source` 명령으로 단번에 실행하도록 아키텍처 변경.

### [Phase 5] 하드웨어 상태 레벨: DDR 컨트롤러 유실

* **원인** : 다운로드 완료 후 메모리 확인 시 `Cannot access DDR` 에러 발생.
* **가설** : `rst -system` 명령어가 Zynq PS의 모든 레지스터를 초기화하여 DDR 컨트롤러가 리셋 상태에 묶임.
* **해결 방식** : 메모리 접근 전 반드시 `ps7_init` 스크립트를 재실행하여 DDR 인터페이스를 활성화하도록 시퀀스 보정.

## 현재 상태 (2026-05-08 ~ 2026-05-13)

- mwr+mrd flush 방식으로 DDR 로딩 정상 확인 ✅ (2026-05-08 시점)
- DMA soft reset 1회 리셋 방식으로 수정 ✅
- **JTAG ELF 로딩 최종 실패** ❌ — 이후 세션에서 pexpect REPL barrier 방식도 byte[3] 비결정적 오염 재발 확인
- **SD카드 부팅으로 전환 결정** (2026-05-13)

> 상세 트러블슈팅 경위(Phase 1~9) → `27_ddr_msb_corruption_investigation.md`

---

## 핵심 교훈

1. **JTAG 부팅 시 ps7_init.tcl 필수.** 없으면 DDR 접근 불가.
2. **xsdb `dow`/연속 `mwr`은 MSB를 오염시킨다.** pexpect REPL barrier(각 mwr 직후 xsdb% 대기)도 비결정적으로 실패함이 이후 확인됨 — sourced 모드의 모든 flush 방법(mrd, after)도 효과 없음. DDR에 신뢰성 있는 JTAG 로딩 방법을 끝내 찾지 못했다.
3. **AXI DMA soft reset은 전체 코어 리셋이다.** 두 채널 설정 전 딱 한 번만 리셋해야 한다.
4. **이전 펌웨어가 실행 중이면 재다운로드 불가.** 전원 재공급 필수.
5. **DMA soft reset 없이 RUN/STOP을 세우면 DMA가 완료되지 않는다.**
6. **JTAG 직접 부팅의 DDR byte[3] 오염은 SD카드 부팅으로 우회한다.** FSBL이 DDR을 하드웨어적으로 초기화하고 ELF를 로드하므로 JTAG 쓰기 경로를 완전히 우회한다.
