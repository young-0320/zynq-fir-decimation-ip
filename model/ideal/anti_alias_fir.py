# File: anti_alias_fir.py
# Role: 1D FIR IDEAL (부동소수점) 참조 모델과 입력/계수 검증 로직을 제공한다.

import numpy as np


def _validate_x(x: np.ndarray) -> np.ndarray:
    if not isinstance(x, np.ndarray):
        raise TypeError("x must be a numpy.ndarray.")
    # 1D인지
    if x.ndim != 1:
        raise ValueError("x must be a 1-D array.")
    # NaN, +Inf, -Inf를 전부 False로 처리
    if not np.isfinite(x).all():
        raise ValueError("x must contain only finite values.")

    return x.astype(np.float64, copy=False)


def _validate_h(h: np.ndarray) -> np.ndarray:
    if not isinstance(h, np.ndarray):
        raise TypeError("h must be a numpy.ndarray.")
    if h.ndim != 1:
        raise ValueError("h must be a 1-D array.")
    if h.size == 0:
        raise ValueError("h must not be empty.")
    if not np.isfinite(h).all():
        raise ValueError("h must contain only finite values.")

    return h.astype(np.float64, copy=False)


def anti_alias_fir_ideal(x: np.ndarray, h: np.ndarray) -> np.ndarray:
    x = _validate_x(x)
    h = _validate_h(h)

    N = len(x)
    num_taps = len(h)  # 필터 h의 길이, 탭 수
    center = num_taps // 2

    y = np.zeros(N, dtype=np.float64)

    for n in range(N):
        acc = 0.0  # Accumulator
        for k in range(num_taps):
            input_idx = n - k + center
            if 0 <= input_idx < N:
                acc += h[k] * x[input_idx]

        # Ideal spec: output is pass-through float (no clamp)
        y[n] = acc

    return y
