# Vitis ELF 빌드 트러블슈팅 기록

- 작성일: 2026-05-08
- 목표: `sw/fir_decimator_demo.c` → `build/output/fir_decimator_demo.elf` 컴파일
- 결과: ✅ 최종 성공 (242KB ELF 생성)

---

## 배경

Zynq-7000(Zybo Z7-20) 보드에서 bare-metal C 코드를 실행하려면 ELF 파일이 필요하다.
ELF를 만들려면 ARM 크로스 컴파일러(arm-none-eabi-gcc)와 BSP(Board Support Package)가 필요하다.

- **BSP란?** Vivado가 만든 하드웨어 정보(XSA)를 기반으로 Vitis가 생성하는 드라이버 모음.
  `XAxiDma_Transfer()`, `XUartPs_Send()` 같은 함수의 헤더와 라이브러리가 여기 있다.
- **XSA란?** Vivado Block Design 합성/구현 후 생성되는 하드웨어 기술 파일. BSP 생성의 입력.
- **ELF란?** ARM CPU가 실행할 수 있는 컴파일된 바이너리. Vitis가 XSA + C 소스로 만든다.

---

## 문제 1: `xsct` 명령어를 찾지 못함

**증상**
```
xsct: command not found
```
Ubuntu가 `xsct`를 알 수 없는 패키지로 인식하고 설치를 권유했다.

**원인**
Vivado 2024.2부터 `xsct`가 `bin/` 디렉토리가 아닌 `xsct-trim/bin/` 디렉토리로 분리됐다.
`settings64.sh`를 소싱해도 이 경로는 PATH에 자동으로 추가되지 않는다.

**해결**
`settings64.sh`를 소싱하면 `$XILINX_VIVADO` 환경변수가 잡히므로, 이를 활용한 풀 경로를 사용한다.
```bash
$XILINX_VIVADO/xsct-trim/bin/xsct vitis/build_fir_decimator_demo.tcl
```

---

## 문제 2: xsct TCL 스크립트 실행 실패

**증상**
```
Error: --classic option is only supported by full Vitis installation.
Timeout while establishing a connection with Vitis
```

**원인**
xsct 2024.2가 내부적으로 `vitis --classic`을 호출하는데,
AMD가 2024.x에서 classic IDE를 별도 컴포넌트로 분리해 제거했다.
사실상 xsct 자체가 2024.x에서 deprecated 됐다.

xsct(구버전 방식)와 Vitis 2024.x의 호환성 문제였다.

**해결**
AMD 공식 권고대로 xsct TCL 스크립트 → **Vitis Python API 스크립트**로 재작성.

- 기존: `xsct vitis/build_fir_decimator_demo.tcl`
- 신규: `vitis -s vitis/build_fir_decimator_demo.py`

TCL → Python 주요 API 대응:

| TCL (xsct) | Python (vitis -s) |
|---|---|
| `setws` | `client.update_workspace()` |
| `platform create` | `client.create_platform_component()` |
| `platform generate` | `platform.build()` |
| `app create` | `client.create_app_component()` |
| `importsources` | `app.import_files()` |
| `app config libs m` | `app.set_app_config(key="USER_LINK_LIBRARIES", values=["m"])` |
| `app build` | `app.build()` |

---

## 문제 3: Python 스크립트 workspace 오류

**증상**
```
Exception: Vitis IDE cannot recognize the workspace version.
```

**원인 1**
`build/vitis/` 안에 구버전 xsct가 만든 `fir_dma_platform/` 디렉토리가 남아 있었다.
새 Vitis가 이를 읽으려다 버전 불일치로 실패.

**원인 2**
Python 스크립트에서 `create_client()` + `set_workspace()` 분리 방식 사용.
새 Vitis에서는 `update_workspace()`로 workspace를 초기화해야 한다.

**해결**
```bash
rm -rf build/vitis
```
스크립트 수정:
```python
# 변경 전
client = vitis.create_client()
client.set_workspace(WORKSPACE)

# 변경 후
client = vitis.create_client()
client.update_workspace(WORKSPACE)
```

---

## 문제 4: Lopper `null` 경로 오류

**증상**
```
Failed to create platform: Invalid Lopper Installation Directory path 'null'.
```

**Lopper란?**
Vitis 2024.x에서 플랫폼(BSP) 생성 시 내부적으로 호출하는 Python 툴.
XSA에서 하드웨어 정보를 읽어 BSP 설정 파일을 만드는 역할.
사용자가 직접 쓰는 툴이 아니라 Vitis가 자동 호출한다.

**원인**
`Vitis (Core Development Kit)`만 설치되어 있고 **`Vitis Embedded Development`** 가 누락.
ARM 툴체인, Lopper, BSP 템플릿이 전혀 없는 상태였다.

AMD가 2023년부터 임베디드 개발 툴을 `Vitis Embedded Development`로 별도 분리했다.
기존에 Vivado만 설치하거나 Vitis Core만 설치한 경우 이 컴포넌트가 없다.

`Vitis`와 `Vitis Embedded Development`의 차이:
- **Vitis (Core)**: Versal AI Engine, HLS 가속 앱 개발용. Zynq-7000 bare-metal에는 불필요.
- **Vitis Embedded Development**: Zynq-7000, ZynqMP bare-metal/RTOS 앱 개발용. ARM 툴체인 + Lopper + BSP 포함.

**해결 과정**
1. AMD Unified Web Installer(BIN, 303MB) 다운로드
2. Vivado 실행 → Help → Add Design Tools or Devices
3. `Vitis Embedded Development` 체크 → 설치 (다운로드 7.27GB)

