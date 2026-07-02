# bd_clkwiz_overlay.tcl  (주파수 파라미터화)
# 목적: PS7 하드 PLL이 정수 분주로 못 만드는 주파수(120/130/140/145/148/150 …)를
#       Clocking Wizard(MMCM)로 정확히 합성해 PL 전체를 그 클럭으로 재구동한다.
#       (PS achievable 주파수 90.9/100/111.1/125/142.86 은 clk_wiz 불필요 — PS PLL로 실제 생성)
#
# 사용: build 스크립트에서 이 파일 source 전에 CLKWIZ_FREQ_MHZ 변수를 설정한다.
#       (미설정 시 130 MHz로 기본 동작)
# 구성: PS FCLK_CLK0(100 MHz) → MMCM 입력, clk_out1 = 목표 주파수, PL 전체 구동.
#       MMCM locked → proc_sys_reset dcm_locked.
# 배선 근거: bd_fir_dma.tcl:633-645 (FCLK_CLK0 net의 소비 핀 12개, axi_mem_intercon/ACLK 포함)

if {![info exists CLKWIZ_FREQ_MHZ]} { set CLKWIZ_FREQ_MHZ 130 }

current_bd_design bd_fir_dma
set ps processing_system7_0

# 1) PS FCLK0을 clk_wiz 기준 입력용 100 MHz로 설정
set_property -dict [list \
  CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100} \
  CONFIG.PCW_CLK0_FREQ {100000000} \
] [get_bd_cells $ps]

# 2) Clocking Wizard: 100 MHz → CLKWIZ_FREQ_MHZ
#    PRIM_SOURCE=Global_buffer : 입력이 이미 PS 내부 BUFG(FCLK)에서 오므로 IBUF 삽입 방지
create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz clk_wiz_0
set_property -dict [list \
  CONFIG.PRIM_SOURCE {Global_buffer} \
  CONFIG.PRIM_IN_FREQ {100.000} \
  CONFIG.CLKOUT1_REQUESTED_OUT_FREQ [format %.3f $CLKWIZ_FREQ_MHZ] \
  CONFIG.USE_LOCKED {true} \
  CONFIG.USE_RESET {false} \
] [get_bd_cells clk_wiz_0]

# 3) 클럭 트리 재배선: 기존 FCLK0 분배 net 삭제 후 clk_wiz 출력으로 재소싱
delete_bd_objs [get_bd_nets processing_system7_0_FCLK_CLK0]
connect_bd_net [get_bd_pins $ps/FCLK_CLK0] [get_bd_pins clk_wiz_0/clk_in1]
connect_bd_net [get_bd_pins clk_wiz_0/clk_out1] \
  [get_bd_pins $ps/M_AXI_GP0_ACLK] \
  [get_bd_pins axi_smc/aclk] \
  [get_bd_pins axi_dma_0/s_axi_lite_aclk] \
  [get_bd_pins rst_ps7_0_100M/slowest_sync_clk] \
  [get_bd_pins axi_dma_0/m_axi_mm2s_aclk] \
  [get_bd_pins axi_mem_intercon/S00_ACLK] \
  [get_bd_pins $ps/S_AXI_HP0_ACLK] \
  [get_bd_pins axi_mem_intercon/M00_ACLK] \
  [get_bd_pins axi_mem_intercon/ACLK] \
  [get_bd_pins axi_dma_0/m_axi_s2mm_aclk] \
  [get_bd_pins axi_mem_intercon/S01_ACLK] \
  [get_bd_pins fir_decimator_n43_ax_0/aclk]

# 4) MMCM lock을 리셋 시퀀서에 연결 (PLL 안정 후 리셋 해제)
connect_bd_net [get_bd_pins clk_wiz_0/locked] [get_bd_pins rst_ps7_0_100M/dcm_locked]

regenerate_bd_layout
validate_bd_design
save_bd_design
puts "=== clk_wiz overlay applied: CLKOUT1 requested = ${CLKWIZ_FREQ_MHZ} MHz ==="
