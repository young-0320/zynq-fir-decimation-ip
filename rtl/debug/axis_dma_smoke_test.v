`timescale 1ns / 1ps
`default_nettype none

/*
 * AXI DMA smoke-test stream endpoint.
 *
 * Purpose:
 *   Isolate AXI DMA MM2S and S2MM behavior from FIR/decimator handshake logic.
 *
 * Behavior:
 *   - MM2S input is always accepted and discarded: s_axis_tready = 1.
 *   - S2MM output is generated independently as a 4096-sample counter packet.
 *   - Output generation starts once per input packet, on the first accepted
 *     input beat, and is not retriggered until the input TLAST arrives.
 *
 * Expected diagnostic value:
 *   - If MM2S still times out, the issue is before/inside MM2S read/streaming.
 *   - If MM2S completes but S2MM times out, the issue is on S2MM write/receive.
 */
module axis_dma_smoke_test #(
    parameter integer N_OUT = 4096
) (
    input wire aclk,
    input wire aresetn,

    // Slave Interface (From DMA MM2S)
    input  wire               s_axis_tvalid,
    output wire               s_axis_tready,
    input  wire signed [15:0] s_axis_tdata,
    input  wire               s_axis_tlast,

    // Master Interface (To DMA S2MM)
    output wire               m_axis_tvalid,
    input  wire               m_axis_tready,
    output wire signed [15:0] m_axis_tdata,
    output wire               m_axis_tlast
);

  localparam integer OUT_CNT_WIDTH = 12;

  reg packet_open;
  reg out_active;
  reg [OUT_CNT_WIDTH-1:0] out_count;

  wire in_fire  = s_axis_tvalid && s_axis_tready;
  wire out_fire = m_axis_tvalid && m_axis_tready;

  assign s_axis_tready = 1'b1;

  assign m_axis_tvalid = out_active;
  assign m_axis_tdata  = {4'h5, out_count};
  assign m_axis_tlast  = out_active && (out_count == N_OUT[OUT_CNT_WIDTH-1:0] - 1'b1);

  always @(posedge aclk) begin
    if (!aresetn) begin
      packet_open <= 1'b0;
      out_active  <= 1'b0;
      out_count   <= {OUT_CNT_WIDTH{1'b0}};
    end else begin
      if (in_fire) begin
        if (!packet_open && !out_active) begin
          out_active <= 1'b1;
          out_count  <= {OUT_CNT_WIDTH{1'b0}};
        end

        packet_open <= !s_axis_tlast;
      end

      if (out_fire) begin
        if (out_count == N_OUT[OUT_CNT_WIDTH-1:0] - 1'b1) begin
          out_active <= 1'b0;
          out_count  <= {OUT_CNT_WIDTH{1'b0}};
        end else begin
          out_count <= out_count + 1'b1;
        end
      end
    end
  end

  wire unused_input = &{1'b0, s_axis_tdata};

endmodule

`default_nettype wire
