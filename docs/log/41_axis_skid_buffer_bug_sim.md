# 41. AXIS 래퍼 skid buffer 4개 버그 — iverilog 재현 및 버퍼 깊이 실측

- 작성일: 2026-07-03
- 선행 문서:
  - `40_clkwiz_precision_sweep_v1_v2_fmax.md` (v1/v2 Fmax 확정 — 이 조사의 직전 단계)
  - `../workflow/workflow_v22.md` (이 로그의 측정 결과를 바탕으로 세운 **수정 계획**)
- 성격: **측정/재현 기록**. 수정 방향·의사결정·실행 순서는 workflow_v22 참고(문서 구분).

---

## 배경

workflow_v21(v2 파이프라인 분할 + clk_wiz 스윕) 완료 후 보드 실측으로 넘어가기 전,
코드 리뷰에서 "미확인 코너케이스"로 남겨뒀던 AXIS 래퍼(`fir_decimator_n43_axis[.v/_v2.v]`)의
3단 skid buffer를 검증했다. 결과적으로 skid buffer 드랍 의심이 사실로 확인됐고 추가 3개
버그가 더 드러났다. 이 로그는 그 **시뮬레이션 재현과 수치**만 기록한다. 버그의 근본 원인
해설·수정안·우선순위는 workflow_v22로 분리했다.

버그 요약(상세 해설은 workflow_v22 §0/버그 절):

1. skid buffer 드랍 (3-slot 용량 부족)
2. 무한 flush 데드락 (`==` 종료 판정)
3. 백프레셔 없이도 발생하는 패킷 경계 오염
4. 홀수 길이 target 계산 오류 + 데시메이터 위상 드리프트

공통: v1/v2 양쪽 해당(래퍼 로직 동일, v2가 새로 만든 버그 아님).

---

## 1. 재현 TB #1 — end-to-end 스트레스 (`tb_skid_stress.sv`)

v1/v2 래퍼를 각각 reference(`m_axis_tready=1` 고정)와 stress(40사이클 중 25 low로
지속 백프레셔) 쌍으로 인스턴스화하고, 연속 입력(버블 0)을 흘려 드랍/데드락/오염을 비교.
현재 기존 `tb_fir_decimator_n43_axis_v2.sv`는 bubble=0이어도 샘플 사이에 최소 1 idle
사이클이 구조적으로 들어가 이 조합을 원리적으로 못 친다.

**N_IN=200(짝수) 결과:**

| DUT | 수신 비트 | TLAST | 상태 |
|---|---|---|---|
| v1 ref (tready=1) | 102 | 정상(beat 99) | +stray 2 (버그 3) |
| v1 stress | 3500+ | 없음 | **무한 flush 데드락**(out_cnt=4002/target=100, 버그 2) |
| v2 ref (tready=1) | 102 | 정상(beat 99) | +stray 2 (버그 3) |
| v2 stress | 87/102 | 없음 | **15개 드랍 + TLAST 유실**(버그 1) |

- **버그 1**: v2 stress에서 102 중 15 드랍, 하필 TLAST 비트도 드랍 → 하류 S2MM 무한 대기.
- **버그 2**: v1 stress에서 종료 등호를 지나쳐 0을 무한 토출(3500+).
- **버그 3**: backpressure 전혀 없는 ref에서도 200입력 → 102비트(TLAST 뒤 stray 2),
  종료 후 `out_cnt=2` 잔류, v1은 `keep_next` 위상 반전(reset값 1 → 0).

**N_IN=201(홀수) 결과:** ref에서 기대 101비트/TLAST at 100인데 TLAST가 beat 99로
한 출력 일찍 나옴(버그 4, `(in_cnt+1)>>1` = floor). stress는 v1/v2 모두 데드락.

---

## 2. 재현 TB #2 — 버퍼 깊이 격리 측정 (`tb_buf_depth.sv`)

버그 1만 격리해 "몇 칸이면 드랍 0인가"를 측정. flush/패킷 FSM은 제외하고 순수하게
"연속 입력 + 최악 backpressure(54사이클 중 48 low)"에서 코어 출력이 버퍼를 넘치는지만
카운트. 무한(64칸) 버퍼로 최대 점유량을 재면 = 필요 깊이. 게이트는
`core_ready = (cnt <= GATE_MAX)`로 파라미터화(`GATE_MAX=1`이 현재 `~valid1`,
`GATE_MAX=0`이 `~valid0`).

