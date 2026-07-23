# FIR Decimation 설계 결정 요약

- sync 시점: 2026-05-24 (§1~§9) / 2026-07-22 (§10 추가 — 이후 결정 요약)
- 목적: 프로젝트의 핵심 설계 결정을 한 번에 복기할 수 있는 단일 요약 문서
- 사용 원칙:
  - 설계 기록은 `docs/log/*.md`
  - 인터페이스/동작 계약은 `docs/spec/*_spec.md`
  - 이 문서는 중요한 설계 결정만 추려서 현재 기준으로 정리한다

---

## 1) 시스템/알고리즘 스펙

| 항목               | 현재 결정                                                     | 상태 | 근거/출처 |
| ------------------ | ------------------------------------------------------------- | ---- | --------- |
| 입력 샘플링 주파수 | `Fs_in = 100 MHz` | 확정 | `01_spec_and_kaiser.md` |
| 디시메이션 계수    | `M = 2` | 확정 | `01_spec_and_kaiser.md` |
| 출력 샘플링 주파수 | `Fs_out = 50 MHz` | 확정 | `docs/spec/ideal_model_spec.md` |
| 통과대역 경계      | `fp = 15 MHz` | 확정 | `01_spec_and_kaiser.md` |
| 저지대역 시작      | `fs = 25 MHz` | 확정 | `01_spec_and_kaiser.md` |
| 목표 감쇠          | `As >= 60 dB` | 확정 | `01_spec_and_kaiser.md` |
| 저지대역 판정 기준 | coefficient 응답의 `f >= 25 MHz` 전체 worst-case attenuation | 확정 | `07_coeff_stopband_spec_check.md` |
| 필터 설계법        | Kaiser window `β=5.65326` | 확정 | `01_spec_and_kaiser.md` |
| 탭 수              | **N=43 확정** (bring-up N=5, 평가 N=39/41 완료) | 확정 | `07_coeff_stopband_spec_check.md` |
| 처리 순서          | `Anti-alias FIR → Decimator` | 확정 | `docs/spec/ideal_model_spec.md` |

---

## 2) Ideal Python 모델 결정

| 항목                 | 현재 결정                                                | 상태      | 근거/출처 |
| -------------------- | -------------------------------------------------------- | --------- | --------- |
| 기준 dtype           | `np.float64` | 구현 완료 | `docs/spec/ideal_model_spec.md` |
| FIR 출력 정책        | causal full convolution (`len(x) + len(h) - 1`) | 구현 완료 | `anti_alias_fir.py` |
| FIR 경계 처리        | 입력 밖 `x[n-k]`는 0으로 간주 | 구현 완료 | `docs/spec/ideal_model_spec.md` |
| Decimator 구현       | `x[phase::m]` | 구현 완료 | `decimator.py` |
| Top-level 경로       | `run_fir_decimator_ideal(x, h, m=2, phase=0)` | 구현 완료 | `fir_decimator_ideal.py` |
| 비교용 baseline      | `run_downsample_only_ideal(x, m=2, phase=0)` | 구현 완료 | `sim/python/downsample_only_ideal.py` |

---

## 3) Fixed / Golden 모델 결정

| 항목                | 현재 결정                                          | 상태      | 근거/출처 |
| ------------------- | -------------------------------------------------- | --------- | --------- |
| 입력/데이터 포맷    | `16-bit signed, Q1.15` | 확정 | `04_input_qformat.md` |
| FIR 계수 포맷       | `16-bit signed, Q1.15` | 확정 | `03_coeff_qformat.md` |
| 내부 곱셈 결과 포맷 | `32-bit signed, Q2.30` | 확정 | `04_input_qformat.md` |
| 입력 양자화 규칙    | 합산 후 1회 양자화, ties-away-from-zero, clip(-32768, 32767) | 확정 | `docs/spec/bringup_input_signal_spec.md` |
| demo 입력 프로파일  | 8192샘플, 3-tone: 5/20/30 MHz, A=0.3, phase=0 | 확정 | `docs/spec/bringup_input_signal_spec.md` |
| 역할                | ideal 기준선과 RTL 사이 bit-exact golden reference | 확정 | `docs/spec/ideal_model_spec.md` |

---

## 4) RTL 결정

(v1 기준 — v2 추가·타이밍 갱신은 §10)

