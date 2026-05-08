# download_and_run.tcl
# Usage: xsdb vitis/download_and_run.tcl  (repo root에서 실행)
#
# 동작: Zybo Z7-20에 비트스트림 프로그래밍 + ELF 다운로드 후 실행

set REPO_ROOT [file normalize [file dirname [file dirname [info script]]]]
set BIT      $REPO_ROOT/build/vivado/fir_decimator_trans_n43.runs/impl_1/bd_fir_dma_wrapper.bit
set ELF      $REPO_ROOT/build/output/fir_decimator_demo.elf
set PS7_INIT $REPO_ROOT/build/vitis/fir_decimator_demo/_ide/psinit/ps7_init.tcl

connect

targets -set -filter {name =~ "APU*"}
fpga $BIT

# ps7_init: Vivado BD에서 자동 생성된 PS7 초기화 스크립트
# DDR 컨트롤러, PLL, MIO 등 PS 전체를 초기화함
# FSBL 없이 JTAG으로 직접 부팅 시 반드시 필요
targets -set -filter {name =~ "*A9*#0"}
rst -processor -clear-registers
source $PS7_INIT
ps7_init
ps7_post_config

dow $ELF
con

puts ""
puts "=== 다운로드 완료 ==="
puts "DONE LED 점등 확인 후 minicom -D /dev/ttyUSB1 -b 115200 으로 UART 접속"
