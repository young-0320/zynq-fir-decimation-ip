# step0: 라이브러리/netlist 로드 + 변수 정의. 이후 단계는 source $S/nitro_step*.tcl
read_lef /mnt/NewHDD/home/vlsiadmin/TannerEDA/TannerTools_v2021.2/Process/Generic_250nm/Generic_250nm_LogicGates/Generic250nm_tech.lef
read_lef /mnt/NewHDD/home/vlsiadmin/TannerEDA/TannerTools_v2021.2/Process/Generic_250nm/Generic_250nm_LogicGates/Generic250nm_StdCells.lef
read_library /mnt/NewHDD/home/vlsiadmin/TannerEDA/TannerTools_v2021.2/Process/Generic_250nm/Generic_250nm_LogicGates/Liberty/TANNER_TT_2P50V_25C.lib
read_library /mnt/NewHDD/home/vlsiadmin/TannerEDA/TannerTools_v2021.2/Process/Generic_250nm/Generic_250nm_LogicGates/PTF/Generic250nm_typ.ptf
set REPO_ROOT {/mnt/NewHDD/home/ddl2026/ddl2026_2023104135/ddl2026_folder/zynq-fir-decimation-ip}
set VER        {v1}
set PERIOD     {10000ps}
set TOP_MODULE {fir_n43}
set S "$REPO_ROOT/asic/nitro/tcl"
read_verilog "$REPO_ROOT/asic/oasys/results/$VER/${VER}_${PERIOD}_synth.v"
set OUT_DIR "$REPO_ROOT/asic/nitro/results/$VER/$PERIOD"
file mkdir $OUT_DIR
puts "step0 done: $VER $PERIOD — 다음: source $S/nitro_step1_floorplan.tcl"