| 항목             | 현재 결정                                                  | 상태 | 근거/출처 |
| ---------------- | ---------------------------------------------------------- | ---- | --------- |
| RTL FIR 구조     | Transposed Form | 확정 | 계획서 |
| 처리 구조        | 1 sample/cycle 병렬 (N=43 MAC 동시 실행) | 확정 | `14_transposed_form_rtl_decisions.md` |
| 파이프라인 단계  | **3단계** (2단계 시작 → 타이밍 위반으로 확장) | 확정 | `15_rtl_vector_pipeline_extension.md` |
| FIR latency      | 3 cycles | 확정 | `14_transposed_form_rtl_decisions.md` |
| Top latency      | 4 cycles (FIR 3 + Decimator 1) | 확정 | `14_transposed_form_rtl_decisions.md` |
| 계수 저장        | `localparam` 하드코딩 (N=43개) | 확정 | `14_transposed_form_rtl_decisions.md` |
| symmetry 활용    | **미사용** — full N=43 계수 독립 배치 | 확정 | `14_transposed_form_rtl_decisions.md` |
| 누산기 비트폭    | signed 48-bit (`z[k]`, `prod_reg[k]`) | 확정 | `13_transposed_form_golden_policy.md` |
| 반올림 정책      | ties-away-from-zero (Q2.30 → Q1.15) | 확정 | `13_transposed_form_golden_policy.md` |
| in_valid=0 동작  | `z[k]` hold, `out_valid=0` | 확정 | `14_transposed_form_rtl_decisions.md` |
| reset 극성       | active-high, `z[k]` / `prod_reg[k]` / `out_valid` 전부 0 | 확정 | `14_transposed_form_rtl_decisions.md` |
| 코어 포트        | `clk/rst/in_valid/in_sample[15:0]/out_valid/out_sample[15:0]` | 확정 | `14_transposed_form_rtl_decisions.md` |
| Vivado 타이밍    | WNS=+0.278ns @ 100MHz (DSP48=16, LUT=1827 — 초기 코어 단독 합성 시점 값. 현행 코어 자원은 LUT 1792/FF 2113, `vivado/reports/sweep_summary_v2.md`) | 확정 | `16_vivado_timing_closure_transposed_n43.md` |
| 타겟 보드        | Zybo Z7-20 (xc7z020clg400-1) | 확정 | 계획서 |

---

## 5) AXI-Stream 래퍼 결정

(2026-05-24 시점 구조 — 이후 2차 수정으로 Auto-flush·depth-3·tready 조건이 변경됨, §10)

| 항목            | 현재 결정                                                               | 상태 | 근거/출처 |
| --------------- | ----------------------------------------------------------------------- | ---- | --------- |
| 모듈 구조       | `fir_decimator_n43_axis`가 기존 `fir_decimator_n43` 코어 instantiate | 확정 | `28_axis_tb_update_for_log25_rtl_redesign.md` |
| 모듈명          | `fir_decimator_n43_axis` | 확정 | `28_axis_tb_update_for_log25_rtl_redesign.md` |
| 리셋            | 동기 액티브 로우 `aresetn` → 래퍼 내부에서 `rst = ~aresetn`으로 코어에 전달 | 확정 | `17_axi_stream_wrapper_design_decisions.md` |
| TLAST           | 입력 `s_axis_tlast` 기준 목표 출력 개수 계산, 마지막 출력 beat에서 `m_axis_tlast` 생성 | 확정 | `28_axis_tb_update_for_log25_rtl_redesign.md` |
| Auto-flush      | `s_axis_tlast` 수신 후 zero sample 주입으로 FIR/decimator 잔여 출력 배출 | 확정 | `28_axis_tb_update_for_log25_rtl_redesign.md` |
| 백프레셔        | `s_axis_tready = core_ready & ~flush_active`, 출력 3단 skid buffer로 `m_axis_tready` stall 흡수 | 확정 | `28_axis_tb_update_for_log25_rtl_redesign.md` |
| 출력 버퍼       | depth-3 (`valid0/1/2`, `data0/1/2`, `tlast0/1/2`) | 확정 | `28_axis_tb_update_for_log25_rtl_redesign.md` |
| TDATA 폭        | 16비트, 패딩 없음 — `np.frombuffer(dtype=np.int16)`으로 직접 파싱 가능 | 확정 | `17_axi_stream_wrapper_design_decisions.md` |
| 포트 명명 규칙  | AXI 관례 (`aclk`, `aresetn`, `*_axis_*`) — Vivado IP 패키저 자동 인식 | 확정 | `17_axi_stream_wrapper_design_decisions.md` |
| 미사용 신호     | TSTRB/TKEEP/TID/TDEST/TUSER 포함 안 함 | 확정 | `17_axi_stream_wrapper_design_decisions.md` |

