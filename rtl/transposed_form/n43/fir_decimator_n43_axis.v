`timescale 1ns / 1ps
`default_nettype none

module fir_decimator_n43_axis #(
    parameter integer TLAST_N = 512
) (
    input wire aclk,
    input wire aresetn,

    input  wire               s_axis_tvalid,
    output wire               s_axis_tready,
    input  wire signed [15:0] s_axis_tdata,
    input  wire               s_axis_tlast,

    output wire               m_axis_tvalid,
    input  wire               m_axis_tready,
    output wire signed [15:0] m_axis_tdata,
    output wire               m_axis_tlast
);

  // AXI 동기 액티브 로우 → 코어 비동기 액티브 하이
  wire               rst_core = ~aresetn;

  // -------------------------------------------------------------------------
  // 코어 인스턴스
  // -------------------------------------------------------------------------
  wire               core_out_valid;
  wire signed [15:0] core_out_sample;

  fir_decimator_n43 u_core (
      .clk       (aclk),
      .rst       (rst_core),
      .in_valid  (s_axis_tvalid & s_axis_tready),
      .in_sample (s_axis_tdata),
      .out_valid (core_out_valid),
      .out_sample(core_out_sample)
  );

  // -------------------------------------------------------------------------
  // depth-3 출력 버퍼: reg0(출력) / reg1 / reg2(오버플로)
  // s_axis_tready = ~valid2: reg2가 찰 때 입력 차단
  //
  // 근거: s_axis_tready는 등록(registered) valid2 기반 → 1사이클 지연.
  // 그 사이 in_valid 최대 3번 누출, 3-cycle FIR + M=2 조합상
  // 최대 2개의 decimated 출력이 emerge → depth-3이 최소 안전 크기.
  // -------------------------------------------------------------------------
  reg valid0, valid1, valid2;
  reg signed [15:0] data0, data1, data2;

  wire transfer = valid0 & m_axis_tready;

  always @(posedge aclk) begin
    if (!aresetn) begin
      valid0 <= 1'b0;
      data0  <= 16'sd0;
      valid1 <= 1'b0;
      data1  <= 16'sd0;
      valid2 <= 1'b0;
      data2  <= 16'sd0;
    end else begin
      if (transfer) begin
        // shift: reg1→reg0, reg2→reg1, reg2 비움
        valid0 <= valid1;
        data0  <= data1;
        valid1 <= valid2;
        data1  <= data2;
        valid2 <= 1'b0;
        // 동시 로드: NBA "last wins" — 쉬프트 전 valid1/valid2로 슬롯 결정
        if (core_out_valid) begin
          if (!valid1) begin
            valid0 <= 1'b1;
            data0  <= core_out_sample;
          end else if (!valid2) begin
            valid1 <= 1'b1;
            data1  <= core_out_sample;
          end else begin
            valid2 <= 1'b1;
            data2  <= core_out_sample;
          end
        end
      end else if (core_out_valid) begin
        if (!valid0) begin
          valid0 <= 1'b1;
          data0  <= core_out_sample;
        end else if (!valid1) begin
          valid1 <= 1'b1;
          data1  <= core_out_sample;
        end else if (!valid2) begin
          valid2 <= 1'b1;
          data2  <= core_out_sample;
        end
      end
    end
  end

  // -------------------------------------------------------------------------
  // TLAST 카운터: TLAST_N번째 M_AXIS 전송마다 TLAST=1
  // -------------------------------------------------------------------------
  reg [$clog2(TLAST_N)-1:0] tlast_cnt;

  always @(posedge aclk) begin
    if (!aresetn) tlast_cnt <= 0;
    else if (transfer) tlast_cnt <= (tlast_cnt == TLAST_N - 1) ? 0 : tlast_cnt + 1;
  end

  // -------------------------------------------------------------------------
  // 출력
  // -------------------------------------------------------------------------
  assign s_axis_tready = ~valid2;
  assign m_axis_tvalid = valid0;
  assign m_axis_tdata  = data0;
  assign m_axis_tlast  = valid0 & (tlast_cnt == TLAST_N - 1);

endmodule

`default_nettype wire
