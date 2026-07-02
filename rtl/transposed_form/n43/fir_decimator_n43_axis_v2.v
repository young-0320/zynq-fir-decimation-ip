`timescale 1ns / 1ps
`default_nettype none

/**
 * 모듈명: fir_decimator_n43_axis_v2
 * 역할: N=43 FIR 필터(v2 4단 파이프라인) 및 M=2 데시메이터를 AXI-Stream으로 래핑
 * v1(fir_decimator_n43_axis.v) 대비 변경점: 내부 코어만 fir_decimator_n43_v2로 교체
 *   (workflow_v21 참고). 래퍼 로직(패킷 관리/Auto-Flush/Skid Buffer)은 무수정 재사용.
 * 특징:
 * 1. 동적 TLAST 생성: 입력 패킷 길이에 맞춰 출력 TLAST 타이밍 자동 조절
 * 2. Auto-Drain: s_axis_tlast 수신 후 마지막 출력이 나올 때까지 다음 패킷 입력 차단
 * 3. Skid Buffer: 4단 버퍼를 통한 안정적인 백프레셔(Backpressure) 처리
 *
 * 주의: 이 블록은 짝수 길이 패킷을 가정한다(홀수 미지원).
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

  // 드레인 중에는 새로운 패킷 입력을 차단하여 패킷 간 섞임 방지.
  // (버그 2 수정) 마지막 샘플(s_axis_tlast)은 버퍼가 꽉 차 있어도 수락한다:
  // 짝수 길이 가정에서 마지막 샘플은 데시메이션 drop 위상이라 출력을 만들지 않으므로
  // 버퍼를 넘치게 하지 않으면서 target_out_cnt를 즉시 확정한다. 이렇게 해야 지속
  // backpressure에서 tlast 입력이 마지막 코어 출력보다 늦어져 TLAST 태깅을 놓치는
  // 레이스가 사라진다(TLAST는 코어 출력 시점에 버퍼 슬롯에 실려 함께 흘러감).
  assign s_axis_tready = (core_ready | s_axis_tlast) & ~flush_active;

  // 코어로 들어가는 Valid/Data는 실제 입력 핸드셰이크에서만 결정.
  // (버그 3 수정) 0-주입 flush 제거 — 파이프라인은 새 입력 없이 이전 스테이지 valid로
  // 스스로 드레인되므로 강제 주입이 불필요하며, 여분 주입이 다음 패킷을 오염시켰다.
  wire               core_in_valid  = s_axis_tvalid & s_axis_tready;
  wire signed [15:0] core_in_sample = s_axis_tdata;

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
          // M=2 데시메이션이므로 (입력수/2)가 목표. 짝수 길이 가정에서 (in_cnt+1)>>1 = N/2로 정확.
          target_out_cnt <= (in_cnt + 1) >> 1;
          in_cnt <= 0;
        end
      end

      // [출력 카운팅] 코어에서 실제 데이터가 나올 때마다 카운트하여 종료 시점 판단
      if (core_out_valid) begin
        out_cnt <= out_cnt + 1;
        // 목표 개수에 도달하면 드레인 상태 종료 (버그 2 수정: 등호 대신 >= 로 방어)
        if (waiting_for_last_out && (out_cnt + 1 >= target_out_cnt)) begin
          waiting_for_last_out <= 1'b0;
          out_cnt <= 0;
        end
      end
    end
  end

  // 코어 출력 타이밍에 맞춘 TLAST 신호 생성 (목표 샘플에 도달했을 때 High, 버그 2 수정: >=)
  wire core_out_tlast = core_out_valid & waiting_for_last_out & (out_cnt + 1 >= target_out_cnt);

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
  // 3. 4단 스키드 버퍼 (데이터 및 TLAST 동기화)
  // -------------------------------------------------------------------------
  // AXI-Stream의 유연한 흐름 제어를 위해 유효 데이터와 TLAST를 함께 버퍼링.
  // 깊이 4 근거(log 41 실측): 2(게이트 ~valid1 허용) + 2(파이프라인 in-flight).
  // 3칸이면 지속 backpressure에서 in-flight 출력이 넘쳐 드랍 발생(버그 1).
  reg valid0, valid1, valid2, valid3;
  reg signed [15:0] data0, data1, data2, data3;
  reg tlast0, tlast1, tlast2, tlast3;

  // 현재 출력이 나가고 마스터가 준비된 상태(Handshake 성공 시)
  wire transfer = valid0 & m_axis_tready;

  always @(posedge aclk) begin
    if (!aresetn) begin
      valid0 <= 1'b0; data0 <= 16'sd0; tlast0 <= 1'b0;
      valid1 <= 1'b0; data1 <= 16'sd0; tlast1 <= 1'b0;
      valid2 <= 1'b0; data2 <= 16'sd0; tlast2 <= 1'b0;
      valid3 <= 1'b0; data3 <= 16'sd0; tlast3 <= 1'b0;
    end else begin
      if (transfer) begin
        // 버퍼 쉬프트 로직 (reg1 -> reg0, reg2 -> reg1, reg3 -> reg2)
        valid0 <= valid1; data0 <= data1; tlast0 <= tlast1;
        valid1 <= valid2; data1 <= data2; tlast1 <= tlast2;
        valid2 <= valid3; data2 <= data3; tlast2 <= tlast3;
        valid3 <= 1'b0;

        // 쉬프트와 동시에 새로운 코어 출력이 들어오는 경우 빈 슬롯에 로드
        if (core_out_valid) begin
          if (!valid1) begin
            valid0 <= 1'b1; data0 <= core_out_sample; tlast0 <= core_out_tlast;
          end else if (!valid2) begin
            valid1 <= 1'b1; data1 <= core_out_sample; tlast1 <= core_out_tlast;
          end else if (!valid3) begin
            valid2 <= 1'b1; data2 <= core_out_sample; tlast2 <= core_out_tlast;
          end else begin
            valid3 <= 1'b1; data3 <= core_out_sample; tlast3 <= core_out_tlast;
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
        end else if (!valid3) begin
          valid3 <= 1'b1; data3 <= core_out_sample; tlast3 <= core_out_tlast;
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
