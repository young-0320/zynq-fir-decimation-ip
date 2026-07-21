# Oasys Synthesis Guide (FIR v1/v2)

목적: workflow_v23 Track A(§8-1) — `fir_n43`(v1) / `fir_n43_v2`(v2)를 **동일 제약**으로
합성해 ASIC 면적/타이밍/전력 보조 지표를 확보하고, "v1의 critical path(FPGA CARRY4
캐리 체인)는 FPGA 전용 병목"이라는 가설을 실증한다. 플로우·파일 구조는
`simple-cpu-gemm-accelerator/asic`(2026-1 디지털시스템설계실습) 방식 그대로.

## 1. 합성 타겟

순수 FIR core만 (AXI-Stream 래퍼/DMA/BD는 Zynq 전용이라 비대상, decimator 제외).
두 코어 모두 단일 파일 · 순수 behavioral Verilog(Xilinx primitive 없음), 포트 동일.

| 대상 | top module   | 소스                                   | FPGA 기준             |
| ---- | ------------ | -------------------------------------- | --------------------- |
| v1   | `fir_n43`    | `rtl/transposed_form/n43/fir_n43.v`    | Fmax 116MHz (CARRY4 체인 병목) |
| v2   | `fir_n43_v2` | `rtl/transposed_form/n43/fir_n43_v2.v` | Fmax 146MHz (파이프라인 분할) |

config는 `v1_config.tcl` / `v2_config.tcl` — 소스가 각 1파일이라 filelist(.f) 없이
경로를 config에 직접 기재했다. 실행 전 두 config의 `REPO_ROOT`를 서버 clone 경로로
수정할 것 (`[수정 필요]` 주석).

## 2. Constraint — v1/v2 동일 제약이 핵심

`clk.sdc` 하나를 v1/v2가 공유한다 — **같은 period로 두 개를 짝지어 돌려야 비교가
성립한다** (한쪽만 다른 period로 돌린 결과는 비교표에 쓰지 않는다).

sweep: `clk.sdc`의 period만 바꾸고 v1/v2를 연달아 합성.
20000ps(50MHz) → 15000(66.7MHz) → 12000(83.3MHz) → 10000(100MHz) → 8000(125MHz)
순으로 줄여 timing이 깨지는 지점을 찾고, 첫 FAIL이 나오면 마지막 PASS와의 사이를
이분탐색으로 좁힌다. 최종적으로 각 버전의 **가장 빠른 passing period**와
**공통 passing period 1개**(비교 기준점)를 확보한다.

sweep 범위(20000→8000ps)의 근거: FPGA Fmax(116/146MHz)는 28nm Zynq 기준이라 250nm
ASIC 예측에 쓸 수 없고, 이 PDK에서 유일한 참조점은 같은 공정·같은 수업 플로우로 돌린
GEMM 프로젝트 결과다 — 유사한 16-bit MAC datapath가 13000~15000ps에서 PASS,
최종 8500ps까지 조임. FIR tap 경로(16×16 곱 + 48-bit 가산)도 같은 급이라 그 부근을
양쪽으로 감싸는 구간을 잡았다: 20000ps는 "확실히 PASS할 시작점"(플로우 검증 겸),
8000ps는 GEMM 최종값보다 살짝 타이트한 하한. 중간값들은 균등 간격일 뿐 특별한 의미
없음 — 실제 Fmax 확정은 위 이분탐색이 담당한다.

## 3. 실행명령어 (합성 후 export)

```
write_verilog "v1_20000ps_synth.v"
report_timing > "v1_20000ps_timing.rpt"
report_area   > "v1_20000ps_area.rpt"
report_power  > "v1_20000ps_power.rpt"
```

파일명 규칙: `{v1|v2}_<period>ps_*`. 산출물은 `results/<ver>/<period>ps/` 아래 보관:

```text
asic/oasys/results/v1/20000ps/
├── v1_20000ps_synth.v      (Nitro 입력)
├── v1_20000ps_timing.rpt
├── v1_20000ps_area.rpt
└── v1_20000ps_power.rpt
```

## 4. 결과에서 봐야 하는 항목 (런당 기록)

| 항목                    | 의미                                             |
| ----------------------- | ------------------------------------------------ |
| clock period            | 사용한 constraint                                |
| slack / WNS             | timing 만족 여부                                 |
| critical path 시작·끝점 | **v1 병목이 FPGA와 같은 가산기 체인인지 판별용** |
| cell count / area       | 표준셀 수·면적 (v2는 파이프라인 FF만큼 클 것)   |
| dynamic/leakage/total power | 전력                                         |

기대 시나리오 (어느 쪽이든 유의미):

```text
v1 ≈ v2 Fmax + v1 면적 우위 → "파이프라인 분할은 FPGA 전용 최적화" 실증
v2가 ASIC에서도 빠름        → 분할의 범용성 입증
```

결과 정리·FPGA 코어 단독 수치(v2: LUT 1792/FF 2113/DSP 16/0.015W,
`sweep_summary_v2.md`) 대비 표는 리포트를 가져오면 에이전트가 작성한다.

## 5. 파일 목록

```text
asic/oasys/
├── README.md
├── clk.sdc          (v1/v2 공용 constraint — sweep 시 이 파일만 수정)
├── v1_config.tcl / v2_config.tcl
└── results/         (서버에서 생성한 netlist·rpt 보관)
```

참고: GEMM 프로젝트의 VCD 기반 power(워크로드 실측 dynamic power)는 1차 범위에서
제외 — 기본 toggle-rate 가정 power로 먼저 진행하고, 필요해지면 iverilog TB에서 VCD를
떠서 `vcd_file`/`vcd_scope`를 채운 config를 추가한다.
