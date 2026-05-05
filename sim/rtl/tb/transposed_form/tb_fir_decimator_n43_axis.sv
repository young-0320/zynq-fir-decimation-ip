`timescale 1ns / 1ps
`default_nettype none

module tb_fir_decimator_n43_axis;

  localparam integer CLK_HALF  = 5;
  localparam integer TLAST_N   = 512;
  localparam integer IN_LEN    = 8192;
  localparam integer FLUSH_LEN = 42;
  localparam integer EXP_LEN   = 4117;
  localparam integer DRAIN_TO  = 200;

  reg  aclk;
  reg  aresetn;

  reg  s_axis_tvalid;
  wire s_axis_tready;
  reg  signed [15:0] s_axis_tdata;
  reg  s_axis_tlast_in;

  wire        m_axis_tvalid;
  reg         m_axis_tready;
  wire signed [15:0] m_axis_tdata;
  wire        m_axis_tlast;

  reg [15:0] input_mem[0:IN_LEN-1];
  reg [15:0] exp_mem[0:EXP_LEN-1];

  int expected_q[$];
  int obs_cnt;
  int timeout_cnt;
  int exp_val;
  int  bp_prob = 30;
  reg  bp_en;
  integer check_mode;

  fir_decimator_n43_axis #(.TLAST_N(TLAST_N)) dut (
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

  // 무작위 TREADY: bp_en=1이면 bp_prob% 확률로 1
  always @(posedge aclk) begin
    if (!aresetn) begin
      m_axis_tready <= 1'b0;
    end else if (bp_en) begin
      m_axis_tready <= ($urandom_range(0, 99) < bp_prob);
    end else begin
      m_axis_tready <= 1'b1;
    end
  end

  // 워치독: 전송 성사 없이 1000 사이클 초과 시 deadlock 판정
  always @(posedge aclk) begin
    if (!aresetn) begin
      timeout_cnt <= 0;
    end else begin
      timeout_cnt <= (m_axis_tvalid && m_axis_tready) ? 0 : timeout_cnt + 1;
      if (timeout_cnt > 1000) begin
        $display("FATAL tb_fir_decimator_n43_axis: watchdog timeout — deadlock detected.");
        $fatal(1);
      end
    end
  end

  // 스코어보드: 핸드셰이크 성사 시점에만 검증
  always @(posedge aclk) begin
    if (aresetn && m_axis_tvalid && m_axis_tready) begin
      if (check_mode >= 1) begin
        if (expected_q.size() == 0) begin
          $display("FAIL tb_fir_decimator_n43_axis: extra output at obs_cnt=%0d data=%0d",
                   obs_cnt, $signed(m_axis_tdata));
          $fatal(1);
        end
        exp_val = expected_q.pop_front();
        if ($signed(m_axis_tdata) !== $signed(exp_val)) begin
          $display("FAIL tb_fir_decimator_n43_axis: idx=%0d actual=%0d expected=%0d",
                   obs_cnt, $signed(m_axis_tdata), $signed(exp_val));
          $fatal(1);
        end
      end
      if (check_mode >= 2) begin
        if (((obs_cnt + 1) % TLAST_N == 0) && !m_axis_tlast) begin
          $display("FAIL tb_fir_decimator_n43_axis: missing TLAST at obs_cnt=%0d", obs_cnt);
          $fatal(1);
        end
        if (((obs_cnt + 1) % TLAST_N != 0) && m_axis_tlast) begin
          $display("FAIL tb_fir_decimator_n43_axis: unexpected TLAST at obs_cnt=%0d", obs_cnt);
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

  // negedge 앵커: deassert와 data 셋업 모두 negedge에서 수행
  task automatic drive_one(input logic signed [15:0] sample, input int max_bubble);
    if (max_bubble > 0) begin
      @(negedge aclk);
      s_axis_tvalid = 1'b0;
      repeat ($urandom_range(0, max_bubble)) @(posedge aclk);
    end
    @(negedge aclk);
    s_axis_tdata  = sample;
    s_axis_tvalid = 1'b1;
    @(posedge aclk);
    while (!s_axis_tready) @(posedge aclk);
  endtask

  task automatic drive_all_samples(input int max_bubble);
    for (int i = 0; i < IN_LEN; i++)
      drive_one($signed(input_mem[i]), max_bubble);
    for (int i = 0; i < FLUSH_LEN; i++)
      drive_one(16'sd0, max_bubble);
    @(negedge aclk);
    s_axis_tvalid = 1'b0;
  endtask

  task automatic drain_and_check();
    int d = 0;
    while (expected_q.size() > 0 && d < DRAIN_TO) begin
      @(posedge aclk);
      d++;
    end
    if (expected_q.size() != 0) begin
      $display("FAIL tb_fir_decimator_n43_axis: missing %0d outputs after %0d drain cycles.",
               expected_q.size(), d);
      $fatal(1);
    end
  endtask

  initial begin
    $readmemh("sim/vectors/transposed_form/n43/input_q15.hex",         input_mem);
    $readmemh("sim/vectors/transposed_form/n43/expected_decim_q15.hex", exp_mem);

    bp_en      = 1'b0;
    check_mode = 0;

    // S1: TREADY=1 고정, 데이터 + TLAST 검증
    check_mode = 2;
    bp_en      = 1'b0;
    do_reset();
    for (int i = 0; i < EXP_LEN; i++) expected_q.push_back($signed(exp_mem[i]));
    drive_all_samples(0);
    drain_and_check();
    $display("PASS [S1] TREADY=1 data+TLAST: %0d samples", obs_cnt);

    // S2: 무작위 백프레셔(30% accept) + 입력 버블, 데이터+TLAST 검증
    check_mode = 2;
    bp_en      = 1'b1;
    do_reset();
    for (int i = 0; i < EXP_LEN; i++) expected_q.push_back($signed(exp_mem[i]));
    drive_all_samples(3);
    drain_and_check();
    bp_en = 1'b0;
    $display("PASS [S2] Random Backpressure + Bubble: %0d samples", obs_cnt);

    // S3: 동작 중 aresetn 인가 후 재구동, 정상 출력 확인
    check_mode = 0;
    bp_en      = 1'b0;
    do_reset();
    for (int i = 0; i < 200; i++) drive_one($signed(input_mem[i]), 0);
    @(negedge aclk);
    s_axis_tvalid = 1'b0;
    aresetn = 1'b0;
    repeat (4) @(negedge aclk);
    aresetn = 1'b1;

    check_mode = 1;
    do_reset();
    for (int i = 0; i < EXP_LEN; i++) expected_q.push_back($signed(exp_mem[i]));
    drive_all_samples(1);
    drain_and_check();
    $display("PASS [S3] Reset Recovery: %0d samples", obs_cnt);

    $display("PASS tb_fir_decimator_n43_axis: all scenarios");
    $finish;
  end

endmodule

`default_nettype wire
