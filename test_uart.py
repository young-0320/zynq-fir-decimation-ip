import serial, time

ser = serial.Serial('/dev/ttyUSB1', 115200, timeout=5)
time.sleep(0.5)

# flush any startup bytes
startup = ser.read(20)
print('startup:', repr(startup))

# send command
cmd = b'1 5000000\n'
ser.write(cmd)
print('sent:', repr(cmd))

# wait for any response
resp = ser.read(20)
print('response:', repr(resp))

ser.close()
