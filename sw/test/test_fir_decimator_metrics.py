import math

import numpy as np
import pytest

from model.q1_15 import quantize_q1_15
from sw import fir_decimator_metrics as metrics


FS_HZ = 100_000_000.0
FS_OUT_HZ = FS_HZ / 2
N_IN = 8192
N_OUT = 4096
FIR_COEFFS_Q15 = np.array([
    10, 0, -33, -32, 47, 107, 0, -197, -159, 206,
    425, 0, -674, -522, 654, 1336, 0, -2258, -1939, 2995,
    9864, 13109, 9864, 2995, -1939, -2258, 0, 1336, 654, -522,
    -674, 0, 425, 206, -159, -197, 0, 107, 47, -32,
    -33, 0, 10,
], dtype=np.int16)


def gen_multitone(freqs_hz, *, n_in=N_IN, fs_hz=FS_HZ, amplitude=0.9):
    n = np.arange(n_in, dtype=np.float64)
    tone_amp = amplitude / len(freqs_hz)
    sig = np.zeros(n_in, dtype=np.float64)
    for freq_hz in freqs_hz:
        sig += tone_amp * np.sin(2.0 * np.pi * float(freq_hz) / fs_hz * n)
    return sig


def _small_tone_fixture():
    tones_hz = [1.0, 3.0]
    n_in = np.arange(8, dtype=np.float64)
    n_out = np.arange(8, dtype=np.float64)
    sig_in = quantize_q1_15(
        0.35 * np.sin(2.0 * np.pi * 1.0 / 8.0 * n_in)
        + 0.25 * np.sin(2.0 * np.pi * 3.0 / 8.0 * n_in)
    )
    golden_out = quantize_q1_15(0.5 * np.sin(2.0 * np.pi * 1.0 / 4.0 * n_out))
    return tones_hz, sig_in, golden_out


# This file fixes the contract for sw.fir_decimator_metrics:
# pure, board-free numeric analysis over Q1.15 samples. UART, argparse,
# plotting, and file writing belong to capture/viewer/report wrappers.


# ---------------------------------------------------------------------------
# alias/fold frequency mapping
# ---------------------------------------------------------------------------


def test_fold_frequency_hz_maps_input_tones_into_output_nyquist_band():
    assert metrics.fold_frequency_hz(5e6, FS_OUT_HZ) == pytest.approx(5e6)
    assert metrics.fold_frequency_hz(20e6, FS_OUT_HZ) == pytest.approx(20e6)
    assert metrics.fold_frequency_hz(25e6, FS_OUT_HZ) == pytest.approx(25e6)
    assert metrics.fold_frequency_hz(30e6, FS_OUT_HZ) == pytest.approx(20e6)
    assert metrics.fold_frequency_hz(45e6, FS_OUT_HZ) == pytest.approx(5e6)


def test_fold_frequency_hz_rejects_invalid_sample_rate():
    with pytest.raises(ValueError, match="sample_rate_hz"):
        metrics.fold_frequency_hz(5e6, 0.0)


# ---------------------------------------------------------------------------
# fixed-point sample-domain comparison
# ---------------------------------------------------------------------------


def test_compare_samples_reports_integer_lsb_metrics():
    golden = np.array([0, 8192, -16384, 24576, 32767, -32768], dtype=np.int16)
    error_lsb = np.array([1, -1, 2, -2, 0, 0], dtype=np.int32)
    board = (golden.astype(np.int32) + error_lsb).astype(np.int16)

    summary = metrics.compare_samples(board, golden)

    assert summary["n_samples_compared"] == 6
    assert summary["max_abs_error_lsb"] == 2
    assert summary["rmse_lsb"] == pytest.approx(math.sqrt(np.mean(error_lsb**2)))
    assert summary["mean_error_lsb"] == pytest.approx(np.mean(error_lsb))
    assert summary["max_error_lsb"] == 2
    assert summary["min_error_lsb"] == -2
    assert summary["saturation_count"] == 2
    assert summary["clipping_count"] == 2
    assert summary["latency_aligned"] is True
    assert summary["trim_head_samples"] == 0
    assert summary["trim_tail_samples"] == 0

    expected_snr = 10.0 * math.log10(
        np.sum(golden.astype(np.float64) ** 2) / np.sum(error_lsb.astype(np.float64) ** 2)
    )
    assert summary["snr_db"] == pytest.approx(expected_snr)
    assert summary["correlation"] > 0.99999


