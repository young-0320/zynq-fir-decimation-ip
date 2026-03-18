import numpy as np
import pytest

from sim.python.run_compare_ideal_vs_fixed import compute_error_metrics, run_compare_ideal_vs_fixed


def test_compute_error_metrics_returns_infinite_snr_for_zero_error() -> None:
    x = np.array([0.0, 1.0, -1.0], dtype=np.float64)

    metrics = compute_error_metrics(x, x.copy())

    assert metrics["mse"] == 0.0
    assert metrics["rmse"] == 0.0
    assert metrics["snr_db"] == float("inf")


def test_compute_error_metrics_rejects_shape_mismatch() -> None:
    with pytest.raises(ValueError):
        compute_error_metrics(
            np.array([0.0, 1.0], dtype=np.float64),
            np.array([0.0], dtype=np.float64),
        )


def test_run_compare_ideal_vs_fixed_returns_expected_shapes_and_keys() -> None:
    artifacts, summary = run_compare_ideal_vs_fixed(
        num_taps=5,
        num_samples=64,
        m=2,
        phase=0,
    )

    assert artifacts["input_float"].shape == (64,)
    assert artifacts["input_q15"].shape == (64,)
    assert artifacts["coeff_float"].shape == (5,)
    assert artifacts["coeff_q15"].shape == (5,)
    assert artifacts["ideal_raw_fir"].shape == artifacts["fixed_fir_float"].shape
    assert artifacts["ideal_raw_decim"].shape == artifacts["fixed_decim_float"].shape
    assert "vs_ideal_raw" in summary["metrics"]
    assert "vs_quantized_reference" in summary["metrics"]
    assert summary["metrics"]["vs_ideal_raw"]["fir"]["num_samples"] == 68
