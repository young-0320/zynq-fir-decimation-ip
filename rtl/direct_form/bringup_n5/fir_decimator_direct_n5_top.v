`timescale 1ns / 1ps
`default_nettype none

module fir_decimator_direct_n5_top (
    input  wire               clk,
    input  wire               rst,
    input  wire               in_valid,
    input  wire signed [15:0] in_sample,
    output wire               out_valid,
    output wire signed [15:0] out_sample
);

    wire               fir_out_valid;
    wire signed [15:0] fir_out_sample;

    fir_direct_n5 u_fir_direct_n5 (
        .clk(clk),
        .rst(rst),
        .in_valid(in_valid),
        .in_sample(in_sample),
        .out_valid(fir_out_valid),
        .out_sample(fir_out_sample)
    );

    decimator_m2_phase0 u_decimator_m2_phase0 (
        .clk(clk),
        .rst(rst),
        .in_valid(fir_out_valid),
        .in_sample(fir_out_sample),
        .out_valid(out_valid),
        .out_sample(out_sample)
    );

endmodule

`default_nettype wire
