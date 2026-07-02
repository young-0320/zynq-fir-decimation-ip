`timescale 1ns / 1ps
// Directed stress test: continuous zero-bubble input + sustained m_axis backpressure,
// TWO back-to-back packets with NO reset between them (mirrors the firmware which calls
// dma_run() repeatedly without resetting the PL wrapper — see workflow_v22 §배경).
//
// v1/v2 wrapper each instantiated twice (reference tready=1, stress 25-low/15-high).
// Each packet ends with >= 43 zero samples so the FIR delay line flushes to zero; with
// even N_IN and no flush 0-injection the decimator phase also returns to its start, so a
// correct design produces bit-identical packet1/packet2. Any residual (bug 3 stray leak /
// bug 4 phase drift / bug 1 drop / bug 2 deadlock) shows up as one of the absolute asserts:
//   - each packet delivers exactly N_IN/2 beats
//   - exactly one TLAST per packet, on its last beat
//   - no stray beats (total == NUM_PKT * N_IN/2)
//   - packet2 == packet1 element-by-element (no contamination / phase drift)

module axis_driver #(
    parameter N_IN = 200,
    parameter NUM_PKT = 2,
    parameter TAIL_ZEROS = 48  // >= FIR length (43) so the delay line is zero at packet end
) (
    input  wire               clk,
    input  wire               aresetn,
    output wire               s_tvalid,
    input  wire               s_tready,
    output wire signed [15:0] s_tdata,
    output wire               s_tlast
);
  reg [15:0] sent;                      // global count of accepted samples
  wire [15:0] idx = sent % N_IN;        // within-packet index (identical pattern each packet)
  always @(posedge clk) begin
    if (!aresetn) sent <= 0;
    else if (s_tvalid && s_tready) sent <= sent + 1;
  end
  assign s_tvalid = aresetn && (sent < N_IN * NUM_PKT);
  // signal in the head, zeros in the tail (flushes FIR state) — same waveform per packet
  assign s_tdata  = (idx < N_IN - TAIL_ZEROS) ? ($signed({idx[7:0], 6'd0}) - 16'sd8000) : 16'sd0;
  assign s_tlast  = (idx == N_IN - 1);
endmodule

module axis_collector #(parameter MAXP = 4) (
    input wire               clk,
    input wire               aresetn,
    input wire               m_tvalid,
    input wire               m_tready,
    input wire signed [15:0] m_tdata,
    input wire               m_tlast
);
  // pkt_mem holds the first two packets for a bit-exact packet1==packet2 comparison.
  reg signed [15:0] pkt_mem [0:1][0:255];
  reg [15:0] pkt_len [0:MAXP-1];        // beats delivered in each packet (segmented by TLAST)
  reg [15:0] beat;                      // beat index within the current packet
  reg [15:0] pkt;                       // number of TLASTs seen so far = current packet index
  reg [15:0] total;                     // total beats received (stray detection)
  integer k;
  always @(posedge clk) begin
    if (!aresetn) begin
      beat <= 0; pkt <= 0; total <= 0;
      for (k = 0; k < MAXP; k = k + 1) pkt_len[k] <= 0;
    end else if (m_tvalid && m_tready) begin
      total <= total + 1;
      if (pkt < 2 && beat < 256) pkt_mem[pkt[0]][beat[7:0]] <= m_tdata;
      if (m_tlast) begin
        if (pkt < MAXP) pkt_len[pkt] <= beat + 1;
        pkt  <= pkt + 1;
        beat <= 0;
      end else begin
        beat <= beat + 1;
      end
    end
  end
endmodule

module tb_skid_stress;

  localparam N_IN = 200;
  localparam NUM_PKT = 2;
  localparam N_OUT_EXP = N_IN / 2;
  localparam TIMEOUT = 40000;

  reg clk = 0;
  reg aresetn = 0;
  always #5 clk = ~clk;

  integer cyc = 0;
  always @(posedge clk) cyc <= cyc + 1;
  wire stress_ready = ((cyc % 40) >= 25);  // sustained backpressure: 25 low / 15 high

  // ---- v1 reference ----
  wire v1r_sv, v1r_sr, v1r_sl, v1r_mv, v1r_ml;
  wire signed [15:0] v1r_sd, v1r_md;
  axis_driver #(N_IN, NUM_PKT) drv_v1r (clk, aresetn, v1r_sv, v1r_sr, v1r_sd, v1r_sl);
  fir_decimator_n43_axis dut_v1r (
      .aclk(clk), .aresetn(aresetn),
      .s_axis_tvalid(v1r_sv), .s_axis_tready(v1r_sr), .s_axis_tdata(v1r_sd), .s_axis_tlast(v1r_sl),
      .m_axis_tvalid(v1r_mv), .m_axis_tready(1'b1), .m_axis_tdata(v1r_md), .m_axis_tlast(v1r_ml));
  axis_collector col_v1r (clk, aresetn, v1r_mv, 1'b1, v1r_md, v1r_ml);

  // ---- v1 stress ----
  wire v1s_sv, v1s_sr, v1s_sl, v1s_mv, v1s_ml;
  wire signed [15:0] v1s_sd, v1s_md;
  axis_driver #(N_IN, NUM_PKT) drv_v1s (clk, aresetn, v1s_sv, v1s_sr, v1s_sd, v1s_sl);
  fir_decimator_n43_axis dut_v1s (
      .aclk(clk), .aresetn(aresetn),
      .s_axis_tvalid(v1s_sv), .s_axis_tready(v1s_sr), .s_axis_tdata(v1s_sd), .s_axis_tlast(v1s_sl),
      .m_axis_tvalid(v1s_mv), .m_axis_tready(stress_ready), .m_axis_tdata(v1s_md), .m_axis_tlast(v1s_ml));
  axis_collector col_v1s (clk, aresetn, v1s_mv, stress_ready, v1s_md, v1s_ml);

  // ---- v2 reference ----
  wire v2r_sv, v2r_sr, v2r_sl, v2r_mv, v2r_ml;
  wire signed [15:0] v2r_sd, v2r_md;
  axis_driver #(N_IN, NUM_PKT) drv_v2r (clk, aresetn, v2r_sv, v2r_sr, v2r_sd, v2r_sl);
  fir_decimator_n43_axis_v2 dut_v2r (
      .aclk(clk), .aresetn(aresetn),
      .s_axis_tvalid(v2r_sv), .s_axis_tready(v2r_sr), .s_axis_tdata(v2r_sd), .s_axis_tlast(v2r_sl),
      .m_axis_tvalid(v2r_mv), .m_axis_tready(1'b1), .m_axis_tdata(v2r_md), .m_axis_tlast(v2r_ml));
  axis_collector col_v2r (clk, aresetn, v2r_mv, 1'b1, v2r_md, v2r_ml);

  // ---- v2 stress ----
  wire v2s_sv, v2s_sr, v2s_sl, v2s_mv, v2s_ml;
  wire signed [15:0] v2s_sd, v2s_md;
  axis_driver #(N_IN, NUM_PKT) drv_v2s (clk, aresetn, v2s_sv, v2s_sr, v2s_sd, v2s_sl);
  fir_decimator_n43_axis_v2 dut_v2s (
      .aclk(clk), .aresetn(aresetn),
      .s_axis_tvalid(v2s_sv), .s_axis_tready(v2s_sr), .s_axis_tdata(v2s_sd), .s_axis_tlast(v2s_sl),
      .m_axis_tvalid(v2s_mv), .m_axis_tready(stress_ready), .m_axis_tdata(v2s_md), .m_axis_tlast(v2s_ml));
  axis_collector col_v2s (clk, aresetn, v2s_mv, stress_ready, v2s_md, v2s_ml);

  integer errors = 0;
  integer i;

  // Absolute per-packet framing checks for one DUT.
  task check_scalars(input [12*8:1] name, input integer pkt, input integer l0,
                     input integer l1, input integer tot);
    begin
      if (pkt !== NUM_PKT) begin
        errors = errors + 1;
        $display("%0s: FAIL TLAST count = %0d (expect %0d — deadlock or stray TLAST)", name, pkt, NUM_PKT);
      end
      if (l0 !== N_OUT_EXP) begin
        errors = errors + 1;
        $display("%0s: FAIL packet1 beats = %0d (expect %0d)", name, l0, N_OUT_EXP);
      end
      if (l1 !== N_OUT_EXP) begin
        errors = errors + 1;
        $display("%0s: FAIL packet2 beats = %0d (expect %0d)", name, l1, N_OUT_EXP);
      end
      if (tot !== NUM_PKT * N_OUT_EXP) begin
        errors = errors + 1;
        $display("%0s: FAIL total beats = %0d (expect %0d — stray samples)", name, tot, NUM_PKT * N_OUT_EXP);
      end
    end
  endtask

  initial begin
    aresetn = 0;
    repeat (5) @(posedge clk);
    aresetn = 1;

    // Wait until every DUT has closed NUM_PKT packets (or timeout = deadlock).
    i = 0;
    while (i < TIMEOUT && !(col_v1r.pkt >= NUM_PKT && col_v1s.pkt >= NUM_PKT
                         && col_v2r.pkt >= NUM_PKT && col_v2s.pkt >= NUM_PKT)) begin
      @(posedge clk);
      i = i + 1;
    end
    // Extra drain window to expose late stray beats after the 2nd packet.
    repeat (400) @(posedge clk);

    $display("--- multi-packet results after %0d cycles (%0d packets x %0d in) ---", cyc, NUM_PKT, N_IN);
    $display("v1 ref   : pkts=%0d len=[%0d,%0d] total=%0d", col_v1r.pkt, col_v1r.pkt_len[0], col_v1r.pkt_len[1], col_v1r.total);
    $display("v1 stress: pkts=%0d len=[%0d,%0d] total=%0d", col_v1s.pkt, col_v1s.pkt_len[0], col_v1s.pkt_len[1], col_v1s.total);
    $display("v2 ref   : pkts=%0d len=[%0d,%0d] total=%0d", col_v2r.pkt, col_v2r.pkt_len[0], col_v2r.pkt_len[1], col_v2r.total);
    $display("v2 stress: pkts=%0d len=[%0d,%0d] total=%0d", col_v2s.pkt, col_v2s.pkt_len[0], col_v2s.pkt_len[1], col_v2s.total);

    check_scalars("v1 ref   ", col_v1r.pkt, col_v1r.pkt_len[0], col_v1r.pkt_len[1], col_v1r.total);
    check_scalars("v1 stress", col_v1s.pkt, col_v1s.pkt_len[0], col_v1s.pkt_len[1], col_v1s.total);
    check_scalars("v2 ref   ", col_v2r.pkt, col_v2r.pkt_len[0], col_v2r.pkt_len[1], col_v2r.total);
    check_scalars("v2 stress", col_v2s.pkt, col_v2s.pkt_len[0], col_v2s.pkt_len[1], col_v2s.total);

    // packet2 == packet1 (no contamination / phase drift) — the check the old single-packet TB could not do.
    for (i = 0; i < N_OUT_EXP; i = i + 1) begin
      if (col_v1r.pkt_mem[1][i] !== col_v1r.pkt_mem[0][i]) begin
        errors = errors + 1;
        $display("v1 ref   : FAIL packet2 != packet1 at out[%0d]: p1=%0d p2=%0d", i, col_v1r.pkt_mem[0][i], col_v1r.pkt_mem[1][i]);
        i = N_OUT_EXP;
      end
    end
    for (i = 0; i < N_OUT_EXP; i = i + 1) begin
      if (col_v1s.pkt_mem[1][i] !== col_v1s.pkt_mem[0][i]) begin
        errors = errors + 1;
        $display("v1 stress: FAIL packet2 != packet1 at out[%0d]: p1=%0d p2=%0d", i, col_v1s.pkt_mem[0][i], col_v1s.pkt_mem[1][i]);
        i = N_OUT_EXP;
      end
    end
    for (i = 0; i < N_OUT_EXP; i = i + 1) begin
      if (col_v2r.pkt_mem[1][i] !== col_v2r.pkt_mem[0][i]) begin
        errors = errors + 1;
        $display("v2 ref   : FAIL packet2 != packet1 at out[%0d]: p1=%0d p2=%0d", i, col_v2r.pkt_mem[0][i], col_v2r.pkt_mem[1][i]);
        i = N_OUT_EXP;
      end
    end
    for (i = 0; i < N_OUT_EXP; i = i + 1) begin
      if (col_v2s.pkt_mem[1][i] !== col_v2s.pkt_mem[0][i]) begin
        errors = errors + 1;
        $display("v2 stress: FAIL packet2 != packet1 at out[%0d]: p1=%0d p2=%0d", i, col_v2s.pkt_mem[0][i], col_v2s.pkt_mem[1][i]);
        i = N_OUT_EXP;
      end
    end

    // Bonus cross-checks: stress must match its reference, and v1 must match v2.
    for (i = 0; i < N_OUT_EXP; i = i + 1) begin
      if (col_v1s.pkt_mem[0][i] !== col_v1r.pkt_mem[0][i]) begin
        errors = errors + 1;
        $display("v1: FAIL stress != ref at out[%0d]: ref=%0d stress=%0d", i, col_v1r.pkt_mem[0][i], col_v1s.pkt_mem[0][i]);
        i = N_OUT_EXP;
      end
    end
    for (i = 0; i < N_OUT_EXP; i = i + 1) begin
      if (col_v2s.pkt_mem[0][i] !== col_v2r.pkt_mem[0][i]) begin
        errors = errors + 1;
        $display("v2: FAIL stress != ref at out[%0d]: ref=%0d stress=%0d", i, col_v2r.pkt_mem[0][i], col_v2s.pkt_mem[0][i]);
        i = N_OUT_EXP;
      end
    end
    for (i = 0; i < N_OUT_EXP; i = i + 1) begin
      if (col_v1r.pkt_mem[0][i] !== col_v2r.pkt_mem[0][i]) begin
        errors = errors + 1;
        $display("v1/v2 REF MISMATCH at out[%0d]: v1=%0d v2=%0d", i, col_v1r.pkt_mem[0][i], col_v2r.pkt_mem[0][i]);
        i = N_OUT_EXP;
      end
    end

    if (errors == 0)
      $display("RESULT: PASS — 2 packets, no drops/deadlock/stray, TLAST per packet, packet2==packet1");
    else
      $display("RESULT: FAIL — %0d errors", errors);
    $finish;
  end

endmodule
