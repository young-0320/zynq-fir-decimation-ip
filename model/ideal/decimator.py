import numpy as np

from model.config import FIR_CONFIG


def decimate(
    x: np.ndarray,
    m: int = FIR_CONFIG.decimation_factor,
    phase: int = FIR_CONFIG.default_phase,
) -> np.ndarray:
    """Downsample a 1-D signal by keeping every m-th sample from `phase`.

    For example, with `m=2`, `phase=0` keeps indices 0, 2, 4, ...
    and `phase=1` keeps indices 1, 3, 5, ....
    """
    if not isinstance(x, np.ndarray):
        raise TypeError("x must be a numpy.ndarray.")
    if x.ndim != 1:
        raise ValueError("x must be a 1-D array.")
    if not np.isfinite(x).all():
        raise ValueError("x must contain only finite values.")
    if not isinstance(m, int):
        raise TypeError("m must be an int.")
    if not isinstance(phase, int):
        raise TypeError("phase must be an int.")
    if m < 1:
        raise ValueError("m must be >= 1.")
    if not (0 <= phase < m):
        raise ValueError("phase must satisfy 0 <= phase < m.")

    x = x.astype(np.float64, copy=False)
    return x[phase::m]
