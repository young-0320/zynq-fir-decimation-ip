import numpy as np
from typing import Sequence

from model.config import FIR_CONFIG
from model.q1_15 import quantize_q1_15


def generate_multitone(
    num_samples: int,
    fs_hz: float,
    tone_freqs_hz: Sequence[float],
    amplitudes: Sequence[float],
    phases_rad: Sequence[float] | None = None,
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
if __name__ == "__main__":
    # Example usage:
    fs = FIR_CONFIG.fs_in_hz
    freqs = FIR_CONFIG.bringup_tone_freqs_hz
    amps = FIR_CONFIG.bringup_tone_amplitudes
    phases = FIR_CONFIG.bringup_tone_phases_rad

    multitone = generate_multitone(
        num_samples=FIR_CONFIG.bringup_num_samples,
        fs_hz=fs,
        tone_freqs_hz=freqs,
        amplitudes=amps,
        phases_rad=phases,
    )
    print(multitone[:10])  # Print first 10 samples

    quantized = quantize_q1_15(multitone)
    print(quantized[:10])  # Print first 10 quantized samples

    print(f"\n[Q1.15 양자화 결과]")
    print(f"  max  = {np.max(quantized)}")
    print(f"  min  = {np.min(quantized)}")
    print(f"  peak = {np.max(np.abs(quantized.astype(np.int32)))}")
    print(
        "  클리핑 여부 = "
        f"{np.any(np.abs(quantized.astype(np.int32)) == FIR_CONFIG.q_scale) or np.max(quantized) == FIR_CONFIG.q_max}"
    )
