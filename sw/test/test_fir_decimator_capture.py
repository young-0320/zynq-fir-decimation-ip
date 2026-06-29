import struct

import numpy as np
import pytest

from sw import fir_decimator_capture as capture
from sw.fir_decimator_capture import (
    MAGIC,
    Q15CaptureResult,
    q15_to_float,
    uart_open,
    uart_recv_result,
    uart_recv_result_q15,
    uart_send_cmd,
)


N_OUT = 4096


class _MockSerial:
    def __init__(self):
        self.sent = b""

    def write(self, data):
        self.sent += data

    def read(self, n=1):
        return b""


def _make_packet(samples: np.ndarray) -> bytes:
    magic = struct.pack("<I", MAGIC)
    n = struct.pack("<I", len(samples))
    data = samples.astype(np.int16).tobytes()
    return magic + n + data


class _BytesSerial:
    def __init__(self, data: bytes):
        self._buf = data
        self._pos = 0

    def read(self, n=1):
        chunk = self._buf[self._pos:self._pos + n]
        self._pos += n
        return chunk


class _PacketSerial(_BytesSerial):
    def __init__(self, samples: np.ndarray):
        super().__init__(_make_packet(samples))
        self.sent = b""
        self.closed = False

    def write(self, data):
        self.sent += data

    def close(self):
        self.closed = True


def test_uart_open_delegates_to_pyserial(monkeypatch):
    calls = []
    sentinel = object()

    def fake_serial(port, baud, timeout):
        calls.append((port, baud, timeout))
        return sentinel

    monkeypatch.setattr(capture.serial, "Serial", fake_serial)

    assert uart_open("/dev/ttyTEST", 115200, 3.5) is sentinel
    assert calls == [("/dev/ttyTEST", 115200, 3.5)]


def test_uart_send_cmd_single_tone():
    ser = _MockSerial()
    uart_send_cmd(ser, [10e6])
    assert ser.sent == b"1 10000000\n"


def test_uart_send_cmd_multi_tone():
    ser = _MockSerial()
    uart_send_cmd(ser, [5e6, 20e6, 30e6])
    assert ser.sent == b"3 5000000 20000000 30000000\n"


def test_uart_send_cmd_float_freq_truncated():
    ser = _MockSerial()
    uart_send_cmd(ser, [9.9e6])
    assert ser.sent == b"1 9900000\n"


def test_uart_send_cmd_accepts_frequency_below_input_nyquist():
    ser = _MockSerial()
    uart_send_cmd(ser, [49e6])
    assert ser.sent == b"1 49000000\n"


@pytest.mark.parametrize(
    ("freqs_hz", "match"),
    [
        ([], "at least one"),
        ([1e6] * 9, "at most 8"),
        ([-1e6], "positive"),
        ([0.0], "positive"),
        ([0.5], ">= 1000000 Hz"),
        ([999_999.0], ">= 1000000 Hz"),
        ([capture.MAX_TONE_FREQ_HZ], "< 50000000 Hz"),
        ([capture.MAX_TONE_FREQ_HZ + 1.0], "< 50000000 Hz"),
        ([float("nan")], "finite"),
        ([float("inf")], "finite"),
    ],
)
def test_uart_send_cmd_rejects_invalid_frequency_contract(freqs_hz, match):
    ser = _MockSerial()

    with pytest.raises(ValueError, match=match):
        uart_send_cmd(ser, freqs_hz)

    assert ser.sent == b""


def test_uart_recv_result_q15_valid_packet():
    expected = np.array([100, -200, 300, -400], dtype=np.int16)
    ser = _BytesSerial(_make_packet(expected))
    result = uart_recv_result_q15(ser)
    assert isinstance(result, Q15CaptureResult)
    assert result.samples.dtype == np.int16
    np.testing.assert_array_equal(result.samples, expected)
    assert result.board_time_us is None


def test_uart_recv_result_q15_parses_fir_time_us():
    expected = np.array([10, -20], dtype=np.int16)
    timing_line = b"FIR_TIME_US:82\r\n"
    ser = _BytesSerial(timing_line + _make_packet(expected))
    result = uart_recv_result_q15(ser)
    np.testing.assert_array_equal(result.samples, expected)
    assert result.board_time_us == 82


