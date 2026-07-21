namespace eval config {
    global input

    # [수정 필요] 학교 서버에 clone한 이 리포의 절대 경로로 변경
    set REPO_ROOT {/mnt/NewHDD/home/ddl2026/ddl2026_2023104135/zynq-fir-decimation-ip}

    # =========================================================
    # FIR v2 (파이프라인 분할판, FPGA Fmax 146MHz)
    set TOP_MODULE {fir_n43_v2}
    # =========================================================

    set input(verilog_files)                  [list "$REPO_ROOT/rtl/transposed_form/n43/fir_n43_v2.v"]
    set input(system_verilog)                 {true}
    set input(verilog_dirs)                   [list "$REPO_ROOT/rtl/transposed_form/n43"]
    set input(verilog_defs)                   {}
    set input(top_module)                     $TOP_MODULE

    set input(lib_files)                      {{default {/mnt/NewHDD/home/vlsiadmin/TannerEDA/TannerTools_v2021.2/Process/Generic_250nm/Generic_250nm_LogicGates/Liberty/TANNER_TT_2P50V_25C.lib}}}
    set input(target_library)                 {default}
    set input(lef_files)                      {/mnt/NewHDD/home/vlsiadmin/TannerEDA/TannerTools_v2021.2/Process/Generic_250nm/Generic_250nm_LogicGates/Generic250nm_StdCells.lef}
    set input(tech_file)                      {/mnt/NewHDD/home/vlsiadmin/TannerEDA/TannerTools_v2021.2/Process/Generic_250nm/Generic_250nm_LogicGates/Generic250nm_tech.lef}

    set input(sdc_files)                      [list "$REPO_ROOT/asic/oasys/clk.sdc"]
    set input(def_files)                      {}
    set input(power_files)                    {}
    set input(vcd_file)                       {}
    set input(vcd_scope)                      {}
    set input(sa_probability)                 {}
    set input(sa_togg_perc)                   {}
    set input(sa_togg_rate)                   {}

    set input(clock_gating_minimum_bitwidth)  {4}
    set input(clock_gating_sequential_cell)   {none}
    set input(clock_gating_control_point)     {}
    set input(clock_gating_control_port)      {}
    set input(clock_gating_observation_point) {false}

    set input(comb_vt_target_library)         {default}
    set input(high_vt_target_library)         {default}
    set input(flow_synthesize)                {true}
    set input(synthesize_map_to_scan)         {false}
    set input(synthesize_gate_clock)          {false}
    set input(flow_optimize)                  {true}
    set input(optimize_leakage)               {false}
    set input(optimize_area)                  {false}
    set input(flow_refine)                    {false}
    set input(pre_synthesize)                 {}
    set input(pre_optimize)                   {}
}
