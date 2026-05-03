# FIR Decimation 프로젝트 워크플로우 v9

- 작성일: 2026-05-03
- 이전 버전: workflow_v8.md
- 변경 배경: N=43 Transposed Form RTL 검증 환경 구축 진행 중 — 벡터 생성 파이프라인 확장 반영

---

## 1. v8 대비 변경 사항

| 항목                             | v8                      | v9                                                |
| -------------------------------- | ----------------------- | ------------------------------------------------- |
| `run_compare_ideal_vs_fixed.py`  | Direct Form golden 고정 | `--form {direct, transposed}` 인수 추가           |
| Transposed Form 중간 산출물 경로 | 미정                    | `sim/output/ideal_vs_fixed_trans_n{N}/` 확정      |
| 벡터 생성 파이프라인             | N=5 bring-up 전용       | `--input-dir` / `--output-dir` 명시로 N=43 재사용 |

---

## 2. 현재 진행 중인 작업 단위

**N=43 Transposed Form RTL 검증 환경 구축**

RTL 구현(`fir_transposed_n43.v`) 전에 iverilog self-checking 시뮬레이션 환경을 먼저 갖추는 단계다.
Python 골든 출력을 RTL testbench가 읽을 수 있는 hex 벡터로 변환하는 파이프라인을 완성하는 것이 목표다.

Python 골든 (Transposed Form)
→ .npy 중간 산출물
→ .hex 벡터
→ RTL testbench $readmemh
→ out_sample vs expected 비교
→ PASS/FAIL

### 현재 단계 완료 기준

- [ ] `run_compare_ideal_vs_fixed --form transposed --num-taps 43` 실행 성공
- [ ] `sim/output/ideal_vs_fixed_trans_n43/` 에 npy 생성 확인
- [ ] `export_rtl_bringup_vectors --input-dir ... --output-dir ...` 실행 성공
- [ ] `sim/vectors/transposed_form/n43/` 에 hex 4종 생성 확인
- [ ] 벡터 길이 확인 (input: 8192, coeff: 43, fir: 8234, decim: 4117)

---

## 5. 다음 작업 순서

### Step 1 — RTL 검증 환경 구축 완료 ← 현재 여기

hex 벡터 생성 파이프라인 완성.

```bash
# Transposed Form golden 실행
.venv/bin/python -m sim.python.run_compare_ideal_vs_fixed \
    --num-taps 43 --form transposed

# hex 벡터 변환
.venv/bin/python -m sim.python.export_rtl_bringup_vectors \
    --num-taps 43 \
    --input-dir sim/output/ideal_vs_fixed_trans_n43 \
    --output-dir sim/vectors/transposed_form/n43
```

생성 대상:
```
sim/vectors/transposed_form/n43/
input_q15.hex        (8192 lines)
coeff_q15.hex        (43 lines)
expected_fir_q15.hex (8234 lines)
expected_decim_q15.hex (4117 lines)
```
---

### Step 2 — fir_transposed_n43.v 구현

설계 기준: `docs/log/14_transposed_form_rtl_decisions.md`
`rtl/transposed_form/fir_transposed_n43.v`
핵심 설계 사항:
- 포트: `clk`, `rst`(active-high), `in_valid`, `in_sample[15:0]`, `out_valid`, `out_sample[15:0]`
- 1 sample/cycle 병렬 처리 (N=43개 MAC 동시)
- 2단계 파이프라인 (Stage1: 곱셈, Stage2: 누산+반올림+포화)
- z[k]: signed 48-bit
- 반올림: ties-away-from-zero
- 포화: 최종 출력 1회
- 계수: localparam 하드코딩

완료 기준:
- [ ] `tb_fir_transposed_n43.v` iverilog PASS

---

### Step 3 — fir_decimator_transposed_n43_top.v 구현

기존 `decimator_m2_phase0.v` 재사용.
`rtl/transposed_form/fir_decimator_transposed_n43_top.v`
완료 기준:
- [ ] `tb_fir_decimator_transposed_n43_top.v` iverilog PASS

---

### Step 4 — Vivado 100MHz 타이밍 클로저

완료 기준:
- [ ] WNS ≥ 0 @ 100MHz
- [ ] `All user specified timing constraints are met.`
- [ ] 타이밍 위반 시 파이프라인 3단계로 확장 후 재시도

---

### Step 5 — AXI-Stream 래퍼 구현

Step 1~4 (순수 RTL core 검증) 완료 후 진입.

