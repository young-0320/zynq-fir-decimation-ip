# CLAUDE.md

zynq-axi-fir-decimation-ip

Updated: 2026-07-03
Repository root: `/home/young/dev/10_zynq-fir-decimation-ip`
README.md root: `/home/young/dev/10_zynq-fir-decimation-ip/README.md`

---

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:

- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:

- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

## 현재 완료 상태 및 작업 순서

Step 1  ✅  N=43 RTL 벡터 생성
Step 2  ✅  fir_n43.v + TB iverilog PASS
Step 3  ✅  fir_decimator_n43.v + TB PASS (4117 samples)
Step 4  ✅  Vivado 100MHz 타이밍 클로저 WNS=+0.278ns (DSP48=16, LUT=1827)
Step 5  ✅  AXI-Stream 래퍼
Step 5-1 ✅ transposed form 모듈의 계층 구조 재설계 및 네이밍 확립
Step 5-2 ✅ AXI-Stream 버그 수정 및 tb robustness 강화(.sv)
Step 6  ✅  PS-PL DMA 연동 (Block Design, bitstream, XSA 생성 완료, main FIR WNS=+0.692ns)
Step 6-1 ✅ AXI DMA MM2S timeout root cause 확정 및 수정
Step 6-2 ✅ smoke/debug BD 분리 생성 (`axis_dma_smoke_test`, `axis_decimator_m2_n43_debug`)
Step 7  ✅  bare-metal C + UART + SD BOOT flow 동작 확인 (`READY FIR`, `READY SMOKE`)
Step 7-1 ✅ `vitis/fir_n43/rebuild_boot_image.sh`로 C-only/bit 교체 BOOT 재생성 자동화
Step 8  ✅  PC Python FFT 시각화 보드 검증 완료 (`mode 1-1`, `mode 1-2` plot 도달)

핵심 장애 원인:

```text
N_IN = 8192 samples
sample = int16_t = 2 bytes
MM2S_LENGTH = 8192 * 2 = 16384 bytes = 0x4000

AXI DMA default c_sg_length_width = 14
14-bit max length = 2^14 - 1 = 16383 bytes

결론: MM2S transfer length가 default DMA length field 한계를 정확히 1 byte 초과.
수정: vivado/fir_n43/bd_fir_dma.tcl 계열에 CONFIG.c_sg_length_width {23} 명시.
```

검증 결과:

```text
수정 전: main FIR / axis debug / smoke 모두 MM2S DMA timeout
수정 후: smoke BOOT 통과, main FIR BOOT 통과, Python FFT plot 도달
```

JTAG ELF 로딩 및 XSDB DDR `mwr/mrd` 경로는 DDR byte[3] MSB 오염이 관찰되어 최종 검증 경로에서 제외한다.
이 문제는 `CONFIG.c_sg_length_width`와 직접 원인을 공유한다고 보지 않는다. SD boot + DMA + UART 경로를 기준 검증 경로로 사용한다.

현재 기준 산출물:

```text
Main FIR Vivado dir: build/fir_n43/vivado/
Main FIR Vitis dir:  build/fir_n43/vitis/
Main FIR output dir: build/fir_n43/output/
Main FIR bitstream:  build/fir_n43/output/bd_fir_dma_wrapper.bit
Main FIR XSA:        build/fir_n43/output/bd_fir_dma_wrapper.xsa
Main FIR SD BOOT:    build/fir_n43/output/BOOT.bin
```

v1/v2, 골든/fallback 등 그 외 빌드 산출물 전체 경로와 재현 명령은 `docs/build_artifacts.md` 참고.

이미 완료된 항목 (과거 "다음 작업 순서"는 모두 끝나 정리함, log 34 / `scenario1_2.md`):

- FFT peak dB 정량 출력 → 완료 (`fir_decimator_metrics.py`)
- `mode 1-1`/`mode 1-2` 7/15/25/45MHz 톤별 수치·판정 → 완료 (`scenario1_2.md` 표)
- 25MHz Nyquist-edge peak / 45MHz alias 억제 문서화 → 완료 (같은 표)
- plot x축 → 크롭 대신 0~50MHz 유지 + invalid region(25~50MHz) 음영 처리로 해결
  (`fir_decimator_fft_viewer.py` `OUTPUT_INVALID_REGION_MHZ`)

다음 작업 순서 (workflow_v22 로드맵 기준):

1. ✅ AXIS 래퍼 버그 수정 완료 (v1·v2, 짝수 전용, 코어 무수정) — 2단계로 진행:
   1차 skid buffer 버그 1~4 (`docs/log/42`), 2차 코드 리뷰에서 발견된 tlast 직전 버블
   데드락을 hold-back으로 수정 (`docs/log/43` 설계, `docs/log/44` 구현·검증).
   `make run_bug`(버블 스윕 회귀 포함)/`run_all`(v2 골든 포함) 전체 PASS.
2. 보드 실측 — v1@115MHz (workflow_v20 v1.0 완결 조건 5/5 마무리)
   - ✅ 수정 RTL 재빌드 + WNS 확인 완료 (+0.231 동일, 크리티컬 패스 코어 불변, Fmax 116
     유효 — `vivado/reports/sweep_summary.md` 재빌드 검증 절). BOOT.bin 준비:
     `build/fir_n43_v1_freq_115mhz/output/BOOT.bin`
3. 보드 실측 — v2@145MHz (workflow_v21 마무리), 이후 v1↔v2 교체 여부 결정
   - ✅ 재빌드 + WNS 확인 완료 (+0.129 동일, Fmax 146 유효 — `sweep_summary_v2.md`).
     BOOT.bin 준비: `build/fir_n43_v2_freq_145mhz/output/BOOT.bin`
   - 실측 절차·리스크는 `docs/workflow/workflow_v22.md` §3/§4 참고

상세 디버깅 기록:

```text
docs/log/31_dma_smoke_test_and_length_width_fix.md
docs/log/32_smoke_pass_after_dma_length_width_fix.md
docs/log/41_axis_skid_buffer_bug_sim.md   (AXIS 버그 재현·수치)
docs/log/42_axis_skid_buffer_bug_fix.md   (AXIS 버그 1차 수정·검증)
docs/log/43_axis_tlast_bubble_deadlock_and_holdback_design.md  (잔존 데드락 재현·hold-back 설계)
docs/log/44_axis_holdback_fix_impl.md     (hold-back 구현·검증)
```

M4 상태: SD boot 기반 end-to-end 실시간 시연 경로 통과, 정량 스펙 검증 완료, AXIS 래퍼
프레이밍 버그 수정 완료(2단계, 시뮬레이션 검증). 남은 작업은 v1@115MHz / v2@145MHz 보드
실측(Fmax 정확도 검증, 재빌드 시 타이밍 확인 포함)뿐.
