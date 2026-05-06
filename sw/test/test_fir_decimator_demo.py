import struct

import numpy as np
import pytest

from sw.fir_decimator_demo import (
    MAGIC,
    N_IN,
    N_OUT,
    FS_HZ,
    FIR_COEFFS,
    _fft_db,
    gen_multitone,
    uart_recv_result,
    uart_send_cmd,
)


# ---------------------------------------------------------------------------
# gen_multitone
# ---------------------------------------------------------------------------

def test_gen_multitone_length():
    sig = gen_multitone([10e6])
    assert len(sig) == N_IN


def test_gen_multitone_single_tone_amplitude():
    sig = gen_multitone([10e6])
    assert np.max(np.abs(sig)) <= 0.9 + 1e-6


def test_gen_multitone_peak_frequency():
    freq = 10e6
    sig = gen_multitone([freq])
    spectrum = np.abs(np.fft.rfft(sig))
    peak_bin = np.argmax(spectrum)
    expected_bin = round(freq / (FS_HZ / N_IN))
    assert abs(peak_bin - expected_bin) <= 1


def test_gen_multitone_amplitude_scales_with_tones():
    # 톤 2개면 진폭 = 0.9/2 = 0.45
    sig = gen_multitone([5e6, 20e6])
    assert np.max(np.abs(sig)) <= 0.9 + 1e-6


def test_gen_multitone_max_tones_no_clip():
    # 최대 8개 톤 합산 시에도 진폭 ≤ 0.9
    freqs = [5e6, 10e6, 15e6, 20e6, 25e6, 30e6, 35e6, 40e6]
    sig = gen_multitone(freqs)
    assert np.max(np.abs(sig)) <= 0.9 + 1e-6


def test_gen_multitone_all_peaks_present():
    # 멀티톤에서 각 주파수의 FFT 피크가 모두 존재해야 함
    freqs = [5e6, 20e6, 30e6]
    sig = gen_multitone(freqs)
    spectrum = np.abs(np.fft.rfft(sig))
    for f in freqs:
        expected_bin = round(f / (FS_HZ / N_IN))
        local = spectrum[max(0, expected_bin - 2):expected_bin + 3]
        assert local.max() > spectrum.mean() * 10


# ---------------------------------------------------------------------------
# _fft_db
# ---------------------------------------------------------------------------

def test_fft_db_output_shape():
    sig = np.ones(N_IN)
    ref = 1.0
    f, db = _fft_db(sig, FS_HZ, ref)
    assert len(f) == N_IN // 2 + 1
    assert len(db) == N_IN // 2 + 1


def test_fft_db_peak_is_0db():
    # ref = FFT 최대값이면 피크가 0dB
    sig = gen_multitone([10e6])
    ref = np.abs(np.fft.rfft(sig)).max()
    f, db = _fft_db(sig, FS_HZ, ref)
    assert abs(db.max()) < 0.1


def test_fft_db_half_amplitude_is_minus6db():
    # 진폭이 절반 → -6dB
    sig = gen_multitone([10e6])
    ref = np.abs(np.fft.rfft(sig)).max()
    _, db_full = _fft_db(sig, FS_HZ, ref)
    _, db_half = _fft_db(sig * 0.5, FS_HZ, ref)
    peak_full = db_full.max()
    peak_half = db_half.max()
    assert abs((peak_full - peak_half) - 6.0) < 0.1


def test_fft_db_frequency_axis_range():
    sig = np.zeros(N_IN)
    f, _ = _fft_db(sig, FS_HZ, 1.0)
    assert f[0] == pytest.approx(0.0)
    assert f[-1] == pytest.approx(FS_HZ / 2 / 1e6, rel=1e-3)


def test_fft_db_zero_signal_no_crash():
    # 모든 샘플이 0이어도 크래시 없어야 함 (epsilon 처리)
    sig = np.zeros(N_IN)
    f, db = _fft_db(sig, FS_HZ, 1.0)
    assert np.all(np.isfinite(db))
    assert np.all(db < -200)  # epsilon으로 인해 매우 낮은 dB값


# ---------------------------------------------------------------------------
# uart_send_cmd
# ---------------------------------------------------------------------------

class _MockSerial:
    def __init__(self):
        self.sent = b""

    def write(self, data):
        self.sent += data

    def read(self, n=1):
        return b""


def test_uart_send_cmd_single_tone():
    ser = _MockSerial()
    uart_send_cmd(ser, [10e6])
    assert ser.sent == b"1 10000000\n"


def test_uart_send_cmd_multi_tone():
    ser = _MockSerial()
    uart_send_cmd(ser, [5e6, 20e6, 30e6])
    assert ser.sent == b"3 5000000 20000000 30000000\n"


def test_uart_send_cmd_float_freq_truncated():
    # float 주파수는 int로 잘려서 전송돼야 함
    ser = _MockSerial()
    uart_send_cmd(ser, [9.9e6])
    assert ser.sent == b"1 9900000\n"


