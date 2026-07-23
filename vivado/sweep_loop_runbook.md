# Vivado Frequency Sweep — Loop Agent Instructions

**목적:** 루프 에이전트가 자율적으로 주파수 스윕 빌드를 실행한다.
**참고:** `docs/workflow/workflow_v19.md`
**실행 위치:** repo root

> **[현행화 주석, 2026-07-23]** 이 문서는 workflow_v19 시절 PS7 FCLK 기반 코스 스윕의
> 실행 기록이다. 아래 "확정 Fmax 115MHz"는 이후 clk_wiz 정밀 스윕에서 **116MHz로
> 정정**되었다(구 115MHz 설정은 PS7 PLL 스냅으로 실제 111.111MHz였음 — `docs/log/40`).
> LUT 등 자원 수치도 당시 빌드 기준이다. 현행 수치는 `vivado/reports/sweep_summary.md`
> (v1) / `sweep_summary_v2.md`(v2) 참고.

---

## 진행 체크리스트

에이전트는 이 목록을 순서대로 실행하고, 완료한 항목은 `[x]`로 업데이트한다.

### Phase 1 — 고정 기준점

- [x] 090 MHz 빌드 → `vivado/reports/090mhz_*.rpt` 복사 (WNS=+1.883ns, LUT=4583, DSP48=16, Power=1.564W)
- [x] 100 MHz 빌드 → `vivado/reports/100mhz_*.rpt` 복사 (WNS=+0.692ns, LUT=4584, DSP48=16, Power=1.567W)

### Phase 2 — 상한 탐색 (코스, 10 MHz 단계, 110 MHz부터 시작)

- [x] 110 MHz 빌드 → WNS: +0.178ns (PASS)
- [x] 120 MHz 빌드 → WNS: -0.783ns (FAIL)
- [ ] ~~___ MHz 빌드 → WNS: ___~~
- [ ] ~~___ MHz 빌드 → WNS: ___~~
- [ ] ~~___ MHz 빌드 → WNS: ___~~

→ **last_pass:** 110 MHz / **first_fail:** 120 MHz

### Phase 3 — 경계 세분화 (파인, 5 MHz 단계)

- [x] 115 MHz 빌드 → WNS: +0.178ns (PASS)
- [ ] ~~___ MHz 빌드 → WNS: ___~~

→ **확정 Fmax:** 115 MHz (WNS ≥ 0인 최대 주파수)

### Phase 4 — 마무리

- [x] `vivado/reports/sweep_summary.md` 생성
- [x] `vivado/fir_n43/bd_fir_dma.tcl` 100 MHz 원복
- [x] git commit(작업 단위별로 나누어서 커밋, 작성자명은 Young)

---

## 동적 주파수 결정 알고리즘

### Phase 1 (고정)

90 MHz, 100 MHz를 순서대로 빌드한다.

### Phase 2 (코스 탐색, 10 MHz 단계)

110 MHz부터 시작. 각 빌드 후:

```
WNS >= 0  →  next = current + 10 MHz  (계속 상향)
WNS <  0  →  코스 탐색 종료
               last_pass  = 직전 통과 주파수 (없으면 100 MHz)
               first_fail = 현재 주파수
```

상한: 175 MHz. 175 MHz까지 전부 통과하면 Phase 3 생략.

### Phase 3 (파인 세분화, 5 MHz 단계)

`last_pass + 5` MHz부터 `first_fail - 5` MHz까지, 5 MHz 단계로 빌드한다.

예시: last_pass=110, first_fail=120 → 115 MHz만 빌드.
예시: last_pass=100, first_fail=120 → 105, 110 MHz 빌드 (단 110은 Phase 2에서 이미 fail이므로 105만).

---

## 실행 절차

### Step 1. `bd_fir_dma.tcl` 수정

수정 대상 (Edit 툴 사용):

- **267번째 줄:** `CONFIG.PCW_CLK0_FREQ {현재값}` → `CONFIG.PCW_CLK0_FREQ {목표Hz}`
- **297번째 줄:** `CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {현재값}` → `CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {목표MHz}`

