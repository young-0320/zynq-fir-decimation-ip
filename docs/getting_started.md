# Getting Started — 빌드·데모·검증 절차

이 문서는 소스에서 실보드 데모까지 재현하는 전체 절차를 담는다. 레포 소개와 결과
요약은 최상위 `README.md`, PASS 기준과 파이프라인 상세는 `docs/project_pipeline.md`,
빌드 산출물 경로 규칙은 `docs/build_artifacts.md` 참고.

## Quick Setup / Dependencies

PC 측 데모·리포트·Python 검증은 bare `python` 대신 프로젝트 `uv` 환경을 사용한다.
의존성은 `pyproject.toml`에 선언되어 있다 (`pyserial`, `numpy`, `scipy`, `matplotlib`,
`pytest`, `pexpect`).

```bash
uv sync
uv run python -c "import serial, numpy, scipy, matplotlib; print('Python deps OK')"
```

PC 스크립트는 `uv run python ...`으로 실행한다. 시리얼 포트 이름은 머신마다 다르다:

| Host OS | Typical UART port |
| --- | --- |
| Linux/Ubuntu | `/dev/ttyUSB0`, `/dev/ttyUSB1` |
| Windows | `COM3`, `COM4`, etc. |

RTL 시뮬레이션에는 `iverilog`/`make`, 하드웨어 빌드에는 AMD Vivado + Vitis Embedded
Development 2024.2 + `bootgen`이 필요하다. 아래 Prerequisites 참고.

## Prerequisites

AMD Vivado + Vitis Embedded Development 2024.2가 하드웨어/bare-metal 빌드에 필요하다.
Vitis Core Development Kit만으로는 Zynq-7000 standalone ELF 생성이 되지 않는다.

하드웨어 빌드 터미널마다 Vivado 2024.2 환경 스크립트를 source한다. Ubuntu의 일반적인
설치 경로는 `$HOME/Xilinx/Vivado/2024.2/settings64.sh` 또는
`/opt/Xilinx/Vivado/2024.2/settings64.sh`.

```bash
export VIVADO_SETTINGS=/path/to/Xilinx/Vivado/2024.2/settings64.sh
source "$VIVADO_SETTINGS"

vivado -version
vitis -version
bootgen -help >/dev/null
```

기타 도구:

| Tool | Use |
| --- | --- |
| `uv` + Python 3.13 | Python environment/tests |
| `iverilog` 11+ | RTL simulation |
| `minicom` or equivalent | UART console |
| Digilent Zybo Z7-20 board files | Vivado board part |

## Main Demo Pipeline

소스에서 SD 부팅 데모까지의 최단 경로다. 모델/RTL 회귀 검증은 아래 Verification
Pipeline에 따로 정리한다.

### 1. Hardware Platform Build

레포 루트에서:

```bash
source "$VIVADO_SETTINGS"
mkdir -p build/fir_n43/vivado build/fir_n43/vitis build/fir_n43/output
cd build/fir_n43/vivado

vivado -mode batch \
  -journal vivado.jou \
  -log vivado.log \
  -source ../../../vivado/fir_n43/build_bd_fir_dma.tcl

cd ../../..
```

기대 산출물:

```text
build/fir_n43/output/bd_fir_dma_wrapper.bit
build/fir_n43/output/bd_fir_dma_wrapper.xsa
```

v1@115MHz / v2@145MHz 골든 빌드의 재현 명령은 `docs/build_artifacts.md` 참고
(clk_wiz 스크립트에 `-tclargs <MHz>`).

### 2. Application And BOOT Image

canonical XSA에서 Vitis platform/app을 빌드하고 FSBL + bitstream + app ELF를 묶는다:

```bash
vitis -s vitis/fir_n43/build_fir_decimator_demo.py

bootgen -arch zynq \
  -image build/fir_n43/output/fir_decimator_demo.bif \
  -o build/fir_n43/output/BOOT.bin -w on
```

기대 산출물:

```text
build/fir_n43/output/fsbl.elf
build/fir_n43/output/fir_decimator_demo.elf
build/fir_n43/output/fir_decimator_demo.bif
build/fir_n43/output/BOOT.bin
```

### 3. Board Demo

1. `build/fir_n43/output/BOOT.bin`을 FAT32 SD 카드 루트에 `BOOT.bin`으로 복사.
2. JP5를 SD boot로, SD 삽입, USB 연결, 보드 전원 인가.
3. UART 배너 확인:

```text
READY FIR
```

4. 보드 리셋 후 시나리오당 한 번씩 PC 측 FFT 확인을 실행.

Ubuntu 예시:

