import re
from pathlib import Path

import numpy as np
import pytest

from sw import fir_decimator_fft_viewer as viewer
from sw.fir_decimator_fft_viewer import (
    FIR_COEFFS,
    FIR_COEFFS_Q15,
    FS_HZ,
    INPUT_FFT_XLIM_MHZ,
    N_IN,
    N_OUT,
    OUTPUT_FFT_XLIM_MHZ,
    OUTPUT_FS_HZ,
    SCENARIO0_FREQS,
    _fft_db,
    _tone_marker_specs,
    build_scenario0_signals,
    gen_multitone,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
RTL_FIR_N43 = REPO_ROOT / "rtl/transposed_form/n43/fir_n43.v"
Q15_SCALE = 1 << 15
Q15_MIN = -(1 << 15)
Q15_MAX = (1 << 15) - 1


def _parse_rtl_coefficients(path: Path) -> np.ndarray:
    pattern = re.compile(r"COEFF_(\d+)\s*=\s*(-?)16'sd(\d+)")
    coeffs: dict[int, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.search(line)
        if match:
            sign = -1 if match.group(2) else 1
            coeffs[int(match.group(1))] = sign * int(match.group(3))

    assert coeffs, f"no COEFF_n localparams found in {path}"
    indexes = sorted(coeffs)
    assert indexes == list(range(indexes[-1] + 1))
    return np.array([coeffs[index] for index in indexes], dtype=np.int16)


def _read_q15_hex(path: Path) -> np.ndarray:
    values = []
    for line in path.read_text(encoding="ascii").splitlines():
        text = line.strip()
        if not text:
            continue
        raw = int(text, 16)
        if raw >= 0x8000:
            raw -= 0x10000
        values.append(raw)
    return np.array(values, dtype=np.int16)


def _write_q15_hex(path: Path, values: np.ndarray) -> None:
    text = "".join(f"{int(value) & 0xFFFF:04x}\n" for value in values)
    path.write_text(text, encoding="ascii")


def _round_ties_away(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    return np.where(arr >= 0.0, np.floor(arr + 0.5), np.ceil(arr - 0.5))


def _quantize_q15_independent(values: np.ndarray) -> np.ndarray:
    rounded = _round_ties_away(np.asarray(values, dtype=np.float64) * Q15_SCALE)
    return np.clip(rounded, Q15_MIN, Q15_MAX).astype(np.int16)


def _manual_multitone_q15(freqs: list[float]) -> np.ndarray:
    n = np.arange(N_IN, dtype=np.float64)
    tone_amp = 0.9 / len(freqs)
    sig = np.zeros(N_IN, dtype=np.float64)
    for freq_hz in freqs:
        sig += tone_amp * np.sin(2.0 * np.pi * float(freq_hz) / FS_HZ * n)
    return _quantize_q15_independent(sig)


def _round_shift_ties_away(value: int, shift_bits: int = 15) -> int:
    rounded_magnitude = (abs(value) + (1 << (shift_bits - 1))) >> shift_bits
    return -rounded_magnitude if value < 0 else rounded_magnitude


def _saturate_q15(value: int) -> int:
    return min(max(value, Q15_MIN), Q15_MAX)


def _direct_form_fir_q15_independent(x_q15: np.ndarray, h_q15: np.ndarray) -> np.ndarray:
    x = np.asarray(x_q15, dtype=np.int32)
    h = np.asarray(h_q15, dtype=np.int32)
    y = np.zeros(x.size + h.size - 1, dtype=np.int16)
    for n in range(y.size):
        acc = 0
        k_min = max(0, n - x.size + 1)
        k_max = min(h.size - 1, n)
        for k in range(k_min, k_max + 1):
            acc += int(h[k]) * int(x[n - k])
        y[n] = _saturate_q15(_round_shift_ties_away(acc))
    return y


def _float_signal_to_q15(samples: np.ndarray) -> np.ndarray:
    return _quantize_q15_independent(np.asarray(samples, dtype=np.float64))


def _peak_near_db_independent(
    samples: np.ndarray,
    sample_rate_hz: float,
    target_hz: float,
    *,
    search_hz: float,
    ref: float,
) -> float:
    sig = np.asarray(samples, dtype=np.float64)
    freqs_hz = np.fft.rfftfreq(sig.size, d=1.0 / sample_rate_hz)
    magnitude = np.abs(np.fft.rfft(sig))
    mask = np.abs(freqs_hz - target_hz) <= search_hz
    if not np.any(mask):
        mask[np.argmin(np.abs(freqs_hz - target_hz))] = True
    peak = float(np.max(magnitude[mask]))
    return 20.0 * np.log10(peak / ref + 1e-12)


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
    sig = gen_multitone([5e6, 20e6])
    assert np.max(np.abs(sig)) <= 0.9 + 1e-6


def test_gen_multitone_max_tones_no_clip():
    freqs = [5e6, 10e6, 15e6, 20e6, 25e6, 30e6, 35e6, 40e6]
    sig = gen_multitone(freqs)
    assert np.max(np.abs(sig)) <= 0.9 + 1e-6


def test_gen_multitone_all_peaks_present():
    freqs = [5e6, 20e6, 30e6]
    sig = gen_multitone(freqs)
    spectrum = np.abs(np.fft.rfft(sig))
    for freq_hz in freqs:
        expected_bin = round(freq_hz / (FS_HZ / N_IN))
        local = spectrum[max(0, expected_bin - 2):expected_bin + 3]
        assert local.max() > spectrum.mean() * 10


def test_fft_db_output_shape():
    sig = np.ones(N_IN)
    f, db = _fft_db(sig, FS_HZ, 1.0)
    assert len(f) == N_IN // 2 + 1
    assert len(db) == N_IN // 2 + 1


def test_fft_db_peak_is_0db():
    sig = gen_multitone([10e6])
    ref = np.abs(np.fft.rfft(sig)).max()
    _, db = _fft_db(sig, FS_HZ, ref)
    assert abs(db.max()) < 0.1


def test_fft_db_half_amplitude_is_minus6db():
    sig = gen_multitone([10e6])
    ref = np.abs(np.fft.rfft(sig)).max()
    _, db_full = _fft_db(sig, FS_HZ, ref)
    _, db_half = _fft_db(sig * 0.5, FS_HZ, ref)
    assert abs((db_full.max() - db_half.max()) - 6.0) < 0.1


def test_fft_db_frequency_axis_range():
    sig = np.zeros(N_IN)
    f, _ = _fft_db(sig, FS_HZ, 1.0)
    assert f[0] == pytest.approx(0.0)
    assert f[-1] == pytest.approx(FS_HZ / 2 / 1e6, rel=1e-3)


def test_fft_db_zero_signal_no_crash():
    sig = np.zeros(N_IN)
    _, db = _fft_db(sig, FS_HZ, 1.0)
    assert np.all(np.isfinite(db))
    assert np.all(db < -200)


def test_tone_marker_specs_show_output_alias_locations():
    markers = _tone_marker_specs([30e6, 45e6, 25e6], OUTPUT_FS_HZ)

    by_freq = {marker["frequency_mhz"]: marker for marker in markers}
    assert by_freq[20.0]["label"] == "30->20 MHz"
    assert by_freq[5.0]["label"] == "45->5 MHz"
    assert by_freq[25.0]["label"] == "25 MHz Nyq"
    assert by_freq[25.0]["nyquist_edge"] is True


def test_tone_marker_specs_show_input_alias_above_nyquist():
    markers = _tone_marker_specs([97e6], FS_HZ)

    assert markers == [
        {
            "frequency_mhz": pytest.approx(3.0),
            "label": "97->3 MHz",
            "nyquist_edge": False,
        }
    ]


def test_tone_marker_specs_group_overlapping_alias_targets():
    markers = _tone_marker_specs([20e6, 30e6], OUTPUT_FS_HZ)

    assert len(markers) == 1
    assert markers[0]["frequency_mhz"] == pytest.approx(20.0)
    assert markers[0]["label"] == "20 MHz / 30->20 MHz"


def test_scenario0_uses_non_edge_stopband_tones_for_alias_demo():
    assert SCENARIO0_FREQS == [7e6, 15e6, 30e6, 45e6]
    assert 25e6 not in SCENARIO0_FREQS


def test_scenario0_naive_aliases_are_suppressed_by_fir_reference():
    sig_in, naive, filtered = build_scenario0_signals()
    ref = np.abs(np.fft.rfft(sig_in)).max()

    for alias_hz in (5e6, 20e6):
        naive_peak = _peak_near_db_independent(
            naive,
            OUTPUT_FS_HZ,
            alias_hz,
            search_hz=0.5e6,
            ref=ref,
        )
        filtered_peak = _peak_near_db_independent(
            filtered,
            OUTPUT_FS_HZ,
            alias_hz,
            search_hz=0.5e6,
            ref=ref,
        )

        assert naive_peak > -15.0
        assert filtered_peak < -45.0
        assert naive_peak - filtered_peak > 35.0


def test_scenario0_signals_match_viewer_float_reference():
    sig_in, naive, filtered = build_scenario0_signals()
    expected_input = _manual_multitone_q15(SCENARIO0_FREQS)
    expected_filtered = np.convolve(sig_in, FIR_COEFFS, mode="same")[::2]

    np.testing.assert_array_equal(_float_signal_to_q15(sig_in), expected_input)
    np.testing.assert_array_equal(_float_signal_to_q15(naive), expected_input[::2])
    np.testing.assert_allclose(filtered, expected_filtered, atol=1e-15)


def test_run_scenario0_uses_input_naive_and_filtered_axes(monkeypatch):
    calls = []

    class _DummyFig:
        def suptitle(self, title):
            self.title = title

        def tight_layout(self, rect=None):
            self.rect = rect

    class _DummyAxis:
        pass

    axes = (_DummyAxis(), _DummyAxis(), _DummyAxis())

    def fake_subplots(*args, **kwargs):
        return _DummyFig(), axes

    def fake_plot_axis(ax, sig, fs, title, **kwargs):
        calls.append(
            {
                "ax": ax,
                "len": len(sig),
                "fs": fs,
                "title": title,
                "xlim": kwargs["xlim"],
                "marker_label": kwargs["marker_label"],
            }
        )

    monkeypatch.setattr(viewer.plt, "subplots", fake_subplots)
    monkeypatch.setattr(viewer.plt, "show", lambda: None)
    monkeypatch.setattr(viewer, "_plot_fft_axis", fake_plot_axis)

    viewer.run_scenario0()

    assert [call["ax"] for call in calls] == list(axes)
    assert [call["fs"] for call in calls] == [FS_HZ, OUTPUT_FS_HZ, OUTPUT_FS_HZ]
    assert [call["len"] for call in calls] == [N_IN, N_OUT, N_OUT]
    assert [call["xlim"] for call in calls] == [
        INPUT_FFT_XLIM_MHZ,
        OUTPUT_FFT_XLIM_MHZ,
        OUTPUT_FFT_XLIM_MHZ,
    ]
    assert calls[0]["title"].startswith("Input FFT")
    assert calls[1]["title"].startswith("Downsample only")
    assert calls[2]["title"].startswith("FIR + decimation")
    assert calls[1]["marker_label"] == "output alias target"
    assert calls[2]["marker_label"] == "output alias target"


def test_run_scenario1_sends_tones_and_plots_board_output(monkeypatch):
    calls = []
    board_out = np.array([0.0, 0.25, -0.25, 0.5], dtype=np.float64)

    class _DummyFig:
        def suptitle(self, title):
            self.title = title

        def tight_layout(self, rect=None):
            self.rect = rect

    class _DummyAxis:
        pass

    class _DummySerial:
        pass

    axes = (_DummyAxis(), _DummyAxis())
    ser = _DummySerial()

    def fake_subplots(*args, **kwargs):
        return _DummyFig(), axes

    def fake_send_cmd(actual_ser, freqs):
        assert actual_ser is ser
        calls.append(("send", list(freqs)))

    def fake_recv_result(actual_ser):
        assert actual_ser is ser
        calls.append(("recv", None))
        return board_out

    def fake_plot_pair(ax_l, ax_r, sig_l, fs_l, sig_r, fs_r, title_l, title_r, **kwargs):
        calls.append(
            (
                "plot",
                ax_l,
                ax_r,
                len(sig_l),
                fs_l,
                np.array_equal(sig_r, board_out),
                fs_r,
                title_l,
                title_r,
                kwargs["xlim_l"],
                kwargs["xlim_r"],
            )
        )

    monkeypatch.setattr(viewer.plt, "subplots", fake_subplots)
    monkeypatch.setattr(viewer.plt, "show", lambda: None)
    monkeypatch.setattr(viewer, "uart_send_cmd", fake_send_cmd)
    monkeypatch.setattr(viewer, "uart_recv_result", fake_recv_result)
    monkeypatch.setattr(viewer, "plot_fft_pair", fake_plot_pair)

    viewer.run_scenario1("Scenario 1-1", [5e6, 20e6, 30e6], ser)

    assert calls[0] == ("send", [5e6, 20e6, 30e6])
    assert calls[1] == ("recv", None)
    assert calls[2][0] == "plot"
    assert calls[2][1:7] == (axes[0], axes[1], N_IN, FS_HZ, True, OUTPUT_FS_HZ)
    assert calls[2][9:] == (INPUT_FFT_XLIM_MHZ, OUTPUT_FFT_XLIM_MHZ)


def test_run_interactive_mentions_max_tones_and_recovers_from_bad_inputs(monkeypatch, capsys):
    calls = []
    board_out = np.array([0.0, 0.25, -0.25, 0.5], dtype=np.float64)

    class _DummyCanvas:
        def draw(self):
            calls.append(("draw",))

        def flush_events(self):
            calls.append(("flush",))

    class _DummyFig:
        def __init__(self):
            self.canvas = _DummyCanvas()

        def suptitle(self, title):
            calls.append(("title", title))

        def tight_layout(self, rect=None):
            calls.append(("layout", rect))

    class _DummyAxis:
        pass

    class _DummySerial:
        pass

    axes = (_DummyAxis(), _DummyAxis())
    ser = _DummySerial()
    user_lines = iter(["abc", "1 2 3 4 5 6 7 8 9", "101", "97"])

    def fake_input(prompt):
        calls.append(("input", prompt))
        try:
            return next(user_lines)
        except StopIteration:
            raise KeyboardInterrupt

    def fake_subplots(*args, **kwargs):
        return _DummyFig(), axes

    def fake_send_cmd(actual_ser, freqs):
        assert actual_ser is ser
        viewer.validate_tone_frequencies(freqs)
        calls.append(("send", list(freqs)))

    def fake_recv_result(actual_ser):
        assert actual_ser is ser
        calls.append(("recv",))
        return board_out

    def fake_plot_pair(*args, **kwargs):
        calls.append(("plot", kwargs["xlim_l"], kwargs["xlim_r"]))

    monkeypatch.setattr(viewer.plt, "ion", lambda: calls.append(("ion",)))
    monkeypatch.setattr(viewer.plt, "subplots", fake_subplots)
    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(viewer, "uart_send_cmd", fake_send_cmd)
    monkeypatch.setattr(viewer, "uart_recv_result", fake_recv_result)
    monkeypatch.setattr(viewer, "plot_fft_pair", fake_plot_pair)

    viewer.run_interactive(ser)

    out = capsys.readouterr().out
    assert f"최대 {viewer.MAX_TONES}개" in out
    assert "범위 0.000001..100 MHz" in out
    assert out.count("예외 발생:") == 3
    assert "<= 100000000 Hz" in out
    assert "종료" in out
    assert ("send", [97e6]) in calls
    assert ("recv",) in calls
    assert ("plot", INPUT_FFT_XLIM_MHZ, OUTPUT_FFT_XLIM_MHZ) in calls


def test_main_mode0_dispatches_without_opening_uart(monkeypatch):
    calls = []

    monkeypatch.setattr(viewer.sys, "argv", ["fir_decimator_fft_viewer.py", "--mode", "0"])
    monkeypatch.setattr(viewer, "run_scenario0", lambda: calls.append(("scenario0",)))

    def fail_uart_open(*args, **kwargs):
        raise AssertionError("mode 0 must not open UART")

    monkeypatch.setattr(viewer, "uart_open", fail_uart_open)

    viewer.main()

    assert calls == [("scenario0",)]


def test_main_mode_1_1_passes_cli_uart_options_to_scenario(monkeypatch):
    calls = []

    class _DummySerial:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True
            calls.append(("close",))

    ser = _DummySerial()

    def fake_uart_open(port, baud, timeout):
        calls.append(("open", port, baud, timeout))
        return ser

    def fake_run_scenario1(mode_name, freqs, actual_ser):
        calls.append(("scenario1", mode_name, list(freqs), actual_ser is ser))

    monkeypatch.setattr(
        viewer.sys,
        "argv",
        [
            "fir_decimator_fft_viewer.py",
            "--mode",
            "1-1",
            "--port",
            "/dev/ttyTEST",
            "--baud",
            "230400",
            "--timeout",
            "2.5",
        ],
    )
    monkeypatch.setattr(viewer, "uart_open", fake_uart_open)
    monkeypatch.setattr(viewer, "run_scenario1", fake_run_scenario1)

    viewer.main()

    assert calls == [
        ("open", "/dev/ttyTEST", 230400, 2.5),
        ("scenario1", "Scenario 1-1", list(viewer.PRESET_1_1), True),
        ("close",),
    ]


def test_fir_coeffs_match_rtl_localparams():
    rtl_coeffs = _parse_rtl_coefficients(RTL_FIR_N43)

    np.testing.assert_array_equal(FIR_COEFFS_Q15, rtl_coeffs)
    np.testing.assert_allclose(FIR_COEFFS, FIR_COEFFS_Q15.astype(np.float64) / Q15_SCALE)


def test_inline_q15_vector_fixture_matches_independent_direct_form_reference(tmp_path):
    vector_dir = tmp_path / "vectors"
    vector_dir.mkdir()

    input_q15 = np.array([8192, -4096, 16384], dtype=np.int16)
    coeff_q15 = np.array([16384, 0, -16384], dtype=np.int16)
    expected_fir = np.array([4096, -2048, 4096, 2048, -8192], dtype=np.int16)
    expected_decim = np.array([4096, 4096, -8192], dtype=np.int16)

    _write_q15_hex(vector_dir / "input_q15.hex", input_q15)
    _write_q15_hex(vector_dir / "coeff_q15.hex", coeff_q15)
    _write_q15_hex(vector_dir / "expected_fir_q15.hex", expected_fir)
    _write_q15_hex(vector_dir / "expected_decim_q15.hex", expected_decim)

    actual_input = _read_q15_hex(vector_dir / "input_q15.hex")
    actual_coeffs = _read_q15_hex(vector_dir / "coeff_q15.hex")
    actual_expected_fir = _read_q15_hex(vector_dir / "expected_fir_q15.hex")
    actual_expected_decim = _read_q15_hex(vector_dir / "expected_decim_q15.hex")
    independent_fir = _direct_form_fir_q15_independent(actual_input, actual_coeffs)

    np.testing.assert_array_equal(actual_expected_fir, expected_fir)
    np.testing.assert_array_equal(actual_expected_decim, expected_decim)
    np.testing.assert_array_equal(actual_expected_fir, independent_fir)
    np.testing.assert_array_equal(actual_expected_decim, independent_fir[::2])


def test_fir_coeffs_length():
    assert len(FIR_COEFFS) == 43


def test_fir_coeffs_symmetric():
    np.testing.assert_allclose(FIR_COEFFS, FIR_COEFFS[::-1], atol=1e-9)


def test_fir_coeffs_center_is_largest():
    center = len(FIR_COEFFS) // 2
    assert FIR_COEFFS[center] == np.max(FIR_COEFFS)


def test_fir_coeffs_stopband_attenuation():
    freq_response = np.fft.rfft(FIR_COEFFS, n=8192)
    freqs = np.fft.rfftfreq(8192, d=1.0 / FS_HZ)
    stopband_idx = np.where(freqs >= 25e6)[0]
    passband_peak = np.abs(freq_response[:stopband_idx[0]]).max()
    stopband_peak = np.abs(freq_response[stopband_idx]).max()
    attenuation_db = 20 * np.log10(stopband_peak / passband_peak)
    assert attenuation_db <= -60
