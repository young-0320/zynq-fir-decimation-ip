# CLAUDE.md

zynq-axi-fir-decimation-ip

Updated: 2026-05-04
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
Step 6  🔄  PS-PL DMA 연동 ← 현재
Step 7      bare-metal C + UART
Step 8      PC Python FFT 실시간 시각화

M4 완성 → Plan A(실시간 시연) 계속. 미완성 → 스코프 재조정.

---

## code style

### Verilog

```verilog
`timescale 1ns / 1ps
`default_nettype none
// ... 모듈 내용
`default_nettype wire
```

- reset: `always @(posedge clk or posedge rst)`
- 출력 레지스터: `output reg`
- signed 명시: `signed [47:0]`, `signed [15:0]`

### Python

- type hint 필수, docstring 필수
- 기존 `model/` 구조 패턴 유지

### 문서

- `docs/log/NN_*.md` 형식, 제목 영어, 본문 한국어
- 커밋: conventional commits (feat/fix/test/docs/refactor)
- 로그 헤더 형식:

```markdown
# NN. English Title

- 작성일: YYYY-MM-DD
- 단계: N          ← 이전 로그 단계 +1, "Step N" 형식 쓰지 않음
- 목적: 한 줄 설명 (마침표 없음)
- 선행 문서: `docs/log/NN_*.md`  ← 없으면 생략
```

- 섹션 번호: `## 1.` 형식 사용 (`)` 사용, `)` 아님)
- 섹션 사이 `---` 구분선 사용
- 마지막 섹션: `## N. 의미` 서술형 — 결론 테이블 쓰지 않음
- 각 결정마다 근거(왜 이렇게 했는가) 포함
- `단계` 값: 직전 로그 +1 (현재 최신 16번 = 단계 8)

---
