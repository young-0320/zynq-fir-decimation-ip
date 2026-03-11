import numpy as np


def generate_multitone(
    num_samples: int,
    fs_hz: float,
    tone_freqs_hz: list[float],
    amplitudes: list[float],
    phases_rad: list[float] | None = None,
) -> np.ndarray:
    """Generate a float64 multitone waveform."""
    if num_samples < 1:
        raise ValueError("num_samples must be >= 1.")
    if fs_hz <= 0.0:
        raise ValueError("fs_hz must be > 0.")
    if len(tone_freqs_hz) == 0:
        raise ValueError("tone_freqs_hz must not be empty.")
    if len(tone_freqs_hz) != len(amplitudes):
        raise ValueError("tone_freqs_hz and amplitudes must have the same length.")

    if phases_rad is None:
        phases = np.zeros(len(tone_freqs_hz), dtype=np.float64)
    else:
        if len(phases_rad) != len(tone_freqs_hz):
            raise ValueError("phases_rad must have the same length as tone_freqs_hz.")
        phases = np.asarray(phases_rad, dtype=np.float64)

    n = np.arange(num_samples, dtype=np.float64)
    x = np.zeros(num_samples, dtype=np.float64)

    for freq_hz, amplitude, phase_rad in zip(
        tone_freqs_hz,
        amplitudes,
        phases,
        strict=True,
    ):
        x += float(amplitude) * np.sin(
            (2.0 * np.pi * float(freq_hz) / fs_hz) * n + phase_rad,
        )

    return x


def quantize_q1_15(x: np.ndarray) -> np.ndarray:
    """Quantize a normalized float waveform to signed Q1.15."""
    x_arr = np.asarray(x, dtype=np.float64)
    scaled = x_arr * (2**15)
    rounded = np.where(
        scaled >= 0.0,
        np.floor(scaled + 0.5),
        np.ceil(scaled - 0.5),
    )
    x_q = np.clip(rounded, -(2**15), (2**15) - 1)
    return x_q.astype(np.int16)
