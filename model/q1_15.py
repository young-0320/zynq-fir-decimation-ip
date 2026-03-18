from __future__ import annotations

import numpy as np


Q1_15_FRACTIONAL_BITS = 15
Q1_15_SCALE = 1 << Q1_15_FRACTIONAL_BITS
Q1_15_MIN = -(1 << 15)
Q1_15_MAX = (1 << 15) - 1


def round_ties_away_from_zero(x: np.ndarray) -> np.ndarray:
    x_arr = np.asarray(x, dtype=np.float64)
    return np.where(
        x_arr >= 0.0,
        np.floor(x_arr + 0.5),
        np.ceil(x_arr - 0.5),
    )


def count_clipped_q1_15(x: np.ndarray) -> int:
    x_arr = np.asarray(x, dtype=np.float64)
    scaled = x_arr * Q1_15_SCALE
    rounded = round_ties_away_from_zero(scaled)
    clip_mask = (rounded < Q1_15_MIN) | (rounded > Q1_15_MAX)
    return int(np.count_nonzero(clip_mask))


def quantize_q1_15(
    x: np.ndarray,
    *,
    warn_on_clip: bool = False,
) -> np.ndarray:
    x_arr = np.asarray(x, dtype=np.float64)
    scaled = x_arr * Q1_15_SCALE
    rounded = round_ties_away_from_zero(scaled)
    clip_mask = (rounded < Q1_15_MIN) | (rounded > Q1_15_MAX)
    if warn_on_clip and np.any(clip_mask):
        print(
            "[WARN] q1.15 clipping: "
            f"{int(np.count_nonzero(clip_mask))} samples, "
            f"max={float(np.max(rounded)):.1f}, "
            f"min={float(np.min(rounded)):.1f}"
        )

    clipped = np.clip(rounded, Q1_15_MIN, Q1_15_MAX)
    return clipped.astype(np.int16)


def dequantize_q1_15(x_q15: np.ndarray) -> np.ndarray:
    x_arr = np.asarray(x_q15)
    if not np.issubdtype(x_arr.dtype, np.integer):
        raise TypeError("x_q15 must contain integer values.")
    if x_arr.size > 0:
        x_min = int(np.min(x_arr))
        x_max = int(np.max(x_arr))
        if x_min < Q1_15_MIN or x_max > Q1_15_MAX:
            raise ValueError("x_q15 must stay within signed Q1.15/int16 range.")
    return x_arr.astype(np.float64) / Q1_15_SCALE
