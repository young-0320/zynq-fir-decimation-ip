import numpy as np

from model.fixed.anti_alias_fir import anti_alias_fir_golden


def test_anti_alias_fir_golden_returns_full_length_q4_12_output() -> None:
    x = np.array([4096, 0, 0], dtype=np.int16)
    h = np.array([4096, 2048], dtype=np.int16)

    y = anti_alias_fir_golden(x, h)

    expected = np.array([4096, 2048, 0, 0], dtype=np.int16)
    assert isinstance(y, np.ndarray)
    assert y.dtype == np.int16
    assert np.array_equal(y, expected)


def test_anti_alias_fir_golden_saturates_to_int16_range() -> None:
    x = np.array([32767], dtype=np.int16)
    h = np.array([32767], dtype=np.int16)

    y = anti_alias_fir_golden(x, h)

    assert np.array_equal(y, np.array([32767], dtype=np.int16))


def test_anti_alias_fir_golden_returns_empty_array_for_empty_input() -> None:
    x = np.array([], dtype=np.int16)
    h = np.array([4096], dtype=np.int16)

    y = anti_alias_fir_golden(x, h)

    assert isinstance(y, np.ndarray)
    assert y.dtype == np.int16
    assert y.size == 0
