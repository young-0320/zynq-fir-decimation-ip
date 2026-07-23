# 50. 공개 전 전수조사와 현재형 문서 정합화, release/ 승격

- 날짜: 2026-07-23
- 목적: 8/7 최종 발표·GitHub 공개 전에 "현재를 주장하는 문서"들의 수치 정합성·참조
  무결성·재현성을 전수 확정하고, 발견 사항을 수정한다.
- 관련: workflow_v24 §4 (GitHub 정리), log 49 (CPU 재측정 히스토리), log 40 (Fmax 정정)

## 1. 조사 방법

병렬 감사 5종을 수행했다. 대원칙: `docs/log/`·`docs/workflow/`는 역사 기록이므로
수정하지 않는다 (낡은 수치가 있어도 당시 기록이면 정상). 조사 대상은 현재형 문서 —
README, CLAUDE.md, docs/spec/**, docs/report/**, build_artifacts, sweep_summary*,
rtl/asic README.

- A. 수치 정합: 확정 수치표(아래) 기준으로 구수치 전수 grep + 문서별 대조
- B. 참조 무결성: 경로/이미지 참조 약 340건 실존·git 추적 여부 확인
- C. 재현성: sim make 전 타겟 실행, Python 체인 fresh 재생성, README 절차 추적
- D. 공개 위생: PII/시크릿/대용량 파일 + git 히스토리 blob 재스캔
- E. README 첫인상: 처음 방문자 관점 구조 점검

기준 확정 수치: CPU 221.0µs / FPGA 85.0µs (2.6배, 이론 81.92µs 대비 3.8%),
Fmax v1 116/배포 115·v2 146/배포 145 MHz, SNR 74.86/72.22 dB, 전력 S0 1.72/S1 2.21/
S2 2.18 W, 코어 DSP 16/LUT 1792/FF 2113, c_sg_length_width=23.

주의 — 162.0/83.0µs(1.95배)는 "오류"가 아니다. CPU 측정은 세션 간 170~300µs로
요동하며, 4차 미팅(7/2) 보고 시점 측정값이 162.0/83.0이었고 이후 반복 재측정으로
221.0/85.0을 최종 채택했다(log 49). 히스토리 부기로는 유지하고, 현재형 문서가
최신값처럼 인용하는 경우만 수정 대상으로 삼았다.

## 2. 주요 발견과 수정 (2026-07-23 반영)

수치 정합 (A):

- README 결과표의 83.0µs/1.3%/1.95× → 85.0µs/3.8%/2.6×(CPU 221.0µs)
- presentation_outline 슬라이드 10의 162.0/83.0 → 221.0/85.0 (+CPU 요동 명기),
  83µs burst 잔존 4곳(outline·power_board_vs_vivado·장학 md) → 85µs
- "통과대역 0~20MHz, 25MHz −6dB" 오기(final_report_draft·outline) → fp=15MHz,
  25MHz(전이대역) 실측 −60.3dB, 45MHz alias −64.5dB (scenario1_2 정합).
  "half-band" 명칭도 Kaiser lowpass로 정정 (fp+fs=40≠50이라 half-band 아님)
- sweep_loop_runbook의 "확정 Fmax 115"에 현행화 주석 — 구 115는 PS7 PLL 스냅으로
  실제 111.111MHz였던 오라벨, clk_wiz 정밀 스윕이 116으로 정정(log 40). 기록 원문은
  보존하고 상단 주석만 추가
- summary_design_decisions의 LUT 1827에 "초기 시점 값, 현행 1792/2113" 주석,
  rtl_n43_transposed_spec §12 보드 체크리스트 완료 처리

참조 무결성 (B):

- outline의 삭제된 `cpu_vs_fpga_timing_window.png` → 실존 `cpu_vs_fpga_timing.png`
  (workflow_v24 §7 그림 목록도 동일 수정)
- sweep_summary_v2가 인용하는 `v2_145mhz_*.rpt` 3종이 `*.rpt` ignore에 걸려 미추적
  → negation 추가 후 추적
- CLAUDE.md·sweep_loop_runbook의 `/home/young/...` 절대경로 제거,
  repository_structure의 유령 todo.md·"Current=v15/v16" 현행화

재현성 (C): 검증 루프는 성립 — pytest 163개 PASS, `sim/vectors` 삭제 후 문서 명령만으로
비트 단위 동일 재생성, `run_all`/`run_bug` 전 시나리오 PASS, git status 오염 없음.
단 README Quick Start의 `make run_all`은 fresh clone에서 벡터 부재로 실패함 —
**수정 보류(사용자 판단 대기)**, workflow_v24 §4 후속 체크리스트에 등재.

공개 위생 (D): 시크릿·10MB 초과 추적 파일 없음. 사용자 결정 — asic tcl 학번 경로,
git author 개인 이메일, 지도교수 전화번호(공개 정보)는 **그대로 공개**. 장학
PDF·hwp(+초안 md 2종 여부)는 공개 전 본인이 직접 삭제 예정.

## 3. README 개편과 release/ 승격

- README를 한/영 병기 전문으로 재작성: 결과 요약 아래 이미지 3종(BD SVG,
  scenario1_1 FFT, CPU vs FPGA 차트) 삽입, Requirements 섹션, 근거 링크 불릿화,
  Repository Map에 boards/·release/ 추가와 build/ 각주, License(MIT) 섹션,
  하단에 영어 전문(이미지는 중복 삽입 없이 상단 그림 참조)
- **release/ 신설**: 검증된 BOOT.bin을 git 정식 추적으로 승격 —
  `release/v2_145mhz/BOOT.bin`(기본 권장, 전력 실측·데모 검증 이미지),
  `release/v1_115mhz/BOOT.bin`. `.gitignore`에 `!release/*/BOOT.bin` negation.
  클론 직후 빌드 없이 보드 데모가 가능해짐. v1↔v2 대표 결정(7/29 미팅)과 무관하게
  둘 다 보존
- 개발 로그 편수 표기는 본 문서 추가로 50편

## 4. fresh clone `make run_all` 실패 해소 (같은 날 추기)

C 발견의 해법으로 세 안(README에 명령 추가 / Makefile 자동 생성 / 벡터 git 추적) 중
**Makefile 자동 생성을 채택**(사용자 결정). `sim/Makefile`에 벡터 대표 파일
(`input_q15.hex`)을 타겟으로 하는 생성 규칙을 추가하고 `run_all`·`run_legacy_n5`의
의존성으로 연결 — 벡터가 없으면 기존 Python 스크립트 2종(run_compare_ideal_vs_fixed
→ export_rtl_bringup_vectors)을 자동 실행하고, 있으면 건드리지 않는다(기존 워크플로우
불변). n5 벡터 재생성 절차 미문서화 문제도 같은 패턴으로 함께 해소.

검증: `sim/vectors`·`sim/output`·`sim/build` 전체 삭제 후 `make run_all` →
벡터 자동 생성 + 4개 TB 전 시나리오 PASS, `run_legacy_n5`·`run_bug` PASS,
재생성 벡터는 삭제 전과 비트 단위 동일(diff clean). README Quick Start는 수정 불필요.

## 5. 남은 항목

workflow_v24 §4 "전수조사 후속" 체크리스트가 단일 기준: 장학 서류 삭제(본인),
axis TB readmemh "Too many words" 경고(참고, 무해).
