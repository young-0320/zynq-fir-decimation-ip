# 44. AXIS 래퍼 hold-back 구현 — tlast 직전 버블 데드락 수정 및 검증

- 작성일: 2026-07-03
- 선행 문서: `43_axis_tlast_bubble_deadlock_and_holdback_design.md` (재현·설계 결정 — 이 로그가 그 구현 결과)
- 성격: **구현/검증 기록**.

---

## 1. 적용한 수정 (v1·v2 동일, 코어/BD/Tcl 무수정)

수정 파일: `rtl/transposed_form/n43/fir_decimator_n43_axis.v`, `fir_decimator_n43_axis_v2.v`

| 요소 | 내용 |
|---|---|
| Hold-back 포인터 | `pend_valid`/`pend_idx[1:0]` 추가 — 길이 미확정 패킷의 "가장 최근 코어 출력" 슬롯 추적. `pend_idx==0`(맨 앞 슬롯이 미확정)이면 `m_axis_tvalid`·`transfer`를 게이팅해 출력 보류 |
| 소급 태깅 | `tlast_accept` 사이클에 `out_cnt >= target_now`(이미 마지막 출력이 나가 있음)면 pend 슬롯의 tlast 비트를 소급 1로 세팅 (같은 사이클 shift 시 이동 후 위치에 기록) |
| 같은 사이클 태깅 | `core_out_tlast`에 `tlast_accept & (out_cnt+1 >= target_now)` 항 추가 — 마지막 출력이 tlast 수락과 같은 사이클에 나오는 경계 케이스(v1 버블=3)를 즉석 판정 |
| 즉시 종결 | tlast 수락 시점에 `out_cnt + core_out_valid >= target_now`면 `waiting_for_last_out`을 세우지 않고 바로 종결 (드레인 대기 무의미) |
| 종료 판정 레벨화 | `waiting && out_cnt >= target` 레벨 체크를 펄스 경로와 별도로 추가 (방어) |

`target_now = (in_cnt+1)>>1`(조합)과 `tlast_accept` 핸드셰이크 wire를 공용 신호로 추출.
log 42의 `| s_axis_tlast` tready 항은 유지(hold-back과 결합해 "버퍼 만석 + 미해소 pend"
조합을 원천 차단하는 역할도 겸함).

**버퍼 깊이 4칸 불변**: hold가 걸리는 것은 `pend_idx==0`일 때뿐이고, 미확정 출력은 항상
버퍼 내 최신 슬롯이므로 `pend_idx==0` ⇔ 점유 1. 즉 hold 상태에서 버퍼는 사실상 비어 있어
점유 상한(게이트 허용 2 + in-flight 2 = 4)에 영향 없음. 아래 회귀로 실증(드랍 0).

**부수 효과**: 길이 미확정 구간의 출력이 다음 출력 확정까지 보류되므로 m_axis 레이턴시가
최대 +2사이클. 출력 rate(2사이클당 1비트)는 불변 — 골든 TB로 데이터 경로 무변화 확인.

## 2. 신규 회귀 TB + Makefile 편입

- **`sim/rtl/tb/transposed_form/tb_tlast_bubble.sv` 신규**: tlast 직전 tvalid 버블 0~6
  스윕 × {v1, v2} × {tready=1, 지속 backpressure} = 28 DUT, 각 2패킷 무리셋.
  assert: 패킷당 정확 N/2비트 / TLAST 패킷당 1개 / stray 0 / 전 샘플이 버블=0 레퍼런스와
  bit-exact. `make run_bug`에 편입.
- **`tb_fir_decimator_n43_axis_v2.sv`를 `run_all`에 편입** (기존 Makefile 타깃 부재로
  v2 골든 회귀가 make 경로에서 한 번도 안 돌던 검증 공백 — 코드 리뷰 지적 해소).

## 3. 검증 결과

**TB 유효성 (수정 전 RTL로 먼저 실행 — log 42 상태 재구성본):**

```text
v1: 버블 0~2 PASS / 3~6 FAIL (pkts=0, TLAST 유실 데드락)   ← log 43 예측과 정확 일치
v2: 버블 0~3 PASS / 4~6 FAIL (동일)
RESULT: FAIL — 28 errors
```

**수정 후 (`make run_bug` + `make run_all` 전체):**

```text
=== run_bug ===
tb_buf_depth    : DEPTH=4 → overflow 0 (깊이 회귀 유지)
tb_skid_stress  : PASS — 2 packets, no drops/deadlock/stray, packet2==packet1
tb_tlast_bubble : PASS — bubble 0..6 before TLAST, v1/v2, free+backpressure

=== run_all === (이제 v2 골든 포함)
tb_fir_n43 / tb_fir_decimator_n43 : PASS (S1/S2)
tb_fir_decimator_n43_axis         : PASS (S1/S2/S3)
tb_fir_decimator_n43_axis_v2      : PASS (S1/S2/S3)   ← 신규 편입
```

log 43 수용 기준 4개 모두 충족 (버블 스윕 상시 회귀 / run_bug·run_all PASS / 깊이 4 실증
유지 / 코어·BD·Tcl 무수정). 골든 TB S2(max_bubble=3 랜덤)도 이제 시드와 무관하게 안전.

## 4. 남은 것

- **보드 실측 전 타이밍 재확인**: 래퍼 로직이 log 42 + 이번 수정으로 두 차례 변경됨.
  v1@115 / v2@145 재빌드 시 타이밍 리포트(WNS) 확인 후 실측 진행 (전체 스윕 재실행 불필요,
  기존 골든 마진 내 흡수 예상 — workflow_v23 재빌드 절차에 포함).
- abort 경로(펌웨어 dma_run 타임아웃 후 래퍼 잔류 상태) 복구 부재는 별개 known limitation
  (코드 리뷰 finding, workflow_v23 "중요 연결 1" 정정 및 README known limitation에 문서화 완료
  — 이번 수정 범위 아님).
