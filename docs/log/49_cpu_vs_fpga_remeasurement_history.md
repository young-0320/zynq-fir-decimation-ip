# 49. CPU vs FPGA 벤치마크 수치 히스토리 — 162/83 → 221/85 정착

- 작성일: 2026-07-22
- 선행 문서:
  - `37_cpu_vs_fpga_benchmark_implementation.md` (벤치마크 구현)
  - `38_professor_meeting_2026_07_01.md` (4차 미팅 보고 수치)
  - `45_golden_rebuild_boot_prep.md` (BOOT.bin 골든 재빌드)

---

## 배경

최종 결과보고서 작성 중, 레포의 비교 차트(`docs/report/fir_n43/plot/cpu_vs_fpga_timing.png`,
CPU 221.0µs / FPGA 85.0µs)와 문서 전반의 수치(162.0µs / 83.0µs)가 불일치함을 발견.
경위를 추적해 히스토리를 확정하고, 보고서 반영 원칙을 정리한다.

## 수치 히스토리

| 시점 | CPU (Windows) | FPGA | 출처 |
| --- | ---: | ---: | --- |
| 2026-06-29 구현 직후 ~ 7/1 미팅 보고 | 162.0µs | 83.0µs | log 38 (미팅 사전 보고자료) |
| 이후 반복 재측정 (3~4회, 동일 노트북) | 221.0µs | 85µs | `cpu_vs_fpga_timing.png` (최종 차트) |

- **확정 수치 (보고서 기준)**: CPU 221.0µs / FPGA 85.0µs — 약 2.6배,
  이론 처리 시간 81.92µs(8192÷2÷100MHz) 대비 오차 약 3.8%.
- Ubuntu 측정 58.6µs는 **별도 머신**(Ryzen 7 9700X 데스크톱, BLAS 최적화 활성) 값.
  같은 노트북의 OS 차이가 아님에 유의.
- 미팅 시점 차트 `cpu_vs_fpga_timing_windows.png` / `_ubuntu.png`는 로컬에서 삭제되어
  레포에 없음. 현존 차트는 `cpu_vs_fpga_timing.png`(221/85, 방법론 각주 포함) 단일본.

## 83 → 85 변화에 대한 소견

FPGA 값은 보드 펌웨어가 `XTime_GetTime()`으로 MM2S kick~S2MM IDLE 구간을 재서
u32 정수 µs로 전송하는 실측값(`fir_decimator_demo.c` `dma_run()`).
정수 µs + 결정론적 데이터패스 특성상 **반복 실행에서 동일 정수가 나오는 것이 정상**이며,
이는 "환경 무관 결정론적 처리 시간" 주장의 실증이기도 하다.
83 → 85 변화는 그 사이 BOOT.bin이 hold-back 수정 후 골든 재빌드본(log 45)으로 교체된
것과 시기가 겹친다(단정은 하지 않음 — 아래 재확인 절차로 provenance만 확정).

## FPGA 값 provenance 재확인 절차

`cpu_benchmark.py`에는 FPGA 기본값이 하드코딩되어 있지 않다. 값이 차트에 들어가는
경로는 두 가지뿐:

1. `--port COM3` → 보드 실측 (`FIR_TIME_US:` UART 수신, 콘솔에
   `Board FIR_TIME_US: 85 us` 출력)
2. `--board-time-us 85` → 수동 입력 (fallback)

확정 차트가 1번 경로로 생성되었는지 재확인하려면:

```bash
uv run python sw/cpu_benchmark.py --port COM3
# 콘솔의 "Board FIR_TIME_US: XX us" 라인이 보드 전송 실측값
```

## 보고서 반영 원칙

- **Ⅰ장 3-2 (성과)**: 최종 확정 수치 221.0/85.0, 약 2.6배, 오차 약 3.8% 사용.
  차트는 `cpu_vs_fpga_timing.png`.
- **Ⅲ장 4-4 (지도내역)**: 4차 미팅에서 실제 보고한 162.0/83.0/1.95배/1.3%를
  역사 기록으로 유지하고, "이후 반복 재측정을 거쳐 221.0µs/85.0µs로 최종 확정"
  정정 문장을 부기 (Fmax 115→116 정정과 동일한 처리).
