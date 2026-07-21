# step7: 산출물 export
write_sdf "$OUT_DIR/${VER}_${PERIOD}.sdf" -skip_backslash true
write_verilog -file "$OUT_DIR/${VER}_${PERIOD}_nitro.v"
report_timing >  "$OUT_DIR/${VER}_${PERIOD}_timing.rpt"
report_design > "$OUT_DIR/${VER}_${PERIOD}_area.rpt"
puts "step7 done — 산출물: $OUT_DIR"
