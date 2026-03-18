import numpy as np
import pytest

from model.fixed.fir_decimator_golden import run_fir_decimator_golden


def test_run_fir_decimator_golden_runs_fir_then_decimation() -> None:
    x = np.array([16384, 0, 0], dtype=np.int16)
    h = np.array([16384, 8192], dtype=np.int16)

    y = run_fir_decimator_golden(x, h, m=2, phase=0)

    expected = np.array([8192, 0], dtype=np.int16)
    assert isinstance(y, np.ndarray)
    assert y.dtype == np.int16
    assert np.array_equal(y, expected)


def test_run_fir_decimator_golden_can_return_intermediate_outputs() -> None:
    x = np.array([16384, 0, 0], dtype=np.int16)
    h = np.array([16384, 8192], dtype=np.int16)

    y_fir, y_decim = run_fir_decimator_golden(
        x,
        h,
        m=2,
        phase=1,
        return_intermediate=True,
    )

    expected_fir = np.array([8192, 4096, 0, 0], dtype=np.int16)
    expected_decim = np.array([4096, 0], dtype=np.int16)

    assert isinstance(y_fir, np.ndarray)
    assert isinstance(y_decim, np.ndarray)
    assert y_fir.dtype == np.int16
    assert y_decim.dtype == np.int16
    assert np.array_equal(y_fir, expected_fir)
    assert np.array_equal(y_decim, expected_decim)


def test_run_fir_decimator_golden_rejects_non_bool_return_intermediate() -> None:
    x = np.array([16384], dtype=np.int16)
    h = np.array([16384], dtype=np.int16)

    with pytest.raises(TypeError):
        run_fir_decimator_golden(x, h, return_intermediate=0)
