# FIR Decimation Project Workflow v19

- Date: 2026-06-29
- Previous: `docs/workflow/workflow_v18.md`
- Purpose: 주파수 스윕 — PL 클럭을 변경하며 타이밍 마진과 기능 correctness를 측정한다.
- 근거: `docs/workflow/workflow_v17.md` P0 항목 (교수님 미팅 전 원래 계획)

---

## 1. 배경

v18(CPU vs FPGA 비교)이 완료되면 원래 계획대로 주파수 스윕으로 넘어간다.

목적: "이 FIR IP는 어느 클럭까지 타이밍을 지키고, 어디서 기능이 깨지는가"를 데이터로 보여준다.

---

## 2. 클럭 소스 확인 결과

- PS7 FCLK0 직접 사용 — 클럭 wizard 없음
- 변경 위치: `vivado/fir_n43/bd_fir_dma.tcl` 두 줄

```tcl
CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100}   ← 목표 주파수 (MHz)
CONFIG.PCW_CLK0_FREQ {100000000}             ← 목표 주파수 (Hz)
```

- `PCW_ACT_FPGA0_PERIPHERAL_FREQMHZ`는 Vivado가 PLL 제약상 실제로 달성한 주파수를 기록한다. 이 값이 실제 측정 기준이다. 목표와 다를 수 있으므로 반드시 실제값을 CSV에 기록한다.

---

## 3. 사전 예상: 현재 WNS 기준 Fmax

현재 100 MHz에서 WNS = +0.692 ns.

```
critical path 지연 ≈ 10.000 - 0.692 = 9.308 ns
Fmax 추정 ≈ 1 / 9.308 ns ≈ 107 MHz
```

즉 **125 MHz에서 타이밍 실패가 거의 확실하다.** 이는 나쁜 결과가 아니다. pass → fail 전환점을 명확히 보여주는 것이 스윕의 목적이다.

예상 결과:

| 포인트 | 예상 WNS | 예상 보드 동작 |
| --- | --- | --- |
| 75 MHz | 크게 양수 | PASS |
| 100 MHz | +0.692 ns (확인됨) | PASS |
| 125 MHz | 음수 (타이밍 실패) | 불확실 |
| 150 MHz | 음수 (타이밍 실패) | FAIL 가능성 높음 |
| 175 MHz | 음수 (타이밍 실패) | FAIL |

타이밍 실패여도 보드 테스트는 반드시 실행한다. WNS < 0 이어도 보드가 동작하는 경우가 있으며, 이 결과 자체가 의미 있는 데이터다.

---

## 4. 산출물 구조

### build (gitignore — 로컬만)

```
build/fir_n43/sweep/
  075mhz_timing_summary.rpt
  075mhz_utilization.rpt
  075mhz_power.rpt
  100mhz_timing_summary.rpt
  100mhz_utilization.rpt
  100mhz_power.rpt
  125mhz_timing_summary.rpt
  ...
```

플랫 구조. 주파수 포인트별 서브폴더를 만들지 않는다.
`build/` 전체가 gitignore이므로 로컬에만 존재한다.

### docs (git 추적)

```
docs/characterization/fir_n43_v1/
  clock_sweep.csv
  pass_fail_matrix.md
  plot/
    fmax_shmoo.png
    wns_vs_clock.png
    snr_vs_clock.png
```

---

## 5. clock_sweep.csv 컬럼

| 컬럼 | 내용 |
| --- | --- |
| `target_mhz` | 목표 클럭 주파수 |
| `actual_mhz` | Vivado 실제 달성 주파수 (`PCW_ACT_FPGA0_PERIPHERAL_FREQMHZ`) |
| `wns_ns` | Worst Negative Slack |
| `timing_pass` | WNS >= 0이면 true |
| `boot_pass` | 보드 부팅 후 `READY FIR` 출력 여부 |
| `scenario_1_2_snr_db` | Scenario 1-2 SNR |
| `scenario_1_2_max_error_lsb` | Scenario 1-2 max error |
| `scenario_1_2_verdict` | PASS / WARN / FAIL |
| `failure_mode` | timing_fail / boot_fail / dma_timeout / output_wrong / — |
| `notes` | 특이사항 |

