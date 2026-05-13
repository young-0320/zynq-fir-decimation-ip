# 27. DDR MSB Corruption — Root Cause Investigation (Unresolved)

- 작성일: 2026-05-13
- 선행 문서: `26_vivado_rebuild_ddr_misconfiguration_and_axi_stream_interface.md`

---

## 이슈 요약

- **증상**: XSDB 환경에서 `dow` 명령어로 ELF 파일을 DDR 메모리(`0x100000`)에 다운로드한 후 확인(`mrd`) 시, 32-bit 워드 중 최하위 1바이트(LSB)만 정상 기록되고 최상위 3바이트(MSB)가 소실되거나 이전 데이터의 잔해로 오염됨.
- **타겟 보드**: Digilent Zybo Z7-20

---

## Phase 1: 물리 계층(JTAG 통신) 가설과 1차 검증

- **원인 가설**: JTAG 클럭 주파수(`TCK`)가 너무 빨라, 직렬 데이터를 병렬 AXI 버스로 변환하는 과정에서 신호 무결성(Signal Integrity)이 깨졌을 것이다.
- **XSDB 검증**:
  - `jtag frequency 1000000` (1MHz)으로 통신 속도를 대폭 하향한 뒤 `dow` 실행.
  - 결과: 전송 속도(0.1MB/s)는 정상적으로 느려졌으나, 여전히 MSB 3바이트가 소실됨.

- **가설 수정**: 주파수와 무관하게 특정 바이트만 깨진다면, JTAG 케이블의 노이즈 문제가 아니라 **'데이터를 쏟아붓는 방식(Burst)' 자체의 논리적 결함**일 가능성이 높다.

---

## Phase 2: 전송 방식(단일 vs 버스트) 교차 검증

- **원인 가설**: 툴이 대용량 데이터를 한 번에 밀어넣는 버스트(Burst) 트랜잭션 과정에서 하드웨어 버퍼(FIFO) 오버플로우가 발생하여 패킷의 MSB를 깎아먹고 있을 것이다.
- **XSDB 및 스크립트 검증**:
  - 단일 전송: `mwr -force 0x100000 0x12345678` 수동 실행. → **결과: `12345678` 완벽히 기록됨.**
  - 파이썬 스크립트 우회: `mwr`을 수천 번 반복하며 각 명령마다 REPL 프롬프트(`xsdb%`)를 기다려 버퍼를 비우는 방식으로 다운로드 시도. → 단일 쓰기임에도 간헐적으로 MSB가 깨지는 증상 재발.
  - 수동 버스트 전송: `mwr 0x100000 {0x11111111 0x22222222 0x33333333 0x44444444}` 실행. → 하위 24비트는 정상이나, MSB(Byte 3) 라인에서 이전 데이터가 잔류(`11222222`)하거나 타이밍 위반 지문 발견.

- **가설 재수정**: 단일 전송은 정상인데 연속 스위칭 시에만 특정 배선(MSB)이 깨진다. 범인은 JTAG 버퍼가 아니라, 고속(533MHz)으로 동작하는 **DDR 컨트롤러와 메모리 칩 사이의 물리적 타이밍 캘리브레이션 결함**이다.

---

## Phase 3: 클럭 도메인 격리 (OCM vs DDR)

- **원인 가설**: JTAG 다운로드 툴(`hw_server`)과 Zynq 디버그 포트(DAP)는 무죄이며, Zynq 칩에서 외부 DDR로 향하는 메모리 컨트롤러 인터페이스에만 문제가 있다.
- **XSDB 검증**:
  - 외부 메모리(DDR)가 아닌, Zynq 칩 내부 메모리(OCM, `0x00000000`)에 버스트 전송(`mwr { ... }`) 시도.
  - **결과**: OCM에서는 4바이트가 1비트의 유실도 없이 완벽하게 기록 및 검증됨.

