import numpy as np
import pytest

from model.q1_15 import count_clipped_q1_15, dequantize_q1_15, quantize_q1_15


def test_quantize_q1_15_rounds_ties_away_from_zero() -> None:
    x = np.array([0.5 / (2**15), -0.5 / (2**15)], dtype=np.float64)

    y = quantize_q1_15(x)

    assert np.array_equal(y, np.array([1, -1], dtype=np.int16))


def test_quantize_q1_15_clips_to_signed_range() -> None:
    x = np.array([2.0, -2.0], dtype=np.float64)

    y = quantize_q1_15(x)

    assert np.array_equal(y, np.array([32767, -32768], dtype=np.int16))


def test_count_clipped_q1_15_counts_overrange_samples() -> None:
    x = np.array([0.0, 1.2, -1.3], dtype=np.float64)

    assert count_clipped_q1_15(x) == 2


def test_dequantize_q1_15_returns_float64_values() -> None:
    x_q15 = np.array([16384, -16384], dtype=np.int16)

    y = dequantize_q1_15(x_q15)

    assert y.dtype == np.float64
    assert np.allclose(y, np.array([0.5, -0.5], dtype=np.float64))


def test_dequantize_q1_15_rejects_non_integer_input() -> None:
    with pytest.raises(TypeError):
        dequantize_q1_15(np.array([0.5], dtype=np.float64))
