# 33. fir_n43 파이프라인 폴더 구조 개편

- 작성일: 2026-05-24
- 선행 문서:
  - `31_dma_smoke_test_and_length_width_fix.md`
  - `32_smoke_pass_after_dma_length_width_fix.md`
  - `../workflow/fir_n43_dependency_map.md`
- 관련 커밋:
  - `4057c59 refactor: organize fir_n43 Vivado and Vitis pipelines`
  - `79c99d7 docs: document fir_n43 reproducible pipeline`

---

## 결론

오늘부터 재현 가능한 메인 데모 기준 target 이름은 `fir_n43`로 둔다.

`v1`, `baseline`, `transposed`, `decimator` 같은 이름은 현재 폴더명에 붙이지 않았다.

이유:

1. 현재 하드웨어의 핵심 식별자는 43-tap FIR target인 `fir_n43`다.
2. `transposed-form`, `M=2 decimator`는 설계 상세이며 문서와 RTL 경로에서 이미 드러난다.
3. 나중에 개선판이 생기면 `fir_n43_pipelined`처럼 target 단위로 추가하면 된다.
4. 아직 존재하지 않는 future target 디렉토리는 미리 만들지 않는다.

확정한 build artifact 구조:

```text
build/
  fir_n43/
    vivado/
    vitis/
    output/
  debug/
    smoke/
      vivado/
      output/
    axis_debug/
      vivado/
      output/
```

예약만 해둔 future target:

```text
build/
  fir_n43_pipelined/      # 추후 확장용. 지금은 생성하지 않음.
    vivado/
    vitis/
    output/
```

---

## 배경

log 31, 32에서 DMA smoke-test와 메인 FIR BOOT가 통과하면서 보드 데모 경로가 살아났다.

그 과정에서 여러 debug script와 임시 build output이 생겼고, repo root와 `vivado/`, `vitis/`, `build/output` 사이의 책임 경계가 흐려졌다.

특히 다음 문제가 있었다.

```text
1. 메인 FIR와 debug smoke/axis_debug 빌드가 같은 output 위치를 공유하기 쉬웠다.
2. Vivado journal/log/backup 파일이 repo root에 남을 수 있었다.
3. Vitis bringup/JTAG legacy script와 SD boot 기반 메인 demo script가 같은 층위에 있었다.
4. 나중에 v2 또는 pipelined variant가 생길 때 target별 산출물 분리가 어렵다.
5. README에서 설명하는 main pipeline과 실제 script path가 계속 어긋날 위험이 있었다.
```

따라서 이번 정리는 기능 변경이 아니라 재현성과 유지보수성을 위한 폴더 구조 정리다.

---

## source-controlled script 구조

### Vivado

개편 후 Vivado script 구조:

```text
vivado/
  fir_n43/
    bd_fir_dma.tcl
    build_bd_fir_dma.tcl
    build_fir_transposed_n43.tcl
  debug/
    smoke/
      bd_fir_dma_smoke.tcl
      build_bd_fir_dma_smoke.tcl
    axis_debug/
      bd_fir_dma_axis_debug.tcl
      build_bd_fir_dma_axis_debug.tcl
```

의미:

| 경로 | 역할 |
| --- | --- |
| `vivado/fir_n43/` | 현재 canonical main hardware target |
| `vivado/debug/smoke/` | DMA/DDR/UART transport smoke-test |
| `vivado/debug/axis_debug/` | FIR를 제거한 AXI-Stream decimator debug target |

메인 build wrapper는 자기 위치 기준으로 repo root를 계산한다.

```tcl
set SCRIPT_DIR [file normalize [file dirname [info script]]]
set REPO_ROOT [file normalize [file join $SCRIPT_DIR ../..]]
```

따라서 `vivado/fir_n43/build_bd_fir_dma.tcl`은 어디에서 실행하더라도 source path는 고정된다.

하지만 Vivado가 생성하는 journal/log/backup 파일을 repo root에 흩뿌리지 않기 위해 권장 실행 위치는 `build/fir_n43/vivado/`다.

```bash
mkdir -p build/fir_n43/vivado build/fir_n43/vitis build/fir_n43/output
cd build/fir_n43/vivado
vivado -mode batch \
  -journal vivado.jou \
  -log vivado.log \
  -source ../../../vivado/fir_n43/build_bd_fir_dma.tcl
cd ../../..
```

---

### Vitis

개편 후 Vitis script 구조:

```text
vitis/
  fir_n43/
    build_fir_decimator_demo.py
    rebuild_boot_image.sh
  legacy/
    download_and_run.py
    bringup_demo/
      download_bringup.py
```

의미:

