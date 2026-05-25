import re
from pathlib import Path

import numpy as np
import pytest

from sw import fir_decimator_fft_viewer as viewer
from sw.fir_decimator_fft_viewer import (
    FIR_COEFFS,
    FIR_COEFFS_Q15,
    FIG_SUPTITLE_FONTSIZE,
    FS_HZ,
    INPUT_BAND_BOUNDARIES_MHZ,
    INPUT_FFT_XLIM_MHZ,
    N_IN,
    N_OUT,
    OUTPUT_FFT_DISPLAY_XLIM_MHZ,
    OUTPUT_FFT_VALID_XLIM_MHZ,
    OUTPUT_FFT_XLIM_MHZ,
    OUTPUT_FS_HZ,
    OUTPUT_INVALID_REGION_MHZ,
    PAIR_FIGSIZE,
    SCENARIO0_FIGSIZE,
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


def test_output_fft_display_range_keeps_valid_band_explicit():
    assert OUTPUT_FFT_VALID_XLIM_MHZ == (0, OUTPUT_FS_HZ / 2 / 1e6)
    assert OUTPUT_FFT_DISPLAY_XLIM_MHZ == INPUT_FFT_XLIM_MHZ
    assert OUTPUT_FFT_XLIM_MHZ == OUTPUT_FFT_DISPLAY_XLIM_MHZ
    assert OUTPUT_INVALID_REGION_MHZ == (OUTPUT_FFT_VALID_XLIM_MHZ[1], OUTPUT_FFT_DISPLAY_XLIM_MHZ[1])


def test_tone_marker_specs_show_output_alias_locations():
    markers = _tone_marker_specs([30e6, 45e6, 25e6], OUTPUT_FS_HZ)

    by_freq = {marker["frequency_mhz"]: marker for marker in markers}
    assert by_freq[20.0]["label"] == "30->20 MHz"
    assert by_freq[5.0]["label"] == "45->5 MHz"
    assert by_freq[25.0]["label"] == "25 MHz Nyq"
    assert by_freq[25.0]["nyquist_edge"] is True



def test_tone_marker_specs_group_overlapping_alias_targets():
    markers = _tone_marker_specs([20e6, 30e6], OUTPUT_FS_HZ)

    assert len(markers) == 1
    assert markers[0]["frequency_mhz"] == pytest.approx(20.0)
    assert markers[0]["label"] == "20 MHz / 30->20 MHz"


def test_plot_fft_pair_passes_visual_metadata_to_each_axis(monkeypatch):
    calls = []

    def fake_plot_axis(ax, sig, fs, title, **kwargs):
        calls.append(
            (
                ax,
                fs,
                kwargs["xlim"],
                kwargs.get("invalid_region_mhz"),
                kwargs.get("band_boundaries_mhz"),
            )
        )

    monkeypatch.setattr(viewer, "_plot_fft_axis", fake_plot_axis)

    viewer.plot_fft_pair(
        "left",
        "right",
        np.zeros(8),
        FS_HZ,
        np.zeros(4),
        OUTPUT_FS_HZ,
        "in",
        "out",
        xlim_l=INPUT_FFT_XLIM_MHZ,
        xlim_r=OUTPUT_FFT_DISPLAY_XLIM_MHZ,
        invalid_region_r=OUTPUT_INVALID_REGION_MHZ,
        band_boundaries_l=INPUT_BAND_BOUNDARIES_MHZ,
    )

    assert calls == [
        ("left", FS_HZ, INPUT_FFT_XLIM_MHZ, None, INPUT_BAND_BOUNDARIES_MHZ),
        ("right", OUTPUT_FS_HZ, OUTPUT_FFT_DISPLAY_XLIM_MHZ, OUTPUT_INVALID_REGION_MHZ, None),
    ]


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

    fig = None

    class _DummyFig:
        def suptitle(self, title, **kwargs):
            self.title = title
            self.title_kwargs = kwargs

        def text(self, x, y, text, **kwargs):
            self.subtitle = (x, y, text, kwargs)

        def tight_layout(self, rect=None):
            self.rect = rect

    class _DummyAxis:
        pass

    axes = (_DummyAxis(), _DummyAxis(), _DummyAxis())

    def fake_subplots(*args, **kwargs):
        nonlocal fig
        assert kwargs["figsize"] == SCENARIO0_FIGSIZE
        fig = _DummyFig()
        return fig, axes

    def fake_plot_axis(ax, sig, fs, title, **kwargs):
        calls.append(
            {
                "ax": ax,
                "len": len(sig),
                "fs": fs,
                "title": title,
                "xlim": kwargs["xlim"],
                "marker_label": kwargs["marker_label"],
                "invalid_region_mhz": kwargs.get("invalid_region_mhz"),
                "band_boundaries_mhz": kwargs.get("band_boundaries_mhz"),
            }
        )

    monkeypatch.setattr(viewer.plt, "subplots", fake_subplots)
    monkeypatch.setattr(viewer.plt, "show", lambda: None)
    monkeypatch.setattr(viewer, "_plot_fft_axis", fake_plot_axis)

    viewer.run_scenario0()

    assert fig.title == viewer._metadata_title("Scenario 0", SCENARIO0_FREQS)
    assert fig.title_kwargs == {"fontsize": FIG_SUPTITLE_FONTSIZE, "y": viewer.FIG_SUPTITLE_Y}
    assert fig.subtitle == (
        0.5,
        viewer.FIG_SUBTITLE_Y,
        viewer._metadata_subtitle(),
        {"ha": "center", "va": "top", "fontsize": viewer.FIG_SUBTITLE_FONTSIZE, "color": viewer.FIG_SUBTITLE_COLOR},
    )
    assert "Input bands: pass <= 15 MHz, transition 15-25 MHz, stop >= 25 MHz" in fig.subtitle[2]
    assert "Output valid: 0-25 MHz" in fig.subtitle[2]
    assert [call["ax"] for call in calls] == list(axes)
    assert [call["fs"] for call in calls] == [FS_HZ, OUTPUT_FS_HZ, OUTPUT_FS_HZ]
    assert [call["len"] for call in calls] == [N_IN, N_OUT, N_OUT]
    assert [call["xlim"] for call in calls] == [
        INPUT_FFT_XLIM_MHZ,
        OUTPUT_FFT_DISPLAY_XLIM_MHZ,
        OUTPUT_FFT_DISPLAY_XLIM_MHZ,
    ]
    assert calls[0]["title"].startswith("Input FFT")
    assert calls[1]["title"].startswith("Downsample only")
    assert calls[2]["title"].startswith("FIR + decimation")
    assert calls[0]["invalid_region_mhz"] is None
    assert calls[1]["invalid_region_mhz"] == OUTPUT_INVALID_REGION_MHZ
    assert calls[2]["invalid_region_mhz"] == OUTPUT_INVALID_REGION_MHZ
    assert calls[0]["band_boundaries_mhz"] == INPUT_BAND_BOUNDARIES_MHZ
    assert calls[1]["band_boundaries_mhz"] is None
    assert calls[2]["band_boundaries_mhz"] is None
    assert calls[1]["marker_label"] == "output alias target"
    assert calls[2]["marker_label"] == "output alias target"


def test_run_scenario1_sends_tones_and_plots_board_output(monkeypatch):
    calls = []
    board_out = np.array([0.0, 0.25, -0.25, 0.5], dtype=np.float64)
    fig = None

    class _DummyFig:
        def suptitle(self, title, **kwargs):
            self.title = title
            self.title_kwargs = kwargs

        def text(self, x, y, text, **kwargs):
            self.subtitle = (x, y, text, kwargs)

        def tight_layout(self, rect=None):
            self.rect = rect

    class _DummyAxis:
        pass

    class _DummySerial:
        pass

    axes = (_DummyAxis(), _DummyAxis())
    ser = _DummySerial()

    def fake_subplots(*args, **kwargs):
        nonlocal fig
        assert kwargs["figsize"] == PAIR_FIGSIZE
        fig = _DummyFig()
        return fig, axes

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
                kwargs.get("invalid_region_r"),
                kwargs.get("band_boundaries_l"),
            )
        )

    monkeypatch.setattr(viewer.plt, "subplots", fake_subplots)
    monkeypatch.setattr(viewer.plt, "show", lambda: None)
    monkeypatch.setattr(viewer, "uart_send_cmd", fake_send_cmd)
    monkeypatch.setattr(viewer, "uart_recv_result", fake_recv_result)
    monkeypatch.setattr(viewer, "plot_fft_pair", fake_plot_pair)

    viewer.run_scenario1("Scenario 1-1", [5e6, 20e6, 30e6], ser)

    assert fig.title == viewer._metadata_title("Scenario 1-1", [5e6, 20e6, 30e6])
    assert fig.title_kwargs == {"fontsize": FIG_SUPTITLE_FONTSIZE, "y": viewer.FIG_SUPTITLE_Y}
    assert fig.subtitle[2] == viewer._metadata_subtitle()
    assert calls[0] == ("send", [5e6, 20e6, 30e6])
    assert calls[1] == ("recv", None)
    assert calls[2][0] == "plot"
    assert calls[2][1:7] == (axes[0], axes[1], N_IN, FS_HZ, True, OUTPUT_FS_HZ)
    assert calls[2][9:] == (
        INPUT_FFT_XLIM_MHZ,
        OUTPUT_FFT_DISPLAY_XLIM_MHZ,
        OUTPUT_INVALID_REGION_MHZ,
        INPUT_BAND_BOUNDARIES_MHZ,
    )


