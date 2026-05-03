`timescale 1ns / 1ps
`default_nettype none

// FIR Transposed Form N=43
//
// 설계 기준: docs/log/14_transposed_form_rtl_decisions.md
//
// 파이프라인 2단계:
//   Stage 1: in_valid=1 → h[k]*in_sample → prod_reg[k]  (k=0..42 병렬)
//   Stage 2: prod_reg[k] + z[k+1] → z[k], round(z[0]) → out_sample
//
// Latency: 2 cycles (accepted input 기준)
// z[k]   : signed 48-bit (Q2.30)
// 반올림 : ties-away-from-zero, 출력 1회
// 포화   : 출력 1회 clip(-32768, 32767)
// z[42]  : prod_reg[42] only (z[43] 없음, B안)

module fir_transposed_n43 (
    input  wire               clk,
    input  wire               rst,
    input  wire               in_valid,
    input  wire signed [15:0] in_sample,
    output reg                out_valid,
    output reg signed  [15:0] out_sample
);

  // -----------------------------------------------------------------------
  // 계수 (Q1.15, ties-away-from-zero 반올림)
  // -----------------------------------------------------------------------
  localparam signed [15:0] COEFF_0 = 16'sd10;
  localparam signed [15:0] COEFF_1 = 16'sd0;
  localparam signed [15:0] COEFF_2 = -16'sd33;
  localparam signed [15:0] COEFF_3 = -16'sd32;
  localparam signed [15:0] COEFF_4 = 16'sd47;
  localparam signed [15:0] COEFF_5 = 16'sd107;
  localparam signed [15:0] COEFF_6 = 16'sd0;
  localparam signed [15:0] COEFF_7 = -16'sd197;
  localparam signed [15:0] COEFF_8 = -16'sd159;
  localparam signed [15:0] COEFF_9 = 16'sd206;
  localparam signed [15:0] COEFF_10 = 16'sd425;
  localparam signed [15:0] COEFF_11 = 16'sd0;
  localparam signed [15:0] COEFF_12 = -16'sd674;
  localparam signed [15:0] COEFF_13 = -16'sd522;
  localparam signed [15:0] COEFF_14 = 16'sd654;
  localparam signed [15:0] COEFF_15 = 16'sd1336;
  localparam signed [15:0] COEFF_16 = 16'sd0;
  localparam signed [15:0] COEFF_17 = -16'sd2258;
  localparam signed [15:0] COEFF_18 = -16'sd1939;
  localparam signed [15:0] COEFF_19 = 16'sd2995;
  localparam signed [15:0] COEFF_20 = 16'sd9864;
  localparam signed [15:0] COEFF_21 = 16'sd13109;
  localparam signed [15:0] COEFF_22 = 16'sd9864;
  localparam signed [15:0] COEFF_23 = 16'sd2995;
  localparam signed [15:0] COEFF_24 = -16'sd1939;
  localparam signed [15:0] COEFF_25 = -16'sd2258;
  localparam signed [15:0] COEFF_26 = 16'sd0;
  localparam signed [15:0] COEFF_27 = 16'sd1336;
  localparam signed [15:0] COEFF_28 = 16'sd654;
  localparam signed [15:0] COEFF_29 = -16'sd522;
  localparam signed [15:0] COEFF_30 = -16'sd674;
  localparam signed [15:0] COEFF_31 = 16'sd0;
  localparam signed [15:0] COEFF_32 = 16'sd425;
  localparam signed [15:0] COEFF_33 = 16'sd206;
  localparam signed [15:0] COEFF_34 = -16'sd159;
  localparam signed [15:0] COEFF_35 = -16'sd197;
  localparam signed [15:0] COEFF_36 = 16'sd0;
  localparam signed [15:0] COEFF_37 = 16'sd107;
  localparam signed [15:0] COEFF_38 = 16'sd47;
  localparam signed [15:0] COEFF_39 = -16'sd32;
  localparam signed [15:0] COEFF_40 = -16'sd33;
  localparam signed [15:0] COEFF_41 = 16'sd0;
  localparam signed [15:0] COEFF_42 = 16'sd10;

  // 반올림 상수: Q2.30 → Q1.15, bias = 2^(15-1) = 16384
  localparam signed [47:0] ROUND_BIAS = 48'sd16384;
  localparam signed [47:0] Q15_MAX = 48'sd32767;
  localparam signed [47:0] Q15_MIN = -48'sd32768;

  // -----------------------------------------------------------------------
  // Stage 1 레지스터
  // -----------------------------------------------------------------------
  reg signed  [47:0] prod_reg   [0:42];
  reg                prod_valid;

  // -----------------------------------------------------------------------
  // Stage 2 레지스터
  // -----------------------------------------------------------------------
  reg signed  [47:0] z          [0:42];  // delay register, Q2.30
  reg signed  [47:0] round_reg;          // round 결과 저장 (3단계 확장)
  reg                round_valid;

  // -----------------------------------------------------------------------
  // 조합 논리: 16x16 → 32bit 곱셈, sign-extend → 48bit
  // -----------------------------------------------------------------------
  wire signed [31:0] prod_comb  [0:42];
  wire signed [47:0] prod_wide  [0:42];

  assign prod_comb[0]  = COEFF_0 * in_sample;
  assign prod_comb[1]  = COEFF_1 * in_sample;
  assign prod_comb[2]  = COEFF_2 * in_sample;
  assign prod_comb[3]  = COEFF_3 * in_sample;
  assign prod_comb[4]  = COEFF_4 * in_sample;
  assign prod_comb[5]  = COEFF_5 * in_sample;
  assign prod_comb[6]  = COEFF_6 * in_sample;
  assign prod_comb[7]  = COEFF_7 * in_sample;
  assign prod_comb[8]  = COEFF_8 * in_sample;
  assign prod_comb[9]  = COEFF_9 * in_sample;
  assign prod_comb[10] = COEFF_10 * in_sample;
  assign prod_comb[11] = COEFF_11 * in_sample;
  assign prod_comb[12] = COEFF_12 * in_sample;
  assign prod_comb[13] = COEFF_13 * in_sample;
  assign prod_comb[14] = COEFF_14 * in_sample;
  assign prod_comb[15] = COEFF_15 * in_sample;
  assign prod_comb[16] = COEFF_16 * in_sample;
  assign prod_comb[17] = COEFF_17 * in_sample;
  assign prod_comb[18] = COEFF_18 * in_sample;
  assign prod_comb[19] = COEFF_19 * in_sample;
  assign prod_comb[20] = COEFF_20 * in_sample;
  assign prod_comb[21] = COEFF_21 * in_sample;
  assign prod_comb[22] = COEFF_22 * in_sample;
  assign prod_comb[23] = COEFF_23 * in_sample;
  assign prod_comb[24] = COEFF_24 * in_sample;
  assign prod_comb[25] = COEFF_25 * in_sample;
  assign prod_comb[26] = COEFF_26 * in_sample;
  assign prod_comb[27] = COEFF_27 * in_sample;
  assign prod_comb[28] = COEFF_28 * in_sample;
  assign prod_comb[29] = COEFF_29 * in_sample;
  assign prod_comb[30] = COEFF_30 * in_sample;
  assign prod_comb[31] = COEFF_31 * in_sample;
  assign prod_comb[32] = COEFF_32 * in_sample;
  assign prod_comb[33] = COEFF_33 * in_sample;
  assign prod_comb[34] = COEFF_34 * in_sample;
  assign prod_comb[35] = COEFF_35 * in_sample;
  assign prod_comb[36] = COEFF_36 * in_sample;
  assign prod_comb[37] = COEFF_37 * in_sample;
  assign prod_comb[38] = COEFF_38 * in_sample;
  assign prod_comb[39] = COEFF_39 * in_sample;
  assign prod_comb[40] = COEFF_40 * in_sample;
  assign prod_comb[41] = COEFF_41 * in_sample;
  assign prod_comb[42] = COEFF_42 * in_sample;

  assign prod_wide[0]  = {{16{prod_comb[0][31]}}, prod_comb[0]};
  assign prod_wide[1]  = {{16{prod_comb[1][31]}}, prod_comb[1]};
  assign prod_wide[2]  = {{16{prod_comb[2][31]}}, prod_comb[2]};
  assign prod_wide[3]  = {{16{prod_comb[3][31]}}, prod_comb[3]};
  assign prod_wide[4]  = {{16{prod_comb[4][31]}}, prod_comb[4]};
  assign prod_wide[5]  = {{16{prod_comb[5][31]}}, prod_comb[5]};
  assign prod_wide[6]  = {{16{prod_comb[6][31]}}, prod_comb[6]};
  assign prod_wide[7]  = {{16{prod_comb[7][31]}}, prod_comb[7]};
  assign prod_wide[8]  = {{16{prod_comb[8][31]}}, prod_comb[8]};
  assign prod_wide[9]  = {{16{prod_comb[9][31]}}, prod_comb[9]};
  assign prod_wide[10] = {{16{prod_comb[10][31]}}, prod_comb[10]};
  assign prod_wide[11] = {{16{prod_comb[11][31]}}, prod_comb[11]};
  assign prod_wide[12] = {{16{prod_comb[12][31]}}, prod_comb[12]};
  assign prod_wide[13] = {{16{prod_comb[13][31]}}, prod_comb[13]};
  assign prod_wide[14] = {{16{prod_comb[14][31]}}, prod_comb[14]};
  assign prod_wide[15] = {{16{prod_comb[15][31]}}, prod_comb[15]};
  assign prod_wide[16] = {{16{prod_comb[16][31]}}, prod_comb[16]};
  assign prod_wide[17] = {{16{prod_comb[17][31]}}, prod_comb[17]};
  assign prod_wide[18] = {{16{prod_comb[18][31]}}, prod_comb[18]};
  assign prod_wide[19] = {{16{prod_comb[19][31]}}, prod_comb[19]};
  assign prod_wide[20] = {{16{prod_comb[20][31]}}, prod_comb[20]};
  assign prod_wide[21] = {{16{prod_comb[21][31]}}, prod_comb[21]};
  assign prod_wide[22] = {{16{prod_comb[22][31]}}, prod_comb[22]};
  assign prod_wide[23] = {{16{prod_comb[23][31]}}, prod_comb[23]};
  assign prod_wide[24] = {{16{prod_comb[24][31]}}, prod_comb[24]};
  assign prod_wide[25] = {{16{prod_comb[25][31]}}, prod_comb[25]};
  assign prod_wide[26] = {{16{prod_comb[26][31]}}, prod_comb[26]};
  assign prod_wide[27] = {{16{prod_comb[27][31]}}, prod_comb[27]};
  assign prod_wide[28] = {{16{prod_comb[28][31]}}, prod_comb[28]};
  assign prod_wide[29] = {{16{prod_comb[29][31]}}, prod_comb[29]};
  assign prod_wide[30] = {{16{prod_comb[30][31]}}, prod_comb[30]};
  assign prod_wide[31] = {{16{prod_comb[31][31]}}, prod_comb[31]};
  assign prod_wide[32] = {{16{prod_comb[32][31]}}, prod_comb[32]};
  assign prod_wide[33] = {{16{prod_comb[33][31]}}, prod_comb[33]};
  assign prod_wide[34] = {{16{prod_comb[34][31]}}, prod_comb[34]};
  assign prod_wide[35] = {{16{prod_comb[35][31]}}, prod_comb[35]};
  assign prod_wide[36] = {{16{prod_comb[36][31]}}, prod_comb[36]};
  assign prod_wide[37] = {{16{prod_comb[37][31]}}, prod_comb[37]};
  assign prod_wide[38] = {{16{prod_comb[38][31]}}, prod_comb[38]};
  assign prod_wide[39] = {{16{prod_comb[39][31]}}, prod_comb[39]};
  assign prod_wide[40] = {{16{prod_comb[40][31]}}, prod_comb[40]};
  assign prod_wide[41] = {{16{prod_comb[41][31]}}, prod_comb[41]};
  assign prod_wide[42] = {{16{prod_comb[42][31]}}, prod_comb[42]};

  // -----------------------------------------------------------------------
  // 반올림/포화 함수 (N=5 bring-up과 동일)
  // -----------------------------------------------------------------------
  function automatic signed [47:0] round_q2_30_to_q1_15;
    input signed [47:0] value;
    reg signed [47:0] magnitude;
    reg signed [47:0] rounded_magnitude;
    begin
      magnitude = (value < 0) ? -value : value;
      rounded_magnitude = (magnitude + ROUND_BIAS) >>> 15;
      round_q2_30_to_q1_15 = (value < 0) ? -rounded_magnitude : rounded_magnitude;
    end
  endfunction

  function automatic signed [15:0] saturate_to_q1_15;
    input signed [47:0] value;
    begin
      if (value > Q15_MAX) saturate_to_q1_15 = 16'sd32767;
      else if (value < Q15_MIN) saturate_to_q1_15 = -16'sd32768;
      else saturate_to_q1_15 = value[15:0];
    end
  endfunction

  // -----------------------------------------------------------------------
  // Stage 1: 곱셈 → prod_reg
  // -----------------------------------------------------------------------
  integer i;
  always @(posedge clk or posedge rst) begin
    if (rst) begin
      prod_valid <= 1'b0;
      for (i = 0; i <= 42; i = i + 1) prod_reg[i] <= 48'sd0;
    end else begin
      if (in_valid) begin
        prod_reg[0]  <= prod_wide[0];
        prod_reg[1]  <= prod_wide[1];
        prod_reg[2]  <= prod_wide[2];
        prod_reg[3]  <= prod_wide[3];
        prod_reg[4]  <= prod_wide[4];
        prod_reg[5]  <= prod_wide[5];
        prod_reg[6]  <= prod_wide[6];
        prod_reg[7]  <= prod_wide[7];
        prod_reg[8]  <= prod_wide[8];
        prod_reg[9]  <= prod_wide[9];
        prod_reg[10] <= prod_wide[10];
        prod_reg[11] <= prod_wide[11];
        prod_reg[12] <= prod_wide[12];
        prod_reg[13] <= prod_wide[13];
        prod_reg[14] <= prod_wide[14];
        prod_reg[15] <= prod_wide[15];
        prod_reg[16] <= prod_wide[16];
        prod_reg[17] <= prod_wide[17];
        prod_reg[18] <= prod_wide[18];
        prod_reg[19] <= prod_wide[19];
        prod_reg[20] <= prod_wide[20];
        prod_reg[21] <= prod_wide[21];
        prod_reg[22] <= prod_wide[22];
        prod_reg[23] <= prod_wide[23];
        prod_reg[24] <= prod_wide[24];
        prod_reg[25] <= prod_wide[25];
        prod_reg[26] <= prod_wide[26];
        prod_reg[27] <= prod_wide[27];
        prod_reg[28] <= prod_wide[28];
        prod_reg[29] <= prod_wide[29];
        prod_reg[30] <= prod_wide[30];
        prod_reg[31] <= prod_wide[31];
        prod_reg[32] <= prod_wide[32];
        prod_reg[33] <= prod_wide[33];
        prod_reg[34] <= prod_wide[34];
        prod_reg[35] <= prod_wide[35];
        prod_reg[36] <= prod_wide[36];
        prod_reg[37] <= prod_wide[37];
        prod_reg[38] <= prod_wide[38];
        prod_reg[39] <= prod_wide[39];
        prod_reg[40] <= prod_wide[40];
        prod_reg[41] <= prod_wide[41];
        prod_reg[42] <= prod_wide[42];
        prod_valid   <= 1'b1;
      end else begin
        prod_valid <= 1'b0;
      end
    end
  end

  // -----------------------------------------------------------------------
  // Stage 2: 누산 → z[k] 갱신, round 결과 → round_reg
  // -----------------------------------------------------------------------
  always @(posedge clk or posedge rst) begin
    if (rst) begin
      round_valid <= 1'b0;
      round_reg   <= 48'sd0;
      for (i = 0; i <= 42; i = i + 1) z[i] <= 48'sd0;
    end else begin
      if (prod_valid) begin
        z[0] <= prod_reg[0] + z[1];
        z[1] <= prod_reg[1] + z[2];
        z[2] <= prod_reg[2] + z[3];
        z[3] <= prod_reg[3] + z[4];
        z[4] <= prod_reg[4] + z[5];
        z[5] <= prod_reg[5] + z[6];
        z[6] <= prod_reg[6] + z[7];
        z[7] <= prod_reg[7] + z[8];
        z[8] <= prod_reg[8] + z[9];
        z[9] <= prod_reg[9] + z[10];
        z[10] <= prod_reg[10] + z[11];
        z[11] <= prod_reg[11] + z[12];
        z[12] <= prod_reg[12] + z[13];
        z[13] <= prod_reg[13] + z[14];
        z[14] <= prod_reg[14] + z[15];
        z[15] <= prod_reg[15] + z[16];
        z[16] <= prod_reg[16] + z[17];
        z[17] <= prod_reg[17] + z[18];
        z[18] <= prod_reg[18] + z[19];
        z[19] <= prod_reg[19] + z[20];
        z[20] <= prod_reg[20] + z[21];
        z[21] <= prod_reg[21] + z[22];
        z[22] <= prod_reg[22] + z[23];
        z[23] <= prod_reg[23] + z[24];
        z[24] <= prod_reg[24] + z[25];
        z[25] <= prod_reg[25] + z[26];
        z[26] <= prod_reg[26] + z[27];
        z[27] <= prod_reg[27] + z[28];
        z[28] <= prod_reg[28] + z[29];
        z[29] <= prod_reg[29] + z[30];
        z[30] <= prod_reg[30] + z[31];
        z[31] <= prod_reg[31] + z[32];
        z[32] <= prod_reg[32] + z[33];
        z[33] <= prod_reg[33] + z[34];
        z[34] <= prod_reg[34] + z[35];
        z[35] <= prod_reg[35] + z[36];
        z[36] <= prod_reg[36] + z[37];
        z[37] <= prod_reg[37] + z[38];
        z[38] <= prod_reg[38] + z[39];
        z[39] <= prod_reg[39] + z[40];
        z[40] <= prod_reg[40] + z[41];
        z[41] <= prod_reg[41] + z[42];
        z[42] <= prod_reg[42];
        // non-blocking 특성상 z[0] 직접 참조 불가 → prod_reg[0]+z[1] 직접 계산
        round_reg   <= round_q2_30_to_q1_15(prod_reg[0] + z[1]);
        round_valid <= 1'b1;
      end else begin
        round_valid <= 1'b0;
      end
    end
  end

  // -----------------------------------------------------------------------
  // Stage 3: 포화 → 출력
  // -----------------------------------------------------------------------
  always @(posedge clk or posedge rst) begin
    if (rst) begin
      out_valid  <= 1'b0;
      out_sample <= 16'sd0;
    end else begin
      if (round_valid) begin
        out_sample <= saturate_to_q1_15(round_reg);
        out_valid  <= 1'b1;
      end else begin
        out_valid <= 1'b0;
      end
    end
  end

endmodule

`default_nettype wire
