# Nitro P&R 에러 원문 기록

P&R 시도(2026-07-21, v1 10000ps) 중 발생한 에러의 원문이다. 중단 판단의 근거로
보존한다 — 맥락과 해석은 `docs/log/47` §4, `../oasys/results/sweep_report.md` §6.

- PLC1020: datapath 매크로가 movable이 아니어서 자동 배치 거부 → 수동 배치로 진행
- SDA101: 수동 배치 후 placer 내부 assertion 크래시 — 칩 면적 확대·재배치 후에도
  동일 지점 재현 (아래 error2/error3)

```text
warning PLC2012: The port 'out_sample[0]' is not fixed.
warning PLC2012: The port 'clk' is not fixed.
warning PLC2012: The port 'out_sample[1]' is not fixed.
warning PLC2012: The port 'out_sample[2]' is not fixed.
warning PLC2012: The port 'out_sample[3]' is not fixed.
warning PLC2012: The port 'out_sample[4]' is not fixed.
warning PLC2012: The port 'out_sample[5]' is not fixed.
warning PLC2012: The port 'out_sample[6]' is not fixed.
warning PLC2012: The port 'out_sample[7]' is not fixed.
warning PLC2012: The port 'out_sample[8]' is not fixed.
error PLC1020: Cannot run macro placement on a design without any movable macros. 
error UI150: Command 'place_timing' execution failed: Global placer failed to complete.. 
info UI: 10 (out of 34) 'PLC2012' messages were displayed
error UI26: Script file '/mnt/NewHDD/home/ddl2026/ddl2026_<user>/ddl2026_folder/zynq-fir-decimation-ip/asic/nitro/tcl/nitro_step1b_macros.tcl' execution failed (and stopped) at line 3 (place_macros -partition $TOP_MODULE). 
error2
error SDA101: internal error has occurred 'grCapFrac <= 1.' at /home/devmgr/work/73777_2020.2.R1/dev/src/pldb/engine/densityboxcontrol.cpp line 245 
error UI150: Command 'place_timing' execution failed. 
error UI26: Script file '/mnt/NewHDD/home/ddl2026/ddl2026_<user>/ddl2026_folder/zynq-fir-decimation-ip/asic/nitro/tcl/nitro_step4.tcl' execution failed (and stopped) at line 2 (run_place_timing -effort high). 
error3
error SDA101: internal error has occurred 'grCapFrac <= 1.' at /home/devmgr/work/73777_2020.2.R1/dev/src/pldb/engine/densityboxcontrol.cpp line 245 
error UI150: Command 'place_timing' execution failed. 
error UI26: Script file '/mnt/NewHDD/home/ddl2026/ddl2026_<user>/ddl2026_folder/zynq-fir-decimation-ip/asic/nitro/tcl/nitro_step4.tcl' execution failed (and stopped) at line 2 (run_place_timing -effort high).
```
