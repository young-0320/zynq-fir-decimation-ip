import json

import numpy as np

from sw import fir_decimator_report as report


def _fake_board_capture_for_golden(port, baud, timeout, freqs_hz, *, expected_samples=None, max_samples=None):
    assert port == "dummy"
    assert baud == 115200
    assert timeout == 1.0
    assert expected_samples == report.N_OUT
    assert max_samples is None
    ref = report.metrics.generate_fixed_reference(
        freqs_hz,
        n_in=report.N_IN,
        fs_hz=report.FS_HZ,
        coeffs_q15=report.FIR_COEFFS_Q15,
        n_out=report.N_OUT,
    )
    return ref["fixed_q15_reference"].copy()


def test_run_report_saves_json_png_and_summary(monkeypatch, tmp_path):
    monkeypatch.setattr(report, "capture_output_q15", _fake_board_capture_for_golden)

    results = report.run_report(
        mode="1-1",
        port="dummy",
        baud=115200,
        timeout=1.0,
        save_dir=tmp_path,
    )

    assert len(results) == 1
    plot_path = tmp_path / "plot" / "scenario1_1_fft.png"
    metrics_path = tmp_path / "metrics" / "scenario1_1_metrics.json"
    summary_path = tmp_path / "summary" / "scenario1_1_summary.md"
    assert plot_path.is_file()
    assert metrics_path.is_file()
    assert summary_path.is_file()
    assert plot_path.stat().st_size > 0

    data = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert data["mode"] == "1-1"
    assert data["sample_metrics"]["max_abs_error_lsb"] == 0
    assert data["sample_metrics"]["snr_db"] == "inf"
    assert data["summary"]["overall_verdict"] == "PASS"
    assert data["artifacts"]["fft_plot_path"].endswith("scenario1_1_fft.png")

    summary = summary_path.read_text(encoding="utf-8")
    assert "Scenario 1-1" in summary
    assert "../plot/scenario1_1_fft.png" in summary
    assert "../metrics/scenario1_1_metrics.json" in summary
    assert "Tone Regions" in summary
    assert "Run one report scenario per board reset." in summary


def test_run_report_captures_only_the_requested_scenario(monkeypatch, tmp_path):
    monkeypatch.setattr(report, "capture_output_q15", _fake_board_capture_for_golden)

    results = report.run_report(
        mode="1-2",
        port="dummy",
        baud=115200,
        timeout=1.0,
        save_dir=tmp_path,
    )

    assert [result.scenario.mode for result in results] == ["1-2"]
    assert not (tmp_path / "plot" / "scenario1_1_fft.png").exists()
    assert (tmp_path / "plot" / "scenario1_2_fft.png").is_file()
    assert not (tmp_path / "metrics" / "scenario1_1_metrics.json").exists()
    assert (tmp_path / "metrics" / "scenario1_2_metrics.json").is_file()
    assert not (tmp_path / "summary" / "scenario1_1_summary.md").exists()
    assert (tmp_path / "summary" / "scenario1_2_summary.md").is_file()


def test_json_safe_converts_numpy_and_non_finite_values():
    safe = report._json_safe({"a": np.int16(3), "b": np.float64(np.inf), "c": np.array([1, 2])})

    assert safe == {"a": 3, "b": "inf", "c": [1, 2]}