---

## 문제 5: Vitis Embedded Development 설치 후에도 Lopper 오류 지속

**증상**
```
Invalid Lopper Directory path '...lopper-1.1.0/env/lib/python3.8/site-packages/lopper/lops'.
```

**원인**
AMD 설치 버그. 설치 프로그램이 Lopper 가상환경 폴더는 만들었지만 실제 `pip install`이 실패했다.
`install.log` 마지막 줄:
```
lopper: command not found
Installation Failed!
```
그럼에도 전체 설치 완료 메시지가 표시됐다.

추가로 Lopper 가상환경이 Python 3.8 기반인데, 시스템에 Python 3.8 shared library가 없어서
pip 자체를 실행할 수 없었다.

**해결**
Vitis 설치 폴더 안에 Python 3.8이 번들되어 있으므로 `LD_LIBRARY_PATH`로 경로를 잡아 수동 설치:
```bash
LD_LIBRARY_PATH=/home/young/Xilinx/Vitis/2024.2/tps/lnx64/python-3.8.3/lib \
/home/young/Xilinx/Vitis/2024.2/tps/lnx64/lopper-1.1.0/env/bin/pip install \
  -r .../lopper-1.1.0-packages/py38/requirements.txt \
  --find-links .../lopper-1.1.0-packages/py38/wheels \
  --no-index
```

---

## 문제 6: `xuartps.h: No such file or directory`

**증상**
```
fatal error: xuartps.h: No such file or directory
```

**원인**
Block Design(bd_fir_dma.tcl)의 PS7 설정에서 UART1이 활성화되지 않은 채로 XSA가 생성됐다.

구버전 xsct BSP는 PS7의 모든 주변장치(UART, SPI, I2C 등)를 활성화 여부와 무관하게 BSP에 포함했다.
새 Vitis Embedded Development는 SDT(System Device Tree) 방식을 사용하며,
XSA에 명시적으로 활성화된 주변장치만 BSP에 포함한다.

**해결 시도 1 (실패)**: 잘못된 파라미터 이름 사용
```tcl
CONFIG.PCW_UART1_ENABLE {1}  ← 존재하지 않는 파라미터명
```

**해결 시도 2 (실패)**: 이름은 맞았지만 클럭 설정 누락

**해결 (성공)**: Zybo Z7-20 공식 보드 preset 파일(`preset.xml`)에서 정확한 파라미터 확인 후 적용
```tcl
CONFIG.PCW_UART0_PERIPHERAL_ENABLE {0}
CONFIG.PCW_UART1_BAUD_RATE {115200}
CONFIG.PCW_UART1_GRP_FULL_ENABLE {0}
CONFIG.PCW_UART1_PERIPHERAL_ENABLE {1}
CONFIG.PCW_UART1_UART1_IO {MIO 48 .. 49}
CONFIG.PCW_UART_PERIPHERAL_CLKSRC {IO PLL}
CONFIG.PCW_UART_PERIPHERAL_DIVISOR0 {10}
CONFIG.PCW_UART_PERIPHERAL_FREQMHZ {100}
```
→ Vivado 재빌드로 XSA 재생성

---

## 문제 7: `XPAR_XUARTPS_1_DEVICE_ID` 미정의

**증상**
```
error: 'XPAR_XUARTPS_1_DEVICE_ID' undeclared; did you mean 'XPAR_XUARTPS_1_CLOCK_HZ'?
```

**원인**
구버전 BSP(xsct 방식)에서는 UART0 = index 0, UART1 = index 1로 두 인스턴스가 있었다.
그래서 C 코드에 `XPAR_XUARTPS_1_DEVICE_ID`를 사용했다.

새 BSP(SDT 방식)에서는 UART1만 활성화했으므로 유일한 인스턴스 → canonical index 0.
`xparameters.h`에 `XPAR_XUARTPS_0_*` 만 존재하고 `DEVICE_ID` 매크로 자체가 없다.

**해결**
`sw/fir_decimator_demo.c` 수정:
```c
// 변경 전
#define UART_DEVICE_ID XPAR_XUARTPS_1_DEVICE_ID

// 변경 후
#define UART_DEVICE_ID 0  // UART1 단일 인스턴스 → canonical index 0
```
Vivado 재빌드 불필요. Vitis 빌드만 다시 실행.

---

## 최종 빌드 명령어

```bash
# 1. Vivado: XSA 생성 (하드웨어 변경 시에만)
vivado -mode batch -source vivado/build_bd_fir_dma.tcl

# 2. Vitis: ELF 빌드 (C 소스 변경 시)
rm -rf build/vitis
vitis -s vitis/build_fir_decimator_demo.py
```

**산출물**
```
build/output/bd_fir_dma_wrapper.xsa   ← Vivado 산출물 (비트스트림 내장)
build/output/fir_decimator_demo.elf   ← Vitis 산출물 (242KB)
```

---

## 핵심 교훈

1. **xsct는 Vitis 2024.x에서 동작하지 않는다.** `vitis -s <script.py>` 방식으로 전환 필요.
2. **Vitis와 Vitis Embedded Development는 별개 제품이다.** bare-metal 개발은 후자가 필요.
3. **새 SDT 기반 BSP는 XSA에 명시된 주변장치만 포함한다.** Block Design에서 UART 등 PS 주변장치를 반드시 활성화해야 한다.
4. **AMD 설치 프로그램에 버그가 있다.** Lopper pip install 실패 후 성공으로 표시. 수동 확인 필요.
