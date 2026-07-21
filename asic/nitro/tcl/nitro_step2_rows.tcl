# step2: rows (수업 pause 지점)
create_rows -partition $TOP_MODULE -core_site CORE -orient north -start_from core -gap 50a -xl_margin 0a -yb_margin 0a -xr_margin 0a -yt_margin 0a
puts "step2 done — 확인 후: source $S/nitro_step3_cfg.tcl"
