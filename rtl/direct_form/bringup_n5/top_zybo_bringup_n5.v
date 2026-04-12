`timescale 1ns / 1ps
`default_nettype none

module top_zybo_bringup_n5 #(
    parameter integer RESET_DEBOUNCE_COUNT_MAX = 32'd1_250_000,
    parameter integer POWER_ON_RESET_CYCLES    = 32'd16,
    parameter integer SOURCE_INPUT_LEN         = 8192,
    parameter integer SOURCE_FLUSH_LEN         = 4,
    parameter SOURCE_MEM_FILE = "input_q15.hex",
    parameter integer CHECKER_EXPECTED_LEN     = 4098,
    parameter integer CHECKER_DRAIN_TIMEOUT    = 64,
    parameter CHECKER_MEM_FILE = "expected_decim_q15.hex"
) (
    input  wire       clk,
    input  wire       reset_btn,
    output wire [3:0] led
);

    wire               rst;
    wire               source_valid;
    wire signed [15:0] source_sample;
    wire               source_running;
    wire               source_done;
    wire               dut_out_valid;
    wire signed [15:0] dut_out_sample;
    wire               checker_done;
    wire               checker_pass;
    wire               checker_fail;
    wire               checker_mismatch_seen;
    wire               demo_running;

    reset_conditioner #(
        .DEBOUNCE_COUNT_MAX(RESET_DEBOUNCE_COUNT_MAX),
        .POWER_ON_RESET_CYCLES(POWER_ON_RESET_CYCLES),
        .BUTTON_ACTIVE_HIGH(1)
    ) u_reset_conditioner (
        .clk(clk),
        .btn_in(reset_btn),
        .rst(rst)
    );

    bringup_vector_source #(
        .INPUT_LEN(SOURCE_INPUT_LEN),
        .FLUSH_LEN(SOURCE_FLUSH_LEN),
        .MEM_FILE(SOURCE_MEM_FILE)
    ) u_bringup_vector_source (
        .clk(clk),
        .rst(rst),
        .out_valid(source_valid),
        .out_sample(source_sample),
        .running(source_running),
        .done(source_done)
    );

    fir_decimator_direct_n5_top u_fir_decimator_direct_n5_top (
        .clk(clk),
        .rst(rst),
        .in_valid(source_valid),
        .in_sample(source_sample),
        .out_valid(dut_out_valid),
        .out_sample(dut_out_sample)
    );

    bringup_output_checker #(
        .EXPECTED_LEN(CHECKER_EXPECTED_LEN),
        .DRAIN_TIMEOUT(CHECKER_DRAIN_TIMEOUT),
        .MEM_FILE(CHECKER_MEM_FILE)
    ) u_bringup_output_checker (
        .clk(clk),
        .rst(rst),
        .source_done(source_done),
        .in_valid(dut_out_valid),
        .in_sample(dut_out_sample),
        .done(checker_done),
        .pass(checker_pass),
        .fail(checker_fail),
        .mismatch_seen(checker_mismatch_seen)
    );

    assign demo_running = (~rst) & (~checker_done);

    assign led[0] = demo_running;
    assign led[1] = checker_done;
    assign led[2] = checker_pass;
    assign led[3] = checker_fail;

endmodule

`default_nettype wire