주파수별 값:

| MHz | PCW_CLK0_FREQ | PCW_FPGA0_PERIPHERAL_FREQMHZ |
| --- | ------------- | ---------------------------- |
| 90  | 90000000      | 90                           |
| 100 | 100000000     | 100                          |
| 105 | 105000000     | 105                          |
| 110 | 110000000     | 110                          |
| 115 | 115000000     | 115                          |
| 120 | 120000000     | 120                          |
| 125 | 125000000     | 125                          |
| 130 | 130000000     | 130                          |
| 135 | 135000000     | 135                          |
| 140 | 140000000     | 140                          |
| 145 | 145000000     | 145                          |
| 150 | 150000000     | 150                          |
| 160 | 160000000     | 160                          |
| 175 | 175000000     | 175                          |

### Step 2. Vivado 배치 빌드

```bash
vivado -mode batch -source vivado/fir_n43/build_bd_fir_dma.tcl \
    2>&1 | tee build/fir_n43/vivado/build_NNNmhz.log
```

`NNNmhz`는 `090mhz`, `100mhz`, `110mhz` 등 3자리 zero-padding.

빌드 성공 확인:

```bash
grep "빌드 완료" build/fir_n43/vivado/build_NNNmhz.log
```

실패 시 해당 주파수를 `BUILD_FAIL`로 sweep_summary.md에 기록하고 다음 단계로 진행.

### Step 3. 리포트 복사

```bash
PROJ=fir_decimator_trans_n43
SRC=build/fir_n43/vivado
PREFIX=NNNmhz

cp ${SRC}/${PROJ}_timing_summary.rpt vivado/reports/${PREFIX}_timing_summary.rpt
cp ${SRC}/${PROJ}_utilization.rpt    vivado/reports/${PREFIX}_utilization.rpt
cp ${SRC}/${PROJ}_power.rpt          vivado/reports/${PREFIX}_power.rpt
```

**주의: 다음 주파수 빌드 전에 반드시 복사 완료. `-force`로 build/ 디렉터리가 덮어써진다.**

### Step 4. WNS 추출 (다음 주파수 결정에 사용)

```bash
grep "WNS = " build/fir_n43/vivado/build_NNNmhz.log
# 출력 예: WNS = 0.278 ns
```

---

## sweep_summary.md 형식

`vivado/reports/sweep_summary.md`를 아래 형식으로 작성한다.

```markdown
# FIR N43 Clock Sweep Summary

- 생성일: YYYY-MM-DD
- 보드: Zybo Z7-20 (xc7z020clg400-1)
- 설계: N=43 taps, M=2, transposed form

## 결과

| target_mhz | wns_ns | timing_pass | lut  | dsp48 | total_power_w |
|-----------|--------|-------------|------|-------|---------------|
| 90        |        | true        |      |       |               |
| 100       | 0.692  | true        | 1827 | 16    |               |
| ...       |        |             |      |       |               |

## Fmax

확정 Fmax: ___ MHz (WNS ≥ 0인 최대 주파수)
```

수치 추출:

```bash
# WNS
grep "WNS = " build/fir_n43/vivado/build_NNNmhz.log

# LUT
grep "Slice LUTs " vivado/reports/NNNmhz_utilization.rpt | head -1

# DSP48
grep "DSPs " vivado/reports/NNNmhz_utilization.rpt | head -1

# 전력
grep "Total On-Chip Power" vivado/reports/NNNmhz_power.rpt | head -1
```

---

## 완료 기준

```bash
ls vivado/reports/*.rpt | wc -l   # 빌드한 주파수 수 × 3
cat vivado/reports/sweep_summary.md
git log --oneline -1
```

---

## 마무리 필수

스윕 완료 후 `bd_fir_dma.tcl`을 반드시 원복한다:

- 267번째 줄: `CONFIG.PCW_CLK0_FREQ {100000000}`
- 297번째 줄: `CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100}`

