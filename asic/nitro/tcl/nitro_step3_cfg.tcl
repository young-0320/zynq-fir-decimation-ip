# step3: route config + SDC
config_route_global -category user_defined
config_route_global -name gr_full_timing_update_thresh -value 0.0
read_constraint "$REPO_ROOT/asic/nitro/tcl/${VER}_${PERIOD}.sdc"
puts "step3 done — 다음: source $S/nitro_step4_place.tcl"
