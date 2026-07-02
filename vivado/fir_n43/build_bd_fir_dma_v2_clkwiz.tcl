# build_bd_fir_dma.tcl
# Usage: vivado -mode batch -source vivado/fir_n43/build_bd_fir_dma.tcl
# Run from repo root, or from build/fir_n43/vivado when isolating Vivado logs
#
# 사전 조건: Digilent Zybo Z7-20 보드 파일 설치
#   $XILINX_VIVADO/data/boards/ 또는 ~/.Xilinx/Vivado/ 아래에 있어야 함
#   없으면 board_part 설정 생략 — PS DDR 설정이 BD에 이미 포함되어 있어 재현 가능
#
# 산출물:
#   build/fir_n43/output/bd_fir_dma_wrapper.xsa  <- Vitis platform/app input
#   build/fir_n43/output/bd_fir_dma_wrapper.bit  <- BOOT image input

# 목표 주파수(MHz)는 -tclargs 로 전달 (미지정 시 130)
#   예: vivado -mode batch -source build_bd_fir_dma_v2_clkwiz.tcl -tclargs 140
if {[llength $argv] >= 1} { set CLKWIZ_FREQ_MHZ [lindex $argv 0] } else { set CLKWIZ_FREQ_MHZ 130 }

set SCRIPT_DIR [file normalize [file dirname [info script]]]
set REPO_ROOT  [file normalize [file join $SCRIPT_DIR ../..]]
set BOARD_DIR [file join $REPO_ROOT "boards"]
# 재현성: 주파수마다 고유 디렉터리 자동 생성. 같은 -tclargs로 재실행하면 항상 같은 경로가
# 나오므로 별도 수동 복사/이름 관리가 필요 없다. -force로 해당 주파수 디렉터리만 덮어씀.
set BUILD_DIR $REPO_ROOT/build/fir_n43_v2_freq_${CLKWIZ_FREQ_MHZ}mhz/vivado
set VITIS_DIR $REPO_ROOT/build/fir_n43_v2_freq_${CLKWIZ_FREQ_MHZ}mhz/vitis
set OUT_DIR   $REPO_ROOT/build/fir_n43_v2_freq_${CLKWIZ_FREQ_MHZ}mhz/output
set PROJ_NAME fir_decimator_trans_n43
set PART      xc7z020clg400-1
set BOARD     digilentinc.com:zybo-z7-20:part0:1.1

# -----------------------------------------------------------------------
# 프로젝트 생성
# -----------------------------------------------------------------------
file mkdir $BUILD_DIR
file mkdir $VITIS_DIR
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
    $REPO_ROOT/rtl/transposed_form/n43/fir_n43_v2.v \
    $REPO_ROOT/rtl/transposed_form/n43/fir_decimator_n43_v2.v \
    $REPO_ROOT/rtl/transposed_form/n43/fir_decimator_n43_axis_v2.v \
    $REPO_ROOT/rtl/transposed_form/decimator_m2_phase0.v \
]

update_compile_order -fileset sources_1

# -----------------------------------------------------------------------
# Block Design 재생성
# -----------------------------------------------------------------------
source $SCRIPT_DIR/bd_fir_dma_v2.tcl

# -----------------------------------------------------------------------
# clk_wiz(MMCM) 삽입: PS FCLK0(100MHz) → CLKWIZ_FREQ_MHZ 로 PL 전체 재구동
# -----------------------------------------------------------------------
source $SCRIPT_DIR/bd_clkwiz_overlay.tcl

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

report_power \
    -file $BUILD_DIR/${PROJ_NAME}_power.rpt

puts ""
puts "=== WNS / TNS ==="
set wns [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]]
puts "WNS = $wns ns"

# -----------------------------------------------------------------------
# XSA 내보내기 (비트스트림 포함, Vitis 입력)
# -----------------------------------------------------------------------
set XSA      $OUT_DIR/bd_fir_dma_wrapper.xsa
set BIT_IMPL $BUILD_DIR/${PROJ_NAME}.runs/impl_1/bd_fir_dma_wrapper.bit
set BIT_OUT  $OUT_DIR/bd_fir_dma_wrapper.bit

write_hw_platform -fixed -include_bit -force -file $XSA

if {![file exists $BIT_IMPL]} {
    error "Bitstream not found: $BIT_IMPL"
}
file copy -force $BIT_IMPL $BIT_OUT

puts ""
puts "=== 빌드 완료 ==="
puts "비트스트림: $BIT_OUT"
puts "구현 결과:   $BIT_IMPL"
puts "XSA:        $XSA"
puts ""
puts "다음 단계(전체 Vitis 재생성): vitis -s vitis/fir_n43/build_fir_decimator_demo.py"
puts "그 다음: bootgen -arch zynq -image build/fir_n43/output/fir_decimator_demo.bif -o build/fir_n43/output/BOOT.bin -w on"
puts "기존 Vitis workspace 재사용 시: vitis/fir_n43/rebuild_boot_image.sh --boot-tag FIR"

close_project
