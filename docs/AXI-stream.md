# AXI-stream 

AXI-stream 인터페이스는 FPGA 내부에서 데이터 스트림을 처리할 때 자주 사용되는 통신 프로토콜입니다. 
데이터는 항상 master에서 slave로 흐릅니다.

## AXI-stream의 주요 신호
1. **TVALID**: Master가 "지금 보내는 데이터가 유효하다"고 알리는 신호
2. **TREADY**: Slave가 "지금 데이터를 받을 준비가 되었다"고 알리는 신호
3. **TDATA**: 실제 전송되는 데이터
4. **TLAST**: (패킷 단위 통신 시) 데이터의 마지막임을 알리는 신호

## Handshake 규칙
1. 전송 조건 (The Condition): 전송은 오직 TVALID && TREADY가 같은 클락 에지(Clock Edge)에서 모두 High일 때만 발생합니다.
2. 안정성 유지 (The Stability Rule): Master가 TVALID를 올렸는데 Slave가 아직 TREADY를 올리지 않았다면(TVALID=1, TREADY=0), Master는 TREADY가 올 때까지 TVALID를 내리거나 TDATA 값을 바꿔서는 안 됩니다.
3. 조합 회로 금지 (No Combinatorial Path): TREADY 신호가 TVALID에 직접적인 조합 회로(Combinatorial logic)로 엮여서는 안 됩니다. 즉, "상대방이 유효한 데이터를 주면 그때서야 내가 받을 준비를 하겠다"는 식으로 설계하면 타이밍 루프(Timing Loop)가 발생할 수 있습니다.

## Back-pressure