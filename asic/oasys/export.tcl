# 합성 완료 후 Oasys 콘솔에서 산출물 4종을 한 번에 export하는 스크립트.
#
# 사용법 (합성 끝난 뒤 콘솔에 두 줄):
#   set VER v1; set PERIOD 15000ps
#   source /mnt/NewHDD/home/ddl2026/ddl2026_2023104135/ddl2026_folder/zynq-fir-decimation-ip/asic/oasys/export.tcl
#
# 결과는 asic/oasys/results/$VER/ 아래에 ${VER}_${PERIOD}_* 이름으로 저장된다
# (폴더 자동 생성, 수동 mv 불필요).

set REPO_ROOT {/mnt/NewHDD/home/ddl2026/ddl2026_2023104135/ddl2026_folder/zynq-fir-decimation-ip}

if {![info exists VER] || ![info exists PERIOD]} {
    error "export.tcl: 먼저 'set VER v1; set PERIOD 15000ps' 형식으로 지정할 것"
}

set EXPORT_DIR "$REPO_ROOT/asic/oasys/results/$VER"
file mkdir $EXPORT_DIR

write_verilog "$EXPORT_DIR/${VER}_${PERIOD}_synth.v"
report_timing > "$EXPORT_DIR/${VER}_${PERIOD}_timing.rpt"
report_area > "$EXPORT_DIR/${VER}_${PERIOD}_area.rpt"
report_power -total_only > "$EXPORT_DIR/${VER}_${PERIOD}_power.rpt"

puts "export 완료: $EXPORT_DIR/${VER}_${PERIOD}_*"
