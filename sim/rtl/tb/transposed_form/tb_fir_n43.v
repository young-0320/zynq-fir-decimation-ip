`timescale 1ns / 1ps
`default_nettype none

module tb_fir_n43;

  localparam integer CLK_HALF_PERIOD_NS = 5;
  localparam integer INPUT_LEN = 8192;
  localparam integer FLUSH_LEN = 42;
  localparam integer EXPECTED_LEN = 8234;
  localparam integer DRAIN_TIMEOUT = 64;

  reg clk;
  reg rst;
  reg in_valid;
  reg signed [15:0] in_sample;
  wire out_valid;
  wire signed [15:0] out_sample;

  reg [15:0] input_mem[0:INPUT_LEN-1];
  reg [15:0] expected_mem[0:EXPECTED_LEN-1];

  integer cycle_count;
  integer observed_count;
  integer drive_idx;
  integer drain_cycles;
  reg signed [15:0] expected_sample;

  fir_n43 dut (
      .clk(clk),
      .rst(rst),
      .in_valid(in_valid),
      .in_sample(in_sample),
      .out_valid(out_valid),
      .out_sample(out_sample)
  );

  initial begin
    clk = 1'b0;
    forever #(CLK_HALF_PERIOD_NS) clk = ~clk;
  end

  task automatic drive_sample;
    input signed [15:0] sample;
    begin
      @(negedge clk);
      in_valid  = 1'b1;
      in_sample = sample;
    end
  endtask

  always @(posedge clk) begin
    if (!rst) begin
      cycle_count = cycle_count + 1;

      if (out_valid) begin
        if (observed_count >= EXPECTED_LEN) begin
          $display("FAIL tb_fir_n43: extra output at cycle=%0d actual=%0d (0x%04h)",
                   cycle_count, out_sample, out_sample);
          $fatal(1);
        end

        expected_sample = $signed(expected_mem[observed_count]);
        if (out_sample !== expected_sample) begin
          $display(
              "FAIL tb_fir_n43: sample_idx=%0d cycle=%0d actual=%0d (0x%04h) expected=%0d (0x%04h)",
              observed_count, cycle_count, out_sample, out_sample, expected_sample,
              expected_sample);
          $fatal(1);
        end

        observed_count = observed_count + 1;
      end
    end
  end

  initial begin
    $readmemh("sim/vectors/transposed_form/n43/input_q15.hex", input_mem);
    $readmemh("sim/vectors/transposed_form/n43/expected_fir_q15.hex", expected_mem);

    rst             = 1'b1;
    in_valid        = 1'b0;
    in_sample       = 16'sd0;
    cycle_count     = 0;
    observed_count  = 0;
    expected_sample = 16'sd0;

    repeat (3) @(negedge clk);
    rst = 1'b0;

    for (drive_idx = 0; drive_idx < INPUT_LEN; drive_idx = drive_idx + 1) begin
      drive_sample($signed(input_mem[drive_idx]));
    end

    for (drive_idx = 0; drive_idx < FLUSH_LEN; drive_idx = drive_idx + 1) begin
      drive_sample(16'sd0);
    end

    @(negedge clk);
    in_valid = 1'b0;
    in_sample = 16'sd0;

    drain_cycles = 0;
    while ((observed_count < EXPECTED_LEN) && (drain_cycles < DRAIN_TIMEOUT)) begin
      @(posedge clk);
      drain_cycles = drain_cycles + 1;
    end

    if (observed_count != EXPECTED_LEN) begin
      $display(
          "FAIL tb_fir_n43: expected %0d samples but observed %0d after %0d drain cycles",
          EXPECTED_LEN, observed_count, drain_cycles);
      $fatal(1);
    end

    $display("PASS tb_fir_n43: observed %0d samples", observed_count);
    $finish;
  end

endmodule

`default_nettype wire

/*
`timescale 1ns / 1ps
`default_nettype none

module tb_fir_n43;

    localparam integer CLK_HALF_PERIOD_NS = 5;
    localparam integer INPUT_LEN          = 8192;
    localparam integer FLUSH_LEN          = 42;
    localparam integer EXPECTED_LEN       = 8234;
    localparam integer DRAIN_TIMEOUT      = 200;

    reg clk;
    reg rst;
    reg in_valid;
    reg signed [15:0] in_sample;
    wire out_valid;
    wire signed [15:0] out_sample;

    reg [15:0] input_mem [0:INPUT_LEN-1];
    reg [15:0] expected_mem [0:EXPECTED_LEN-1];

    // --- SystemVerilog Queue for Scoreboard ---
    int expected_q [$];
    int observed_count;
    int cycle_count;
    int timeout_cnt;

    fir_n43 dut (
        .clk(clk),
        .rst(rst),
        .in_valid(in_valid),
        .in_sample(in_sample),
        .out_valid(out_valid),
        .out_sample(out_sample)
    );

    initial begin
        clk = 1'b0;
        forever #(CLK_HALF_PERIOD_NS) clk = ~clk;
    end

    // --- Watchdog Timer ---
    always @(posedge clk) begin
        if (!rst) begin
            if (out_valid || in_valid) timeout_cnt <= 0;
            else timeout_cnt <= timeout_cnt + 1;

            if (timeout_cnt > 1000) begin
                $display("FATAL: Watchdog Timeout! Pipeline stalled permanently.");
                $fatal(1);
            end
        end else begin
            timeout_cnt <= 0;
        end
    end

    // --- Scoreboard Monitor ---
    always @(posedge clk) begin
        if (!rst) begin
            cycle_count++;
            if (out_valid) begin
                if (expected_q.size() == 0) begin
                    $display("FAIL: Extra output at cycle=%0d, actual=%0d", cycle_count, $signed(out_sample));
                    $fatal(1);
                end

                begin
                    int expected_val = expected_q.pop_front();
                    if ($signed(out_sample) !== $signed(expected_val)) begin
                        $display("FAIL: Mismatch at obs=%0d actual=%0d exp=%0d", 
                                 observed_count, $signed(out_sample), $signed(expected_val));
                        $fatal(1);
                    end
                end
                observed_count++;
            end
        end
    end

    // --- Dynamic Drive Task ---
    task automatic drive_sample(input signed [15:0] sample, input int max_bubble);
        begin
            // 랜덤 Bubble 주입 (0 ~ max_bubble 클락 동안 in_valid = 0 유지)
            if (max_bubble > 0) begin
                in_valid <= 1'b0;
                repeat($urandom_range(0, max_bubble)) @(posedge clk);
            end

            in_sample <= sample;
            in_valid  <= 1'b1;
            @(posedge clk); // 데이터를 1클락 유지 후 리턴
        end
    endtask

    task automatic drive_all_samples(input int max_bubble);
        begin
            for (int i = 0; i < INPUT_LEN; i++) begin
                drive_sample($signed(input_mem[i]), max_bubble);
            end
            for (int i = 0; i < FLUSH_LEN; i++) begin
                drive_sample(16'sd0, max_bubble);
            end
            in_valid <= 1'b0;
        end
    endtask

    task automatic drain_and_check();
        int d = 0;
        begin
            while (expected_q.size() > 0 && d < DRAIN_TIMEOUT) begin
                @(posedge clk);
                d++;
            end
            if (expected_q.size() != 0) begin
                $display("FAIL: Missing %0d expected outputs.", expected_q.size());
                $fatal(1);
            end
        end
    endtask

    initial begin
        $display("Start Testbench (Seed: %0d)", $get_initial_random_seed());
        $readmemh("sim/vectors/transposed_form/n43/input_q15.hex", input_mem);
        $readmemh("sim/vectors/transposed_form/n43/expected_fir_q15.hex", expected_mem);

        // --- S1: Happy Path (버블 없음, 기존 tb 완벽 커버) ---
        rst            = 1'b1;
        in_valid       = 1'b0;
        in_sample      = 16'sd0;
        cycle_count    = 0;
        observed_count = 0;
        expected_q.delete();
        repeat (3) @(negedge clk);
        rst = 1'b0;

        for (int i=0; i<EXPECTED_LEN; i++) expected_q.push_back(expected_mem[i]);
        
        drive_all_samples(0); // max_bubble = 0
        drain_and_check();
        $display("PASS [S1] Happy Path: %0d samples", observed_count);

        // --- S2: Stress Test (랜덤 입력 버블 주입) ---
        rst            = 1'b1;
        in_valid       = 1'b0;
        observed_count = 0;
        expected_q.delete();
        repeat (3) @(negedge clk);
        rst = 1'b0;

        for (int i=0; i<EXPECTED_LEN; i++) expected_q.push_back(expected_mem[i]);
        
        drive_all_samples(3); // 데이터 사이에 최대 3사이클의 버블 무작위 주입
        drain_and_check();
        $display("PASS [S2] Random Bubble Stress: %0d samples", observed_count);

        $finish;
    end
endmodule
`default_nettype wire
*/