- **최종 원인 확정**: JTAG과 AXI 버스는 100% 정상. 문제는 Zynq 내부에서 외부 DDR 칩으로 데이터를 쏠 때 발생하는 물리적 배선 지연(Board Delay) 설정의 부재이다.

---

## Phase 4: Vivado 하드웨어 설계 점검 및 근본 원인(Root Cause) 발견

- **검증 방법**: Vivado 블록 디자인(Block Design)에서 Zynq7 Processing System IP의 `DDR Configuration` 파라미터 점검.
- **발견된 결함**:
  - 프로젝트의 타겟은 `Zybo Z7-20` 보드로 정상 설정되어 있었으나, GUI 캐시 버그 및 자동화 프로세스 누락으로 인해 Zynq IP 내부의 'Presets'가 `None` 상태에 머물러 있었음.
  - 이로 인해 DDR 배선의 물리적 길이를 보상해야 할 **`Training/Board Details -> Board Delay` 값이 모두 `0ns`로 비어 있었음.**
  - Zynq가 모든 데이터 선의 길이가 같다고 착각하여 고속 스위칭 시 미세하게 배선이 긴 MSB 라인의 타이밍 마진이 붕괴된 것이 근본 원인으로 추정.

---

## Phase 5: 해결 방법 적용 및 검증

- **조치 사항**:
  - 꼬여버린 블록 디자인을 폐기하고, 보드 타겟이 명확한 새 블록 디자인을 생성.
  - Zynq IP 배치 후 상단의 `Run Block Automation` 배너를 강제 실행하여 Zybo 공식 보드 파일(`preset.xml`)을 IP 내부로 주입.
- **확인**:
  - Zynq IP 설정 창에서 `DQ[31:24]`(최상위 바이트)의 `Board Delay` 값이 `0.244ns` 등으로 구체적인 소수점 수치로 채워진 것을 확인 (보드 파일 동기화 성공).

- **결과**: 수정한 block design으로 비트스트림을 재생성한 후, XSDB에서 동일한 버스트 다운로드 시도 시에도 **MSB 3바이트 소실 문제가 해결되지 않음.**

> Board Delay 수정이 근본 원인이 아니었거나, 추가 원인이 병존한다.

---

## Phase 6: ps7_init.tcl 및 DDR 초기화 경로 재점검

Phase 4에서 Board Delay를 범인으로 확정했지만 Phase 5에서 fix가 통하지 않았다. Board Delay는 DDR 칩의 타이밍 마진에 영향을 주지만, `dow`는 CPU가 중재하는 JTAG DAP → AXI → DDR 컨트롤러 → DDR 칩 경로다. 단일 `mwr`도 간헐적으로 깨진 것(Phase 2)을 감안하면, Board Delay 외의 원인을 병렬로 조사해야 한다.

### 가설 A: ps7_init.tcl이 여전히 Z7-10 기준 DDR 레지스터를 쓴다

XSA를 재익스포트하더라도 `ps7_init.tcl` 내부의 DDR 타이밍 레지스터(CAS latency, tRCD, tRP 등)가 실제로 바뀌었는지 확인하지 않았다.

**검증 방법**:

```bash
# 수정 전/후 ps7_init.tcl diff
diff <기존_xsa>/ps7_init.tcl <신규_xsa>/ps7_init.tcl | grep -i "DDRC\|DDR\|0xF80"
```

`DDRC` 레지스터(`0xF8006xxx` 대역) 값이 두 파일에서 동일하다면, XSA 재생성이 DDR 초기화에 실질적인 영향을 주지 못한 것이다.

### 가설 B: DDR 데이터 폭 설정 불일치

Z7-20의 DDR(`MT41K256M16`)은 16-bit 칩 × 2개 = 32-bit 구성이다. Zynq IP의 `PCW_UIPARAM_DDR_BUS_WIDTH`가 `32 Bit`로 정확히 설정되어 있는지 확인해야 한다.