---

## 6. 작업 순서

### 6-1. build_bd_fir_dma.tcl 수정

현재 스크립트는 리포트를 `build/fir_n43/vivado/` 아래에 저장한다. 스윕에서는 각 포인트 실행 후 리포트를 즉시 `build/fir_n43/sweep/` 아래 주파수 prefix 이름으로 복사해야 한다. 다음 주파수를 돌리면 이전 Vivado 프로젝트가 덮어써지기 때문이다.

수정 범위:
- `report_power` 추가 (현재 없음)
- 리포트 3개를 `build/fir_n43/sweep/${FREQ}mhz_*.rpt`로 복사하는 코드 추가
- 또는 sweep 전용 wrapper Tcl을 별도로 만든다

### 6-2. 주파수 포인트별 실행

각 포인트:
1. `bd_fir_dma.tcl`에서 `PCW_FPGA0_PERIPHERAL_FREQMHZ`와 `PCW_CLK0_FREQ` 수정
2. `build_bd_fir_dma.tcl` 실행 → bitstream + XSA + 리포트 생성
3. 리포트 3개를 sweep 폴더에 복사
4. `rebuild_boot_image.sh --boot-tag FIR` 실행 → BOOT.bin 재생성
5. 보드에 SD 카드 교체 후 scenario 1-2 실행 → SNR / max_error 기록
6. CSV에 한 행 추가

### 6-3. 결과 수집 스크립트

**파일:** `sw/sweep_collect.py` (신규)

- `build/fir_n43/sweep/*.rpt` 파일들을 파싱해 WNS, LUT, DSP48 수치 추출
- `docs/characterization/fir_n43_v1/clock_sweep.csv`에 저장
- `wns_vs_clock.png`, `fmax_shmoo.png`, `snr_vs_clock.png` 생성

---

## 7. 추가 고려사항

### 100 MHz 포인트 처리

현재 100 MHz WNS = +0.692 ns는 기존 빌드에서 확인됐다. 그러나 sweep 폴더에 리포트가 없으므로 **100 MHz도 다시 한 번 빌드해서 sweep 폴더에 리포트를 생성하는 것이 깔끔하다.** 재빌드 결과가 기존과 약간 다를 수 있으나 허용 범위다.

### Vivado 프로젝트 덮어쓰기

`build_bd_fir_dma.tcl`은 `-force` 옵션으로 프로젝트를 덮어쓴다. 각 주파수 빌드가 완료된 직후 리포트를 sweep 폴더로 복사하지 않으면 데이터가 유실된다. 빌드 스크립트 안에서 복사까지 처리하거나, 매 빌드 후 즉시 수동 복사한다.

### BOOT.bin 재생성 필요

클럭이 바뀌면 XSA가 달라지고, FSBL이 PS 초기화 시 다른 클럭 설정을 적용한다. 반드시 매 포인트마다 BOOT.bin을 새로 만들어야 한다.

### 타이밍 실패 포인트도 보드 테스트

WNS < 0이어도 보드 테스트를 실행하고 결과를 기록한다. `failure_mode` 컬럼에 `timing_fail`로 표시한 뒤 실제 보드 동작 결과를 함께 남긴다.

---

## 8. 완료 기준

| 기준 | 확인 방법 |
| --- | --- |
| 5개 포인트 전부 빌드 완료 | sweep 폴더에 15개 .rpt 파일 존재 |
| 각 포인트 보드 테스트 완료 | clock_sweep.csv에 5행 기록 |
| pass → fail 전환점 확인 | WNS 열에서 양수 → 음수 전환 확인 |
| 차트 3개 생성 | docs/characterization/fir_n43_v1/plot/ 확인 |
