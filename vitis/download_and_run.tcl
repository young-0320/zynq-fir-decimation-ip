# download_and_run.tcl
# Usage: xsdb vitis/download_and_run.tcl  (repo root에서 실행)
#
# 동작: Zybo Z7-20에 비트스트림 프로그래밍 + ELF 다운로드 후 실행

set REPO_ROOT [file normalize [file dirname [file dirname [info script]]]]
set BIT $REPO_ROOT/build/vivado/fir_decimator_trans_n43.runs/impl_1/bd_fir_dma_wrapper.bit
set ELF $REPO_ROOT/build/output/fir_decimator_demo.elf

connect

targets -set -filter {name =~ "APU*"}
fpga $BIT

targets -set -filter {name =~ "*A9*#0"}
rst -processor
dow $ELF
con

puts ""
puts "=== 다운로드 완료 ==="
puts "DONE LED 점등 확인 후 minicom -D /dev/ttyUSB1 -b 115200 으로 UART 접속"