def test_uart_recv_result_q15_ignores_malformed_fir_time_us():
    expected = np.array([1, 2], dtype=np.int16)
    timing_line = b"FIR_TIME_US:notanumber\r\n"
    ser = _BytesSerial(timing_line + _make_packet(expected))
    result = uart_recv_result_q15(ser)
    np.testing.assert_array_equal(result.samples, expected)
    assert result.board_time_us is None


def test_uart_recv_result_q15_rejects_unexpected_sample_count():
    samples = np.array([1, 2, 3], dtype=np.int16)
    ser = _BytesSerial(_make_packet(samples))

    with pytest.raises(ValueError, match="sample count 3 != expected 4"):
        uart_recv_result_q15(ser, expected_samples=4)


def test_uart_recv_result_q15_rejects_excessive_sample_count():
    samples = np.array([1, 2, 3, 4, 5], dtype=np.int16)
    ser = _BytesSerial(_make_packet(samples))

    with pytest.raises(ValueError, match="exceeds max_samples 4"):
        uart_recv_result_q15(ser, max_samples=4)


def test_q15_to_float_normalizes_samples():
    samples = np.array([32767, -32768, 0], dtype=np.int16)
    result = q15_to_float(samples)
    np.testing.assert_allclose(result, np.array([32767 / 32768.0, -1.0, 0.0]), atol=1e-12)


def test_uart_recv_result_valid_packet():
    expected = np.array([100, -200, 300, -400], dtype=np.int16)
    ser = _BytesSerial(_make_packet(expected))
    result = uart_recv_result(ser)
    np.testing.assert_allclose(result, expected / 32768.0, atol=1e-5)


def test_uart_recv_result_magic_sync():
    expected = np.zeros(4, dtype=np.int16)
    garbage = b"\x00\xAA\xBB\xCC"
    ser = _BytesSerial(garbage + _make_packet(expected))
    result = uart_recv_result(ser)
    assert len(result) == 4


def test_uart_recv_result_near_magic_sync():
    magic_bytes = struct.pack("<I", MAGIC)
    fake_start = magic_bytes[:3] + b"\x00"
    expected = np.array([1, 2, 3, 4], dtype=np.int16)
    ser = _BytesSerial(fake_start + _make_packet(expected))
    result = uart_recv_result(ser)
    np.testing.assert_allclose(result, expected / 32768.0, atol=1e-5)


def test_uart_recv_result_int16_boundary_values():
    samples = np.array([32767, -32768], dtype=np.int16)
    ser = _BytesSerial(_make_packet(samples))
    result = uart_recv_result(ser)
    assert result[0] == pytest.approx(32767 / 32768.0, rel=1e-5)
    assert result[1] == pytest.approx(-32768 / 32768.0, rel=1e-5)


def test_uart_recv_result_n_out_samples():
    samples = np.zeros(N_OUT, dtype=np.int16)
    ser = _BytesSerial(_make_packet(samples))
    result = uart_recv_result(ser)
    assert len(result) == N_OUT


def test_uart_recv_result_timeout():
    class _TimeoutSerial:
        def read(self, n=1):
            return b""

    with pytest.raises(TimeoutError):
        uart_recv_result(_TimeoutSerial())


def test_uart_recv_result_reports_mm2s_error():
    ser = _BytesSerial(b"ERR:1\r\n")
    with pytest.raises(RuntimeError, match="MM2S DMA timeout"):
        uart_recv_result(ser)


def test_uart_recv_result_reports_s2mm_error():
    ser = _BytesSerial(b"ERR:2\r\n")
    with pytest.raises(RuntimeError, match="S2MM DMA timeout"):
        uart_recv_result(ser)


def test_uart_recv_result_reports_dma_reset_error():
    ser = _BytesSerial(b"ERR:3\r\n")
    with pytest.raises(RuntimeError, match="AXI DMA reset timeout"):
        uart_recv_result(ser)


def test_uart_recv_result_partial_header_timeout():
    magic = struct.pack("<I", MAGIC)
    ser = _BytesSerial(magic)

    with pytest.raises(TimeoutError, match="패킷 수신 중 timeout"):
        uart_recv_result(ser)


