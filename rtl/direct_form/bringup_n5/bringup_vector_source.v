`timescale 1ns / 1ps
`default_nettype none

module bringup_vector_source #(
    parameter integer INPUT_LEN = 8192,
    parameter integer FLUSH_LEN = 4,
    parameter MEM_FILE = "sim/vectors/direct_form/bringup_n5/input_q15.hex"
) (
    input  wire              clk,
    input  wire              rst,
    output reg               out_valid,
    output reg signed [15:0] out_sample,
    output reg               running,
    output reg               done
);

  localparam integer TOTAL_LEN = INPUT_LEN + FLUSH_LEN;
  localparam integer COUNT_W = (TOTAL_LEN < 1) ? 1 : $clog2(TOTAL_LEN + 1);
  localparam [COUNT_W-1:0] INPUT_LEN_W = INPUT_LEN;
  localparam [COUNT_W-1:0] TOTAL_LEN_W = TOTAL_LEN;

  reg     [COUNT_W-1:0] sample_idx;
  reg                   replay_active;
  reg     [       15:0] input_mem     [0:INPUT_LEN-1];

  integer               i;

  initial begin
    for (i = 0; i < INPUT_LEN; i = i + 1) begin
      input_mem[i] = 16'h0000;
    end

    $readmemh(MEM_FILE, input_mem);
  end

  always @(posedge clk or posedge rst) begin
    if (rst) begin
      sample_idx    <= {COUNT_W{1'b0}};
      replay_active <= 1'b0;
      out_valid     <= 1'b0;
      out_sample    <= 16'sd0;
      running       <= 1'b0;
      done          <= 1'b0;
    end else if (!replay_active && !done) begin
      replay_active <= 1'b1;
      sample_idx    <= {{(COUNT_W - 1) {1'b0}}, 1'b1};
      out_valid     <= 1'b1;
      running       <= 1'b1;
      done          <= 1'b0;

      if ({COUNT_W{1'b0}} < INPUT_LEN_W) begin
        out_sample <= $signed(input_mem[0]);
      end else begin
        out_sample <= 16'sd0;
      end
    end else if (replay_active) begin
      if (sample_idx < TOTAL_LEN_W) begin
        out_valid <= 1'b1;
        running   <= 1'b1;
        done      <= 1'b0;

        if (sample_idx < INPUT_LEN_W) begin
          out_sample <= $signed(input_mem[sample_idx]);
        end else begin
          out_sample <= 16'sd0;
        end

        sample_idx <= sample_idx + {{(COUNT_W - 1) {1'b0}}, 1'b1};
      end else begin
        replay_active <= 1'b0;
        sample_idx    <= {COUNT_W{1'b0}};
        out_valid     <= 1'b0;
        out_sample    <= 16'sd0;
        running       <= 1'b0;
        done          <= 1'b1;
      end
    end else begin
      out_valid  <= 1'b0;
      out_sample <= 16'sd0;
      running    <= 1'b0;
      done       <= 1'b1;
    end
  end

endmodule

`default_nettype wire
