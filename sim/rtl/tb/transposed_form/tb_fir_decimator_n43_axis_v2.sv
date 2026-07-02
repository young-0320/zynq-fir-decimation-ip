`timescale 1ns / 1ps
`default_nettype none

module tb_fir_decimator_n43_axis_v2;

  localparam integer CLK_HALF = 5;
  localparam integer IN_LEN   = 8192;
  localparam integer EXP_LEN  = 4096;   // 8192 inputs / M=2 = 4096 outputs
  localparam integer DRAIN_TO = 10000;

  reg  aclk;
  reg  aresetn;

  reg  s_axis_tvalid;
  wire s_axis_tready;
  reg  signed [15:0] s_axis_tdata;
  reg  s_axis_tlast_in;

  wire               m_axis_tvalid;
  reg                m_axis_tready;
  wire signed [15:0] m_axis_tdata;
  wire               m_axis_tlast;

  reg [15:0] input_mem[0:IN_LEN-1];
  reg [15:0] exp_mem[0:EXP_LEN-1];

  int     expected_q[$];
  int     obs_cnt;
  int     timeout_cnt;
  int     exp_val;
  int     bp_prob = 30;
  reg     bp_en;
  integer check_mode;

  fir_decimator_n43_axis_v2 dut (
      .aclk         (aclk),
      .aresetn      (aresetn),
      .s_axis_tvalid(s_axis_tvalid),
      .s_axis_tready(s_axis_tready),
      .s_axis_tdata (s_axis_tdata),
      .s_axis_tlast (s_axis_tlast_in),
      .m_axis_tvalid(m_axis_tvalid),
      .m_axis_tready(m_axis_tready),
      .m_axis_tdata (m_axis_tdata),
      .m_axis_tlast (m_axis_tlast)
  );

  initial begin
    aclk = 1'b0;
    forever #(CLK_HALF) aclk = ~aclk;
  end

  always @(posedge aclk) begin
    if (!aresetn)   m_axis_tready <= 1'b0;
    else if (bp_en) m_axis_tready <= ($urandom_range(0, 99) < bp_prob);
    else            m_axis_tready <= 1'b1;
  end

  // watchdog: 3000 cycles without any output handshake → deadlock
  always @(posedge aclk) begin
    if (!aresetn) begin
      timeout_cnt <= 0;
    end else begin
      timeout_cnt <= (m_axis_tvalid && m_axis_tready) ? 0 : timeout_cnt + 1;
      if (timeout_cnt > 3000) begin
        $display("FATAL tb_fir_decimator_n43_axis_v2: watchdog timeout — deadlock at obs_cnt=%0d", obs_cnt);
        $fatal(1);
      end
    end
  end

  // scoreboard: fires on every output handshake
  always @(posedge aclk) begin
    if (aresetn && m_axis_tvalid && m_axis_tready) begin
      if (check_mode >= 1) begin
        if (expected_q.size() == 0) begin
          $display("FAIL tb_fir_decimator_n43_axis_v2: extra output at obs_cnt=%0d data=%0d",
                   obs_cnt, $signed(m_axis_tdata));
          $fatal(1);
        end
        exp_val = expected_q.pop_front();
        if ($signed(m_axis_tdata) !== $signed(exp_val)) begin
          $display("FAIL tb_fir_decimator_n43_axis_v2: idx=%0d actual=%0d expected=%0d",
                   obs_cnt, $signed(m_axis_tdata), $signed(exp_val));
          $fatal(1);
        end
      end
      if (check_mode >= 2) begin
        // TLAST must be asserted on the last output sample and nowhere else
        if (obs_cnt == EXP_LEN - 1 && !m_axis_tlast) begin
          $display("FAIL tb_fir_decimator_n43_axis_v2: missing TLAST at obs_cnt=%0d", obs_cnt);
          $fatal(1);
        end
        if (obs_cnt < EXP_LEN - 1 && m_axis_tlast) begin
          $display("FAIL tb_fir_decimator_n43_axis_v2: unexpected TLAST at obs_cnt=%0d", obs_cnt);
          $fatal(1);
        end
      end
      obs_cnt++;
    end
  end

  task automatic do_reset();
    aresetn         = 1'b0;
    s_axis_tvalid   = 1'b0;
    s_axis_tdata    = 16'sd0;
    s_axis_tlast_in = 1'b0;
    obs_cnt         = 0;
    expected_q.delete();
    repeat (4) @(negedge aclk);
    aresetn = 1'b1;
    @(negedge aclk);
  endtask

  // Drive one sample. Clears tlast during any bubble interval.
  task automatic drive_one(input logic signed [15:0] sample, input int max_bubble,
                           input logic tlast);
    if (max_bubble > 0) begin
      @(negedge aclk);
      s_axis_tvalid   = 1'b0;
      s_axis_tlast_in = 1'b0;
      repeat ($urandom_range(0, max_bubble)) @(posedge aclk);
    end
    @(negedge aclk);
    s_axis_tdata    = sample;
    s_axis_tvalid   = 1'b1;
    s_axis_tlast_in = tlast;
    @(posedge aclk);
    while (!s_axis_tready) @(posedge aclk);
  endtask

  // Drive exactly IN_LEN samples; asserts tlast on the last sample only.
  // Hardware auto-flush takes over after tlast — no manual zeros needed.
  task automatic drive_packet(input int max_bubble);
    for (int i = 0; i < IN_LEN; i++)
      drive_one($signed(input_mem[i]), max_bubble, (i == IN_LEN - 1));
    @(negedge aclk);
    s_axis_tvalid   = 1'b0;
    s_axis_tlast_in = 1'b0;
  endtask

  task automatic drain_and_check();
    int d = 0;
    while (expected_q.size() > 0 && d < DRAIN_TO) begin
      @(posedge aclk);
      d++;
    end
    if (expected_q.size() != 0) begin
      $display("FAIL tb_fir_decimator_n43_axis_v2: missing %0d outputs after %0d drain cycles.",
               expected_q.size(), d);
      $fatal(1);
    end
  endtask

  initial begin
    $readmemh("sim/vectors/transposed_form/n43/input_q15.hex",         input_mem);
    $readmemh("sim/vectors/transposed_form/n43/expected_decim_q15.hex", exp_mem);

    bp_en      = 1'b0;
    check_mode = 0;

    // S1: TREADY=1, verify data values and TLAST position
    check_mode = 2;
    bp_en      = 1'b0;
    do_reset();
    for (int i = 0; i < EXP_LEN; i++) expected_q.push_back($signed(exp_mem[i]));
    drive_packet(0);
    drain_and_check();
    $display("PASS [S1] TREADY=1 data+TLAST: %0d samples", obs_cnt);

    // S2: 30% downstream backpressure + upstream bubbles, verify data and TLAST
    check_mode = 2;
    bp_en      = 1'b1;
    do_reset();
    for (int i = 0; i < EXP_LEN; i++) expected_q.push_back($signed(exp_mem[i]));
    drive_packet(3);
    drain_and_check();
    bp_en = 1'b0;
    $display("PASS [S2] Random Backpressure + Bubble: %0d samples", obs_cnt);

    // S3: mid-stream reset; full packet after reset must produce correct output + TLAST
    check_mode = 0;
    bp_en      = 1'b0;
    do_reset();
    for (int i = 0; i < 200; i++) drive_one($signed(input_mem[i]), 0, 1'b0);
    @(negedge aclk);
    s_axis_tvalid = 1'b0;
    aresetn       = 1'b0;
    repeat (4) @(negedge aclk);
    aresetn = 1'b1;

    check_mode = 2;
    do_reset();
    for (int i = 0; i < EXP_LEN; i++) expected_q.push_back($signed(exp_mem[i]));
    drive_packet(1);
    drain_and_check();
    $display("PASS [S3] Reset Recovery: %0d samples", obs_cnt);

    $display("PASS tb_fir_decimator_n43_axis_v2: all scenarios");
    $finish;
  end

endmodule

`default_nettype wire