def test_compare_samples_exact_match_has_infinite_snr():
    golden = np.array([0, 8192, -16384, 24576], dtype=np.int16)

    summary = metrics.compare_samples(golden, golden)

    assert summary["max_abs_error_lsb"] == 0
    assert summary["rmse_lsb"] == pytest.approx(0.0)
    assert math.isinf(summary["snr_db"])
    assert summary["correlation"] == pytest.approx(1.0)


def test_compare_samples_applies_head_and_tail_trim_before_metrics():
    golden = np.array([0, 100, 200, 300, 400, 500], dtype=np.int16)
    board = np.array([32767, 101, 198, 303, -32768, 1234], dtype=np.int16)
    compared_error = np.array([1, -2, 3], dtype=np.int32)

    summary = metrics.compare_samples(
        board,
        golden,
        trim_head_samples=1,
        trim_tail_samples=2,
    )

    assert summary["n_samples_compared"] == 3
    assert summary["max_abs_error_lsb"] == 3
    assert summary["rmse_lsb"] == pytest.approx(math.sqrt(np.mean(compared_error**2)))
    assert summary["mean_error_lsb"] == pytest.approx(np.mean(compared_error))
    assert summary["max_error_lsb"] == 3
    assert summary["min_error_lsb"] == -2
    assert summary["saturation_count"] == 0
    assert summary["trim_head_samples"] == 1
    assert summary["trim_tail_samples"] == 2


@pytest.mark.parametrize(("trim_head_samples", "trim_tail_samples"), [(3, 3), (6, 0), (0, 6)])
def test_compare_samples_rejects_trim_that_removes_all_samples(
    trim_head_samples,
    trim_tail_samples,
):
    samples = np.array([0, 1, 2, 3, 4, 5], dtype=np.int16)

    with pytest.raises(ValueError, match="leave at least one sample"):
        metrics.compare_samples(
            samples,
            samples,
            trim_head_samples=trim_head_samples,
            trim_tail_samples=trim_tail_samples,
        )


def test_compare_samples_requires_same_length_q15_arrays():
    with pytest.raises(ValueError, match="same length"):
        metrics.compare_samples(np.zeros(4, dtype=np.int16), np.zeros(5, dtype=np.int16))

    with pytest.raises(TypeError, match="integer"):
        metrics.compare_samples(np.zeros(4, dtype=np.float64), np.zeros(4, dtype=np.int16))


# ---------------------------------------------------------------------------
# fixed-point reference generation
# ---------------------------------------------------------------------------


def test_generate_fixed_reference_quantizes_input_and_trims_injected_golden(monkeypatch):
    tones_hz = [1.0, 3.0]
    n_in = 8
    fs_hz = 8.0
    coeffs_q15 = np.array([16384, -16384], dtype=np.int16)
    fake_full_reference = np.array([10, -20, 30, -40, 50], dtype=np.int16)
    captured = {}

    def fake_golden(input_q15, coeffs, m, phase):
        captured["input_q15"] = input_q15.copy()
        captured["coeffs"] = coeffs.copy()
        captured["m"] = m
        captured["phase"] = phase
        return fake_full_reference

    monkeypatch.setattr(metrics, "run_fir_decimator_transposed_golden", fake_golden)

    ref = metrics.generate_fixed_reference(
        tones_hz,
        n_in=n_in,
        fs_hz=fs_hz,
        coeffs_q15=coeffs_q15,
        n_out=3,
        decimation=2,
        phase=1,
        amplitude=0.5,
    )

    expected_input = quantize_q1_15(gen_multitone(tones_hz, n_in=n_in, fs_hz=fs_hz, amplitude=0.5))
    np.testing.assert_array_equal(captured["input_q15"], expected_input)
    np.testing.assert_array_equal(captured["coeffs"], coeffs_q15)
    assert captured["m"] == 2
    assert captured["phase"] == 1
    assert ref["input_q15"].dtype == np.int16
    assert ref["fixed_q15_reference"].dtype == np.int16
    assert ref["input_clipping_count"] == 0
    assert ref["golden_saturation_count"] == 0
    assert ref["decimation"] == 2
    assert ref["phase"] == 1
    np.testing.assert_array_equal(ref["input_q15"], expected_input)
    np.testing.assert_array_equal(ref["fixed_q15_reference"], fake_full_reference[:3])
    np.testing.assert_array_equal(ref["full_fixed_q15_reference"], fake_full_reference)


# ---------------------------------------------------------------------------
# FFT peak extraction
# ---------------------------------------------------------------------------