**무한 버퍼 최대 점유량 = 필요 깊이:**

| 게이트 규칙 | 최대 점유 |
|---|---|
| 현재 `~valid1` (cnt≤1에서 수락) | **4칸** |
| `~valid0` (cnt≤0에서 수락, 더 일찍 막기) | **3칸** |

**유한 깊이별 드랍(overflow) 횟수:**

| 게이트 | DEPTH=3 | DEPTH=4 | DEPTH=5 |
|---|---|---|---|
| 현재 `~valid1` | 드랍 112 | **0** | 0 |
| `~valid0` | **0** | 0 | — |

- 현재 게이트 유지 시 **DEPTH 4면 드랍 0**(깊이 근거 = 2 게이트 허용 + 2 파이프라인 in-flight).
- 게이트를 `~valid0`로 한 칸 일찍 막으면 **DEPTH 3으로도 0**.
- 두 안 모두 `delivered/accepted ≈ 0.5`로 데시메이션 비율 유지 → throughput 손실 없음.

---

## 3. 왜 실보드 검증(`scenario1_2.md`, 100MHz PASS)은 통과했나 (해석)

- **버그 1·2(드랍·데드락)**: 발동 조건은 "하류가 여러 사이클 연속 backpressure". 실 DMA는
  데시메이션으로 2사이클당 16비트(≈100MB/s)만 받으므로 DDR/HP가 밀릴 일이 거의 없어
  tready가 죽지 않는다 → 방아쇠가 안 당겨진 **잠복 버그**. DDR 혼잡 / 클럭 상승(146MHz 스윕)
  / S2MM FIFO 축소 등에서 터질 수 있다.
- **버그 3·4(오염)**: backpressure 없이도 매 두 번째 명령부터 발생했을 가능성이 높지만,
  검증 지표(FFT 크기 스펙트럼 / SNR / 피크 주파수)가 "몇 샘플 시프트"(크기 스펙트럼 불변)와
  "데시메이션 위상 뒤집힘"(Nyquist 아래 동일 톤)에 **원리적으로 둔감**해서 못 봤다. 즉 양이
  적어 희석된 게 아니라, 오염의 종류가 하필 FFT가 못 보는 종류였다.
- 미확인: 그 PASS 캡처가 부팅 후 첫 캡처였는지. **결정적 실험** = 같은 세션 run1/run2 raw
  캡처를 샘플 단위로 diff(run2 앞에 stray 2 + 시프트가 보이면 실보드 재현 확정).

---

## 4. 버그 1 버퍼 수정 — 권장 (결론)

- 실측상 두 안 모두 드랍 0: **안 A**(게이트 유지, DEPTH 3→**4**) / **안 B**(DEPTH 3, `~valid0`).
- **권장 = 안 A(DEPTH 4)**. 버퍼만 키우면 입력 수락 타이밍(`core_in_valid`)을 안 건드려서
  버그 2·3·4 로직과 간섭이 없다(가장 국소적). 안 B는 게이트 타이밍이 flush/FSM과 얽혀
  그 수정과 함께 봐야 안전. 깊이 4의 근거 = 2(게이트 허용) + 2(파이프라인 in-flight).
- 어느 쪽이든 "왜 이 숫자인지" 주석 + 스트레스 TB 회귀로 못 박아 latency 변경 시 CI가 잡게 할 것.
- **향후(보류)**: 매직넘버 대신 표준 AXI-Stream register-slice/FIFO(full 기반 backpressure)로
  가면 latency 불변으로 correct-by-construction. 버그 2·3·4 재설계 때 함께 검토.

---

## 5. 결론 (수치)

- 버그 1~4 모두 iverilog로 재현 확정. v1/v2 공통.
- 버그 1 필요 버퍼 깊이: **현재 게이트 4칸 / `~valid0` 게이트 3칸** (실측).
- 버그 2·3·4는 버퍼 크기와 무관한 로직 버그(flush 종료 판정/과다 주입/위상) — 버퍼만
  키워선 안 고쳐짐.

**재현 자산**: `sim/rtl/tb/transposed_form/tb_skid_stress.sv`,
`sim/rtl/tb/transposed_form/tb_buf_depth.sv` (편입 완료). 실행: `cd sim && make run_bug`.
미수정 상태에선 FAIL(드랍/데드락 재현) — 버그 1 수정 성공 기준 = `run_bug` PASS.

수정 방향/우선순위/실행 순서는 → `../workflow/workflow_v22.md`.