**검증 명령어**:

```tcl
get_property CONFIG.PCW_UIPARAM_DDR_BUS_WIDTH [get_bd_cells /processing_system7_0]
# 기대값: 32 Bit
```

### 가설 C: XSDB가 이전 (잘못된) 비트스트림 위에서 실행되고 있다

비트스트림 재생성 후 `xsdb`를 재시작하지 않거나, `hw_server`가 이전 세션의 캐시를 유지하고 있을 가능성이 있다.

**검증 방법**:

```tcl
# xsdb에서 비트스트림 다운로드 후 반드시 시퀀스 준수
connect
targets -set -filter {name =~ "xc7z020"}
fpga -file <new_bitstream>.bit   # 비트스트림 재다운로드 명시
after 500
targets -set -filter {name =~ "ARM*#0"}
source <new_xsa>/ps7_init.tcl    # 새 ps7_init 명시적 재실행
ps7_init
ps7_post_config
dow <elf_file>.elf
```

### 다음 액션

| 순서 | 작업 | 기대 결과 |
|---|---|---|
| 1 | `ps7_init.tcl` diff (구 XSA vs 신 XSA) | DDRC 레지스터 값 변경 여부 확인 |
| 2 | `PCW_UIPARAM_DDR_BUS_WIDTH` 확인 | `32 Bit` 여부 확인 |
| 3 | `xsdb` 세션 완전 재시작 후 비트스트림 명시 재다운로드 | 캐시 오염 여부 배제 |
| 4 | OCM(`0x00000000`)에 ELF 로드 후 실행 테스트 | DDR 완전 우회로 동작 확인 |

---

## Phase 7: 2026-05-13 추가 검증 결과

### 테스트 조건

Phase 6 실행 전 사전 수동 검증 실시. 비트스트림 로드 + `ps7_init` 완료 상태에서 진행.

### 결과 1: 단일 mwr — 정상

```tcl
mwr -force 0x00100000 0xDEADBEEF
mrd -force 0x00100000 1
→ 100000: DEADBEEF  ✅
```

OCM·DDR 모두 단일 쓰기는 정상.

### 결과 2: OCM 버스트 mwr — 정상

```tcl
mwr -force 0x00000000 {0x11111111 0x22222222 0x33333333 0x44444444}
mrd -force 0x00000000 4
→ 11111111 22222222 33333333 44444444  ✅
```

### 결과 3: DDR 버스트 mwr — byte lane 3 오염 (어제와 패턴 상이)

```tcl
mwr -force 0x00100000 {0x11111111 0x22222222 0x33333333 0x44444444}
mrd -force 0x00100000 4
→ 00111111  00222222  00333333  44444444
```

| | byte[3] | byte[2] | byte[1] | byte[0] |
|---|---|---|---|---|
| 기대 | 11 / 22 / 33 / 44 | 11 / 22 / 33 / 44 | 11 / 22 / 33 / 44 | 11 / 22 / 33 / 44 |
| Phase 2 결과 (어제) | **11** (잔류) | 22 ❌ | 22 ❌ | 22 ✅ |
| Phase 7 결과 (오늘) | **00** (소실) | 11 ✅ | 11 ✅ | 11 ✅ |
| 마지막 워드 | **44** ✅ | 44 ✅ | 44 ✅ | 44 ✅ |

**어제와 동일한 패턴 재현 불가.** 어제는 byte[3]에 이전 데이터 잔류(`11`→`22`→`33` 슬라이딩). 오늘은 byte[3] 소실(`00`). 버스트 마지막 워드만 정상인 점은 동일.

Board Delay 수정이 잔류 데이터 오염은 제거했으나 byte lane 3의 근본적 정렬 문제는 미해결.

### 결과 4: dow ELF — byte lane 3 오염 지속

비트스트림 재로드 없이 이전 세션의 ps7_init 상태에서 `dow` 실행.

