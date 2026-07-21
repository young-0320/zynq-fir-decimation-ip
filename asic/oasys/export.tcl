# 합성 산출물 4종 export 함수 정의.
#
# 사용법: Oasys 세션 시작 때 한 번만
#   source /mnt/NewHDD/home/ddl2026/ddl2026_2023104135/ddl2026_folder/zynq-fir-decimation-ip/asic/oasys/export.tcl
# 이후 각 합성이 끝날 때마다
#   ex v1 12000ps
#   ex v2 12000ps
#
# 결과는 asic/oasys/results/<ver>/ 아래 <ver>_<period>_* 로 저장 (폴더 자동 생성).

proc ex {ver period} {
    set REPO_ROOT {/mnt/NewHDD/home/ddl2026/ddl2026_2023104135/ddl2026_folder/zynq-fir-decimation-ip}
    set dir "$REPO_ROOT/asic/oasys/results/$ver"
    file mkdir $dir
    write_verilog "$dir/${ver}_${period}_synth.v"
    report_timing > "$dir/${ver}_${period}_timing.rpt"
    report_area > "$dir/${ver}_${period}_area.rpt"
    report_power -total_only > "$dir/${ver}_${period}_power.rpt"
    puts "export 완료: $dir/${ver}_${period}_*"
}
