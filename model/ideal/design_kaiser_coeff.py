# File: design_kaiser_coeff.py
"""Utilities to generate ideal FIR coefficients for simulation."""

from __future__ import annotations

import math

import numpy as np

from model.config import FIR_CONFIG


def _validate_design_inputs(
    fs_in_hz: float,
    fp_hz: float,
    fs_hz: float,
    as_db: float,
) -> None:
    if fs_in_hz <= 0.0:
        raise ValueError("fs_in_hz must be positive.")
    if not (0.0 < fp_hz < fs_hz < fs_in_hz / 2.0):
        raise ValueError("Expected 0 < fp_hz < fs_hz < fs_in_hz/2.")
    if as_db <= 0.0:
        raise ValueError("as_db must be positive.")


def kaiser_beta(as_db: float) -> float:
    """Return Kaiser beta from stopband attenuation in dB."""
    if as_db <= 21.0:
        return 0.0
    elif as_db <= 50.0:
        return 0.5842 * (as_db - 21.0) ** 0.4 + 0.07886 * (as_db - 21.0)
    return 0.1102 * (as_db - 8.7)


def estimate_num_taps(
    fs_in_hz: float,
    fp_hz: float,
    fs_hz: float,
    as_db: float,
) -> int:
    """Estimate odd number of taps using Kaiser approximation."""
    _validate_design_inputs(
        fs_in_hz=fs_in_hz,
        fp_hz=fp_hz,
        fs_hz=fs_hz,
        as_db=as_db,
    )

    transition_hz = fs_hz - fp_hz
    delta_omega = 2.0 * math.pi * transition_hz / fs_in_hz
    order = (as_db - 8.0) / (2.285 * delta_omega)
    num_taps = int(math.ceil(order)) + 1

    # Prefer odd taps for a Type-I linear-phase LPF.
    if num_taps % 2 == 0:
        num_taps += 1
    return num_taps


def design_kaiser_lpf(
    fs_in_hz: float,
    fp_hz: float,
    fs_hz: float,
    as_db: float,
    num_taps: int | None = None,
) -> np.ndarray:
    """Design low-pass FIR coefficients with Kaiser window.

    Args:
        fs_in_hz: Input sampling frequency (Hz).
        fp_hz: Passband edge frequency (Hz).
        fs_hz: Stopband start frequency (Hz).
        as_db: Target stopband attenuation (dB).
        num_taps: Number of taps. If None, estimate via Kaiser approximation.

    Returns:
        FIR coefficients as float64 numpy array.
    """
    _validate_design_inputs(
        fs_in_hz=fs_in_hz,
        fp_hz=fp_hz,
        fs_hz=fs_hz,
        as_db=as_db,
    )

    if num_taps is None:
        num_taps = estimate_num_taps(
            fs_in_hz=fs_in_hz,
            fp_hz=fp_hz,
            fs_hz=fs_hz,
            as_db=as_db,
        )
    if num_taps < 3:
        raise ValueError("num_taps must be >= 3.")

    fc_hz = 0.5 * (fp_hz + fs_hz)
    fc_norm = fc_hz / fs_in_hz

    n = np.arange(num_taps, dtype=np.float64)
    m = n - (num_taps - 1) / 2.0
    h_ideal = 2.0 * fc_norm * np.sinc(2.0 * fc_norm * m)

    beta = kaiser_beta(as_db)
    window = np.kaiser(num_taps, beta)
    h = h_ideal * window

    # Normalize DC gain to 1 for stable passband reference.
    h /= np.sum(h)
    return h.astype(np.float64, copy=False)

if __name__ == "__main__":
    # Example usage.
    fs_in_hz = FIR_CONFIG.fs_in_hz
    fp_hz = FIR_CONFIG.fp_hz
    fs_hz = FIR_CONFIG.fs_hz
    as_db = FIR_CONFIG.as_db
    beta = kaiser_beta(as_db)

    num_taps = estimate_num_taps(
        fs_in_hz=fs_in_hz,
        fp_hz=fp_hz,
        fs_hz=fs_hz,
        as_db=as_db,
    )
    print(f"beta={beta:.5f}")
    print(f"num_taps={num_taps}")
