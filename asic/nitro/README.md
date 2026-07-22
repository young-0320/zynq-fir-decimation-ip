# Nitro P&R Guide (FIR v1/v2)

상태(2026-07-21): v1 10000ps 1런을 시도했으나 placer 내부 오류(SDA101)가 재현되어
중단했다. 시도 기록과 중단 판단은 `../oasys/results/sweep_report.md` §6, `docs/log/47`
§4. 아래 절차와 `tcl/`의 step 스크립트는 재개 가능한 상태로 보존한다.

Oasys netlist(`asic/oasys/results/<ver>/<period>ps/*_synth.v`)를 대상으로 P&R.
flow·공정 파일 경로는 GEMM 프로젝트(교수님 예제) 기준 그대로.

## 실행 방법

1. Oasys sweep에서 Nitro로 넘길 period를 고른다 (각 버전의 최속 passing period +
   공통 비교 period 권장).
2. `template_nitro.tcl`을 `tcl/{v1|v2}_<period>ps_nitro.tcl`로 복사하고 상단
   `REPO_ROOT`/`VER`/`PERIOD`/`TOP_MODULE`만 수정한다.
3. 같은 폴더에 `tcl/{v1|v2}_<period>ps.sdc`를 만든다:

   ```tcl
   create_clock -name clk -period 20000.0 [get_ports clk]
   ```

4. Nitro에서 tcl 실행 (`#run after pause` 주석 지점마다 끊어 실행 — GEMM 방식 동일).
5. 결과는 `results/<ver>/<period>ps/`에 생성 (SDF, post-route netlist,
   timing/area rpt).

## 확인 항목

| 항목                 | 의미                            |
| -------------------- | ------------------------------- |
| post-route WNS/slack | 배선 이후 timing 만족 여부      |
| chip/core area, utilization | 물리 면적                |
| congestion/route 상태 | 배선 정상 완료 여부            |

chip area는 14000000a(1.4mm 변)에서 시작 — FIR은 병렬 곱셈기 43개라 셀 면적이
1.35mm²로 **GEMM step2(0.31mm²)의 4배** (초기 "GEMM보다 작다" 가정은 FPGA 자원
감각의 오판이었음). 단위 a=0.1nm, 필요 변 = √(cell_area/util). placement 실패나
congestion이면 키우고, 너무 널널하면 줄여 재시도.

주의: Nitro tcl에는 `report_power`가 없다(GEMM 프로젝트에서 미지원 확인).
전력 비교는 Oasys `report_power` 기준으로 한다.
