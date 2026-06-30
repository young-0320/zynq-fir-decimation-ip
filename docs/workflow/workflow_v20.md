# FIR Decimation Project Workflow v20

- Date: 2026-07-01
- Previous: `docs/workflow/workflow_v19.md`
- Purpose: 115 MHz 보드 정확도 검증 → v1.0 최종 완료 선언

---

## 배경

v19에서 클럭 스윕 타이밍 결과: Fmax = 115 MHz (WNS ≥ 0 기준).
그러나 타이밍 통과 ≠ 출력 정확도 보장. 115 MHz bitstream을 보드에서 실행해
FIR 출력이 golden과 일치하는지 확인해야 v1.0이 완료된다.

---

## 목표

| 목표 | 확인 방법 |
|------|----------|
| 115 MHz에서 scenario 1-2 PASS | SNR, max_error, tone 판정 |
| sweep_summary.md correctness 컬럼 추가 | SNR/max_error/verdict 기록 |
| v1.0 완료 선언 | CLAUDE.md Step 목록 업데이트 |

---

## 사전 확인

현재 `build/fir_n43/output/bd_fir_dma_wrapper.bit`는 v19 루프의 마지막 빌드인
115 MHz bitstream이다 (타임스탬프 2026-07-01 01:50).

확인 방법:

```bash
ls -lh build/fir_n43/output/bd_fir_dma_wrapper.bit
# → Jul 1 01:50 이면 115 MHz 맞음
```

타임스탬프가 다르거나 불확실하면 115 MHz로 재빌드:

```bash
# bd_fir_dma.tcl을 115 MHz로 수정 후
vivado -mode batch -source vivado/fir_n43/build_bd_fir_dma.tcl 2>&1 | tee build/fir_n43/vivado/build_115mhz_rerun.log
# 완료 후 bd_fir_dma.tcl 100 MHz 원복
```

---

## 작업 순서

### Step 1. 115 MHz BOOT.bin 재빌드

현재 bitstream(115 MHz)을 그대로 쓰고 C 펌웨어만 다시 패키징한다:

```bash
vitis/fir_n43/rebuild_boot_image.sh --boot-tag FIR
```

`build/fir_n43/output/BOOT.bin` 생성 확인.

### Step 2. SD 카드 교체 및 보드 부팅

1. SD 카드에 `build/fir_n43/output/BOOT.bin` 복사
2. 보드 전원 인가
3. UART 터미널에서 `READY FIR` 확인

### Step 3. Scenario 1-2 실행

```bash
uv run python sw/fir_decimator_report.py --mode 1-2 --port /dev/ttyUSB0
```

출력 확인:
- Overall verdict: **PASS** 목표
- SNR, max_error (100 MHz 기준: SNR=72.2 dB, max_error=7 LSB)

### Step 4. 결과 기록

`vivado/reports/sweep_summary.md`에 correctness 컬럼 추가:

```markdown
| target_mhz | wns_ns | timing_pass | snr_db | max_error_lsb | correctness |
|-----------|--------|-------------|--------|---------------|-------------|
| 90        | +1.883 | true        | —      | —             | 미검증      |
| 100       | +0.692 | true        | 72.2   | 7             | PASS        |
| 110       | +0.178 | true        | —      | —             | 미검증      |
| 115       | +0.178 | true        | (측정값)| (측정값)      | PASS/FAIL   |
| 120       | -0.783 | false       | —      | —             | 타이밍실패  |
```

### Step 5. 분기 처리

**115 MHz PASS인 경우:**
- `docs/report/fir_n43/summary/scenario1_2_115mhz.md` 저장
- sweep_summary.md correctness 업데이트
- CLAUDE.md에 v1.0 완료 기록
- git commit

**115 MHz FAIL인 경우:**
- 110 MHz도 동일하게 Step 1~4 반복
- Fmax(correctness) = 110 MHz로 정정
- sweep_summary.md 업데이트

---

## 완료 기준

- [ ] 115 MHz BOOT.bin SD 부팅 → `READY FIR` 확인
- [ ] scenario 1-2 실행 → SNR / max_error 측정
- [ ] sweep_summary.md correctness 컬럼 기입
- [ ] git commit

---

## v1.0 완료 선언 조건

아래 모두 충족 시 v1.0 완료:

| 항목 | 근거 |
|------|------|
| 100 MHz 기능 검증 | docs/report/fir_n43/summary/scenario1_2.md (PASS) |
| CPU vs FPGA 벤치마크 | docs/report/fir_n43/plot/cpu_vs_fpga_timing_window.png |
| 클럭 스윕 타이밍 | vivado/reports/sweep_summary.md |
| 크리티컬 패스 분석 | vivado/reports/sweep_summary.md |
| Fmax 정확도 검증 | scenario1_2_115mhz.md (본 workflow 산출물) |

---

## 다음 단계

v20 완료 후 → **v21: v2.0 RTL 개선**
- 누산기 CARRY4 체인 파이프라인 분할
- 목표 Fmax: 150+ MHz
- 근거: `vivado/reports/sweep_summary.md` 크리티컬 패스 분석
