# 빌드 산출물 경로 매니페스트

- 갱신일: 2026-07-02
- `build/`는 전체가 `.gitignore` 대상이라 git에는 아무것도 남지 않는다. 다른 머신에서는
  아래 명령을 그대로 재실행해야 산출물이 재현된다 — **경로는 스크립트가 자동으로 결정**하므로
  수동으로 파일을 옮기거나 이름 붙일 필요가 없다.

## v1 (`fir_n43.v`, 3-stage 파이프라인)

| 용도 | 경로 | 재현 명령 |
| --- | --- | --- |
| **메인 baseline (100 MHz golden)** | `build/fir_n43/output/` | `vivado -mode batch -source vivado/fir_n43/build_bd_fir_dma.tcl` |
| 골든 배포 (115 MHz, Fmax 116의 안전마진 버전) | `build/fir_n43_v1_freq_115mhz/output/` | `vivado -mode batch -source vivado/fir_n43/build_bd_fir_dma_clkwiz.tcl -tclargs 115` |

- 메인 baseline(`fir_n43/`)은 CLAUDE.md에 명시된 v1.0 제출/데모 기준선. Vitis workspace가
  이 경로에 물려 있어 리네임하지 않는다.
- Fmax/골든 상세 데이터: `vivado/reports/sweep_summary.md`

## v2 (`fir_n43_v2.v`, 4-stage 파이프라인, round 분리)

| 용도 | 경로 | 재현 명령 |
| --- | --- | --- |
| **골든 배포 (145 MHz, Fmax 146의 안전마진 버전)** | `build/fir_n43_v2_freq_145mhz/output/` | `vivado -mode batch -source vivado/fir_n43/build_bd_fir_dma_v2_clkwiz.tcl -tclargs 145` |
| fallback (130 MHz, 구 골든) | `build/fir_n43_v2_freq_130mhz/output/` | 동일 스크립트 `-tclargs 130` |
| 참고용 (146 MHz, 실측 Fmax 자체 — 배포 안 함) | 미보존(필요 시 재생성) | 동일 스크립트 `-tclargs 146` |

- Fmax/골든 상세 데이터: `vivado/reports/sweep_summary_v2.md`

## 각 경로가 공통으로 담는 것

각 `build/fir_n43[_v{1,2}_freq_<N>mhz]/` 아래:

```text
vivado/                          Vivado 프로젝트 (합성/구현/타이밍·전력 리포트)
output/bd_fir_dma_wrapper.bit    비트스트림
output/bd_fir_dma_wrapper.xsa    Vitis platform/app 입력
output/BOOT.bin                  SD 부팅 이미지 (Vitis 빌드까지 마친 경우)
```

## 재현 규칙

- clk_wiz 계열 스크립트(`build_bd_fir_dma_clkwiz.tcl`, `build_bd_fir_dma_v2_clkwiz.tcl`)는
  `-tclargs <MHz>`로 받은 주파수를 그대로 디렉터리 이름에 사용한다
  (`build/fir_n43_v{1,2}_freq_<MHz>mhz/`). 같은 인자로 재실행하면 항상 같은 경로가
  `-force`로 덮어써지므로, "이 폴더가 어떤 빌드인지" 수동으로 추적할 필요가 없다.
- 새 골든/fallback을 지정할 때는 **디렉터리를 옮기거나 이름 붙이지 말고**, 이 문서와
  `sweep_summary*.md`에서 어떤 `freq_<N>mhz` 경로를 가리키는지만 갱신한다.