def test_run_interactive_mentions_max_tones_and_runs_valid_input_once(monkeypatch, capsys):
    calls = []
    board_out = np.array([0.0, 0.25, -0.25, 0.5], dtype=np.float64)

    class _DummyFig:
        def suptitle(self, title, **kwargs):
            calls.append(("title", title, kwargs))

        def text(self, x, y, text, **kwargs):
            calls.append(("subtitle", x, y, text, kwargs))

        def tight_layout(self, rect=None):
            calls.append(("layout", rect))

    class _DummyAxis:
        pass

    class _DummySerial:
        pass

    axes = (_DummyAxis(), _DummyAxis())
    ser = _DummySerial()
    user_lines = iter(["abc", "1 2 3 4 5 6 7 8 9", "50", "34"])

    def fake_input(prompt):
        calls.append(("input", prompt))
        try:
            return next(user_lines)
        except StopIteration as exc:
            raise AssertionError("run_interactive requested input after the one-shot capture") from exc

    def fake_subplots(*args, **kwargs):
        assert args == (1, 2)
        assert kwargs["figsize"] == PAIR_FIGSIZE
        calls.append(("subplots", args, kwargs))
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
        assert args[0:2] == axes
        calls.append(
            (
                "plot",
                len(args[2]),
                args[3],
                np.array_equal(args[4], board_out),
                args[5],
                kwargs["xlim_l"],
                kwargs["xlim_r"],
                kwargs.get("invalid_region_r"),
                kwargs.get("band_boundaries_l"),
            )
        )

    def fail_ion():
        raise AssertionError("one-shot mode must not enable interactive plot reuse")

    monkeypatch.setattr(viewer.plt, "ion", fail_ion)
    monkeypatch.setattr(viewer.plt, "subplots", fake_subplots)
    monkeypatch.setattr(viewer.plt, "show", lambda: calls.append(("show",)))
    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(viewer, "uart_send_cmd", fake_send_cmd)
    monkeypatch.setattr(viewer, "uart_recv_result", fake_recv_result)
    monkeypatch.setattr(viewer, "plot_fft_pair", fake_plot_pair)

    viewer.run_interactive(ser)

    out = capsys.readouterr().out
    title_calls = [call for call in calls if call[0] == "title"]
    assert title_calls == [
        (
            "title",
            viewer._metadata_title("Scenario 2", [34e6]),
            {"fontsize": FIG_SUPTITLE_FONTSIZE, "y": viewer.FIG_SUPTITLE_Y},
        )
    ]
    assert ("subtitle", 0.5, viewer.FIG_SUBTITLE_Y, viewer._metadata_subtitle(), {
        "ha": "center",
        "va": "top",
        "fontsize": viewer.FIG_SUBTITLE_FONTSIZE,
        "color": viewer.FIG_SUBTITLE_COLOR,
    }) in calls
    assert f"최대 {viewer.MAX_TONES}개" in out
    assert "범위 [1, 50) MHz" in out
    assert "보드 실행 1회" in out
    assert out.count("예외 발생:") == 3
    assert "< 50000000 Hz" in out
    assert "\n종료\n" not in out
    assert [call for call in calls if call[0] == "input"] == [("input", "주파수 (MHz): ")] * 4
    assert [call for call in calls if call[0] == "send"] == [("send", [34e6])]
    assert [call for call in calls if call[0] == "recv"] == [("recv",)]
    assert [call for call in calls if call[0] == "plot"] == [
        (
            "plot",
            N_IN,
            FS_HZ,
            True,
            OUTPUT_FS_HZ,
            INPUT_FFT_XLIM_MHZ,
            OUTPUT_FFT_DISPLAY_XLIM_MHZ,
            OUTPUT_INVALID_REGION_MHZ,
            INPUT_BAND_BOUNDARIES_MHZ,
        )
    ]
    assert calls[-1] == ("show",)


