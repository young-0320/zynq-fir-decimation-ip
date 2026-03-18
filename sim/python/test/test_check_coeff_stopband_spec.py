import pytest

from sim.python.run_check_coeff_stopband_spec import (
    analyze_frequency_response,
    run_check_coeff_stopband_spec,
)


def _result_by_tap(summary: dict, num_taps: int) -> dict:
    for result in summary["results"]:
        if result["num_taps"] == num_taps:
            return result
    raise AssertionError(f"Missing tap count: {num_taps}")


def test_analyze_frequency_response_rejects_shape_mismatch() -> None:
    with pytest.raises(ValueError):
        analyze_frequency_response(
            freq_hz=[0.0, 1.0],
            mag_db=[0.0],
            fp_hz=0.5,
            fs_hz=0.75,
            as_db=60.0,
        )


def test_run_check_coeff_stopband_spec_identifies_39_and_43() -> None:
    artifacts, summary = run_check_coeff_stopband_spec(
        num_taps_list=[39, 43],
        num_freq_samples=131_072,
    )

    assert artifacts["freq_hz"].ndim == 1
    assert artifacts["n39_ideal_mag_db"].shape == artifacts["freq_hz"].shape
    assert artifacts["n43_quantized_mag_db"].shape == artifacts["freq_hz"].shape

    result_39 = _result_by_tap(summary, 39)
    result_43 = _result_by_tap(summary, 43)

    assert result_39["ideal"]["meets_stopband_spec"] is False
    assert result_39["quantized"]["meets_stopband_spec"] is False
    assert result_43["ideal"]["meets_stopband_spec"] is True
    assert result_43["quantized"]["meets_stopband_spec"] is True
    assert (
        result_43["ideal"]["stopband_min_atten_db"]
        > result_39["ideal"]["stopband_min_atten_db"]
    )
