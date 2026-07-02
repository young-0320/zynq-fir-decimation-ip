`timescale 1ns / 1ps
// Directed stress test: continuous zero-bubble input + sustained m_axis backpressure.
// v1/v2 wrapper each instantiated twice (reference tready=1, stress 25-low/15-high).
// A skid-buffer drop shows up as count deficit / element mismatch / missing TLAST.

module axis_driver #(parameter N_IN = 200) (
    input  wire               clk,
    input  wire               aresetn,
    output wire               s_tvalid,
    input  wire               s_tready,
    output wire signed [15:0] s_tdata,
    output wire               s_tlast
);
  reg [15:0] sent;
  always @(posedge clk) begin
    if (!aresetn) sent <= 0;
    else if (s_tvalid && s_tready) sent <= sent + 1;
  end
  assign s_tvalid = aresetn && (sent < N_IN);
  assign s_tdata  = $signed({sent[7:0], 6'd0}) - 16'sd8000;  // ramp, sign wiggle
  assign s_tlast  = (sent == N_IN - 1);
endmodule

module axis_collector (
    input wire               clk,
    input wire               aresetn,
    input wire               m_tvalid,
    input wire               m_tready,
    input wire signed [15:0] m_tdata,
    input wire               m_tlast
);
  reg signed [15:0] mem [0:255];
  reg [15:0] cnt;
  reg        got_last;
  reg [15:0] last_idx;
  always @(posedge clk) begin
    if (!aresetn) begin
      cnt <= 0;
      got_last <= 0;
      last_idx <= 16'hFFFF;
    end else if (m_tvalid && m_tready) begin
      mem[cnt[7:0]] <= m_tdata;
      cnt <= cnt + 1;
      if (m_tlast) begin
        got_last <= 1;
        last_idx <= cnt;  // 0-based beat index carrying TLAST
      end
    end
  end
endmodule

module tb_skid_stress;

  localparam N_IN = 200;
  localparam N_OUT_EXP = N_IN / 2;
  localparam TIMEOUT = 20000;

  reg clk = 0;
  reg aresetn = 0;
  always #5 clk = ~clk;

  integer cyc = 0;
  always @(posedge clk) cyc <= cyc + 1;
  wire stress_ready = ((cyc % 40) >= 25);

  // ---- v1 reference ----
  wire v1r_sv, v1r_sr, v1r_sl, v1r_mv, v1r_ml;
  wire signed [15:0] v1r_sd, v1r_md;
  axis_driver #(N_IN) drv_v1r (clk, aresetn, v1r_sv, v1r_sr, v1r_sd, v1r_sl);
  fir_decimator_n43_axis dut_v1r (
      .aclk(clk), .aresetn(aresetn),
      .s_axis_tvalid(v1r_sv), .s_axis_tready(v1r_sr), .s_axis_tdata(v1r_sd), .s_axis_tlast(v1r_sl),
      .m_axis_tvalid(v1r_mv), .m_axis_tready(1'b1), .m_axis_tdata(v1r_md), .m_axis_tlast(v1r_ml));
  axis_collector col_v1r (clk, aresetn, v1r_mv, 1'b1, v1r_md, v1r_ml);

  // ---- v1 stress ----
  wire v1s_sv, v1s_sr, v1s_sl, v1s_mv, v1s_ml;
  wire signed [15:0] v1s_sd, v1s_md;
  axis_driver #(N_IN) drv_v1s (clk, aresetn, v1s_sv, v1s_sr, v1s_sd, v1s_sl);
  fir_decimator_n43_axis dut_v1s (
      .aclk(clk), .aresetn(aresetn),
      .s_axis_tvalid(v1s_sv), .s_axis_tready(v1s_sr), .s_axis_tdata(v1s_sd), .s_axis_tlast(v1s_sl),
      .m_axis_tvalid(v1s_mv), .m_axis_tready(stress_ready), .m_axis_tdata(v1s_md), .m_axis_tlast(v1s_ml));
  axis_collector col_v1s (clk, aresetn, v1s_mv, stress_ready, v1s_md, v1s_ml);

  // ---- v2 reference ----
  wire v2r_sv, v2r_sr, v2r_sl, v2r_mv, v2r_ml;
  wire signed [15:0] v2r_sd, v2r_md;
  axis_driver #(N_IN) drv_v2r (clk, aresetn, v2r_sv, v2r_sr, v2r_sd, v2r_sl);
  fir_decimator_n43_axis_v2 dut_v2r (
      .aclk(clk), .aresetn(aresetn),
      .s_axis_tvalid(v2r_sv), .s_axis_tready(v2r_sr), .s_axis_tdata(v2r_sd), .s_axis_tlast(v2r_sl),
      .m_axis_tvalid(v2r_mv), .m_axis_tready(1'b1), .m_axis_tdata(v2r_md), .m_axis_tlast(v2r_ml));
  axis_collector col_v2r (clk, aresetn, v2r_mv, 1'b1, v2r_md, v2r_ml);

  // ---- v2 stress ----
  wire v2s_sv, v2s_sr, v2s_sl, v2s_mv, v2s_ml;
  wire signed [15:0] v2s_sd, v2s_md;
  axis_driver #(N_IN) drv_v2s (clk, aresetn, v2s_sv, v2s_sr, v2s_sd, v2s_sl);
  fir_decimator_n43_axis_v2 dut_v2s (
      .aclk(clk), .aresetn(aresetn),
      .s_axis_tvalid(v2s_sv), .s_axis_tready(v2s_sr), .s_axis_tdata(v2s_sd), .s_axis_tlast(v2s_sl),
      .m_axis_tvalid(v2s_mv), .m_axis_tready(stress_ready), .m_axis_tdata(v2s_md), .m_axis_tlast(v2s_ml));
  axis_collector col_v2s (clk, aresetn, v2s_mv, stress_ready, v2s_md, v2s_ml);

  integer errors = 0;
  integer i;
  integer hit;

  initial begin
    aresetn = 0;
    repeat (5) @(posedge clk);
    aresetn = 1;

    i = 0;
    while (i < TIMEOUT && !(col_v1r.got_last && col_v1s.got_last && col_v2r.got_last && col_v2s.got_last)) begin
      @(posedge clk);
      i = i + 1;
    end

    $display("--- results after %0d cycles ---", cyc);
    $display("v1 ref   : recv=%0d tlast=%0d tlast_at_beat=%0d (expect %0d beats, tlast at %0d)",
             col_v1r.cnt, col_v1r.got_last, col_v1r.last_idx, N_OUT_EXP, N_OUT_EXP - 1);
    $display("v1 stress: recv=%0d tlast=%0d tlast_at_beat=%0d", col_v1s.cnt, col_v1s.got_last, col_v1s.last_idx);
    $display("v2 ref   : recv=%0d tlast=%0d tlast_at_beat=%0d", col_v2r.cnt, col_v2r.got_last, col_v2r.last_idx);
    $display("v2 stress: recv=%0d tlast=%0d tlast_at_beat=%0d", col_v2s.cnt, col_v2s.got_last, col_v2s.last_idx);
    $display("v1 stress FSM: waiting_for_last_out=%0d out_cnt=%0d target=%0d in_cnt=%0d",
             dut_v1s.waiting_for_last_out, dut_v1s.out_cnt, dut_v1s.target_out_cnt, dut_v1s.in_cnt);
    $display("v2 stress FSM: waiting_for_last_out=%0d out_cnt=%0d target=%0d in_cnt=%0d",
             dut_v2s.waiting_for_last_out, dut_v2s.out_cnt, dut_v2s.target_out_cnt, dut_v2s.in_cnt);

    if (col_v1s.cnt != col_v1r.cnt) begin
      errors = errors + 1;
      $display("V1 DROP: stress delivered %0d of %0d (%0d dropped)", col_v1s.cnt, col_v1r.cnt, col_v1r.cnt - col_v1s.cnt);
    end
    if (col_v2s.cnt != col_v2r.cnt) begin
      errors = errors + 1;
      $display("V2 DROP: stress delivered %0d of %0d (%0d dropped)", col_v2s.cnt, col_v2r.cnt, col_v2r.cnt - col_v2s.cnt);
    end

    hit = 0;
    for (i = 0; i < col_v1s.cnt && i < col_v1r.cnt && i < 256; i = i + 1)
      if (!hit && col_v1s.mem[i] !== col_v1r.mem[i]) begin
        errors = errors + 1; hit = 1;
        $display("V1 MISMATCH at out[%0d]: stress=%0d ref=%0d", i, col_v1s.mem[i], col_v1r.mem[i]);
      end
    hit = 0;
    for (i = 0; i < col_v2s.cnt && i < col_v2r.cnt && i < 256; i = i + 1)
      if (!hit && col_v2s.mem[i] !== col_v2r.mem[i]) begin
        errors = errors + 1; hit = 1;
        $display("V2 MISMATCH at out[%0d]: stress=%0d ref=%0d", i, col_v2s.mem[i], col_v2r.mem[i]);
      end
    hit = 0;
    for (i = 0; i < col_v1r.cnt && i < col_v2r.cnt && i < 256; i = i + 1)
      if (!hit && col_v1r.mem[i] !== col_v2r.mem[i]) begin
        errors = errors + 1; hit = 1;
        $display("V1/V2 REF MISMATCH at out[%0d]: v1=%0d v2=%0d", i, col_v1r.mem[i], col_v2r.mem[i]);
      end

    if (!col_v1s.got_last) $display("V1 stress: TLAST never delivered (hang)");
    if (!col_v2s.got_last) $display("V2 stress: TLAST never delivered (hang)");

    if (errors == 0) $display("RESULT: PASS — no drops under continuous input + sustained backpressure");
    else $display("RESULT: FAIL — %0d error groups", errors);
    $finish;
  end

endmodule