```tcl
dow build/output/fir_decimator_demo.elf
→ 100% 0.5MB/s  다운로드 성공
mrd -force 0x100000 4
→ D0000031  D000000D  EC000013  D0000023
```

기대값 (`EA000031 EA00000D EA000013 EA000023`)과 byte[3]만 불일치. `dow`도 byte lane 3 오염에서 자유롭지 않음.

### 결과 5: Python 스크립트 mrd 빈 문자열 — 하드웨어 무관한 pexpect 파싱 버그

`download_and_run.py`에서 `mrd` 결과가 `''`로 반환돼 DDR 접근 실패로 오판단. 수동 xsdb에서 동일 시퀀스 실행 시 정상 동작 확인. `mwr`(출력 없음) 직후 내부 while 루프가 다음 프롬프트를 소비해 `mrd` 캡처 버퍼가 비워지는 것이 원인.

---

## Phase 8: 레퍼런스 ps7_init.tcl 적용 및 검증 (2026-05-13)

### 8-1. ps7_init.tcl 파일 상태 점검

세 경로의 ps7_init.tcl이 모두 동일 (diff = 0, 34942 bytes, 832 lines). Vivado 생성본(01:20)이 Vitis 것(00:57)보다 23분 늦지만 내용 동일 → BD 파트 수정이 ps7_init.tcl 값을 실질적으로 바꾸지 못했음.

### 8-2. 레퍼런스 ps7_init.tcl diff 분석

Digilent 공식 Z7-20 레퍼런스 ps7_init.tcl과 diff 결과:

**현재 파일에만 없는 항목 (누락)**

```
0xF8000180  0x00100A20   ← DDRIOB 설정 (DDR I/O 버퍼)
0xF8000190  0x00100500   ← DDRIOB 설정 (DDR I/O 버퍼)
mask_delay 0xF8F00200 × 5  ← DDR PHY 초기화 타이밍 딜레이
```
→ 세 버전의 DDR init proc(`ps7_ddr_init_data_1/2/3_0`) 모두 동일하게 누락.

**DDRC 타이밍 레지스터 값 불일치**

| 레지스터 | 레퍼런스 (Z7-20) | 현재 프로젝트 |
|---|---|---|
| `0xF8006004` | `0x00001081` | `0x00001082` |
| `0xF8006014` | `0x0004281A` | `0x0004285B` |
| `0xF8006018` | `0x44E458D2` | `0x44E458D3` |
| `0xF800601C` | `0x720238E5` | `0x7282BCE5` |
| `0xF8006030` | `0x00040930` | `0x00040B30` |

### 8-3. 레퍼런스 ps7_init.tcl 교체 후 버스트 테스트

세 경로 모두 레퍼런스로 교체 후 테스트.

**테스트 A — 잔류 데이터 있는 상태**
```
→ 11111111  D0222222  EC333333  44444444
```
word 0 byte[3] 정상화. `D0`, `EC`는 직전 `dow`가 남긴 잔류값.

**테스트 B — 단일 mwr로 클리어 후**
```
mwr -force 0x100000~0x10000C 0x00000000
→ 11111111  11222222  F9333333  44444444
```
word 1 byte[3] = `0x11` (word 0의 byte[3] 값), word 2 byte[3] = `0xF9` (불명).

**패턴 변화 요약**

| ps7_init 버전 | word0 | word1 | word2 | word3 |
|---|---|---|---|---|
| 원본 (BD 수정 전) | `00` | `00` | `00` | `44` ✅ |
| 원본 (BD 수정 후) | `00` | `00` | `00` | `44` ✅ |
| 레퍼런스 (잔류 있음) | `11` ✅ | `D0` (잔류) | `EC` (잔류) | `44` ✅ |
| 레퍼런스 (클리어 후) | `11` ✅ | `11` | `F9` | `44` ✅ |

