# build_bd_fir_dma_smoke.tcl
# Usage: vivado -mode batch -source vivado/build_bd_fir_dma_smoke.tcl
# Run from repo root
#
# Purpose:
#   Build a debug variant of the PS + AXI DMA block design where the FIR
#   wrapper is replaced by rtl/debug/axis_dma_smoke_test.v.
#
# Outputs:
#   build/output/bd_fir_dma_smoke_wrapper.xsa
#   build/output/bd_fir_dma_smoke_wrapper.bit

set REPO_ROOT [file normalize [file dirname [file dirname [info script]]]]
set BOARD_DIR [file join $REPO_ROOT "boards"]
set BUILD_DIR $REPO_ROOT/build/vivado_smoke
set OUT_DIR   $REPO_ROOT/build/output
set PROJ_NAME fir_dma_smoke
set PART      xc7z020clg400-1
set BOARD     digilentinc.com:zybo-z7-20:part0:1.1

file mkdir $OUT_DIR
set_param board.repoPaths [list $BOARD_DIR]

create_project $PROJ_NAME $BUILD_DIR -part $PART -force
set_property target_language Verilog [current_project]

if {[catch {set_property board_part $BOARD [current_project]}]} {
    error "ERROR: Board part $BOARD not found in $BOARD_DIR!"
}

# Module Reference source for the debug AXI-Stream wrapper.
add_files [list \
    $REPO_ROOT/rtl/debug/axis_dma_smoke_test.v \
]
update_compile_order -fileset sources_1

source $REPO_ROOT/vivado/bd_fir_dma_smoke.tcl

set wrapper [make_wrapper -files [get_files bd_fir_dma_smoke.bd] -top]
add_files -norecurse $wrapper
set_property top bd_fir_dma_smoke_wrapper [current_fileset]
update_compile_order -fileset sources_1

launch_runs synth_1 -jobs 4
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] != "100%"} {
    error "Synthesis failed"
}

launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] != "100%"} {
    error "Implementation failed"
}

open_run impl_1

report_timing_summary \
    -file $BUILD_DIR/${PROJ_NAME}_timing_summary.rpt \
    -warn_on_violation

report_utilization \
    -file $BUILD_DIR/${PROJ_NAME}_utilization.rpt

puts ""
puts "=== WNS / TNS ==="
set wns [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]]
puts "WNS = $wns ns"

set XSA      $OUT_DIR/bd_fir_dma_smoke_wrapper.xsa
set BIT_IMPL $BUILD_DIR/${PROJ_NAME}.runs/impl_1/bd_fir_dma_smoke_wrapper.bit
set BIT_OUT  $OUT_DIR/bd_fir_dma_smoke_wrapper.bit

write_hw_platform -fixed -include_bit -force -file $XSA

if {![file exists $BIT_IMPL]} {
    error "Bitstream not found: $BIT_IMPL"
}
file copy -force $BIT_IMPL $BIT_OUT

puts ""
puts "=== DMA smoke-test build complete ==="
puts "Bitstream: $BIT_OUT"
puts "Impl bit:  $BIT_IMPL"
puts "XSA:       $XSA"
puts ""
puts "Next: vitis/rebuild_boot_image.sh --bit build/output/bd_fir_dma_smoke_wrapper.bit --boot-out build/output/BOOT_smoke.bin --boot-tag SMOKE"

close_project