---

## 6) PS-PL DMA 연동 결정

| 항목              | 현재 결정                                                               | 상태 | 근거/출처 |
| ----------------- | ----------------------------------------------------------------------- | ---- | --------- |
| FIR IP 삽입 방식  | Module Reference — IP Packaging 아님 (이 BD 하나에서만 사용) | 확정 | `19_ps_pl_dma_integration_design.md` |
| DMA 모드          | Simple DMA (Scatter Gather 비활성) — 시작 주소+길이만으로 충분 | 확정 | `19_ps_pl_dma_integration_design.md` |
| DMA length width  | `CONFIG.c_sg_length_width {23}` — 16384-byte MM2S 전송을 표현하기 위해 명시 | 확정 | `32_smoke_pass_after_dma_length_width_fix.md` |
| Stream 폭         | 16비트 (MM2S/S2MM 모두) — 샘플 포맷 Q1.15와 직접 대응 | 확정 | `19_ps_pl_dma_integration_design.md` |
| DMA 기본 주소     | `0x40400000` (`bd_fir_dma.tcl` assign_bd_address 기준) | 확정 | `20_baremetal_c_fir_dma.md` |
| DDR 접근 경로     | PS HP0 (High Performance) — GP 포트는 PS→PL 방향 전용이라 불가 | 확정 | `19_ps_pl_dma_integration_design.md` |
| 클럭              | PS `FCLK_CLK0` 100MHz → FIR/DMA 전체 공용 | 확정 | `19_ps_pl_dma_integration_design.md` |
| Block Design 재현 | `vivado/fir_n43/bd_fir_dma.tcl` — `source vivado/fir_n43/bd_fir_dma.tcl`로 재생성 가능 | 확정 | `19_ps_pl_dma_integration_design.md` |
| Vivado 타이밍     | main FIR WNS=+0.692ns @ 100MHz | 확정 | `32_smoke_pass_after_dma_length_width_fix.md` |

---

## 7) bare-metal C + UART 결정

| 항목              | 현재 결정                                                               | 상태 | 근거/출처 |
| ----------------- | ----------------------------------------------------------------------- | ---- | --------- |
| 샘플 수           | `N_IN=8192`, `N_OUT=4096` (M=2) | 확정 | `20_baremetal_c_fir_dma.md` |
| UART 디바이스     | `UART_DEVICE_ID = 0` (Vitis BSP 단일 UART 인스턴스 기준) | 확정 | `23_vitis_embedded_build_troubleshooting.md` |
| UART baud rate    | 115200 — 710ms 전송 지연이 데모에서 유리 | 확정 | `22_pc_python_fft_visualization_plan.md` |
| 패킷 동기화 마커  | `MAGIC = 0xDEADBEEF` | 확정 | `20_baremetal_c_fir_dma.md` |
| 캐시 정책         | MM2S 전 `Xil_DCacheFlushRange(src_buf)`, S2MM 후 `Xil_DCacheInvalidateRange(dst_buf)` | 확정 | `20_baremetal_c_fir_dma.md` |
| 최대 톤 개수      | 8개 (`MAX_TONES=8`) | 확정 | `20_baremetal_c_fir_dma.md` |
| 주파수 범위 제한  | 1MHz~49MHz (50MHz는 `sin(πn)=0`으로 신호 없음) | 확정 | `21_vitis_build_and_uart_usage.md` |
| 전체 빌드 도구    | Vitis 2024.2 (`vitis -s vitis/fir_n43/build_fir_decimator_demo.py`) | 확정 | `workflow_v15.md` |
| 빠른 BOOT 재생성  | `vitis/fir_n43/rebuild_boot_image.sh --boot-tag FIR` | 확정 | `31_dma_smoke_test_and_length_width_fix.md` |

---

## 8) PC Python FFT 시각화 결정

