import numpy as np
import pytest

from model.fixed.anti_alias_fir import anti_alias_fir_golden
from model.fixed.decimator import decimate_golden
from model.fixed.fir_decimator_golden import run_fir_decimator_golden


def test_anti_alias_fir_golden_returns_full_length_q1_15_output() -> None:
    x = np.array([16384, 0, 0], dtype=np.int16)
    h = np.array([16384, 8192], dtype=np.int16)

    y = anti_alias_fir_golden(x, h)

    expected = np.array([8192, 4096, 0, 0], dtype=np.int16)
    assert isinstance(y, np.ndarray)
    assert y.dtype == np.int16
    assert np.array_equal(y, expected)


def test_anti_alias_fir_golden_saturates_to_int16_range() -> None:
    x = np.array([-32768], dtype=np.int16)
    h = np.array([-32768], dtype=np.int16)

    y = anti_alias_fir_golden(x, h)

    assert np.array_equal(y, np.array([32767], dtype=np.int16))


@pytest.mark.parametrize(
    ("x", "h", "expected"),
    [
        (
            np.array([1], dtype=np.int16),
            np.array([16384], dtype=np.int16),
            np.array([1], dtype=np.int16),
        ),
        (
            np.array([-1], dtype=np.int16),
            np.array([16384], dtype=np.int16),
            np.array([-1], dtype=np.int16),
        ),
    ],
)
def test_anti_alias_fir_golden_rounds_ties_away_from_zero(
    x: np.ndarray,
    h: np.ndarray,
    expected: np.ndarray,
) -> None:
    y = anti_alias_fir_golden(x, h)

    assert np.array_equal(y, expected)


def test_anti_alias_fir_golden_returns_empty_array_for_empty_input() -> None:
    x = np.array([], dtype=np.int16)
    h = np.array([16384], dtype=np.int16)

    y = anti_alias_fir_golden(x, h)

    assert isinstance(y, np.ndarray)
    assert y.dtype == np.int16
    assert y.size == 0


def test_anti_alias_fir_golden_rejects_empty_coefficients() -> None:
    x = np.array([16384], dtype=np.int16)
    h = np.array([], dtype=np.int16)

    with pytest.raises(ValueError):
        anti_alias_fir_golden(x, h)


def test_decimate_golden_keeps_even_index_samples_when_phase_is_zero() -> None:
    x = np.array([0, 1, 2, 3, 4, 5], dtype=np.int16)

    y = decimate_golden(x, m=2, phase=0)

    expected = np.array([0, 2, 4], dtype=np.int16)
    assert isinstance(y, np.ndarray)
    assert y.dtype == np.int16
    assert np.array_equal(y, expected)


def test_decimate_golden_keeps_odd_index_samples_when_phase_is_one() -> None:
    x = np.array([0, 1, 2, 3, 4, 5], dtype=np.int16)

    y = decimate_golden(x, m=2, phase=1)

    expected = np.array([1, 3, 5], dtype=np.int16)
    assert np.array_equal(y, expected)


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
        run_fir_decimator_golden(x, h, return_intermediate=1)
