`timescale 1ns / 1ps
`default_nettype none

module decimator_m2_phase0 (
    input  wire               clk,
    input  wire               rst,
    input  wire               in_valid,
    input  wire signed [15:0] in_sample,
    output reg                out_valid,
    output reg  signed [15:0] out_sample
);

    reg keep_next;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            keep_next  <= 1'b1;
            out_valid  <= 1'b0;
            out_sample <= 16'sd0;
        end else begin
            if (in_valid) begin
                if (keep_next) begin
                    out_valid  <= 1'b1;
                    out_sample <= in_sample;
                end else begin
                    out_valid <= 1'b0;
                end

                keep_next <= ~keep_next;
            end else begin
                out_valid <= 1'b0;
            end
        end
    end

endmodule

`default_nettype wire
