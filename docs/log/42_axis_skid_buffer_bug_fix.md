# 42. AXIS 래퍼 skid buffer 4개 버그 — 수정 구현 및 검증

- 작성일: 2026-07-03
- 선행 문서:
  - `41_axis_skid_buffer_bug_sim.md` (버그 4종 iverilog 재현·수치 — 이 수정의 근거)
  - `../workflow/workflow_v22.md` (수정 계획 "수정 설계" 절 — 이 로그가 그 구현 결과)
- 성격: **구현/검증 기록**. 계획은 workflow_v22, 재현 수치는 log 41 참고(문서 구분).

---

## 배경

workflow_v22 "수정 설계"(짝수 전용 · v1·v2 둘 다 · 코어 무수정)에 따라 AXIS 래퍼
(`fir_decimator_n43_axis[.v/_v2.v]`)의 버그 1~4를 구현하고, 업그레이드된 재현 TB
(`make run_bug`)와 골든 회귀(`make run_all`)로 검증했다.

수정 파일(코어/데시메이터/BD/Tcl 무수정):

- `rtl/transposed_form/n43/fir_decimator_n43_axis.v` (v1)
- `rtl/transposed_form/n43/fir_decimator_n43_axis_v2.v` (v2, 동일 변경)
- `sim/rtl/tb/transposed_form/tb_skid_stress.sv` (단일 → 2패킷 무리셋 + 절대 assert 업그레이드)

---

## 1. 적용한 수정 (v1·v2 동일)

| 버그 | 수정 내용 | 계획 대비 |
|---|---|---|
| 1 (skid 드랍) | skid buffer 3칸 → **4칸** (`valid3/data3/tlast3` 추가). 게이트 `~valid1` 유지, shift/로드 우선순위 한 단 연장 | 계획대로 |
| 3 (경계 오염) | flush **0-주입 제거** (`core_in_valid = s_axis_tvalid & s_axis_tready`, `core_in_sample = s_axis_tdata`). 파이프라인은 새 입력 없이 이전-스테이지 valid로 스스로 드레인 | 계획대로 |
| 2 (무한 flush + TLAST 유실) | 종료/TLAST 판정 `out_cnt+1 == target` → **`>=`** (2곳) **+ tready에 `\| s_axis_tlast` 추가**(아래 §2) | **계획에 없던 추가 필요** |
| 4 (홀수 parity) | 로직 무변경. `target = (in_cnt+1)>>1` 는 짝수 N에서 정확. "짝수 전용" 주석만 | 계획대로 |

---

## 2. 계획에 없던 발견 — v1 TLAST 유실 레이스 (버그 2 note b 실측)

업그레이드된 2패킷 TB를 먼저 돌리자 workflow_v22 "수정 설계"의 **최소 패치
(`==→>=` + skid 4칸 + flush 제거)만으로는 버그 2가 완전히 안 고쳐짐**이 드러났다.

**증상**: 지속 backpressure에서 **v1(latency 4)이 패킷2의 TLAST를 잃고 데드락**
(수신 200비트 전부 왔는데 TLAST 0개 → S2MM 무한 대기). v2(latency 5)는 통과 —
즉 최소 패치는 correct가 아니라 **latency 타이밍 운**에 의존했다.

**근본 원인**(workflow_v22 버그2 note b가 예견): tlast 입력이 buffer full로 지연되면,
마지막 코어 출력이 `target`/`waiting_for_last_out`이 확정되기 **전에** 코어를 떠나
버퍼로 들어간다 → 그 출력에 TLAST 태깅을 놓치고, 이후 `out_cnt`가 target을 지나쳐
등호(`>=`여도)가 다시 성립할 코어 출력 펄스가 없어 잠긴다.

**해결(추가 수정)**:

```verilog
assign s_axis_tready = (core_ready | s_axis_tlast) & ~flush_active;
```

짝수 길이 가정에서 **마지막 샘플은 데시메이션 drop 위상이라 출력을 만들지 않는다**
→ 버퍼가 꽉 차 있어도 안전하게 수락 가능. 이렇게 tlast 입력을 즉시 받으면
`target_out_cnt`가 마지막 코어 출력보다 먼저 확정되고, 마지막 출력이 TLAST 태그를
달고 버퍼 슬롯에 실려 나간다(태그가 데이터와 함께 흘러 레이스 소멸).

> 이 항을 지우면 v1이 backpressure에서 다시 깨진다. 래퍼 재수정/새 주파수 재검증 시 유지할 것.

---

## 3. TB 업그레이드 (`tb_skid_stress.sv`)

workflow_v22 수용 기준 2번: 단일 패킷 TB는 버그 3의 *패킷 간* 오염을 못 잡으므로
**리셋 없이 2패킷 연속 + 절대값 assert**로 업그레이드.

- **드라이버**: 2패킷 무리셋 연속 전송, 패킷당 동일 파형. 각 패킷 꼬리에 **≥43개
  zero**를 넣어 FIR 지연선을 0으로 플러시 → 두 패킷이 동일 상태에서 시작하므로
  correct 설계에서 packet2 == packet1 이 성립(짝수 N + flush 제거로 데시메이션 위상도 보존).
- **콜렉터**: TLAST로 패킷 경계 분할, 앞 2패킷 저장, 패킷별 비트수/총 비트수 집계.
- **절대 assert (DUT 4개 각각)**: 패킷당 정확히 N/2(=100)비트 / TLAST는 각 패킷
  마지막 1비트에만 / 총 비트 == 2·N/2(stray 0) / **packet2 == packet1**(오염·위상 드리프트 0).
- 보너스 교차검증: stress == ref, v1 == v2.
- `tb_buf_depth.sv`는 깊이 회귀로 유지(무수정).

---

## 4. 검증 결과

```text
=== make run_bug ===  (미수정 상태에선 FAIL, 수정 후)
tb_buf_depth : 현재 게이트 DEPTH=4 → overflow 0 (DEPTH=3은 112 드랍 — 4칸 근거 회귀)
tb_skid_stress:
  v1 ref    : pkts=2 len=[100,100] total=200
  v1 stress : pkts=2 len=[100,100] total=200
  v2 ref    : pkts=2 len=[100,100] total=200
  v2 stress : pkts=2 len=[100,100] total=200
  RESULT: PASS — 2 packets, no drops/deadlock/stray, TLAST per packet, packet2==packet1

=== make run_all ===  (골든 회귀, 데이터 경로 불변)
tb_fir_n43            : PASS (S1/S2)
tb_fir_decimator_n43  : PASS (S1/S2)
tb_fir_decimator_n43_axis : PASS (S1 TREADY=1 / S2 Random BP+Bubble / S3 Reset Recovery)
```

수용 기준 3개 모두 충족: `run_all` PASS 유지 · `tb_skid_stress` 멀티패킷 업그레이드 ·
업그레이드된 `run_bug` PASS(v1·v2).

---

## 5. 남은 것 / 다음 단계

- BD/Tcl/코어 무수정 확인 완료. Tcl 이슈 2건(workflow_v22 "부수적 Tcl 이슈")은 여전히 미착수(독립·저위험).
- 이제 workflow_v22 로드맵의 보드 실측(v1@115MHz, v2@145MHz)을 진행할 수 있다
  (깨진 래퍼로 재측정하는 리스크 해소).
- **향후(보류)**: 매직넘버(depth 4, `|tlast` 예외) 대신 표준 AXI-Stream register-slice/FIFO로
  전환하면 latency 불변으로 correct-by-construction (log 41 §4, workflow_v22 "확인 필요 3").
