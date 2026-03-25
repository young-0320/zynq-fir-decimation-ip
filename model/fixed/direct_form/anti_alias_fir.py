import numpy as np

from model.config import FIR_CONFIG


Q1_15_FRACTIONAL_BITS = FIR_CONFIG.fractional_bits
Q1_15_MIN = FIR_CONFIG.q_min
Q1_15_MAX = FIR_CONFIG.q_max


def _validate_q1_15_int_array(x: np.ndarray, name: str) -> np.ndarray:
    if not isinstance(x, np.ndarray):
        raise TypeError(f"{name} must be a numpy.ndarray.")
    if x.ndim != 1:
        raise ValueError(f"{name} must be a 1-D array.")
    if not np.issubdtype(x.dtype, np.integer):
        raise TypeError(f"{name} must contain fixed-point integers.")
    if x.size > 0:
        x_min = int(np.min(x))
        x_max = int(np.max(x))
        if x_min < Q1_15_MIN or x_max > Q1_15_MAX:
            raise ValueError(f"{name} must stay within signed Q1.15/int16 range.")
    return x


def _round_shift_ties_away_from_zero(value: int, shift_bits: int) -> int:
    if shift_bits < 1:
        raise ValueError("shift_bits must be >= 1.")

    magnitude = abs(value)
    rounded_magnitude = (magnitude + (1 << (shift_bits - 1))) >> shift_bits
    if value < 0:
        return -rounded_magnitude
    return rounded_magnitude


def _saturate_to_q1_15(value: int) -> int:
    if value > Q1_15_MAX:
        return Q1_15_MAX
    if value < Q1_15_MIN:
        return Q1_15_MIN
    return value


def anti_alias_fir_golden(x: np.ndarray, h: np.ndarray) -> np.ndarray:
    """Apply a full-convolution FIR in signed Q1.15 integer domain.

    This model assumes both `x` and `h` are already quantized fixed-point
    integers. Products are accumulated without intermediate clipping, rounded
    back to Q1.15 using round-to-nearest with ties away from zero, and clipped
    once when storing the final int16 output array.
    """
    x_arr = _validate_q1_15_int_array(x, name="x")
    h_arr = _validate_q1_15_int_array(h, name="h")

    if h_arr.size == 0:
        raise ValueError("h must not be empty.")

    if x_arr.size == 0:
        return np.array([], dtype=np.int16)

    x_q = x_arr.astype(np.int64, copy=False)
    h_q = h_arr.astype(np.int64, copy=False)

    output_len = x_q.size + h_q.size - 1
    y = np.zeros(output_len, dtype=np.int16)

    for n in range(output_len):
        acc = 0
        for k in range(h_q.size):
            input_idx = n - k
            if 0 <= input_idx < x_q.size:
                acc += int(h_q[k]) * int(x_q[input_idx])

        rounded = _round_shift_ties_away_from_zero(
            acc,
            shift_bits=Q1_15_FRACTIONAL_BITS,
        )
        y[n] = _saturate_to_q1_15(rounded)

    return y