def test_uart_recv_result_partial_data_timeout():
    magic = struct.pack("<I", MAGIC)
    n = struct.pack("<I", 4)
    ser = _BytesSerial(magic + n + b"\x00\x00")

    with pytest.raises(TimeoutError, match="샘플 수신 중 timeout"):
        uart_recv_result(ser)


def test_capture_output_q15_sends_command_receives_samples_and_closes(monkeypatch):
    expected = np.array([1, -2, 3, -4], dtype=np.int16)
    created = {}

    def fake_uart_open(port, baud, timeout):
        assert (port, baud, timeout) == ("/dev/ttyTEST", 115200, 2.5)
        ser = _PacketSerial(expected)
        created["ser"] = ser
        return ser

    monkeypatch.setattr(capture, "uart_open", fake_uart_open)

    result = capture.capture_output_q15("/dev/ttyTEST", 115200, 2.5, [5e6, 20e6])

    assert isinstance(result, Q15CaptureResult)
    np.testing.assert_array_equal(result.samples, expected)
    assert created["ser"].sent == b"2 5000000 20000000\n"
    assert created["ser"].closed is True


def test_capture_output_q15_forwards_sample_count_guards(monkeypatch):
    expected = np.array([1, -2, 3, -4], dtype=np.int16)
    calls = []

    class _GuardSerial:
        def __init__(self):
            self.sent = b""
            self.closed = False

        def write(self, data):
            self.sent += data

        def close(self):
            self.closed = True

    ser = _GuardSerial()

    def fake_uart_open(port, baud, timeout):
        assert (port, baud, timeout) == ("/dev/ttyTEST", 115200, 2.5)
        calls.append(("open",))
        return ser

    def fake_recv_result_q15(actual_ser, *, expected_samples=None, max_samples=None):
        assert actual_ser is ser
        calls.append(("recv", expected_samples, max_samples))
        return Q15CaptureResult(samples=expected, board_time_us=None)

    monkeypatch.setattr(capture, "uart_open", fake_uart_open)
    monkeypatch.setattr(capture, "uart_recv_result_q15", fake_recv_result_q15)

    result = capture.capture_output_q15(
        "/dev/ttyTEST",
        115200,
        2.5,
        [5e6],
        expected_samples=4,
        max_samples=8,
    )

    assert isinstance(result, Q15CaptureResult)
    np.testing.assert_array_equal(result.samples, expected)
    assert calls == [("open",), ("recv", 4, 8)]
    assert ser.sent == b"1 5000000\n"
    assert ser.closed is True


def test_capture_output_q15_closes_uart_when_receive_fails(monkeypatch):
    created = {}

    class _FailingSerial:
        def __init__(self):
            self.sent = b""
            self.closed = False

        def write(self, data):
            self.sent += data

        def read(self, n=1):
            return b""

        def close(self):
            self.closed = True

    def fake_uart_open(port, baud, timeout):
        ser = _FailingSerial()
        created["ser"] = ser
        return ser

    monkeypatch.setattr(capture, "uart_open", fake_uart_open)

    with pytest.raises(TimeoutError):
        capture.capture_output_q15("/dev/ttyTEST", 115200, 2.5, [5e6])

    assert created["ser"].sent == b"1 5000000\n"
    assert created["ser"].closed is True


def test_capture_output_float_converts_q15_capture(monkeypatch):
    samples = np.array([32767, -32768, 0], dtype=np.int16)

    def fake_capture_output_q15(
        port,
        baud,
        timeout,
        freqs_hz,
        *,
        expected_samples=None,
        max_samples=None,
    ):
        assert (port, baud, timeout, freqs_hz) == ("/dev/ttyTEST", 115200, 1.0, [10e6])
        assert expected_samples is None
        assert max_samples is None
        return Q15CaptureResult(samples=samples, board_time_us=None)

    monkeypatch.setattr(capture, "capture_output_q15", fake_capture_output_q15)

    result = capture.capture_output_float("/dev/ttyTEST", 115200, 1.0, [10e6])
    np.testing.assert_allclose(result, np.array([32767 / 32768.0, -1.0, 0.0]), atol=1e-12)
