## 1. 프로젝트 환경

1. 보드: Zybo Z7-20 (Zynq-7000, xc7z020clg400-1)
2. 개발 환경: Linux 데스크탑, Vivado 네이티브, Python 3.13, uv 패키지 매니저
3. Python 실행: `.venv/bin/python` 또는 `uv run --no-sync python`
4. 시뮬레이션: iverilog (`-g2012`) + vvp
5. GitHub: young-0320/zynq-axi-fir-decimation-ip
6. Vivado 빌드 경로: `/mnt/workspace/10_zynq-fir-decimation-ip_build/`


---

## 2. RTL 설계 확정 사항

근거 문서: `docs/log/14_transposed_form_rtl_decisions.md`

### 파이프라인 구조

```
[Stage 1] in_valid=1
    → h[k] * in_sample  (k=0..42, 43개 병렬) → prod_reg[k] 저장 (signed 48-bit)
    → prod_valid = 1

[Stage 2] prod_valid=1
    → z[k] = prod_reg[k] + z[k+1]  (k=0..41)
      z[42] = prod_reg[42]           ← B안: z[43] 더미 없음
    → round_reg = round(prod_reg[0] + z[1])
      ※ non-blocking 특성상 z[0] 직접 참조 불가 → prod_reg[0]+z[1] 직접 계산
    → round_valid = 1

[Stage 3] round_valid=1
    → out_sample = saturate(round_reg)
    → out_valid = 1
```

### 3. 확정 결정 요약

| 항목        | 결정                                          |
| ----------- | --------------------------------------------- |
| 처리 구조   | 1 sample/cycle 병렬 (N=43개 MAC 동시)         |
| 파이프라인  | 3단계 (100MHz 타이밍 위반으로 확장)           |
| FIR latency | 3 cycles                                      |
| Top latency | 4 cycles (keep sample 기준)                   |
| z[k] 비트폭 | signed 48-bit (Q2.30)                         |
| prod_reg[k] | signed 48-bit (32-bit 곱 → sign-extend)       |
| 반올림      | ties-away-from-zero, z[0] 출력 1회만          |
| 포화        | 출력 1회 clip(-32768, 32767)                  |
| in_valid=0  | z[k] hold, prod_valid=0, out_valid=0          |
| reset       | active-high, 전체 state 0                     |
| 계수 저장   | localparam 하드코딩 43개                      |
| z[42] 경계  | B안:`z[42] <= prod_reg[42]` (z[43] 더미 없음) |


## FIR spec

| 항목     | 값                         |
| -------- | -------------------------- |
| Fs_in    | 100 MHz                    |
| Fs_out   | 50 MHz (M=2)               |
| fp       | 15 MHz                     |
| fs       | 25 MHz                     |
| As       | ≥ 60 dB                    |
| N        | 43 (Kaiser window β=5.653) |
| 포맷     | Q1.15 signed 16-bit        |
| FIR 구조 | Transposed Form            |
| 클럭     | 100 MHz (Clocking Wizard)  |



---

## 4. 데모 시나리오 (확정)

| 시나리오       | 방식                                                                             | 핵심                                                                 |
| -------------- | -------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| 0 — 비교 시연  | PC Python만으로 실행 (보드 불필요)                                               | FIR 없이 다운샘플만 → 앨리어싱 발생 / FIR 적용 → 제거. "왜 필요한가" |
| 1 — 기본 동작  | PS C코드로 고정 멀티톤(5/20/30MHz) 생성 → DMA → PL → UART → PC FFT               | "제대로 동작하는가"                                                  |
| 2 — 인터랙티브 | 청중이 주파수 지정 → PC Python이 UART로 값 전송 → PS 즉석 생성 → 동일 파이프라인 | "직접 체험"                                                          |

전체 파이프라인: `docs/하드웨어 파이프라인.md` 참고.
처리 방식: 블록 처리. UART로는 주파수 값(숫자 몇 바이트)만 전송, 신호 데이터 아님.

---
## 5. 자주 쓰는 명령어

```bash
# pytest 전체
.venv/bin/pytest -q

# 벡터 생성 (2단계)
.venv/bin/python -m sim.python.run_compare_ideal_vs_fixed --num-taps 43 --form transposed
.venv/bin/python -m sim.python.export_rtl_bringup_vectors \
    --num-taps 43 \
    --input-dir sim/output/ideal_vs_fixed_trans_n43 \
    --output-dir sim/vectors/transposed_form/n43

# FIR 단독 시뮬레이션
iverilog -g2012 -Wall -o /tmp/tb_fir.out \
    sim/rtl/tb/transposed_form/tb_fir_transposed_n43.v \
    rtl/transposed_form/n43/fir_transposed_n43.v
vvp /tmp/tb_fir.out

# Top (decimator 포함) 시뮬레이션
iverilog -g2012 -Wall -o /tmp/tb_top.out \
    sim/rtl/tb/transposed_form/tb_fir_decimator_transposed_n43_top.v \
    rtl/transposed_form/n43/fir_transposed_n43.v \
    rtl/transposed_form/n43/fir_decimator_transposed_n43_top.v \
    rtl/direct_form/decimator_m2_phase0.v
vvp /tmp/tb_top.out
```

## 6. 디렉토리 구조

```
rtl/
├── direct_form/
│   ├── bringup_n5/                            ✅ N=5 bring-up 완료
│   └── decimator_m2_phase0.v                  ✅ N=43 재사용
└── transposed_form/n43/
    ├── fir_transposed_n43.v                   ✅
    ├── fir_decimator_transposed_n43_top.v     ✅
    └── constrs/zybo_n43.xdc

sim/
├── python/
│   ├── run_compare_ideal_vs_fixed.py          ✅ --form 인수 지원
│   └── export_rtl_bringup_vectors.py          ✅
├── output/ideal_vs_fixed_trans_n43/           ✅ .npy 벡터
├── vectors/transposed_form/n43/               ✅ hex 벡터 (4종)
└── rtl/tb/transposed_form/
    ├── tb_fir_transposed_n43.v                ✅
    └── tb_fir_decimator_transposed_n43_top.v  ✅

model/
├── ideal/                                     ✅
└── fixed/                                     ✅ (direct_form + transposed_form)

docs/
    study_roadmap.md                               ✅ 단계별 학습 자료 (ZipCPU/Xilinx 문서 링크)
    하드웨어 파이프라인.md                          ✅ 데모 시나리오 0/1/2 및 파이프라인 구조
    summary_design_decisions.md                    ✅ 핵심 설계 결정 요약

docs/log/
    01~08  스펙·포맷·입력·브링업·비교 (초기 단계)
    09     bringup_rtl_decisions          ← N=5 RTL 결정
    10     bringup_rtl_module_walkthrough
    11     vivado_timing_violation_and_fir_pipelining
    12     project_direction_change       ← 교수 피드백 후 방향 전환
    13     transposed_form_golden_policy
    14     transposed_form_rtl_decisions  ← N=43 RTL 핵심 결정
    15     rtl_vector_pipeline_extension
    16     vivado_timing_closure_transposed_n43  ← 최신
    workflow_v1~v9  워크플로우 변천 이력 (v9가 현행)
```

생성 벡터 구성:

```
sim/vectors/transposed_form/n43/
    input_q15.hex          (8192 lines)
    coeff_q15.hex          (43 lines)
    expected_fir_q15.hex   (8234 lines = 8192 + 42 flush)
    expected_decim_q15.hex (4117 lines)
```

---