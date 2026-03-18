import numpy as np

from model.fixed.decimator import decimate_golden


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