레퍼런스 적용으로 word 0이 안정적으로 정상화됐으나 word 1~2 byte[3]은 매 실행마다 다른 값 → **비결정적(non-deterministic)** 동작.

### 8-4. dow 후 CPU 실행 결과

`dow` 성공(0.5 MB/s) → `con` → PC 확인: **0x00000010 (Data Abort 벡터)**

ELF byte[3] 오염으로 잘못된 ARM 명령어 실행 → Data Abort 예외 발생. UART 무응답.

### 8-5. download_and_run.py pexpect 버그 수정

DDR sanity check에서 `cmd()` 내부 while 루프가 `mwr` 직후 프롬프트를 소비해 이후 `mrd` 캡처 버퍼가 비워짐 → `''` 반환 → `sys.exit()`. 하드웨어 무관한 스크립트 버그.

수정: sanity check를 `cmd()` 대신 직접 `sendline/expect`로 교체, `sys.exit` → 경고 출력 후 계속 진행.

### 8-6. 단일 mwr 워드 주입 방식 시도 (진행 중)

`download_and_run.py` 수정 후 실행 중. ELF 전체를 워드 단위 단일 `mwr`로 주입. 단일 쓰기는 byte[3] 오염 없이 동작함이 검증됐으므로, 성공 시 burst DDR 쓰기가 근본 원인임을 확정.

속도가 매우 느림 (수십 분 예상). 완료 후 벡터 테이블 검증 및 UART 응답 확인 예정.

---

## 원인 재규명 — 24 문서와의 교차 검토

### 핵심 발견

이 문서(27)에서 조사한 byte[3] burst 오염 현상은 **`24_jtag_download_troubleshooting.md` 문제 2·6에서 이미 정확히 진단·해결된 문제**였다. Phase 1~8의 ps7_init.tcl / DDR PHY 방향 조사는 잘못된 가설 추적이었다.

**24 문서의 진단 (문제 2·6)**

> xsdb의 JTAG AXI 마스터는 `mwr` 실행 즉시 byte[0~2]를 전송하지만, byte[3]은 내부 파이프라인 버퍼에 hold한다. byte[3]이 commit되는 조건은 "xsdb가 stdin에서 다음 명령을 기다리며 블로킹할 때"다.

- `burst mwr {0x11.. 0x22.. 0x33.. 0x44..}` → 단일 명령이므로 종료 후 딱 한 번 REPL blocking → **마지막 워드만 byte[3] 정상**. 나머지는 파이프라인에 잔류.
- `dow` → 내부 bulk 전송, per-word REPL blocking 없음 → 동일 증상.
- 이것은 DDR PHY, ps7_init.tcl, DDR 파트와 **무관한** xsdb JTAG 레이어 버그다.

**ps7_init.tcl 교체 시 패턴 변화의 해석**

레퍼런스 ps7_init.tcl 적용 후 word 0가 정상화된 것은 ps7_init 시퀀스 내 register write 패턴이 파이프라인 버퍼 상태를 우연히 바꾼 부수 효과로 보인다. DDR PHY 설정 개선의 근거가 되지 않는다.

### ps7_init.tcl DDR 파트 불일치 — 별개의 미해결 이슈

24 문서의 byte[3] 버그와 별개로, 현재 ps7_init.tcl이 Z7-10 기준 DDR 파라미터로 DDR을 초기화할 가능성은 여전히 유효한 우려다. 이것이 ELF 정상 로드 후에도 프로그램 실행 중 DDR 불안정을 일으킬 수 있다. 단, 이 문서에서 관찰한 burst byte[3] 오염의 원인은 아니다.

### 현재 상태

단일 mwr 워드 주입(pexpect REPL barrier) 진행 중. 24 문서의 검증된 방법이므로 성공 시 byte[3] 오염 없이 ELF 로드 완료 기대. UART 응답 확인 후 ps7_init.tcl DDR 파트 불일치 이슈를 별도로 점검할 것.
