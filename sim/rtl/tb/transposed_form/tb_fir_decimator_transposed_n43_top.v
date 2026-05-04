`timescale 1ns / 1ps
`default_nettype none

module tb_fir_decimator_transposed_n43_top;

    localparam integer CLK_HALF_PERIOD_NS = 5;
    localparam integer INPUT_LEN          = 8192;
    localparam integer FLUSH_LEN          = 42;
    localparam integer EXPECTED_LEN       = 4117;
    localparam integer DRAIN_TIMEOUT      = 64;

    reg clk;
    reg rst;
    reg in_valid;
    reg signed [15:0] in_sample;
    wire out_valid;
    wire signed [15:0] out_sample;

    reg [15:0] input_mem [0:INPUT_LEN-1];
    reg [15:0] expected_mem [0:EXPECTED_LEN-1];

    integer cycle_count;
    integer observed_count;
    integer drive_idx;
    integer drain_cycles;
    reg signed [15:0] expected_sample;

    fir_decimator_transposed_n43_top dut (
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
                    $display("FAIL tb_fir_decimator_transposed_n43_top: extra output at cycle=%0d actual=%0d (0x%04h)", cycle_count, out_sample, out_sample);
                    $fatal(1);
                end

                expected_sample = $signed(expected_mem[observed_count]);
                if (out_sample !== expected_sample) begin
                    $display(
                        "FAIL tb_fir_decimator_transposed_n43_top: sample_idx=%0d cycle=%0d actual=%0d (0x%04h) expected=%0d (0x%04h)",
                        observed_count,
                        cycle_count,
                        out_sample,
                        out_sample,
                        expected_sample,
                        expected_sample
                    );
                    $fatal(1);
                end

                observed_count = observed_count + 1;
            end
        end
    end

    initial begin
        $readmemh("sim/vectors/transposed_form/n43/input_q15.hex", input_mem);
        $readmemh("sim/vectors/transposed_form/n43/expected_decim_q15.hex", expected_mem);

        rst            = 1'b1;
        in_valid       = 1'b0;
        in_sample      = 16'sd0;
        cycle_count    = 0;
        observed_count = 0;
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
        in_valid  = 1'b0;
        in_sample = 16'sd0;

        drain_cycles = 0;
        while ((observed_count < EXPECTED_LEN) && (drain_cycles < DRAIN_TIMEOUT)) begin
            @(posedge clk);
            drain_cycles = drain_cycles + 1;
        end

        if (observed_count != EXPECTED_LEN) begin
            $display(
                "FAIL tb_fir_decimator_transposed_n43_top: expected %0d samples but observed %0d after %0d drain cycles",
                EXPECTED_LEN,
                observed_count,
                drain_cycles
            );
            $fatal(1);
        end

        $display("PASS tb_fir_decimator_transposed_n43_top: observed %0d samples", observed_count);
        $finish;
    end

endmodule

`default_nettype wire
/*
`timescale 1ns / 1ps
`default_nettype none

module tb_fir_decimator_transposed_n43_top;

    localparam integer CLK_HALF_PERIOD_NS = 5;
    localparam integer INPUT_LEN          = 8192;
    localparam integer FLUSH_LEN          = 42;
    localparam integer EXPECTED_LEN       = 4117;
    localparam integer DRAIN_TIMEOUT      = 64;

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

    fir_decimator_transposed_n43_top dut (
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

    // --- Scoreboard Monitor ---
    always @(posedge clk) begin
        if (!rst) begin
            cycle_count++;
            if (out_valid) begin
                if (expected_q.size() == 0) begin
                    $display("FAIL: Extra output at cycle=%0d", cycle_count);
                    $fatal(1);
                end

                int expected_val = expected_q.pop_front();
                if ($signed(out_sample) !== $signed(expected_val)) begin
                    $display("FAIL: Mismatch at obs=%0d actual=%0d exp=%0d", 
                             observed_count, $signed(out_sample), $signed(expected_val));
                    $fatal(1);
                end
                observed_count++;
            end
        end
    end

    // --- Dynamic Drive Task ---
    task automatic drive_sample(input signed [15:0] sample, input int max_bubble);
        begin
            // 무작위 Bubble 주입
            if (max_bubble > 0) begin
                @(negedge clk);
                in_valid = 1'b0; // Bubble 구간 동안 invalid 처리
                repeat($urandom_range(0, max_bubble)) @(negedge clk);
            end

            // 데이터 인가
            @(negedge clk);
            in_valid  = 1'b1;
            in_sample = sample;
        end
    endtask

    initial begin
        $display("Start Testbench (Seed: %0d)", $get_initial_random_seed());
        $readmemh("sim/vectors/transposed_form/n43/input_q15.hex", input_mem);
        $readmemh("sim/vectors/transposed_form/n43/expected_decim_q15.hex", expected_mem);

        // --- 시나리오 1: Happy Path (버블 없음) ---
        rst            = 1'b1;
        in_valid       = 1'b0;
        in_sample      = 16'sd0;
        cycle_count    = 0;
        observed_count = 0;
        expected_q.delete();
        repeat (3) @(negedge clk);
        rst = 1'b0;

        for (int i=0; i<EXPECTED_LEN; i++) expected_q.push_back(expected_mem[i]);
        
        for (int i=0; i<INPUT_LEN; i++) drive_sample($signed(input_mem[i]), 0);
        for (int i=0; i<FLUSH_LEN; i++) drive_sample(16'sd0, 0);
        
        @(negedge clk);
        in_valid = 1'b0;
        while (expected_q.size() > 0) @(posedge clk);
        $display("PASS [S1] Happy Path: %0d samples", observed_count);

        // --- 시나리오 2: Bubble 주입 (랜덤 입력 지연) ---
        rst = 1'b1;
        in_valid = 1'b0;
        observed_count = 0;
        expected_q.delete();
        repeat (3) @(negedge clk);
        rst = 1'b0;

        for (int i=0; i<EXPECTED_LEN; i++) expected_q.push_back(expected_mem[i]);
        
        for (int i=0; i<INPUT_LEN; i++) drive_sample($signed(input_mem[i]), 3); // 0~3 무작위 딜레이
        for (int i=0; i<FLUSH_LEN; i++) drive_sample(16'sd0, 3);
        
        @(negedge clk);
        in_valid = 1'b0;
        while (expected_q.size() > 0) @(posedge clk);
        $display("PASS [S2] Random Bubble: %0d samples", observed_count);

        $finish;
    end
endmodule
`default_nettype wire
*/