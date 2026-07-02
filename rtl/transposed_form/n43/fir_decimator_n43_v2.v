`timescale 1ns / 1ps
`default_nettype none

// fir_decimator_n43 v2 — fir_n43_v2(4-stage 파이프라인) + decimator_m2_phase0 결합 top
// v1(fir_decimator_n43.v) 대비 변경점: 코어를 fir_n43_v2로 교체 (workflow_v21 참고)
// decimator_m2_phase0은 무수정 재사용 (valid 핸드셰이크 기반이라 latency 변화 무관)

module fir_decimator_n43_v2 (
    input  wire               clk,
    input  wire               rst,
    input  wire               in_valid,
    input  wire signed [15:0] in_sample,
    output wire               out_valid,
    output wire signed [15:0] out_sample
);

  wire               fir_out_valid;
  wire signed [15:0] fir_out_sample;

  fir_n43_v2 u_fir_n43_v2 (
      .clk(clk),
      .rst(rst),
      .in_valid(in_valid),
      .in_sample(in_sample),
      .out_valid(fir_out_valid),
      .out_sample(fir_out_sample)
  );

  decimator_m2_phase0 u_decimator_m2_phase0 (
      .clk(clk),
      .rst(rst),
      .in_valid(fir_out_valid),
      .in_sample(fir_out_sample),
      .out_valid(out_valid),
      .out_sample(out_sample)
  );

endmodule

`default_nettype wire
