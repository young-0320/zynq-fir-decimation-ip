# vivado/ — 하드웨어 빌드 스크립트와 리포트

| 경로 | 내용 |
| --- | --- |
| `fir_n43/build_bd_fir_dma.tcl` | 메인 100 MHz baseline BD·bitstream·XSA 빌드 |
| `fir_n43/build_bd_fir_dma_clkwiz.tcl` | v1 clk_wiz 빌드 (`-tclargs <MHz>`, 115 골든) |
| `fir_n43/build_bd_fir_dma_v2_clkwiz.tcl` | v2 clk_wiz 빌드 (`-tclargs <MHz>`, 145 골든) |
| `debug/` | DMA smoke/AXIS debug BD 빌드 (근본원인 격리용) |
| `reports/` | 주파수 스윕 리포트 — `sweep_summary.md`(v1) / `sweep_summary_v2.md`(v2) |
| `sweep_loop_runbook.md` | 초기 PS7 PLL 스윕의 실행 지시서 (기록 보존 — 이후 clk_wiz 정밀 스윕으로 대체됨) |

빌드 절차 전체는 `docs/getting_started.md`, 산출물 경로 규칙은 `docs/build_artifacts.md` 참고.
