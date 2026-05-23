`timescale 1ns / 1ps
`default_nettype none

/*
 * Debug AXI-Stream M=2 N43-path decimator.
 *
 * Purpose:
 *   Replace fir_decimator_n43_axis in the PS-PL DMA block design to isolate
 *   DMA/BD wiring from FIR-wrapper handshake logic.
 *
 * Behavior:
 *   - 16-bit AXI-Stream input and output, same top-level ports as the FIR
 *     wrapper.
 *   - Accepts one input packet from DMA MM2S.
 *   - Emits every second accepted input sample: input samples 1, 3, 5, ...
 *   - Propagates TLAST when the final accepted input sample is also an output
 *     sample. For the project packet length of 8192 input samples, this emits
 *     exactly 4096 output samples and asserts m_axis_tlast on the final output.
 *
 * Notes:
 *   This module is intentionally conservative: when the single output register
 *   is full and S2MM is not ready, it deasserts s_axis_tready. That makes the
 *   handshake easy to reason about and avoids any internal overflow path.
 */
module axis_decimator_m2_n43_debug (
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

  reg               phase;
  reg               out_valid;
  reg signed [15:0] out_data;
  reg               out_last;

  wire out_fire = out_valid && m_axis_tready;
  wire can_load = !out_valid || out_fire;
  wire in_fire  = s_axis_tvalid && s_axis_tready;
  wire emit     = in_fire && phase;

  assign s_axis_tready = can_load;

  assign m_axis_tvalid = out_valid;
  assign m_axis_tdata  = out_data;
  assign m_axis_tlast  = out_last;

  always @(posedge aclk) begin
    if (!aresetn) begin
      phase     <= 1'b0;
      out_valid <= 1'b0;
      out_data  <= 16'sd0;
      out_last  <= 1'b0;
    end else begin
      if (out_fire) begin
        out_valid <= 1'b0;
        out_last  <= 1'b0;
      end

      if (in_fire) begin
        phase <= ~phase;

        if (emit) begin
          out_valid <= 1'b1;
          out_data  <= s_axis_tdata;
          out_last  <= s_axis_tlast;
        end

        if (s_axis_tlast) begin
          phase <= 1'b0;
        end
      end
    end
  end

endmodule

`default_nettype wire