def test_compute_fft_peaks_finds_q15_tone_with_shared_reference():
    sig_q15 = quantize_q1_15(gen_multitone([7e6]))
    ref = np.abs(np.fft.rfft(sig_q15.astype(np.float64))).max()
    bin_hz = FS_HZ / N_IN

    peaks = metrics.compute_fft_peaks(
        sig_q15,
        FS_HZ,
        [7e6],
        search_hz=0.5e6,
        ref=ref,
    )

    assert len(peaks) == 1
    assert peaks[0]["target_hz"] == pytest.approx(7e6)
    assert peaks[0]["peak_frequency_hz"] == pytest.approx(7e6, abs=bin_hz)
    assert peaks[0]["peak_db"] == pytest.approx(0.0, abs=0.1)


def test_compute_fft_peaks_reports_half_scale_as_minus_6db():
    sig_q15 = quantize_q1_15(gen_multitone([15e6]))
    ref = np.abs(np.fft.rfft(sig_q15.astype(np.float64))).max()

    full = metrics.compute_fft_peaks(sig_q15, FS_HZ, [15e6], ref=ref)[0]
    half = metrics.compute_fft_peaks((sig_q15.astype(np.int32) // 2).astype(np.int16), FS_HZ, [15e6], ref=ref)[0]

    assert full["peak_db"] - half["peak_db"] == pytest.approx(6.0, abs=0.2)


# ---------------------------------------------------------------------------
# tone peak and report dictionaries
# ---------------------------------------------------------------------------


def test_compare_tone_peaks_compares_board_against_golden_at_folded_bins():
    tones_hz, sig_in, golden_out = _small_tone_fixture()
    board_out = golden_out.copy()

    rows = metrics.compare_tone_peaks(
        sig_in,
        board_out,
        golden_out,
        tones_hz,
        fs_in_hz=8.0,
        fs_out_hz=4.0,
        regions={1.0: "passband", 3.0: "stopband"},
        search_hz=0.1,
    )

    assert [row["tone_hz"] for row in rows] == [1.0, 3.0]
    assert rows[1]["expected_output_hz"] == pytest.approx(1.0)
    assert rows[1]["expected_output_mhz"] == pytest.approx(0.000001)

    for row in rows:
        assert row["board_vs_golden_peak_delta_db"] == pytest.approx(0.0, abs=1e-9)
        assert row["board_peak_db"] == pytest.approx(row["golden_peak_db"])
        assert row["verdict"] == "PASS"
        assert set(row) >= {
            "tone_hz",
            "expected_output_hz",
            "input_peak_db",
            "board_peak_db",
            "golden_peak_db",
            "board_vs_golden_peak_delta_db",
            "board_attenuation_db",
            "golden_attenuation_db",
            "region",
            "verdict",
        }


def test_build_report_contains_scenario_sample_and_tone_metrics():
    tones_hz, sig_in, golden_out = _small_tone_fixture()

    report = metrics.build_report(
        "1-1",
        tones_hz,
        sig_in,
        golden_out.copy(),
        golden_out,
        fs_in_hz=8.0,
        fs_out_hz=4.0,
        regions={1.0: "passband", 3.0: "stopband"},
        search_hz=0.1,
    )

    assert report["mode"] == "1-1"
    assert report["n_in"] == sig_in.size
    assert report["n_out"] == golden_out.size
    assert report["fs_in_hz"] == 8.0
    assert report["fs_out_hz"] == 4.0
    assert report["input_tones_hz"] == tones_hz
    assert report["sample_metrics"]["max_abs_error_lsb"] == 0
    assert report["sample_metrics"]["rmse_lsb"] == pytest.approx(0.0)
    assert len(report["tone_metrics"]) == 2
    assert report["summary"]["verdict_counts"] == {"PASS": 2}


def test_build_report_carries_artifact_paths_and_known_limitations():
    tones_hz, sig_in, golden_out = _small_tone_fixture()
    transition_tones = [1.0, 2.0, 3.0]

    report = metrics.build_report(
        "1-1",
        transition_tones,
        sig_in,
        golden_out,
        golden_out,
        fs_in_hz=8.0,
        fs_out_hz=4.0,
        regions={1.0: "passband", 2.0: "transition", 3.0: "stopband"},
        search_hz=0.1,
        fft_plot_path="docs/report/fir_n43_demo_evidence/scenario1_1_fft.png",
        known_limitations=["Board reset is required between board scenarios."],
    )

    assert report["artifacts"]["fft_plot_path"] == "docs/report/fir_n43_demo_evidence/scenario1_1_fft.png"
    assert report["input_tones_hz"] == transition_tones
    assert "Board reset is required between board scenarios." in report["known_limitations"]
    assert "Transition-band tones are reported as INFO, not hard PASS criteria." in report["known_limitations"]
    assert report["summary"]["verdict_counts"] == {"PASS": 2, "INFO": 1}
    assert report["summary"]["overall_verdict"] == "PASS"
