`timescale 1ns / 1ps
`default_nettype none

module bringup_output_checker #(
    parameter integer EXPECTED_LEN   = 4098,
    parameter integer DRAIN_TIMEOUT  = 64,
    parameter MEM_FILE = "sim/vectors/direct_form/bringup_n5/expected_decim_q15.hex"
) (
    input  wire               clk,
    input  wire               rst,
    input  wire               source_done,
    input  wire               in_valid,
    input  wire signed [15:0] in_sample,
    output reg                done,
    output reg                pass,
    output reg                fail,
    output reg                mismatch_seen
);

    localparam integer COUNT_W = (EXPECTED_LEN < 1) ? 1 : $clog2(EXPECTED_LEN + 1);
    localparam integer DRAIN_W = (DRAIN_TIMEOUT < 1) ? 1 : $clog2(DRAIN_TIMEOUT + 1);
    localparam [COUNT_W-1:0] EXPECTED_LEN_W = EXPECTED_LEN;

    reg [15:0] expected_mem [0:EXPECTED_LEN-1];
    reg [COUNT_W-1:0] observed_count;
    reg [COUNT_W-1:0] observed_count_n;
    reg [DRAIN_W-1:0] drain_count;
    reg [DRAIN_W-1:0] drain_count_n;
    reg               done_n;
    reg               pass_n;
    reg               fail_n;
    reg               mismatch_seen_n;

    integer i;

    initial begin
        for (i = 0; i < EXPECTED_LEN; i = i + 1) begin
            expected_mem[i] = 16'h0000;
        end

        $readmemh(MEM_FILE, expected_mem);
    end

    always @* begin
        observed_count_n = observed_count;
        drain_count_n    = drain_count;
        done_n           = done;
        pass_n           = pass;
        fail_n           = fail;
        mismatch_seen_n  = mismatch_seen;

        if (!done) begin
            if (in_valid) begin
                if (observed_count < EXPECTED_LEN_W) begin
                    if (in_sample !== $signed(expected_mem[observed_count])) begin
                        done_n          = 1'b1;
                        pass_n          = 1'b0;
                        fail_n          = 1'b1;
                        mismatch_seen_n = 1'b1;
                    end else begin
                        observed_count_n = observed_count + {{(COUNT_W-1){1'b0}}, 1'b1};
                    end
                end else begin
                    done_n          = 1'b1;
                    pass_n          = 1'b0;
                    fail_n          = 1'b1;
                    mismatch_seen_n = 1'b1;
                end
            end

            if (!done_n) begin
                if (source_done) begin
                    if ((DRAIN_TIMEOUT <= 1) || (drain_count == DRAIN_TIMEOUT - 1)) begin
                        done_n = 1'b1;
                        if ((observed_count_n == EXPECTED_LEN_W) && !mismatch_seen_n) begin
                            pass_n = 1'b1;
                            fail_n = 1'b0;
                        end else begin
                            pass_n = 1'b0;
                            fail_n = 1'b1;
                        end
                    end else begin
                        drain_count_n = drain_count + {{(DRAIN_W-1){1'b0}}, 1'b1};
                    end
                end else begin
                    drain_count_n = {DRAIN_W{1'b0}};
                end
            end
        end
    end

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            observed_count <= {COUNT_W{1'b0}};
            drain_count    <= {DRAIN_W{1'b0}};
            done           <= 1'b0;
            pass           <= 1'b0;
            fail           <= 1'b0;
            mismatch_seen  <= 1'b0;
        end else begin
            observed_count <= observed_count_n;
            drain_count    <= drain_count_n;
            done           <= done_n;
            pass           <= pass_n;
            fail           <= fail_n;
            mismatch_seen  <= mismatch_seen_n;
        end
    end

endmodule

`default_nettype wire
