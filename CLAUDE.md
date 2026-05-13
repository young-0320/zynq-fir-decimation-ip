# CLAUDE.md

zynq-axi-fir-decimation-ip

Updated: 2026-05-13
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
Step 6  ✅  PS-PL DMA 연동 (Block Design, 비트스트림, XSA 생성 완료, WNS=+1.239ns)
Step 7  ✅  bare-metal C + UART (ELF 생성 완료 242KB)
Step 8  🔄  PC Python FFT 실시간 시각화 (sw/fir_decimator_demo.py 완성, 보드 검증 대기)

JTAG ELF 로딩은 DDR byte[3] 비결정적 오염으로 폐기 (docs/log/24, docs/log/27).
SD카드 부팅으로 전환 결정 (2026-05-13). SD카드 배송 대기 중.

다음: SD카드 도착 시. 상세 절차 → docs/workflow/workflow_v12.md
  A. BD 재생성 (Preset = ZYBO Z7-20 확인, Board Delay 숫자 채워짐 확인)
  B. ps7_init.tcl이 Digilent 레퍼런스와 일치하는지 diff 검증
  C. Vitis ELF 재빌드 (rm -rf build/vitis && vitis -s vitis/build_fir_decimator_demo.py)
  D. bootgen으로 BOOT.bin 생성
  E. SD카드 FAT32 포맷, BOOT.bin 복사
  F. JP5를 SD로, 전원 인가, DONE LED → UART 응답 → Python FFT 확인

M4 완성 → Plan A(실시간 시연) 계속. 미완성 → HW 결함 가능성 검토 (Plan B).
