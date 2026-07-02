`timescale 1ns / 1ps
// 버그 1 격리 실험: 스키드 버퍼가 몇 칸이어야 드랍이 0이 되는가?
// - flush/packet FSM 은 빼고 (그건 버그 2/3/4 영역), 순수하게 "연속 입력 + 최악
//   backpressure" 에서 코어 출력이 버퍼를 넘치는지만 측정한다.
// - 무한(64칸) 버퍼로 최대 점유량(max_cnt)을 재면 = 필요한 깊이.
// - core_ready = (cnt <= GATE_MAX): GATE_MAX=1 이 현재 설계(~valid1),
//   GATE_MAX=0 이 "투입구 더 일찍 막기"(~valid0).

module buf_dut #(
    parameter DEPTH = 3,
    parameter GATE_MAX = 1
) (
    input  wire clk,
    input  wire rstn,
    input  wire feed,     // 상류가 항상 보낼 게 있음
    input  wire tready,   // 하류 준비 (0 = backpressure)
    output reg [31:0] overflow,
    output reg [31:0] delivered,
    output reg [31:0] accepted,
    output reg [31:0] max_cnt
);
  wire rst_core = ~rstn;

  // 게이트: 버퍼 점유 cnt 가 GATE_MAX 이하일 때만 새 입력 수락
  reg [31:0] cnt;
  wire core_ready = (cnt <= GATE_MAX);
  wire core_in_valid = feed & core_ready;

  reg signed [15:0] ramp;
  always @(posedge clk) begin
    if (!rstn) ramp <= 0;
    else if (core_in_valid) ramp <= ramp + 1;
  end

  wire core_out_valid;
  wire signed [15:0] core_out_sample;
  fir_decimator_n43_v2 u_core (
      .clk(clk), .rst(rst_core),
      .in_valid(core_in_valid), .in_sample(ramp),
      .out_valid(core_out_valid), .out_sample(core_out_sample)
  );

  // count 기반 collapsing 버퍼 모델 (출력 = 맨 앞, transfer 시 전체 shift)
  integer occ;
  always @(posedge clk) begin
    if (!rstn) begin
      cnt <= 0; overflow <= 0; delivered <= 0; accepted <= 0; max_cnt <= 0;
    end else begin
      if (core_in_valid) accepted <= accepted + 1;
      occ = cnt;
      if ((cnt != 0) && tready) begin   // pop
        occ = occ - 1;
        delivered <= delivered + 1;
      end
      if (core_out_valid) begin          // push
        if (occ >= DEPTH) overflow <= overflow + 1;  // 드랍
        else occ = occ + 1;
      end
      cnt <= occ[31:0];
      if (occ[31:0] > max_cnt) max_cnt <= occ[31:0];
    end
  end
endmodule

module tb_buf_depth;
  reg clk = 0; always #5 clk = ~clk;
  reg rstn = 0;

  integer cyc = 0;
  always @(posedge clk) cyc <= cyc + 1;

  // 최악 backpressure: 길게 막았다가(48) 잠깐 뚫기(6). 채워지고→멈추는 전이에서 버스트 발생.
  wire tready = ((cyc % 54) >= 48);
  wire feed = rstn;  // 연속 입력, 버블 0

  // 무한 버퍼로 필요 깊이 측정
  wire [31:0] ov_inf1, dl_inf1, ac_inf1, mx_inf1;
  buf_dut #(.DEPTH(64), .GATE_MAX(1)) inf1 (clk, rstn, feed, tready, ov_inf1, dl_inf1, ac_inf1, mx_inf1);
  wire [31:0] ov_inf0, dl_inf0, ac_inf0, mx_inf0;
  buf_dut #(.DEPTH(64), .GATE_MAX(0)) inf0 (clk, rstn, feed, tready, ov_inf0, dl_inf0, ac_inf0, mx_inf0);

  // 유한 깊이 검증 (현재 게이트 GATE_MAX=1)
  wire [31:0] ov31, x1, x2, x3; buf_dut #(.DEPTH(3), .GATE_MAX(1)) d31 (clk, rstn, feed, tready, ov31, x1, x2, x3);
  wire [31:0] ov41, y1, y2, y3; buf_dut #(.DEPTH(4), .GATE_MAX(1)) d41 (clk, rstn, feed, tready, ov41, y1, y2, y3);
  wire [31:0] ov51, z1, z2, z3; buf_dut #(.DEPTH(5), .GATE_MAX(1)) d51 (clk, rstn, feed, tready, ov51, z1, z2, z3);
  // 유한 깊이 검증 (게이트 더 일찍 GATE_MAX=0)
  wire [31:0] ov30, w1, w2, w3; buf_dut #(.DEPTH(3), .GATE_MAX(0)) d30 (clk, rstn, feed, tready, ov30, w1, w2, w3);
  wire [31:0] ov40, v1, v2, v3; buf_dut #(.DEPTH(4), .GATE_MAX(0)) d40 (clk, rstn, feed, tready, ov40, v1, v2, v3);

  initial begin
    rstn = 0; repeat (5) @(posedge clk); rstn = 1;
    repeat (6000) @(posedge clk);
    $display("=== 필요 깊이 측정 (무한 버퍼에서 최대 점유량) ===");
    $display("현재 게이트(~valid1, GATE_MAX=1): 최대 점유 %0d칸  (accepted=%0d delivered=%0d overflow=%0d)", mx_inf1, ac_inf1, dl_inf1, ov_inf1);
    $display("일찍 막기 (~valid0, GATE_MAX=0): 최대 점유 %0d칸  (accepted=%0d delivered=%0d overflow=%0d)", mx_inf0, ac_inf0, dl_inf0, ov_inf0);
    $display("");
    $display("=== 유한 깊이별 드랍(overflow) 횟수 ===");
    $display("현재 게이트(~valid1):  DEPTH=3 -> %0d,  DEPTH=4 -> %0d,  DEPTH=5 -> %0d", ov31, ov41, ov51);
    $display("일찍 막기(~valid0):    DEPTH=3 -> %0d,  DEPTH=4 -> %0d", ov30, ov40);
    $finish;
  end
endmodule
