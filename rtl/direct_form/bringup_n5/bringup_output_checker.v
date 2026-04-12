`timescale 1ns / 1ps
`default_nettype none

module bringup_output_checker #(
    parameter integer EXPECTED_LEN = 4098,
    parameter integer DRAIN_TIMEOUT = 64,
    parameter MEM_FILE = "sim/vectors/direct_form/bringup_n5/expected_decim_q15.hex"
) (
    input  wire               clk,
    input  wire               rst,
    input  wire               source_done,
    input  wire               in_valid,
    input  wire signed [15:0] in_sample,
    output reg                done,
    output wire               pass,
    output reg                fail,
    output reg                mismatch_seen
);

  localparam integer COUNT_W = (EXPECTED_LEN < 1) ? 1 : $clog2(EXPECTED_LEN + 1);
  localparam integer DRAIN_W = (DRAIN_TIMEOUT < 1) ? 1 : $clog2(DRAIN_TIMEOUT + 1);
  localparam [COUNT_W-1:0] EXPECTED_LEN_W = EXPECTED_LEN;

  (* rom_style = "block" *)reg        [       15:0] expected_mem     [0:EXPECTED_LEN-1];
  reg        [COUNT_W-1:0] observed_count;
  reg        [DRAIN_W-1:0] drain_count;
  reg                      compare_pending;
  reg signed [       15:0] sample_pipe;
  reg signed [       15:0] expected_pipe;
  wire                     compare_mismatch;

  integer                  i;

  assign compare_mismatch = compare_pending && (sample_pipe != expected_pipe);
  assign pass = done & ~fail;

  initial begin
    for (i = 0; i < EXPECTED_LEN; i = i + 1) begin
      expected_mem[i] = 16'h0000;
    end

    $readmemh(MEM_FILE, expected_mem);
  end

  always @(posedge clk) begin
    if (rst) begin
      observed_count  <= {COUNT_W{1'b0}};
      drain_count     <= {DRAIN_W{1'b0}};
      compare_pending <= 1'b0;
      sample_pipe     <= 16'sd0;
      expected_pipe   <= 16'sd0;
      done            <= 1'b0;
      fail            <= 1'b0;
      mismatch_seen   <= 1'b0;
    end else begin
      if (compare_mismatch) begin
        compare_pending <= 1'b0;
        drain_count     <= {DRAIN_W{1'b0}};
        done            <= 1'b1;
        fail            <= 1'b1;
        mismatch_seen   <= 1'b1;
      end else if (!done) begin
        if (in_valid) begin
          drain_count <= {DRAIN_W{1'b0}};

          if (observed_count < EXPECTED_LEN_W) begin
            sample_pipe     <= in_sample;
            expected_pipe   <= $signed(expected_mem[observed_count]);
            compare_pending <= 1'b1;
            observed_count  <= observed_count + {{(COUNT_W - 1) {1'b0}}, 1'b1};
          end else begin
            compare_pending <= 1'b0;
            done            <= 1'b1;
            fail            <= 1'b1;
            mismatch_seen   <= 1'b1;
          end
        end else begin
          compare_pending <= 1'b0;

          if (source_done) begin
            if ((DRAIN_TIMEOUT <= 1) || (drain_count == DRAIN_TIMEOUT - 1)) begin
              done <= 1'b1;

              if (observed_count != EXPECTED_LEN_W) begin
                fail <= 1'b1;
              end
            end else begin
              drain_count <= drain_count + {{(DRAIN_W - 1) {1'b0}}, 1'b1};
            end
          end else begin
            drain_count <= {DRAIN_W{1'b0}};
          end
        end
      end else begin
        compare_pending <= 1'b0;
      end
    end
  end

endmodule

`default_nettype wire
