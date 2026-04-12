`timescale 1ns / 1ps
`default_nettype none

module fir_direct_n5 (
    input  wire               clk,
    input  wire               rst,
    input  wire               in_valid,
    input  wire signed [15:0] in_sample,
    output reg                out_valid,
    output reg  signed [15:0] out_sample
);

    localparam signed [15:0] COEFF_0 = 16'sd88;
    localparam signed [15:0] COEFF_1 = 16'sd7069;
    localparam signed [15:0] COEFF_2 = 16'sd18455;
    localparam signed [15:0] COEFF_3 = 16'sd7069;
    localparam signed [15:0] COEFF_4 = 16'sd88;

    localparam signed [47:0] ROUND_BIAS = 48'sd16384;
    localparam signed [47:0] Q15_MAX    = 48'sd32767;
    localparam signed [47:0] Q15_MIN    = -48'sd32768;

    reg signed [15:0] delay_1;
    reg signed [15:0] delay_2;
    reg signed [15:0] delay_3;
    reg signed [15:0] delay_4;

    wire signed [31:0] prod_0;
    wire signed [31:0] prod_1;
    wire signed [31:0] prod_2;
    wire signed [31:0] prod_3;
    wire signed [31:0] prod_4;
    wire signed [47:0] acc_wide;
    wire signed [47:0] rounded_wide;
    wire signed [15:0] saturated_q15;

    assign prod_0 = COEFF_0 * in_sample;
    assign prod_1 = COEFF_1 * delay_1;
    assign prod_2 = COEFF_2 * delay_2;
    assign prod_3 = COEFF_3 * delay_3;
    assign prod_4 = COEFF_4 * delay_4;

    assign acc_wide = {{16{prod_0[31]}}, prod_0}
                    + {{16{prod_1[31]}}, prod_1}
                    + {{16{prod_2[31]}}, prod_2}
                    + {{16{prod_3[31]}}, prod_3}
                    + {{16{prod_4[31]}}, prod_4};

    assign rounded_wide = round_q2_30_to_q1_15(acc_wide);
    assign saturated_q15 = saturate_to_q1_15(rounded_wide);

    function automatic signed [47:0] round_q2_30_to_q1_15;
        input signed [47:0] value;
        reg signed [47:0] magnitude;
        reg signed [47:0] rounded_magnitude;
        begin
            if (value < 0) begin
                magnitude = -value;
            end else begin
                magnitude = value;
            end

            rounded_magnitude = (magnitude + ROUND_BIAS) >>> 15;

            if (value < 0) begin
                round_q2_30_to_q1_15 = -rounded_magnitude;
            end else begin
                round_q2_30_to_q1_15 = rounded_magnitude;
            end
        end
    endfunction

    function automatic signed [15:0] saturate_to_q1_15;
        input signed [47:0] value;
        begin
            if (value > Q15_MAX) begin
                saturate_to_q1_15 = 16'sd32767;
            end else if (value < Q15_MIN) begin
                saturate_to_q1_15 = -16'sd32768;
            end else begin
                saturate_to_q1_15 = value[15:0];
            end
        end
    endfunction

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            delay_1    <= 16'sd0;
            delay_2    <= 16'sd0;
            delay_3    <= 16'sd0;
            delay_4    <= 16'sd0;
            out_valid  <= 1'b0;
            out_sample <= 16'sd0;
        end else begin
            if (in_valid) begin
                delay_4    <= delay_3;
                delay_3    <= delay_2;
                delay_2    <= delay_1;
                delay_1    <= in_sample;
                out_valid  <= 1'b1;
                out_sample <= saturated_q15;
            end else begin
                out_valid <= 1'b0;
            end
        end
    end

endmodule

`default_nettype wire
