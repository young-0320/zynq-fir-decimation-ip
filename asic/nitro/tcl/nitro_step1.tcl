# step1: chip/floorplan/power/track (pause 전 블록)
# chip 1.4mm x 1.4mm: 셀 면적 1.35mm²(43개 병렬 곱셈기) / util 70% 역산.
# GEMM step2(0.31mm², 630µm 칩)보다 4배 큰 디자인이므로 그보다 커야 함.
create_chip -xl_area 0a -yb_area 0a -xr_area 14000000a -yt_area 14000000a -core_site CORE -xl_margin 0a -yt_margin 0a -orient north -double_backed true -gap 0a
create_floorplan_regions -partition $TOP_MODULE -min_cells 0 -max_cells 1000000000 -min_area_percent 1 -max_area_percent 100 -core_cell_util 70
stack_macros
create_power_domain -domain primary -include_scope true
create_supply_net -net_name vss -domain primary -power_net false
create_supply_net -net_name vdd -domain primary -power_net true
set_domain_supply_net -domain primary -primary_power_net vdd -primary_ground_net vss
create_tracks -layers Metal4 -step 11500a
create_tracks -layers Metal3 -step 13500a
create_tracks -layers Metal2 -step 11500a
create_tracks -layers Metal1 -step 13500a
report_tracks -type preferred
puts "step1 done — 여기서 GUI로 datapath 블럭 36개를 칩 안에 드래그(겹침 없이 고르게, 수업 방식). 완료 후: source $S/nitro_step2.tcl"
