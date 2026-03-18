import numpy as np
import pytest

from model.fixed.anti_alias_fir import anti_alias_fir_golden


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