| 경로 | 역할 |
| --- | --- |
| `vitis/fir_n43/build_fir_decimator_demo.py` | XSA에서 Vitis platform/app/workspace 전체 재생성 |
| `vitis/fir_n43/rebuild_boot_image.sh` | C source만 바뀐 경우 빠른 app rebuild + BOOT packaging |
| `vitis/legacy/` | JTAG/XSDB 기반 historical debug path. 최종 검증 경로가 아님 |

메인 Vitis script도 자기 위치 기준으로 repo root를 계산한다.

```python
REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)
```

기본 산출물은 모두 `build/fir_n43/` 아래로 간다.

```text
build/fir_n43/vitis/    # Vitis workspace
build/fir_n43/output/   # XSA, bit, ELF, BIF, BOOT.bin copies
```

---

## 메인 데모 파이프라인

현재 README와 dependency map의 canonical 흐름은 다음이다.

```text
RTL + BD Tcl
  -> Vivado hardware build
  -> XSA + bitstream
  -> Vitis platform/app build
  -> FSBL + app ELF + BIF
  -> bootgen
  -> BOOT.bin
  -> SD boot board demo
```

각 단계의 대표 명령:

```bash
# 1. Vivado hardware build
mkdir -p build/fir_n43/vivado build/fir_n43/vitis build/fir_n43/output
cd build/fir_n43/vivado
vivado -mode batch \
  -journal vivado.jou \
  -log vivado.log \
  -source ../../../vivado/fir_n43/build_bd_fir_dma.tcl
cd ../../..

# 2. Vitis full regeneration
vitis -s vitis/fir_n43/build_fir_decimator_demo.py

# 3. BOOT.bin packaging
bootgen -arch zynq \
  -image build/fir_n43/output/fir_decimator_demo.bif \
  -o build/fir_n43/output/BOOT.bin -w on
```

이 흐름은 데모 재현을 위한 메인 경로다.

Python float/fixed golden model, vector generation, RTL sim은 별도의 verification pipeline으로 둔다. 메인 데모 README에는 연결점만 남기고, 보드 demo pipeline과 섞지 않는다.

---

## fast rebuild 정책

C source만 바뀐 경우 전체 Vivado/Vitis 재생성을 반복하지 않는다.

대표 명령:

```bash
vitis/fir_n43/rebuild_boot_image.sh --boot-tag FIR
```

이 script는 기본적으로 다음 산출물을 `build/fir_n43/output/`에 모은다.

```text
fsbl.elf
bd_fir_dma_wrapper.bit
fir_decimator_demo.elf
fir_decimator_demo.bif
BOOT.bin
```

Debug BOOT를 만들 때는 `--bit`, `--boot-out`, `--boot-tag`로 output directory를 분리한다.

예:

```bash
vitis/fir_n43/rebuild_boot_image.sh \
  --bit build/debug/smoke/output/bd_fir_dma_smoke_wrapper.bit \
  --boot-out build/debug/smoke/output/BOOT.bin \
  --boot-tag SMOKE
```

이 경우 BIF, FSBL copy, bit copy, app ELF copy, BOOT image는 모두 `build/debug/smoke/output/` 아래에 생성된다.

---

## debug build 격리

이번 정리에서 smoke/axis_debug script는 삭제하지 않았다.

삭제하지 않은 이유:

1. log 31, 32에서 실제 root cause 분리에 사용한 검증 자산이다.
2. 나중에 FIR RTL이 다시 timeout을 만들면 transport와 FIR datapath를 빠르게 분리할 수 있다.
3. 단, 메인 파이프라인과 같은 output 위치를 공유하면 혼동이 커지므로 `debug/` 아래로 격리하는 것이 맞다.

Smoke build:

```bash
mkdir -p build/debug/smoke/vivado build/debug/smoke/output
cd build/debug/smoke/vivado
vivado -mode batch \
  -journal vivado.jou \
  -log vivado.log \
  -source ../../../../vivado/debug/smoke/build_bd_fir_dma_smoke.tcl
cd ../../../..
```

AXIS debug build:

```bash
mkdir -p build/debug/axis_debug/vivado build/debug/axis_debug/output
cd build/debug/axis_debug/vivado
vivado -mode batch \
  -journal vivado.jou \
  -log vivado.log \
  -source ../../../../vivado/debug/axis_debug/build_bd_fir_dma_axis_debug.tcl
cd ../../../..
```

---

## legacy bringup/JTAG path 정책

기존 Vitis bringup/JTAG download script는 삭제하지 않고 `vitis/legacy/`로 이동했다.

판정:

```text
vitis/legacy/download_and_run.py
vitis/legacy/bringup_demo/download_bringup.py
```

이 경로는 historical debug context로 남긴다. 최종 demo 재현성의 기준은 아니다.

최종 검증 기준:

```text
SD boot
-> bare-metal app
-> AXI DMA
-> DDR buffer
-> UART result return
-> PC Python demo
```

JTAG/XSDB direct DDR write path는 이전 log에서 MSB 오염 가능성이 있었기 때문에 최종 demo pipeline의 신뢰 기준으로 쓰지 않는다.

---

## path 변경 후 확인한 것

정적 확인:

```bash
bash -n vitis/fir_n43/rebuild_boot_image.sh

python -m py_compile \
  vitis/fir_n43/build_fir_decimator_demo.py \
  vitis/legacy/download_and_run.py \
  vitis/legacy/bringup_demo/download_bringup.py
```

경로 consistency 확인:

```bash
rg -n "vitis/(build_fir_decimator_demo|rebuild_boot_image|download_and_run|bringup_demo)|vivado/(build_bd|bd_fir_dma|bd_fir_dma_axis|bd_fir_dma_smoke|build_fir_transposed)|build/(vivado|vitis|output)" \
  -g '!docs/log/**' \
  -g '!docs/workflow/workflow_v1[0-4].md' \
  -g '!docs/workflow/fir_n43_dependency_map.md' \
  -g '!build/**' \
  -g '!*.jou' \
  -g '!*.log'
```

예외:

1. `docs/log/**`는 historical log이므로 당시 경로를 그대로 둘 수 있다.
2. `docs/workflow/workflow_v10`부터 `workflow_v14`까지는 당시 작업 기록이므로 old path가 남아도 된다.
3. 새 canonical 경로는 README, `workflow_v15.md`, `fir_n43_dependency_map.md`를 기준으로 본다.

추가로 세 BD Tcl 모두 `CONFIG.c_sg_length_width {23}` 설정이 유지되는지 확인했다.

---

## 앞으로의 규칙

### 1. build output은 target별로 분리한다

메인 target:

```text
build/fir_n43/
```

Debug target:

```text
build/debug/<debug_target>/
```

Future target:

```text
build/<target_name>/
```

예상 예:

```text
build/fir_n43_pipelined/
```

단, 실제 target이 생기기 전에는 디렉토리를 미리 생성하지 않는다.

### 2. source script도 target별로 둔다

메인:

```text
vivado/fir_n43/
vitis/fir_n43/
```

Debug:

```text
vivado/debug/smoke/
vivado/debug/axis_debug/
```

Legacy:

```text
vitis/legacy/
```

### 3. Vivado는 build working directory에서 실행한다

Vivado는 실행 위치에 journal/log/backup 파일을 만들 수 있다.

따라서 `vivado -source ...`를 repo root에서 바로 실행하지 않고, 가능하면 아래 위치로 들어가서 실행한다.

```text
build/fir_n43/vivado/
build/debug/smoke/vivado/
build/debug/axis_debug/vivado/
```

이렇게 하면 `vivado.jou`, `vivado.log`, `vivado_*.backup.jou` 같은 파일이 repo root에 남는 일을 줄일 수 있다.

### 4. 재현성 문서의 기준은 dependency map이다

경로를 바꾸면 먼저 아래 문서를 갱신한다.

```text
docs/workflow/fir_n43_dependency_map.md
```

그 다음 README의 메인 명령어와 `workflow_v*.md`를 맞춘다.

---

## 이번 정리의 의미

이번 개편으로 repo는 다음 경계를 갖게 됐다.

```text
메인 데모:
  source: vivado/fir_n43/, vitis/fir_n43/
  build:  build/fir_n43/

디버그 하드웨어:
  source: vivado/debug/<target>/
  build:  build/debug/<target>/

레거시 JTAG:
  source: vitis/legacy/
  build:  build/legacy/...
```

따라서 앞으로 작업 순서는 다음처럼 잡는다.

1. README의 Main Demo Pipeline으로 보드 demo 재현성을 유지한다.
2. Verification Pipeline은 Python model/vector/RTL sim 쪽에서 별도로 유지한다.
3. smoke/axis_debug는 메인 artifact를 오염시키지 않고 `build/debug/` 아래에서만 사용한다.
4. 새 아키텍처가 생기면 `fir_n43_pipelined` 같은 별도 target으로 추가한다.

한 줄 요약:

```text
오늘의 정리는 기능 추가가 아니라, 메인 demo target과 debug/legacy 경로를 분리해서
다음 재현과 다음 아키텍처 확장을 안전하게 만들기 위한 repo 구조 정리다.
```
