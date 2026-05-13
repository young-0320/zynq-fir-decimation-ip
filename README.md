# zynq-axi-fir-decimation-ip

N=43 Transposed Form FIR LPF + M=2 Decimator IP on Zybo Z7-20 (Zynq-7000).

- FIR: Kaiser β=5.653, fp=15MHz, fs=25MHz, As≥60dB, Q1.15 signed 16-bit
- AXI-Stream wrapper → AXI DMA → PS DDR (Simple DMA, HP0)
- PS bare-metal C: UART(115200) + DMA transfer + PC-side Python FFT 확인

---

## 재현 방법

### 사전 조건

#### 1. Vivado + Vitis Embedded Development 2024.2

AMD Unified Web Installer로 설치. **반드시 `Vitis Embedded Development` 컴포넌트를 포함해야 한다.**

> **주의:** `Vitis (Core Development Kit)`와 `Vitis Embedded Development`는 별개 제품이다.
> Zynq-7000 bare-metal ELF 빌드에는 후자가 필요하다. Core만 설치하면 ARM 툴체인, Lopper, BSP 템플릿이 없어서 ELF 생성이 불가능하다.

설치 후 확인:
```bash
# 아래 두 바이너리가 모두 존재해야 한다
ls ~/Xilinx/Vitis/2024.2/bin/vitis        # Vitis Core
ls ~/Xilinx/Vitis/2024.2/bin/xsdb         # Vitis Embedded Development
```

#### 2. Lopper 수동 설치 확인 (AMD 설치 버그 대응)

AMD 설치 프로그램에 알려진 버그가 있어 Lopper pip install이 실패해도 설치 완료로 표시된다.
Vitis가 XSA → BSP 변환 시 Lopper를 내부적으로 호출하므로, 설치되어 있지 않으면 플랫폼 빌드가 실패한다.

```bash
# 설치 여부 확인
ls ~/Xilinx/Vitis/2024.2/tps/lnx64/lopper-1.1.0/env/lib/python3.8/site-packages/lopper/

# 위 경로가 비어 있으면 수동 설치 필요:
LD_LIBRARY_PATH=~/Xilinx/Vitis/2024.2/tps/lnx64/python-3.8.3/lib \
~/Xilinx/Vitis/2024.2/tps/lnx64/lopper-1.1.0/env/bin/pip install \
  -r ~/Xilinx/Vitis/2024.2/tps/lnx64/lopper-1.1.0-packages/py38/requirements.txt \
  --find-links ~/Xilinx/Vitis/2024.2/tps/lnx64/lopper-1.1.0-packages/py38/wheels \
  --no-index
```

#### 3. 환경변수 설정 (터미널 세션마다)

`vivado`, `vitis`, `xsdb` 명령어를 쓰려면 매 터미널 세션에서 한 번 소싱해야 한다.

```bash
source ~/Xilinx/Vivado/2024.2/settings64.sh
# 설치 경로가 다르면 해당 경로로 수정
```

#### 4. 기타 의존성

| 항목 | 버전 | 용도 |
|------|------|------|
| iverilog | 11 이상 | RTL 시뮬레이션 |
| Python | 3.13 | PC 측 FFT 스크립트 |
| uv | 최신 | Python 가상환경 관리 |
| minicom | 임의 | UART 터미널 (보드 검증 시) |
| Zybo Z7-20 보드 파일 | — | Vivado 보드 지원 |

```bash
# Ubuntu 기준 설치
sudo apt install iverilog minicom
pip install uv   # 또는 공식 설치 방법: https://docs.astral.sh/uv/
```

---

### 빌드 순서

```bash
# 1. Python 환경
uv sync

# 2. 시뮬레이션 벡터 생성
uv run python -m sim.python.run_compare_ideal_vs_fixed --num-taps 43 --form transposed
uv run python -m sim.python.export_rtl_bringup_vectors \
    --num-taps 43 \
    --input-dir sim/output/ideal_vs_fixed_trans_n43 \
    --output-dir sim/vectors/transposed_form/n43

# 3. Python 모델 테스트
uv run pytest -q

# 4. RTL 시뮬레이션 (iverilog -g2012)
iverilog -g2012 -o sim/build/tb_fir_decimator_n43_axis.out \
    sim/rtl/tb/transposed_form/tb_fir_decimator_n43_axis.sv \
    rtl/transposed_form/n43/fir_decimator_n43_axis.v \
    rtl/transposed_form/n43/fir_decimator_n43.v \
    rtl/transposed_form/n43/fir_n43.v \
    rtl/transposed_form/decimator_m2_phase0.v
vvp sim/build/tb_fir_decimator_n43_axis.out

# 5. Vivado: 비트스트림 + XSA 생성 → build/output/bd_fir_dma_wrapper.xsa
#    (실행 전: source <Xilinx 설치경로>/Vivado/2024.2/settings64.sh)
mkdir -p build/vivado
vivado -mode batch \
  -journal build/vivado/vivado.jou \
  -log build/vivado/vivado.log \
  -source vivado/build_bd_fir_dma.tcl

# 6. Vitis: BSP + ELF 빌드 → build/output/fir_decimator_demo.elf
rm -rf build/vitis
vitis -s vitis/build_fir_decimator_demo.py

# 7. BOOT.bin 생성 (FSBL + 비트스트림 + ELF 패키징)
bootgen -arch zynq -image build/output/fir_decimator_demo.bif \
        -o build/output/BOOT.bin -w on

# 8. SD카드 준비 (FAT32 포맷 후 BOOT.bin 한 파일만 루트에 복사)
#    JP5 점퍼를 SD 위치로 이동 후 SD카드 삽입, USB 케이블 연결, 전원 인가
#    → DONE LED 점등 확인

# 9. UART 동작 확인
minicom -D /dev/ttyUSB1 -b 115200
# minicom에서 입력: 3 5000000 20000000 30000000

# 10. PC Python FFT 시각화
python sw/fir_decimator_demo.py --mode 1-1 --port /dev/ttyUSB1
```

> JTAG `xsdb dow` 방식은 DDR byte lane 3 오염으로 폐기됨 (`docs/log/24`, `docs/log/27`).
> 현재 워크플로우 → `docs/workflow/workflow_v12.md`
> Vitis 빌드 트러블슈팅 상세 → `docs/log/23_vitis_embedded_build_troubleshooting.md`