```bash
uv run python sw/fir_decimator_demo.py --mode 1-1 --port /dev/ttyUSB1 --timeout 30
uv run python sw/fir_decimator_demo.py --mode 1-2 --port /dev/ttyUSB1 --timeout 30
```

Windows 예시:

```powershell
uv run python sw/fir_decimator_demo.py --mode 2 --port COM3 --timeout 30
```

기대 결과: 각 명령이 보드 출력을 수신해 FFT plot에 도달한다.

알려진 제약: 100 MHz baseline `BOOT.bin`은 검증 이력 보존을 위해 수정 전 RTL을
의도적으로 유지하므로, 보드 리셋 없이 `1-1` 후 `1-2`를 연속 실행하면 `ERR:1`/MM2S
timeout이 날 수 있다. 이 back-to-back 실패의 근본 원인은 AXIS 래퍼 프레이밍 버그로
규명·수정되었고(`docs/log/41`–`44`), 수정 RTL이 포함된 115/145 MHz 빌드에서는 리셋
없는 반복 실행이 시뮬레이션과 보드 실측(전력 측정 중 `mode 1-1` 반복, `docs/log/46`
§5)에서 확인되었다. 단 어느 빌드든 전송 도중 abort(timeout)된 뒤에는 보드 리셋이
필요하다 — 펌웨어에 PL 래퍼 리셋 수단이 없다(`docs/log/44` §4).

## Verification Pipeline

DSP 수식, Q-format 정책, RTL datapath, 계수를 바꾸거나 릴리스/리포트 결과를 기록하기
전에 사용한다. `sim/output/`과 `sim/vectors/` 아래 생성물은 일회용 산출물로 커밋하지
않는다 — 레포는 모델·생성기·테스트벤치 소스만 추적하고, `.npy`/`.hex` 벡터는 필요할
때 Python 모델 파이프라인에서 재생성한다.

### 1. Python Float/Fixed Model And Vector Generation

```bash
uv sync
uv run pytest -q

uv run python -m sim.python.run_check_coeff_stopband_spec --num-taps 43
uv run python -m sim.python.run_compare_ideal_vs_fixed --num-taps 43 --form transposed
uv run python -m sim.python.export_rtl_bringup_vectors \
  --num-taps 43 \
  --input-dir sim/output/ideal_vs_fixed_trans_n43 \
  --output-dir sim/vectors/transposed_form/n43
```

기대 결과: Python 테스트 통과, 43-tap 이상/양자화 계수 응답이 60 dB stopband 기준
충족, N=43 transposed fixed-point 벡터 재생성. stopband 기준 미달 시 계수 체크가
non-zero로 종료하며 실패 탭/응답을 출력한다.

### 2. RTL Simulation

```bash
cd sim
make clean
make run_all
make run_bug
cd ..
```

기대 결과: canonical N=43 테스트벤치 전체(v1/v2 AXIS 골든 포함)가 fail/mismatch/error
없이 PASS. `make run_bug`는 AXIS 래퍼 회귀 스위트(skid-buffer depth, multi-packet
stress, TLAST-bubble sweep — `docs/log/41`–`44`)로 역시 PASS여야 한다. N=5
direct-form bringup 테스트는 legacy 전용으로 `make run_legacy_n5`로 따로 돈다.

## Fast Rebuild

`sw/fir_decimator_demo.c`만 바뀌었고 기존 `build/fir_n43/vitis` workspace가 유효할 때
사용한다. 현재 하드웨어/플랫폼을 재사용해 app ELF, BIF, BOOT 이미지만 재생성한다.

```bash
vitis/fir_n43/rebuild_boot_image.sh --boot-tag FIR
```

기대 산출물:

```text
build/fir_n43/output/BOOT.bin
```

## Debug And Historical Flows

Smoke/debug 경로는 회귀·근본원인 도구로 레포에 남아 있으며, 메인 재현 파이프라인은
아니다:

- `rtl/debug/axis_dma_smoke_test.v`
- `rtl/debug/axis_decimator_m2_n43_debug.v`
- `vivado/debug/smoke/build_bd_fir_dma_smoke.tcl`
- `vivado/debug/axis_debug/build_bd_fir_dma_axis_debug.tcl`
- `vitis/legacy/download_and_run.py`, `vitis/legacy/bringup_demo/download_bringup.py`는
  역사적 JTAG/XSDB 플로우로, 신뢰 검증 경로가 아니다.

DMA/DDR/UART 전송 문제를 디버깅할 때는 `docs/log/31`–`32`(DMA length 근본원인)를
먼저 본다.
