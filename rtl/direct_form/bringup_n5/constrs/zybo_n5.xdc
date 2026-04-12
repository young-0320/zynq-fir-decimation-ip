## Zybo Z7 bring-up constraints for top_zybo_bringup_n5
## Clock: direct use of the board 125 MHz system clock
## Button: btn[0] used as active-high reset button
## LEDs:
##   led[0] = running
##   led[1] = done
##   led[2] = pass
##   led[3] = fail

set_property -dict { PACKAGE_PIN K17   IOSTANDARD LVCMOS33 } [get_ports { clk }]; # IO_L12P_T1_MRCC_35 Sch=sysclk
create_clock -add -name sys_clk_pin -period 8.00 -waveform {0 4} [get_ports { clk }];

set_property -dict { PACKAGE_PIN K18   IOSTANDARD LVCMOS33 } [get_ports { reset_btn }]; # IO_L12N_T1_MRCC_35 Sch=btn[0]

set_property -dict { PACKAGE_PIN M14   IOSTANDARD LVCMOS33 } [get_ports { led[0] }]; # IO_L23P_T3_35 Sch=led[0]
set_property -dict { PACKAGE_PIN M15   IOSTANDARD LVCMOS33 } [get_ports { led[1] }]; # IO_L23N_T3_35 Sch=led[1]
set_property -dict { PACKAGE_PIN G14   IOSTANDARD LVCMOS33 } [get_ports { led[2] }]; # IO_0_35 Sch=led[2]
set_property -dict { PACKAGE_PIN D18   IOSTANDARD LVCMOS33 } [get_ports { led[3] }]; # IO_L3N_T0_DQS_AD1N_35 Sch=led[3]