# ---------------------------------------------------------------------------
# uart_recv_result
# ---------------------------------------------------------------------------

def _make_packet(samples: np.ndarray) -> bytes:
    magic = struct.pack('<I', MAGIC)
    n = struct.pack('<I', len(samples))
    data = samples.astype(np.int16).tobytes()
    return magic + n + data


class _BytesSerial:
    """bytes 버퍼를 serial처럼 1바이트씩 read()하는 mock."""

    def __init__(self, data: bytes):
        self._buf = data
        self._pos = 0

    def read(self, n=1):
        chunk = self._buf[self._pos:self._pos + n]
        self._pos += n
        return chunk


def test_uart_recv_result_valid_packet():
    expected = np.array([100, -200, 300, -400], dtype=np.int16)
    ser = _BytesSerial(_make_packet(expected))
    result = uart_recv_result(ser)
    np.testing.assert_allclose(result, expected / 32768.0, atol=1e-5)


def test_uart_recv_result_magic_sync():
    # magic 앞에 쓰레기 바이트가 있어도 동기화돼야 함
    expected = np.zeros(4, dtype=np.int16)
    garbage = b'\x00\xAA\xBB\xCC'
    ser = _BytesSerial(garbage + _make_packet(expected))
    result = uart_recv_result(ser)
    assert len(result) == 4


def test_uart_recv_result_near_magic_sync():
    # magic과 첫 3바이트가 일치하는 가짜 시작 후 진짜 magic이 오는 경우
    magic_bytes = struct.pack('<I', MAGIC)
    fake_start = magic_bytes[:3] + b'\x00'  # 마지막 바이트만 다름
    expected = np.array([1, 2, 3, 4], dtype=np.int16)
    ser = _BytesSerial(fake_start + _make_packet(expected))
    result = uart_recv_result(ser)
    np.testing.assert_allclose(result, expected / 32768.0, atol=1e-5)


def test_uart_recv_result_int16_boundary_values():
    # int16 최대/최소값이 정확히 ±1.0으로 정규화돼야 함
    samples = np.array([32767, -32768], dtype=np.int16)
    ser = _BytesSerial(_make_packet(samples))
    result = uart_recv_result(ser)
    assert result[0] == pytest.approx(32767 / 32768.0, rel=1e-5)
    assert result[1] == pytest.approx(-32768 / 32768.0, rel=1e-5)


def test_uart_recv_result_n_out_samples():
    # 실제 N_OUT 크기 패킷이 정상 수신돼야 함
    samples = np.zeros(N_OUT, dtype=np.int16)
    ser = _BytesSerial(_make_packet(samples))
    result = uart_recv_result(ser)
    assert len(result) == N_OUT


def test_uart_recv_result_timeout():
    class _TimeoutSerial:
        def read(self, n=1):
            return b""  # timeout: 빈 bytes 반환

    with pytest.raises(TimeoutError):
        uart_recv_result(_TimeoutSerial())


def test_uart_recv_result_partial_data_timeout():
    # magic은 도착했지만 이후 데이터가 없음
    magic = struct.pack('<I', MAGIC)

    class _PartialSerial:
        def __init__(self):
            self._buf = magic
            self._pos = 0

        def read(self, n=1):
            chunk = self._buf[self._pos:self._pos + n]
            self._pos += n
            return chunk  # magic 이후엔 빈 bytes

    with pytest.raises(TimeoutError):
        uart_recv_result(_PartialSerial())


# ---------------------------------------------------------------------------
# FIR_COEFFS 기본 검증
# ---------------------------------------------------------------------------

def test_fir_coeffs_length():
    assert len(FIR_COEFFS) == 43


def test_fir_coeffs_symmetric():
    # 선형 위상 FIR → 계수가 대칭
    np.testing.assert_allclose(FIR_COEFFS, FIR_COEFFS[::-1], atol=1e-9)


def test_fir_coeffs_center_is_largest():
    # 저역통과 FIR → 중심 계수가 최대
    center = len(FIR_COEFFS) // 2
    assert FIR_COEFFS[center] == np.max(FIR_COEFFS)


def test_fir_coeffs_stopband_attenuation():
    # 30MHz(저지대역)에서 ≥ 60dB 감쇠 확인
    freq_response = np.fft.rfft(FIR_COEFFS, n=8192)
    freqs = np.fft.rfftfreq(8192, d=1.0 / FS_HZ)
    stopband_idx = np.where(freqs >= 25e6)[0]
    passband_peak = np.abs(freq_response[:stopband_idx[0]]).max()
    stopband_peak = np.abs(freq_response[stopband_idx]).max()
    attenuation_db = 20 * np.log10(stopband_peak / passband_peak)
    assert attenuation_db <= -60
