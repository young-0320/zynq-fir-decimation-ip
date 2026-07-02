# 45. 수정 RTL 골든 재빌드 (v1@115 / v2@145) + BOOT.bin 준비

- 작성일: 2026-07-03
- 선행 문서: `44_axis_holdback_fix_impl.md` (hold-back 구현 — §4 "보드 실측 전 타이밍 재확인"이 이 로그의 작업)
- 성격: **빌드/검증 기록**. 이 로그로 보드 실측 전 에이전트 측 작업이 완료됨.

---

## 배경

AXIS 래퍼 RTL이 2차례 수정되어(log 42 skid/flush/tready, log 43·44 hold-back) 기존
비트스트림들이 전부 수정 전 넷리스트 산출물이 되었다. 보드 실측(workflow_v22 §3/§4) 전에
골든 주파수 재빌드 + 타이밍 영향 확인 + BOOT.bin 재생성을 수행했다.

**커밋 이력 정리 선행**: 수정 일체를 4개 커밋으로 분리 커밋 후 빌드
(`46016d1` 1차 수정 / `673c935` Tcl / `7d85750` wf23 / `6a4bf36` hold-back).
빌드는 `6a4bf36` 시점 워킹트리(클린)에서 수행 — 비트스트림 소속 커밋이 명확하다.

## 1. 재빌드 결과 — 타이밍 완전 중립 (재스윕 불필요 판정)

| 빌드 | WNS | 수정 전 대비 | LUT/DSP/전력 | 크리티컬 패스 |
|---|---|---|---|---|
| v1@115 (`build_bd_fir_dma_clkwiz.tcl -tclargs 115`) | +0.231 | **동일** | 4582/16/1.699W 동일 | `u_fir_n43/prod_reg→round_reg` (코어 CARRY4, 래퍼 아님) |
| v2@145 (`build_bd_fir_dma_v2_clkwiz.tcl -tclargs 145`) | +0.129 | **동일** | 4556/16/1.705W 동일 | `waiting_for_last_out_reg→DSP48.A` (기존 래퍼↔코어 인터페이스 경로, 슬랙까지 동일) |

- hold-back 로직(FF 3개 + 소수 LUT)은 타이밍/자원에 흡수 — **Fmax 116/146 특성은 수정 후
  넷리스트에서도 유효**. 사전에 정한 조건 분기(크리티컬 패스가 래퍼로 이동 시 국소 재스윕)는
  해당 없음으로 종결. 상세는 `vivado/reports/sweep_summary[.md/_v2.md]` "재빌드 검증" 절.
- 새 RTL 반영 확인: 빌드 스크립트가 리포 RTL 경로를 직접 읽고, 빌드 시점 워킹트리가
  hold-back 커밋과 동일(클린)임을 확인.

## 2. BOOT.bin 재생성

```text
build/fir_n43_v1_freq_115mhz/output/BOOT.bin  (--boot-tag FIR,    부팅 배너 "READY FIR")
build/fir_n43_v2_freq_145mhz/output/BOOT.bin  (--boot-tag FIR_V2, 부팅 배너 "READY FIR_V2")
```

- `rebuild_boot_image.sh` 기존 Vitis workspace 재사용 — **v2도 플랫폼 재export 없이 빌드
  통과** (workflow_v22 §4의 fsbl/플랫폼 불일치 리스크는 빌드 단계 미발생, 최종 확인은 보드
  부팅 배너로). C 코드 무변경(동일 소스 재컴파일 + 새 bit 교체).
- **100MHz 골든(`build/fir_n43/output/`)은 의도적으로 무수정** — 실보드 검증 이력 보존 +
  log 41 "확인 필요 1"(구버전 bit로 run1/run2 raw diff, 옛 버그 실보드 재현 확정 실험)의
  입력물이기 때문. 같은 파일명 `BOOT.bin`이므로 경로로 구분할 것.

## 3. 남은 것 (전부 보드 물리 작업 → 이후 문서 반영)

1. v1@115 SD boot → `READY FIR` → `mode 1-2` 실측 (같은 세션 2회 이상 — 반복 실행 오염
   수정의 실보드 확인 겸). PASS 시 sweep_summary correctness 반영 + v1.0 완료 선언.
2. v2@145 동일 절차 → v1↔v2 교체 여부 논의.
3. (선택) 구 100MHz BOOT.bin으로 run1/run2 raw diff — 옛 버그 3 실보드 재현 확정.