| 항목          | 현재 결정                                                               | 상태 | 근거/출처 |
| ------------- | ----------------------------------------------------------------------- | ---- | --------- |
| 스크립트 위치 | `sw/fir_decimator_demo.py` (C 코드와 같은 `sw/` — 파일이 하나씩이라 폴더 분리 불필요) | 확정 | `22_pc_python_fft_visualization_plan.md` |
| FFT y축       | dB scale, 입력 최대 피크 = 0dB (상대 감쇠량 직접 확인) | 확정 | `22_pc_python_fft_visualization_plan.md` |
| FFT x축       | 0~50MHz 유지 + 출력 무효 영역(25~50MHz) 음영 표시 (`OUTPUT_INVALID_REGION_MHZ`) | 확정 | `34_python_demo_report_modularization.md` |
| mode 0        | 보드 불필요 — 로컬 naive downsample vs FIR 비교 (앨리어싱 확인) | 확정 | `22_pc_python_fft_visualization_plan.md` |
| mode 1-1/1-2  | 실보드 연동 — UART로 명령 전송 → binary 수신 → FFT 표시 | 확정 | `22_pc_python_fft_visualization_plan.md` |
| UART 수신     | magic 찾을 때까지 1바이트씩 스캔 (노이즈 내성) | 확정 | `22_pc_python_fft_visualization_plan.md` |
| FIR 계수      | RTL `fir_n43.v`와 동일한 Q1.15 정수값 / 32768.0 하드코딩 | 확정 | `22_pc_python_fft_visualization_plan.md` |

---

## 9) 검증 계획

| 항목                    | 현재 결정                                          | 상태      | 근거/출처 |
| ----------------------- | -------------------------------------------------- | --------- | --------- |
| ideal 단위테스트        | FIR, decimator, top-level, Kaiser 설계 함수 테스트 | 완료      | `sim/python/test/ideal/*.py` |
| Python vs RTL 비교 방식 | Python golden model과 RTL 출력 bit-exact 자동 비교 | 완료      | 계획서 |
| alias 비교 실험         | `downsample only` vs `FIR → downsample`           | 완료      | `sim/python/downsample_only_ideal.py` |
| RTL TB 방식             | M_AXIS 핸드셰이크(tvalid & tready) 성사 시점에만 비교 | 완료 | `18_axis_buffer_overflow_fix_and_tb_robustness.md` |
| 실보드 검증             | SD boot `READY FIR`, UART 수신, Python modes `1-1`/`1-2` plot 도달 | 완료 | `32_smoke_pass_after_dma_length_width_fix.md` |

---

## 미정 항목

PC FFT 시각화와 정량 pass/fail 리포팅은 다음 작업. 보드 bring-up 경로는 SD boot 기준으로 통과.

## 10) 2026-05-24 이후 갱신 (2026-07-22 sync)

| 항목 | 결정 | 상태 | 근거/출처 |
| --- | --- | ---- | --------- |
| v2 코어 | round 분리 4-stage 추가, FIR latency 4 cycle, Fmax 116→146MHz | 확정 | `39`, `40`, `sweep_summary_v2.md` |
| 래퍼 1차 수정 | skid 4칸으로 재설계, auto-flush 제거, `s_axis_tready`에 `\| s_axis_tlast` 항 추가 | 확정 | `41`, `42` |
| 래퍼 2차 수정 | 마지막 출력 hold-back — tlast 직전 버블 데드락의 구조적 해결 | 확정 | `43`, `44` |
| 배포 주파수 | v1 115MHz / v2 145MHz (Fmax 바로 아래 마진 확보) — 둘 다 보드 기능 동작 확인 | 확정 | `sweep_summary*.md`, `45` |
| DMA length 필드 | `c_sg_length_width=23` (기본 14-bit가 16384B를 1B 초과로 미표현) | 확정 | `31`, `32` |
| 검증 기준 경로 | SD boot + DMA + UART (JTAG/XSDB DDR 직접 쓰기는 신뢰 경로에서 제외) | 확정 | `24`, `27`, `32` |
| ASIC 교차 검증 | 250nm 합성에서 v1≈v2 동률 — v2 분할 이득은 FPGA CARRY4 종속으로 확정 | 확정 | `47`, `asic_vs_fpga.md` |
| 보드 전력 실측 | S0 1.72 / S1 2.21 / S2 2.18W, Vivado 1.705W와 정합 범위 | 확정 | `46` §5, `power_board_vs_vivado.md` |
