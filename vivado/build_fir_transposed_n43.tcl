# build_fir_transposed_n43.tcl
# Usage: vivado -mode batch -source vivado/build_fir_transposed_n43.tcl
# Run from repo root: /home/young/dev/10_zynq-fir-decimation-ip

set REPO_ROOT [file normalize [file dirname [file dirname [info script]]]]
set BUILD_DIR /mnt/workspace/10_zynq-fir-decimation-ip_build/fir_transposed_n43
set PROJ_NAME fir_transposed_n43
set PART      xc7z020clg400-1
set TOP       fir_decimator_n43

# -----------------------------------------------------------------------
# 프로젝트 생성
# -----------------------------------------------------------------------
create_project $PROJ_NAME $BUILD_DIR -part $PART -force

set_property target_language Verilog [current_project]

# -----------------------------------------------------------------------
# 소스 추가
# -----------------------------------------------------------------------
add_files [list \
    $REPO_ROOT/rtl/transposed_form/n43/fir_n43.v \
    $REPO_ROOT/rtl/transposed_form/n43/fir_decimator_n43.v \
    $REPO_ROOT/rtl/transposed_form/decimator_m2_phase0.v \
]

add_files -fileset constrs_1 \
    $REPO_ROOT/rtl/transposed_form/n43/constrs/zybo_n43.xdc

set_property top $TOP [current_fileset]
update_compile_order -fileset sources_1

# -----------------------------------------------------------------------
# 합성
# -----------------------------------------------------------------------
launch_runs synth_1 -jobs 4
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] != "100%"} {
    error "Synthesis failed"
}

# -----------------------------------------------------------------------
# 구현
# -----------------------------------------------------------------------
launch_runs impl_1 -jobs 4
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] != "100%"} {
    error "Implementation failed"
}

# -----------------------------------------------------------------------
# 리포트
# -----------------------------------------------------------------------
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

puts ""
puts "=== DSP48 usage ==="
set dsp_count [llength [get_cells -hierarchical -filter {REF_NAME =~ DSP48*}]]
puts "DSP48 used = $dsp_count  (expected 16)"
puts ""
puts "Timing report:      $BUILD_DIR/${PROJ_NAME}_timing_summary.rpt"
puts "Utilization report: $BUILD_DIR/${PROJ_NAME}_utilization.rpt"

close_project
