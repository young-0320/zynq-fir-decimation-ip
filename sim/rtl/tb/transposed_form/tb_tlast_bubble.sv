`timescale 1ns / 1ps
// Directed regression for log 43: tvalid bubble immediately BEFORE the tlast beat.
//
// Pre-fix failure: bubble >= 3 (v1, core latency 4) / >= 4 (v2, latency 5) lets the final
// core output leave before target_out_cnt / waiting_for_last_out are set -> that beat is
// never tagged, no further core_out_valid pulse re-evaluates the termination -> TLAST lost
// + s_axis_tready stuck low (permanent deadlock until reset).
//
// Fix under test (docs/log/43): hold-back of the newest length-unresolved output +
// retroactive TLAST tagging + immediate termination at tlast accept.
//
// Sweep: bubble 0..MAXB cycles x {v1, v2} x {free-running tready=1, sustained backpressure}.
// Two back-to-back packets per DUT (verifies recovery / next packet after the bubble case).
// Asserts per DUT: exactly NUM_PKT TLASTs, each packet exactly N_IN/2 beats, no strays,
// and every delivered sample equal to the bubble=0 free-running reference of the same core
// (bubbles and backpressure must not change data).

module bubble_drv #(
    parameter N_IN = 12,
    parameter NUM_PKT = 2,
    parameter BUBBLE = 0
) (
    input  wire clk,
    input  wire aresetn,
    output reg                s_tvalid,
    input  wire               s_tready,
    output reg signed [15:0]  s_tdata,
    output reg                s_tlast
);
  integer p, i;
  initial begin
    s_tvalid = 0; s_tdata = 0; s_tlast = 0;
    @(posedge aresetn);
    @(posedge clk);
    for (p = 0; p < NUM_PKT; p = p + 1) begin
      // beats 0 .. N-2 back-to-back
      for (i = 0; i < N_IN - 1; i = i + 1) begin
        s_tvalid <= 1; s_tdata <= 16'sd100 * (i + 1); s_tlast <= 0;
        @(posedge clk);
        while (!s_tready) @(posedge clk);
      end
      // the bubble under test: tvalid low for BUBBLE cycles right before the tlast beat
      s_tvalid <= 0; s_tlast <= 0;
      repeat (BUBBLE) @(posedge clk);
      s_tvalid <= 1; s_tdata <= -16'sd999; s_tlast <= 1;
      @(posedge clk);
      while (!s_tready) @(posedge clk);
      s_tvalid <= 0; s_tlast <= 0;
    end
  end
endmodule

module bubble_col #(parameter MAXN = 16) (
    input wire               clk,
    input wire               aresetn,
    input wire               m_tvalid,
    input wire               m_tready,
    input wire signed [15:0] m_tdata,
    input wire               m_tlast
);
  reg signed [15:0] mem [0:1][0:MAXN-1];
  reg [15:0] len [0:1];
  reg [15:0] beat, pkt, total;
  always @(posedge clk) begin
    if (!aresetn) begin
      beat <= 0; pkt <= 0; total <= 0;
      len[0] <= 0; len[1] <= 0;
    end else if (m_tvalid && m_tready) begin
      total <= total + 1;
      if (pkt < 2 && beat < MAXN) mem[pkt[0]][beat[3:0]] <= m_tdata;
      if (m_tlast) begin
        if (pkt < 2) len[pkt[0]] <= beat + 1;
        pkt  <= pkt + 1;
        beat <= 0;
      end else begin
        beat <= beat + 1;
      end
    end
  end
endmodule

module tb_tlast_bubble;

  localparam N_IN    = 12;
  localparam NUM_PKT = 2;
  localparam N_OUT   = N_IN / 2;
  localparam MAXB    = 6;        // covers v1 threshold(3) / v2 threshold(4) with margin
  localparam TIMEOUT = 20000;

  reg clk = 0;
  always #5 clk = ~clk;
  reg aresetn = 0;

  integer cyc = 0;
  always @(posedge clk) cyc <= cyc + 1;
  wire stress_ready = ((cyc % 40) >= 25);  // sustained backpressure: 25 low / 15 high

  reg  start_check = 0;
  integer errors = 0;

  wire [MAXB:0] done_v1f, done_v1b, done_v2f, done_v2b;

  genvar b;
  generate
    for (b = 0; b <= MAXB; b = b + 1) begin : g_v1f
      wire sv, sr, sl, mv, ml; wire signed [15:0] sd, md;
      bubble_drv #(N_IN, NUM_PKT, b) drv (clk, aresetn, sv, sr, sd, sl);
      fir_decimator_n43_axis dut (
          .aclk(clk), .aresetn(aresetn),
          .s_axis_tvalid(sv), .s_axis_tready(sr), .s_axis_tdata(sd), .s_axis_tlast(sl),
          .m_axis_tvalid(mv), .m_axis_tready(1'b1), .m_axis_tdata(md), .m_axis_tlast(ml));
      bubble_col col (clk, aresetn, mv, 1'b1, md, ml);
      assign done_v1f[b] = (col.pkt >= NUM_PKT);
      integer i, p;
      initial begin
        @(posedge start_check);
        if (col.pkt !== NUM_PKT || col.len[0] !== N_OUT || col.len[1] !== N_OUT
            || col.total !== NUM_PKT * N_OUT) begin
          errors = errors + 1;
          $display("v1 free   b=%0d: FAIL pkts=%0d len=[%0d,%0d] total=%0d (expect %0d/[%0d,%0d]/%0d)",
                   b, col.pkt, col.len[0], col.len[1], col.total, NUM_PKT, N_OUT, N_OUT, NUM_PKT*N_OUT);
        end
        for (p = 0; p < 2; p = p + 1)
          for (i = 0; i < N_OUT; i = i + 1)
            if (col.mem[p][i] !== tb_tlast_bubble.g_v1f[0].col.mem[p][i]) begin
              errors = errors + 1;
              $display("v1 free   b=%0d: FAIL data pkt%0d out[%0d]=%0d != ref %0d",
                       b, p, i, col.mem[p][i], tb_tlast_bubble.g_v1f[0].col.mem[p][i]);
              p = 2; i = N_OUT;
            end
      end
    end

    for (b = 0; b <= MAXB; b = b + 1) begin : g_v1b
      wire sv, sr, sl, mv, ml; wire signed [15:0] sd, md;
      bubble_drv #(N_IN, NUM_PKT, b) drv (clk, aresetn, sv, sr, sd, sl);
      fir_decimator_n43_axis dut (
          .aclk(clk), .aresetn(aresetn),
          .s_axis_tvalid(sv), .s_axis_tready(sr), .s_axis_tdata(sd), .s_axis_tlast(sl),
          .m_axis_tvalid(mv), .m_axis_tready(stress_ready), .m_axis_tdata(md), .m_axis_tlast(ml));
      bubble_col col (clk, aresetn, mv, stress_ready, md, ml);
      assign done_v1b[b] = (col.pkt >= NUM_PKT);
      integer i, p;
      initial begin
        @(posedge start_check);
        if (col.pkt !== NUM_PKT || col.len[0] !== N_OUT || col.len[1] !== N_OUT
            || col.total !== NUM_PKT * N_OUT) begin
          errors = errors + 1;
          $display("v1 stress b=%0d: FAIL pkts=%0d len=[%0d,%0d] total=%0d",
                   b, col.pkt, col.len[0], col.len[1], col.total);
        end
        for (p = 0; p < 2; p = p + 1)
          for (i = 0; i < N_OUT; i = i + 1)
            if (col.mem[p][i] !== tb_tlast_bubble.g_v1f[0].col.mem[p][i]) begin
              errors = errors + 1;
              $display("v1 stress b=%0d: FAIL data pkt%0d out[%0d]=%0d != ref %0d",
                       b, p, i, col.mem[p][i], tb_tlast_bubble.g_v1f[0].col.mem[p][i]);
              p = 2; i = N_OUT;
            end
      end
    end

    for (b = 0; b <= MAXB; b = b + 1) begin : g_v2f
      wire sv, sr, sl, mv, ml; wire signed [15:0] sd, md;
      bubble_drv #(N_IN, NUM_PKT, b) drv (clk, aresetn, sv, sr, sd, sl);
      fir_decimator_n43_axis_v2 dut (
          .aclk(clk), .aresetn(aresetn),
          .s_axis_tvalid(sv), .s_axis_tready(sr), .s_axis_tdata(sd), .s_axis_tlast(sl),
          .m_axis_tvalid(mv), .m_axis_tready(1'b1), .m_axis_tdata(md), .m_axis_tlast(ml));
      bubble_col col (clk, aresetn, mv, 1'b1, md, ml);
      assign done_v2f[b] = (col.pkt >= NUM_PKT);
      integer i, p;
      initial begin
        @(posedge start_check);
        if (col.pkt !== NUM_PKT || col.len[0] !== N_OUT || col.len[1] !== N_OUT
            || col.total !== NUM_PKT * N_OUT) begin
          errors = errors + 1;
          $display("v2 free   b=%0d: FAIL pkts=%0d len=[%0d,%0d] total=%0d",
                   b, col.pkt, col.len[0], col.len[1], col.total);
        end
        for (p = 0; p < 2; p = p + 1)
          for (i = 0; i < N_OUT; i = i + 1)
            if (col.mem[p][i] !== tb_tlast_bubble.g_v2f[0].col.mem[p][i]) begin
              errors = errors + 1;
              $display("v2 free   b=%0d: FAIL data pkt%0d out[%0d]=%0d != ref %0d",
                       b, p, i, col.mem[p][i], tb_tlast_bubble.g_v2f[0].col.mem[p][i]);
              p = 2; i = N_OUT;
            end
      end
    end

    for (b = 0; b <= MAXB; b = b + 1) begin : g_v2b
      wire sv, sr, sl, mv, ml; wire signed [15:0] sd, md;
      bubble_drv #(N_IN, NUM_PKT, b) drv (clk, aresetn, sv, sr, sd, sl);
      fir_decimator_n43_axis_v2 dut (
          .aclk(clk), .aresetn(aresetn),
          .s_axis_tvalid(sv), .s_axis_tready(sr), .s_axis_tdata(sd), .s_axis_tlast(sl),
          .m_axis_tvalid(mv), .m_axis_tready(stress_ready), .m_axis_tdata(md), .m_axis_tlast(ml));
      bubble_col col (clk, aresetn, mv, stress_ready, md, ml);
      assign done_v2b[b] = (col.pkt >= NUM_PKT);
      integer i, p;
      initial begin
        @(posedge start_check);
        if (col.pkt !== NUM_PKT || col.len[0] !== N_OUT || col.len[1] !== N_OUT
            || col.total !== NUM_PKT * N_OUT) begin
          errors = errors + 1;
          $display("v2 stress b=%0d: FAIL pkts=%0d len=[%0d,%0d] total=%0d",
                   b, col.pkt, col.len[0], col.len[1], col.total);
        end
        for (p = 0; p < 2; p = p + 1)
          for (i = 0; i < N_OUT; i = i + 1)
            if (col.mem[p][i] !== tb_tlast_bubble.g_v2f[0].col.mem[p][i]) begin
              errors = errors + 1;
              $display("v2 stress b=%0d: FAIL data pkt%0d out[%0d]=%0d != ref %0d",
                       b, p, i, col.mem[p][i], tb_tlast_bubble.g_v2f[0].col.mem[p][i]);
              p = 2; i = N_OUT;
            end
      end
    end
  endgenerate

  integer w;
  initial begin
    aresetn = 0;
    repeat (5) @(posedge clk);
    aresetn = 1;

    w = 0;
    while (w < TIMEOUT && !(&done_v1f && &done_v1b && &done_v2f && &done_v2b)) begin
      @(posedge clk);
      w = w + 1;
    end
    // extra drain window to expose late stray beats
    repeat (200) @(posedge clk);

    if (w >= TIMEOUT)
      $display("TIMEOUT after %0d cycles — some DUT never delivered %0d TLASTs (deadlock)", cyc, NUM_PKT);

    start_check = 1;
    #100;
    if (errors == 0)
      $display("RESULT: PASS — bubble 0..%0d before TLAST, v1/v2, free+backpressure, %0d packets each",
               MAXB, NUM_PKT);
    else
      $display("RESULT: FAIL — %0d errors", errors);
    $finish;
  end

endmodule
