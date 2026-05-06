import argparse
import struct

import matplotlib.pyplot as plt
import numpy as np
import serial

N_IN = 8192
N_OUT = 4096
FS_HZ = 100e6
MAGIC = 0xDEADBEEF

FIR_COEFFS = np.array([
    10, 0, -33, -32, 47, 107, 0, -197, -159, 206,
    425, 0, -674, -522, 654, 1336, 0, -2258, -1939, 2995,
    9864, 13109, 9864, 2995, -1939, -2258, 0, 1336, 654, -522,
    -674, 0, 425, 206, -159, -197, 0, 107, 47, -32,
    -33, 0, 10
]) / 32768.0

SCENARIO0_FREQS = [7e6, 15e6, 25e6, 45e6]
PRESET_1_1 = [5e6, 20e6, 30e6]
PRESET_1_2 = [7e6, 15e6, 25e6, 45e6]


def gen_multitone(freqs):
    n = np.arange(N_IN, dtype=np.float64)
    amp = 0.9 / len(freqs)
    return sum(amp * np.sin(2 * np.pi * f / FS_HZ * n) for f in freqs)


def uart_open(port, baud):
    return serial.Serial(port, baud, timeout=5)


def uart_send_cmd(ser, freqs):
    cmd = f"{len(freqs)} " + " ".join(str(int(f)) for f in freqs) + "\n"
    ser.write(cmd.encode())


def uart_recv_result(ser):
    magic_bytes = struct.pack('<I', MAGIC)
    buf = b''
    while True:
        b = ser.read(1)
        if not b:
            raise TimeoutError("보드 응답 없음 (timeout). 연결 및 비트스트림을 확인하세요.")
        buf += b
        if len(buf) >= 4 and buf[-4:] == magic_bytes:
            break
    n_data = ser.read(4)
    if len(n_data) < 4:
        raise TimeoutError("패킷 수신 중 timeout.")
    n = struct.unpack('<I', n_data)[0]
    raw = ser.read(n * 2)
    if len(raw) < n * 2:
        raise TimeoutError("샘플 수신 중 timeout.")
    return np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0


def _fft_db(sig, fs, ref):
    f = np.fft.rfftfreq(len(sig), d=1.0 / fs) / 1e6
    db = 20 * np.log10(np.abs(np.fft.rfft(sig)) / ref + 1e-12)
    return f, db


def plot_fft_pair(ax_l, ax_r, sig_l, fs_l, sig_r, fs_r, title_l, title_r, ref=None):
    if ref is None:
        ref = np.abs(np.fft.rfft(sig_l)).max()
    if ref == 0:
        ref = 1.0

    for ax, sig, fs, title in [
        (ax_l, sig_l, fs_l, title_l),
        (ax_r, sig_r, fs_r, title_r),
    ]:
        f, db = _fft_db(sig, fs, ref)
        ax.cla()
        ax.plot(f, db)
        ax.set_title(title)
        ax.set_xlabel("주파수 (MHz)")
        ax.set_ylabel("크기 (dB)")
        ax.set_xlim(0, 50)
        ax.set_ylim(-100, 5)
        ax.grid(True)


def run_scenario0():
    sig = gen_multitone(SCENARIO0_FREQS)
    naive = sig[::2]
    filtered = np.convolve(sig, FIR_COEFFS, mode='same')[::2]
    ref = np.abs(np.fft.rfft(sig)).max()

    fig, (ax_l, ax_r) = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Scenario 0: FIR 없을 때 vs 있을 때")
    plot_fft_pair(
        ax_l, ax_r,
        naive, FS_HZ / 2,
        filtered, FS_HZ / 2,
        "다운샘플만 (앨리어싱 발생)",
        "FIR + 데시메이션 (우리 시스템)",
        ref=ref,
    )
    plt.tight_layout()
    plt.show()


def run_scenario1(freqs, ser):
    sig_in = gen_multitone(freqs)
    uart_send_cmd(ser, freqs)
    sig_out = uart_recv_result(ser)

    label = " / ".join(f"{int(f / 1e6)}MHz" for f in freqs)
    fig, (ax_l, ax_r) = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle(f"Scenario 1: {label}")
    plot_fft_pair(
        ax_l, ax_r,
        sig_in, FS_HZ,
        sig_out, FS_HZ / 2,
        "입력 FFT",
        "출력 FFT (FIR 후)",
    )
    plt.tight_layout()
    plt.show()


def run_interactive(ser):
    plt.ion()
    fig, (ax_l, ax_r) = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Scenario 2: 인터랙티브")
    plt.tight_layout()

    print("주파수 입력 형식: 'f1 f2 ...' (MHz, 공백 구분) | 종료: Ctrl+C")

    while True:
        try:
            line = input("주파수 (MHz): ").strip()
            if not line:
                continue
            freqs = [float(x) * 1e6 for x in line.split()]

            sig_in = gen_multitone(freqs)
            uart_send_cmd(ser, freqs)
            sig_out = uart_recv_result(ser)

            plot_fft_pair(
                ax_l, ax_r,
                sig_in, FS_HZ,
                sig_out, FS_HZ / 2,
                "입력 FFT",
                "출력 FFT (FIR 후)",
            )
            fig.canvas.draw()
            fig.canvas.flush_events()

        except TimeoutError as e:
            print(f"오류: {e}")
        except KeyboardInterrupt:
            print("\n종료")
            break


def main():
    parser = argparse.ArgumentParser(description="FIR 데시메이터 데모")
    parser.add_argument("--mode", required=True, choices=["0", "1-1", "1-2", "2"],
                        help="0=앨리어싱 비교, 1-1/1-2=고정 프리셋, 2=인터랙티브")
    parser.add_argument("--port", default="/dev/ttyUSB1", help="UART 포트")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (기본값 115200)")
    args = parser.parse_args()

    if args.mode == "0":
        run_scenario0()
        return

    ser = uart_open(args.port, args.baud)
    try:
        if args.mode == "1-1":
            run_scenario1(PRESET_1_1, ser)
        elif args.mode == "1-2":
            run_scenario1(PRESET_1_2, ser)
        elif args.mode == "2":
            run_interactive(ser)
    finally:
        ser.close()


if __name__ == "__main__":
    main()
