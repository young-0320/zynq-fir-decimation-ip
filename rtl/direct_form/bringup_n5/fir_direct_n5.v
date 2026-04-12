`timescale 1ns / 1ps
`default_nettype none

module fir_direct_n5 (
    input  wire               clk,
    input  wire               rst,
    input  wire               in_valid,
    input  wire signed [15:0] in_sample,
    output reg                out_valid,
    output reg signed  [15:0] out_sample
);

  localparam signed [15:0] COEFF_0 = 16'sd88;
  localparam signed [15:0] COEFF_1 = 16'sd7069;
  localparam signed [15:0] COEFF_2 = 16'sd18455;
  localparam signed [15:0] COEFF_3 = 16'sd7069;
  localparam signed [15:0] COEFF_4 = 16'sd88;

  localparam signed [47:0] ROUND_BIAS = 48'sd16384;
  localparam signed [47:0] Q15_MAX = 48'sd32767;
  localparam signed [47:0] Q15_MIN = -48'sd32768;

  reg signed  [15:0] sample_0;
  reg signed  [15:0] delay_1;
  reg signed  [15:0] delay_2;
  reg signed  [15:0] delay_3;
  reg signed  [15:0] delay_4;
  reg                tap_valid;
  reg signed  [47:0] prod_0_reg;
  reg signed  [47:0] prod_1_reg;
  reg signed  [47:0] prod_2_reg;
  reg signed  [47:0] prod_3_reg;
  reg signed  [47:0] prod_4_reg;
  reg                prod_valid;
  reg signed  [47:0] acc_reg;
  reg                acc_valid;
  reg signed  [47:0] round_reg;
  reg                round_valid;

  wire signed [31:0] prod_0;
  wire signed [31:0] prod_1;
  wire signed [31:0] prod_2;
  wire signed [31:0] prod_3;
  wire signed [31:0] prod_4;
  wire signed [47:0] prod_0_wide;
  wire signed [47:0] prod_1_wide;
  wire signed [47:0] prod_2_wide;
  wire signed [47:0] prod_3_wide;
  wire signed [47:0] prod_4_wide;
  wire signed [47:0] acc_wide;
  wire signed [47:0] rounded_wide;
  wire signed [15:0] saturated_q15;

  assign prod_0 = COEFF_0 * sample_0;
  assign prod_1 = COEFF_1 * delay_1;
  assign prod_2 = COEFF_2 * delay_2;
  assign prod_3 = COEFF_3 * delay_3;
  assign prod_4 = COEFF_4 * delay_4;

  assign prod_0_wide = {{16{prod_0[31]}}, prod_0};
  assign prod_1_wide = {{16{prod_1[31]}}, prod_1};
  assign prod_2_wide = {{16{prod_2[31]}}, prod_2};
  assign prod_3_wide = {{16{prod_3[31]}}, prod_3};
  assign prod_4_wide = {{16{prod_4[31]}}, prod_4};

  assign acc_wide = prod_0_reg + prod_1_reg + prod_2_reg + prod_3_reg + prod_4_reg;

  assign rounded_wide = round_q2_30_to_q1_15(acc_reg);
  assign saturated_q15 = saturate_to_q1_15(round_reg);

  function automatic signed [47:0] round_q2_30_to_q1_15;
    input signed [47:0] value;
    reg signed [47:0] magnitude;
    reg signed [47:0] rounded_magnitude;
    begin
      // In this N=5 bring-up FIR, the reachable accumulator range is far
      // smaller than the 48-bit signed limit, so abs(value) never sees
      // the most-negative 48-bit corner case.
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
      sample_0   <= 16'sd0;
      delay_1    <= 16'sd0;
      delay_2    <= 16'sd0;
      delay_3    <= 16'sd0;
      delay_4    <= 16'sd0;
      tap_valid  <= 1'b0;
      prod_0_reg <= 48'sd0;
      prod_1_reg <= 48'sd0;
      prod_2_reg <= 48'sd0;
      prod_3_reg <= 48'sd0;
      prod_4_reg <= 48'sd0;
      prod_valid <= 1'b0;
      acc_reg    <= 48'sd0;
      acc_valid  <= 1'b0;
      round_reg  <= 48'sd0;
      round_valid <= 1'b0;
      out_valid  <= 1'b0;
      out_sample <= 16'sd0;
    end else begin
      if (round_valid) begin
        out_valid  <= 1'b1;
        out_sample <= saturated_q15;
      end else begin
        out_valid <= 1'b0;
      end

      if (prod_valid) begin
        acc_reg   <= acc_wide;
        acc_valid <= 1'b1;
      end else begin
        acc_valid <= 1'b0;
      end

      if (acc_valid) begin
        round_reg   <= rounded_wide;
        round_valid <= 1'b1;
      end else begin
        round_valid <= 1'b0;
      end

      if (tap_valid) begin
        prod_0_reg <= prod_0_wide;
        prod_1_reg <= prod_1_wide;
        prod_2_reg <= prod_2_wide;
        prod_3_reg <= prod_3_wide;
        prod_4_reg <= prod_4_wide;
        prod_valid <= 1'b1;
      end else begin
        prod_valid <= 1'b0;
      end

      if (in_valid) begin
        delay_4   <= delay_3;
        delay_3   <= delay_2;
        delay_2   <= delay_1;
        delay_1   <= sample_0;
        sample_0  <= in_sample;
        tap_valid <= 1'b1;
      end else begin
        tap_valid <= 1'b0;
      end
    end
  end

endmodule

`default_nettype wire
