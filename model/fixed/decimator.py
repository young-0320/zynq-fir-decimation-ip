import numpy as np

from model.config import FIR_CONFIG


def decimate_golden(
    x: np.ndarray,
    m: int = FIR_CONFIG.decimation_factor,
    phase: int = FIR_CONFIG.default_phase,
) -> np.ndarray:
    """Downsample a fixed-point 1-D signal by keeping every m-th sample."""
    if not isinstance(x, np.ndarray):
        raise TypeError("x must be a numpy.ndarray.")
    if x.ndim != 1:
        raise ValueError("x must be a 1-D array.")
    if not np.issubdtype(x.dtype, np.integer):
        raise TypeError("x must contain fixed-point integers.")
    if not isinstance(m, int):
        raise TypeError("m must be an int.")
    if not isinstance(phase, int):
        raise TypeError("phase must be an int.")
    if m < 1:
        raise ValueError("m must be >= 1.")
    if not (0 <= phase < m):
        raise ValueError("phase must satisfy 0 <= phase < m.")
    if x.size > 0:
        x_min = int(np.min(x))
        x_max = int(np.max(x))
        if x_min < FIR_CONFIG.q_min or x_max > FIR_CONFIG.q_max:
            raise ValueError("x must stay within signed Q1.15/int16 range.")

    x_q = x.astype(np.int16, copy=False)
    return x_q[phase::m]
