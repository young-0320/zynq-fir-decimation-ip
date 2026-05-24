import serial
import time
import struct

PORT = '/dev/ttyUSB1'
BAUD = 115200
MAGIC = 0xDEADBEEF

try:
    # 1. 포트 개방 및 안정화
    ser = serial.Serial(PORT, BAUD, timeout=5)
    time.sleep(1)
    ser.reset_input_buffer()

    # 2. 명령어 전송 (개행 문자 포함 필수)
    cmd = b'1 5000000\n'
    ser.write(cmd)
    print(f'>>> Sent: {cmd.decode().strip()}')

    # 3. 수신부: Magic Code(0xDEADBEEF) 동기화
    print('<<< Waiting for MAGIC Sync...')
    magic_bytes = struct.pack('<I', MAGIC)
    buf = b''
    
    while True:
        b = ser.read(1) # 1바이트씩 슬라이딩 윈도우 검색
        if not b:
            print("!!! Timeout: Board didn't send MAGIC")
            break
        buf += b
        
        if len(buf) >= 4 and buf[-4:] == magic_bytes:
            print("--- MAGIC Sync Complete ---")
            break
            
    if buf[-4:] == magic_bytes:
        # 4. N_OUT (데이터 개수) 파싱
        n_data = ser.read(4)
        n_out = struct.unpack('<I', n_data)[0]
        print(f"--- Payload Size: {n_out} samples ---")

        # 5. 실제 데이터(int16_t) 수신
        raw_data = ser.read(n_out * 2) # int16은 2바이트이므로 * 2
        
        if len(raw_data) == n_out * 2:
            # 바이트 배열을 파이썬 정수 튜플로 변환 (리틀 엔디안, short)
            samples = struct.unpack(f'<{n_out}h', raw_data)
            print(f"<<< First 5 samples: {samples[:5]}")
            print(f"<<< Last 5 samples: {samples[-5:]}")
        else:
            print("!!! Error: Incomplete payload received")

except Exception as e:
    print(f"!!! Error: {e}")
finally:
    if 'ser' in locals() and ser.is_open:
        ser.close()
        print("--- Port Closed ---")