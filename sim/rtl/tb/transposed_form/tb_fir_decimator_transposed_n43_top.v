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
