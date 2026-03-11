import numpy as np

Q1_15_FRACTIONAL_BITS = 15
Q1_15_MIN = -(1 << 15)
Q1_15_MAX = (1 << 15) - 1


def anti_alias_fir_golden(x: np.ndarray, h: np.ndarray) -> np.ndarray:
    """Apply a full-convolution FIR in signed Q1.15 integer domain.

    This model assumes both `x` and `h` are already quantized fixed-point
    integers. Products are accumulated in a wide integer accumulator, shifted
    back to Q1.15 with an arithmetic right shift, and saturated to int16.
    """
    x_arr = np.asarray(x)
    h_arr = np.asarray(h)

    if x_arr.ndim != 1:
        raise ValueError("x must be a 1-D array.")
    if h_arr.ndim != 1:
        raise ValueError("h must be a 1-D array.")
    if not np.issubdtype(x_arr.dtype, np.integer):
        raise TypeError("x must contain fixed-point integers.")
    if not np.issubdtype(h_arr.dtype, np.integer):
        raise TypeError("h must contain fixed-point integers.")

    if x_arr.size == 0 or h_arr.size == 0:
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

        shifted = acc >> Q1_15_FRACTIONAL_BITS
        if shifted > Q1_15_MAX:
            shifted = Q1_15_MAX
        elif shifted < Q1_15_MIN:
            shifted = Q1_15_MIN

        y[n] = shifted

    return y
