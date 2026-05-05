`timescale 1ns / 1ps
`default_nettype none

module tb_fir_decimator_n43;

  localparam integer CLK_HALF  = 5;
  localparam integer INPUT_LEN = 8192;
  localparam integer FLUSH_LEN = 42;
  localparam integer EXP_LEN   = 4117;
  localparam integer DRAIN_TO  = 200;

  reg clk;
  reg rst;
  reg in_valid;
  reg signed [15:0] in_sample;
  wire out_valid;
  wire signed [15:0] out_sample;

  reg [15:0] input_mem[0:INPUT_LEN-1];
  reg [15:0] expected_mem[0:EXP_LEN-1];

  int expected_q[$];
  int obs_cnt;
  int cycle_cnt;
  int timeout_cnt;
  int exp_val;

  fir_decimator_n43 dut (
      .clk      (clk),
      .rst      (rst),
      .in_valid (in_valid),
      .in_sample(in_sample),
      .out_valid(out_valid),
      .out_sample(out_sample)
  );

  initial begin
    clk = 1'b0;
    forever #(CLK_HALF) clk = ~clk;
  end

  always @(posedge clk) begin
    if (rst) begin
      timeout_cnt <= 0;
    end else begin
      timeout_cnt <= (out_valid || in_valid) ? 0 : timeout_cnt + 1;
      if (timeout_cnt > 1000) begin
        $display("FATAL tb_fir_decimator_n43: watchdog timeout.");
        $fatal(1);
      end
    end
  end

  always @(posedge clk) begin
    if (!rst) begin
      cycle_cnt++;
      if (out_valid) begin
        if (expected_q.size() == 0) begin
          $display("FAIL tb_fir_decimator_n43: extra output at cycle=%0d actual=%0d",
                   cycle_cnt, $signed(out_sample));
          $fatal(1);
        end
        exp_val = expected_q.pop_front();
        if ($signed(out_sample) !== $signed(exp_val)) begin
          $display("FAIL tb_fir_decimator_n43: idx=%0d cycle=%0d actual=%0d expected=%0d",
                   obs_cnt, cycle_cnt, $signed(out_sample), $signed(exp_val));
          $fatal(1);
        end
        obs_cnt++;
      end
    end
  end

  task automatic drive_sample(input logic signed [15:0] sample, input int max_bubble);
    if (max_bubble > 0) begin
      @(negedge clk);
      in_valid = 1'b0;
      repeat ($urandom_range(0, max_bubble)) @(negedge clk);
    end
    @(negedge clk);
    in_valid  = 1'b1;
    in_sample = sample;
  endtask

  task automatic drain_and_check();
    int d = 0;
    while (expected_q.size() > 0 && d < DRAIN_TO) begin
      @(posedge clk);
      d++;
    end
    if (expected_q.size() != 0) begin
      $display("FAIL tb_fir_decimator_n43: missing %0d outputs after %0d drain cycles.",
               expected_q.size(), d);
      $fatal(1);
    end
  endtask

  task automatic run_scenario(input int max_bubble);
    for (int i = 0; i < EXP_LEN; i++) expected_q.push_back($signed(expected_mem[i]));
    for (int i = 0; i < INPUT_LEN; i++) drive_sample($signed(input_mem[i]), max_bubble);
    for (int i = 0; i < FLUSH_LEN; i++) drive_sample(16'sd0, max_bubble);
    @(negedge clk);
    in_valid = 1'b0;
    drain_and_check();
  endtask

  initial begin
    $readmemh("sim/vectors/transposed_form/n43/input_q15.hex",         input_mem);
    $readmemh("sim/vectors/transposed_form/n43/expected_decim_q15.hex", expected_mem);

    // S1: Happy Path
    rst = 1'b1; in_valid = 1'b0; in_sample = 16'sd0;
    cycle_cnt = 0; obs_cnt = 0;
    expected_q.delete();
    repeat (3) @(negedge clk);
    rst = 1'b0;
    run_scenario(0);
    $display("PASS [S1] Happy Path: %0d samples", obs_cnt);

    // S2: Random Bubble Stress
    rst = 1'b1; in_valid = 1'b0;
    cycle_cnt = 0; obs_cnt = 0;
    expected_q.delete();
    repeat (3) @(negedge clk);
    rst = 1'b0;
    run_scenario(3);
    $display("PASS [S2] Random Bubble: %0d samples", obs_cnt);

    $finish;
  end

endmodule

`default_nettype wire