def test_run_interactive_stops_after_board_error_without_retry(monkeypatch, capsys):
    calls = []

    class _DummySerial:
        pass

    ser = _DummySerial()

    def fake_input(prompt):
        calls.append(("input", prompt))
        if len([call for call in calls if call[0] == "input"]) > 1:
            raise AssertionError("board errors must not trigger another frequency prompt")
        return "34"

    def fake_send_cmd(actual_ser, freqs):
        assert actual_ser is ser
        viewer.validate_tone_frequencies(freqs)
        calls.append(("send", list(freqs)))

    def fake_recv_result(actual_ser):
        assert actual_ser is ser
        calls.append(("recv",))
        raise RuntimeError("DMA fail")

    def fail_plot(*args, **kwargs):
        raise AssertionError("board errors must return before plotting")

    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(viewer, "uart_send_cmd", fake_send_cmd)
    monkeypatch.setattr(viewer, "uart_recv_result", fake_recv_result)
    monkeypatch.setattr(viewer.plt, "subplots", fail_plot)
    monkeypatch.setattr(viewer.plt, "show", fail_plot)
    monkeypatch.setattr(viewer, "plot_fft_pair", fail_plot)

    viewer.run_interactive(ser)

    out = capsys.readouterr().out
    assert "예외 발생: DMA fail" in out
    assert calls == [("input", "주파수 (MHz): "), ("send", [34e6]), ("recv",)]


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
