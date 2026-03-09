import numpy as np

from model.ideal.decimator import decimate


def run_downsample_only_ideal(
    x: np.ndarray,
    m: int = 2,
    phase: int = 0,
) -> np.ndarray:
    """FIR 없이 입력 신호를 바로 decimation하는 비교용 baseline 경로."""
    return decimate(x, m=m, phase=phase)
