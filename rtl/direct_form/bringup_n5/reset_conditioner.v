`timescale 1ns / 1ps
`default_nettype none

module reset_conditioner #(
    parameter integer DEBOUNCE_COUNT_MAX = 32'd1_250_000,
    parameter integer POWER_ON_RESET_CYCLES = 32'd16,
    parameter integer BUTTON_ACTIVE_HIGH = 1
) (
    input  wire clk,
    input  wire btn_in,
    output wire rst
);

  // Reset is asserted immediately by POR or a pressed button.
  // Release is delayed until the button release has been debounced.

  reg sync_0;
  reg sync_1;
  reg [31:0] debounce_count;
  reg [31:0] por_count;
  reg btn_reset_active;
  reg por_active;

  wire btn_sync_active;

  assign btn_sync_active = (BUTTON_ACTIVE_HIGH != 0) ? sync_1 : ~sync_1;
  assign rst = por_active | btn_reset_active;

  initial begin
    sync_0           = (BUTTON_ACTIVE_HIGH != 0) ? 1'b0 : 1'b1;
    sync_1           = (BUTTON_ACTIVE_HIGH != 0) ? 1'b0 : 1'b1;
    debounce_count   = 32'd0;
    por_count        = 32'd0;
    btn_reset_active = 1'b0;
    por_active       = 1'b1;
  end

  always @(posedge clk) begin
    sync_0 <= btn_in;
    sync_1 <= sync_0;

    if (btn_sync_active) begin
      btn_reset_active <= 1'b1;
      debounce_count   <= 32'd0;
    end else if (btn_reset_active) begin
      if ((DEBOUNCE_COUNT_MAX <= 1) || (debounce_count == DEBOUNCE_COUNT_MAX - 1)) begin
        btn_reset_active <= 1'b0;
        debounce_count   <= 32'd0;
      end else begin
        debounce_count <= debounce_count + 32'd1;
      end
    end else begin
      debounce_count <= 32'd0;
    end

    if (por_active) begin
      if ((POWER_ON_RESET_CYCLES <= 1) || (por_count == POWER_ON_RESET_CYCLES - 1)) begin
        por_active <= 1'b0;
        por_count  <= 32'd0;
      end else begin
        por_count <= por_count + 32'd1;
      end
    end else begin
      por_count <= 32'd0;
    end
  end

endmodule

`default_nettype wire
