# build_bd_fir_dma.tcl
# Usage: vivado -mode batch -source vivado/build_bd_fir_dma.tcl
# Run from repo root
#
# 사전 조건: Digilent Zybo Z7-20 보드 파일 설치
#   $XILINX_VIVADO/data/boards/ 또는 ~/.Xilinx/Vivado/ 아래에 있어야 함
#   없으면 board_part 설정 생략 — PS DDR 설정이 BD에 이미 포함되어 있어 재현 가능
#
# 산출물:
#   build/output/bd_fir_dma_wrapper.xsa  ← vitis/build_fir_decimator_demo.tcl 입력
#   build/vivado/fir_decimator_trans_n43.runs/impl_1/bd_fir_dma_wrapper.bit

set REPO_ROOT [file normalize [file dirname [file dirname [info script]]]]
set BOARD_DIR [file join $REPO_ROOT "boards"]
set BUILD_DIR $REPO_ROOT/build/vivado
set OUT_DIR   $REPO_ROOT/build/output
set PROJ_NAME fir_decimator_trans_n43
set PART      xc7z020clg400-1
set BOARD     digilentinc.com:zybo-z7-20:part0:1.1

# -----------------------------------------------------------------------
# 프로젝트 생성
# -----------------------------------------------------------------------
file mkdir $OUT_DIR

# 보드 경로 설정
set_param board.repoPaths [list $BOARD_DIR]
# -----------------------------------------------------------------------


create_project $PROJ_NAME $BUILD_DIR -part $PART -force


set_property target_language Verilog [current_project]

# 유력한 버그 의심 지점------------------------------------------------------
# if {[catch {set_property board_part $BOARD [current_project]}]} {
#     puts "WARNING: board_part '$BOARD' not found — 보드 파일 미설치."
#     puts "         BD 안의 PS 설정은 bd_fir_dma.tcl에 내장되어 있어 재현 가능."
# } 
# if {[catch {set_property board_part $BOARD [current_project]}]} {
#     puts "****************************************************************"
#     puts " FATAL ERROR: Board part '$BOARD' not found!"
#     puts " Check path: $BOARD_REPO"
#     puts "****************************************************************"
#     error "Build halted due to missing board file."
# }

if {[catch {set_property board_part $BOARD [current_project]}]} {
    error "ERROR: Board part $BOARD not found in $BOARD_DIR!"
}
# -----------------------------------------------------------------------



# -----------------------------------------------------------------------
# RTL 소스 추가 (Module Reference — bd_fir_dma.tcl source 전에 필요)
# -----------------------------------------------------------------------
add_files [list \
    $REPO_ROOT/rtl/transposed_form/n43/fir_n43.v \
    $REPO_ROOT/rtl/transposed_form/n43/fir_decimator_n43.v \
    $REPO_ROOT/rtl/transposed_form/n43/fir_decimator_n43_axis.v \
    $REPO_ROOT/rtl/transposed_form/decimator_m2_phase0.v \
]

update_compile_order -fileset sources_1

# -----------------------------------------------------------------------
# Block Design 재생성
# -----------------------------------------------------------------------
source $REPO_ROOT/vivado/bd_fir_dma.tcl

# -----------------------------------------------------------------------
# BD wrapper 생성 및 top 설정
# -----------------------------------------------------------------------
set wrapper [make_wrapper -files [get_files bd_fir_dma.bd] -top]
add_files -norecurse $wrapper
set_property top bd_fir_dma_wrapper [current_fileset]
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
# 구현 + 비트스트림
# -----------------------------------------------------------------------
launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] != "100%"} {
    error "Implementation failed"
}

# -----------------------------------------------------------------------
# 타이밍 / 리소스 리포트
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

# -----------------------------------------------------------------------
# XSA 내보내기 (비트스트림 포함, Vitis 입력)
# -----------------------------------------------------------------------
set XSA $OUT_DIR/bd_fir_dma_wrapper.xsa

write_hw_platform -fixed -include_bit -force -file $XSA

puts ""
puts "=== 빌드 완료 ==="
puts "비트스트림: $BUILD_DIR/${PROJ_NAME}.runs/impl_1/bd_fir_dma_wrapper.bit"
puts "XSA:        $XSA"
puts ""
puts "다음 단계: xsct vitis/build_fir_decimator_demo.tcl"

close_project
