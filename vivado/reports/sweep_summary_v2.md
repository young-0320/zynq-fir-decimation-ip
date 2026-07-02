# FIR N43 (v2) Clock Sweep — clk_wiz 정밀 스윕

- 생성일: 2026-07-02
- 보드: Zybo Z7-20 (xc7z020clg400-1)
- 설계: N=43 taps, M=2, transposed form — **v2 (`fir_n43_v2.v`, 4-stage 파이프라인)**
- v1(`fir_n43.v`, 3-stage) 대비: round를 별도 stage로 분리, latency 3→4 cycle
- 방법: Clocking Wizard(MMCM)로 PL 전체를 목표 주파수로 **정확히 분주** (요청 = 실제, 오차 0).
  빌드: `vivado/fir_n43/build_bd_fir_dma_v2_clkwiz.tcl -tclargs <MHz>`

## 결과 (target = actual)

| actual_mhz | wns_ns | timing_pass | lut  | dsp48 | total_power_w |
| ---------- | ------ | ----------- | ---- | ----- | ------------- |
| 120.000    | +0.655 | true        | 4550 | 16    | 1.697         |
| 130.000    | +0.563 | true        | 4549 | 16    | 1.701         |
| 140.000    | +0.069 | true        | 4542 | 16    | 1.703         |
| 145.000    | +0.129 | true        | 4556 | 16    | 1.705         |
| 146.000    | +0.022 | true        | 4554 | 16    | 1.701         |
| 147.000    | -0.102 | false       | 4553 | 16    | 1.701         |
| 148.000    | -0.021 | false       | 4556 | 16    | 1.707         |
| 150.000    | -0.012 | false       | 4567 | 16    | 1.706         |

> 130.000 MHz는 **골든 배포 빌드**(`build/fir_n43_v2_clkwiz/`, bit/xsa 보존).

## Fmax

**확정 Fmax: 146 MHz** (WNS ≥ 0인 최대 실제 주파수)

- last PASS: **146.000 MHz** (WNS +0.022) / first FAIL: 147.000 MHz (WNS -0.102)
- 경계 해상도 1 MHz. v1(116 MHz) 대비 **+30 MHz**.

## 크리티컬 패스 — 상한을 정하는 건 FIR이 아니라 AXI DMA IP

147 MHz FAIL 경계의 worst 경로:
```
Source:      axi_dma_0/.../I_S2MM_REALIGNER/.../sig_max_first_increment_reg[1]
Destination: axi_dma_0/.../I_S2MM_REALIGNER/.../sig_btt_eq_0_reg
```
Xilinx **AXI DMA IP 내부**(S2MM realigner의 byte-count 로직)다. 경계 부근에서는 이 DMA 경로와
AXIS 래퍼 경로가 비슷하게 임계여서 배치에 따라 둘 중 하나가 worst가 되지만, **어느 쪽도 FIR
코어의 곱셈/누산/round 데이터패스가 아니다.**

**의미:** v2의 4-stage 분할이 v1 round CARRY4 병목을 제거하면서, 이제 전체 설계 상한은
FIR이 아니라 DMA IP가 결정한다. FIR 추가 개선(round 재분할 등)은 Fmax를 더 올리지 못한다.

## 비고

- DSP48 16개로 전 주파수 동일. LUT ~4542–4567 (clk_wiz MMCM/BUFG 포함분).
- 125.000 MHz는 PS7 하드 PLL ÷8로 정확히 만들어지는 native 지점(clk_wiz 불필요):
  base 빌드 WNS +0.261 PASS, LUT 4549, 1.572 W (MMCM 없어 전력 낮음).
- v1 상세 스윕/Fmax는 `sweep_summary.md` 참조.
