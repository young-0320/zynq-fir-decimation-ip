# release/ — 배포용 SD Boot 이미지

빌드 없이 바로 보드 데모를 돌릴 수 있도록 검증된 BOOT.bin을 정식 추적한다.
(그 외 빌드 산출물은 전부 `build/` 아래 git 미추적 — `docs/build_artifacts.md`)

| 경로 | 구성 | 비고 |
| --- | --- | --- |
| `v2_145mhz/BOOT.bin` | v2 코어(4-stage) @ 145 MHz | **기본 권장** — 전력 실측·데모에 사용된 검증 이미지 |
| `v1_115mhz/BOOT.bin` | v1 코어(3-stage) @ 115 MHz | v1 실측 검증 이미지 |

사용법: 원하는 BOOT.bin을 FAT32 SD 카드 **루트에 `BOOT.bin` 이름 그대로** 복사 →
Zybo Z7-20 부트 점퍼 SD 설정 → 전원 인가 → UART(115200)에 `READY FIR` 출력 확인.
이후 절차는 `docs/getting_started.md` 참고.

재현: `vivado/fir_n43/build_bd_fir_dma_v2_clkwiz.tcl -tclargs 145` (v2) /
`build_bd_fir_dma_clkwiz.tcl -tclargs 115` (v1) → `vitis/fir_n43/rebuild_boot_image.sh`.
소속 커밋·넷리스트 이력은 `docs/build_artifacts.md`.

*English*: Pre-built, board-verified SD boot images. Copy one `BOOT.bin` to the root of
a FAT32 SD card, set the Zybo Z7-20 boot jumper to SD, power on, and wait for
`READY FIR` on UART (115200 baud). `v2_145mhz` is the recommended default.