`rtl/transposed_form/fir_decimator_axi_wrapper.v`
완료 기준:
- [ ] AXI-Stream 인터페이스 시뮬레이션 PASS
- [ ] BRAM 콜드 데이터 기준 보드 동작 확인
- [ ] PC Python FFT로 30MHz stopband tone 제거 확인

---

### Step 6 — PS-PL DMA 연동
Zynq PS → AXI DMA → FIR Decimator AXI-Stream IP
완료 기준:
- [ ] Block Design DRC PASS
- [ ] bare-metal C DMA 송수신 동작 확인

---

### Step 7 — bare-metal C + UART

완료 기준:
- [ ] 멀티톤 생성 및 DMA 송수신 동작
- [ ] UART 출력 PC 수신 확인

---

### Step 8 — PC Python FFT 실시간 시각화

시연 목표: 30MHz stopband tone이 필터 후 출력에서 제거되는 것을 실시간 스펙트럼으로 확인.

완료 기준:
- [ ] 실시간 스펙트럼 플롯 동작
- [ ] 필터 전/후 비교 시각적으로 명확

---

## 6. 마일스톤 및 일정

| 마일스톤             | 목표 시점     | 내용                                               |
| -------------------- | ------------- | -------------------------------------------------- |
| **M1**               | **5월 1주차** | **RTL 검증 환경 구축 완료 (hex 벡터 생성)** ← 현재 |
| M2                   | 5월 3주차     | N=43 Transposed Form RTL + iverilog PASS           |
| M3                   | 6월 1주차     | Vivado 100MHz 타이밍 클로저                        |
| **M4 (안전 마감선)** | **6월 말**    | **AXI-Stream 래퍼 + BRAM 오프라인 FFT 확인**       |
| M5                   | 7월 2주차     | PS-PL DMA 연동 완료                                |
| M6                   | 7월 3주차     | 실시간 시연 파이프라인 완성                        |
| M7                   | 7월 말        | 발표 준비 + 보고서 완성                            |

**M4(6월 말)가 분기점이다.** M4 완성 여부로 Plan A/B를 판단한다.

### Plan A vs Plan B

**Plan A (목표):** Step 1~8 전체 완성 → 실시간 FFT 스펙트럼 시각화 시연

**Plan B (안전 마감):** Step 1~5 완성
- N=43 Transposed Form RTL 동작 확인
- AXI-Stream 래퍼
- BRAM 콜드 데이터 + PC Python 오프라인 FFT 스펙트럼 비교

---

## 7. 변경되지 않은 것

| 항목                                              | 상태 |
| ------------------------------------------------- | ---- |
| 필터 스펙 (fp=15MHz, fs=25MHz, As≥60dB)           | 유지 |
| N=43 탭 수                                        | 유지 |
| Q1.15 고정소수점 포맷                             | 유지 |
| Python golden → RTL bit-exact 검증 방식           | 유지 |
| 입력 신호 멀티톤 프로파일 (5/20/30 MHz, 8192샘플) | 유지 |
| Zybo Z7-20 타겟 보드                              | 유지 |
| Kaiser window β=5.653                             | 유지 |
| ties-away-from-zero 반올림                        | 유지 |
| 48-bit 누산기                                     | 유지 |
| Decimator 재사용 (decimator_m2_phase0.v)          | 유지 |

---

## 8. 디렉토리 구조 현황
sim/
├── python/
│   ├── run_compare_ideal_vs_fixed.py  ✅ --form 인수 추가 (v9 변경)
│   └── export_rtl_bringup_vectors.py  ✅ 기존 그대로 재사용
├── output/
│   ├── ideal_vs_fixed_n5/             ✅ N=5 Direct Form 산출물
│   └── ideal_vs_fixed_trans_n43/      ← Step 1에서 생성
└── vectors/
├── direct_form/bringup_n5/        ✅ N=5 bring-up
└── transposed_form/n43/           ← Step 1에서 생성
rtl/
├── direct_form/                       ✅ N=5 bring-up 완료
└── transposed_form/                   ← Step 2~5에서 생성
├── fir_transposed_n43.v
├── fir_decimator_transposed_n43_top.v
├── fir_decimator_axi_wrapper.v
└── constrs/zybo_n43.xdc
sim/rtl/tb/
├── direct_form/                       ✅
└── transposed_form/                   ← Step 2~3에서 생성
├── tb_fir_transposed_n43.v
└── tb_fir_decimator_transposed_n43_top.v