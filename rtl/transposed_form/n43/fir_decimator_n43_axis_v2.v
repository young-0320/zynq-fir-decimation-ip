`timescale 1ns / 1ps
`default_nettype none

/**
 * 모듈명: fir_decimator_n43_axis_v2
 * 역할: N=43 FIR 필터(v2 4단 파이프라인) 및 M=2 데시메이터를 AXI-Stream으로 래핑
 * v1(fir_decimator_n43_axis.v) 대비 변경점: 내부 코어만 fir_decimator_n43_v2로 교체
 *   (workflow_v21 참고). 래퍼 로직(패킷 관리/Auto-Flush/Skid Buffer)은 무수정 재사용.
 * 특징:
 * 1. 동적 TLAST 생성: 입력 패킷 길이에 맞춰 출력 TLAST 타이밍 자동 조절
 * 2. Auto-Flush: s_axis_tlast 수신 시 파이프라인 잔여 데이터를 강제 배출
 * 3. Skid Buffer: 3단 버퍼를 통한 안정적인 백프레셔(Backpressure) 처리
 */
module fir_decimator_n43_axis_v2 (
    input wire aclk,
    input wire aresetn,

    // Slave Interface (From DMA MM2S)
    input  wire               s_axis_tvalid,
    output wire               s_axis_tready,
    input  wire signed [15:0] s_axis_tdata,
    input  wire               s_axis_tlast, // 입력 패킷의 끝을 알리는 신호

    // Master Interface (To DMA S2MM)
    output wire               m_axis_tvalid,
    input  wire               m_axis_tready,
    output wire signed [15:0] m_axis_tdata,
    output wire               m_axis_tlast  // 출력 패킷의 끝을 알리는 신호
);

  // AXI 동기 액티브 로우 리셋을 코어용 액티브 하이 리셋으로 변환
  wire rst_core = ~aresetn;

  // -------------------------------------------------------------------------
  // 1. 패킷 관리 및 Auto-Flush 제어 상태 머신
  // -------------------------------------------------------------------------
  reg [15:0] in_cnt;               // 현재 패킷에서 들어온 입력 샘플 수 카운트
  reg [15:0] out_cnt;              // 코어에서 나가는 출력 샘플 수 카운트
  reg [15:0] target_out_cnt;       // 이번 패킷에서 최종적으로 나가야 할 목표 샘플 수
  reg        waiting_for_last_out; // s_axis_tlast 수신 후, 마지막 출력을 기다리는 상태(Flush 중)

  // 버퍼에 2개 이상의 여유가 있을 때만 코어 및 입력 수락 (s_axis_tready 로직과 연동)
  wire core_ready = ~valid1;
  wire flush_active = waiting_for_last_out;

  // Flush 중에는 새로운 패킷 입력을 차단하여 패킷 간 섞임 방지
  assign s_axis_tready = core_ready & ~flush_active;

  // 코어로 들어가는 최종 Valid/Data 결정 (정상 입력 또는 Flush용 0 주입)
  wire               core_in_valid  = (s_axis_tvalid & s_axis_tready) | (flush_active & core_ready);
  wire signed [15:0] core_in_sample = flush_active ? 16'sd0 : s_axis_tdata;

  always @(posedge aclk) begin
    if (!aresetn) begin
      in_cnt <= 0;
      out_cnt <= 0;
      target_out_cnt <= 0;
      waiting_for_last_out <= 0;
    end else begin
      // [입력 카운팅] s_axis_tlast 감지 시 목표 출력 개수 계산
      if (s_axis_tvalid && s_axis_tready) begin
        in_cnt <= in_cnt + 1;
        if (s_axis_tlast) begin
          waiting_for_last_out <= 1'b1;
          // M=2 데시메이션이므로 (입력수/2)가 목표. 홀수 입력 대응을 위해 +1 후 시프트
          target_out_cnt <= (in_cnt + 1) >> 1;
          in_cnt <= 0;
        end
      end

      // [출력 카운팅] 코어에서 실제 데이터가 나올 때마다 카운트하여 종료 시점 판단
      if (core_out_valid) begin
        out_cnt <= out_cnt + 1;
        // 목표 개수에 도달하면 Flush 상태 종료
        if (waiting_for_last_out && (out_cnt + 1 == target_out_cnt)) begin
          waiting_for_last_out <= 1'b0;
          out_cnt <= 0;
        end
      end
    end
  end

  // 코어 출력 타이밍에 맞춘 TLAST 신호 생성 (목표 샘플에 도달했을 때 High)
  wire core_out_tlast = core_out_valid & waiting_for_last_out & (out_cnt + 1 == target_out_cnt);

  // -------------------------------------------------------------------------
  // 2. FIR 필터 코어 인스턴스 (N=43, Transposed Form, v2 4단 파이프라인)
  // -------------------------------------------------------------------------
  wire               core_out_valid;
  wire signed [15:0] core_out_sample;

  fir_decimator_n43_v2 u_core (
      .clk       (aclk),
      .rst       (rst_core),
      .in_valid  (core_in_valid),
      .in_sample (core_in_sample),
      .out_valid (core_out_valid),
      .out_sample(core_out_sample)
  );

  // -------------------------------------------------------------------------
  // 3. 3단 스키드 버퍼 (데이터 및 TLAST 동기화)
  // -------------------------------------------------------------------------
  // AXI-Stream의 유연한 흐름 제어를 위해 유효 데이터와 TLAST를 함께 버퍼링
  reg valid0, valid1, valid2;
  reg signed [15:0] data0, data1, data2;
  reg tlast0, tlast1, tlast2;

  // 현재 출력이 나가고 마스터가 준비된 상태(Handshake 성공 시)
  wire transfer = valid0 & m_axis_tready;

  always @(posedge aclk) begin
    if (!aresetn) begin
      valid0 <= 1'b0; data0 <= 16'sd0; tlast0 <= 1'b0;
      valid1 <= 1'b0; data1 <= 16'sd0; tlast1 <= 1'b0;
      valid2 <= 1'b0; data2 <= 16'sd0; tlast2 <= 1'b0;
    end else begin
      if (transfer) begin
        // 버퍼 쉬프트 로직 (reg1 -> reg0, reg2 -> reg1)
        valid0 <= valid1; data0 <= data1; tlast0 <= tlast1;
        valid1 <= valid2; data1 <= data2; tlast1 <= tlast2;
        valid2 <= 1'b0;

        // 쉬프트와 동시에 새로운 코어 출력이 들어오는 경우 빈 슬롯에 로드
        if (core_out_valid) begin
          if (!valid1) begin
            valid0 <= 1'b1; data0 <= core_out_sample; tlast0 <= core_out_tlast;
          end else if (!valid2) begin
            valid1 <= 1'b1; data1 <= core_out_sample; tlast1 <= core_out_tlast;
          end else begin
            valid2 <= 1'b1; data2 <= core_out_sample; tlast2 <= core_out_tlast;
          end
        end
      end else if (core_out_valid) begin
        // 쉬프트가 일어나지 않는 상황에서 데이터 로드 (우선순위: 빈 앞칸부터)
        if (!valid0) begin
          valid0 <= 1'b1; data0 <= core_out_sample; tlast0 <= core_out_tlast;
        end else if (!valid1) begin
          valid1 <= 1'b1; data1 <= core_out_sample; tlast1 <= core_out_tlast;
        end else if (!valid2) begin
          valid2 <= 1'b1; data2 <= core_out_sample; tlast2 <= core_out_tlast;
        end
      end
    end
  end

  // -------------------------------------------------------------------------
  // 4. 최종 출력 할당
  // -------------------------------------------------------------------------
  assign m_axis_tvalid = valid0;
  assign m_axis_tdata  = data0;
  assign m_axis_tlast  = tlast0;

endmodule
`default_nettype wire
