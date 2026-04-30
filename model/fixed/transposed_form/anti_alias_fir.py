# File: anti_alias_fir_transposed_golden.py
# Role: 1D FIR Transposed Form Q1.15 고정소수점 골든 모델을 제공한다.
#
# 정책 근거: docs/log/13_transposed_form_golden_policy.md
#
# Transposed Form 구조:
#   z[k]: k번째 delay register (signed 48-bit, Q2.30, int64로 표현)
#
#   매 출력 샘플 n마다:
#       x_n        = x[n] if 0 <= n < input_len else 0  (np.int32)
#       prod       = np.int32(h[k]) * np.int32(x_n)     (32-bit 곱셈)
#       new_z[k]   = np.int64(prod) + z[k+1]            (48-bit 누산)
#       new_z[N-1] = np.int64(np.int32(h[N-1]) * x_n)
#       y[n]       = round_and_saturate(new_z[0])        (Q2.30 → Q1.15, 1회)
#       z          = new_z

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
    """Q2.30 → Q1.15 변환 시 ties-away-from-zero 반올림."""
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


def anti_alias_fir_transposed_golden(
    x: np.ndarray,
    h: np.ndarray,
) -> np.ndarray:
    """Transposed Form FIR을 Q1.15 고정소수점으로 구현한 골든 모델.

    이 모델은 RTL Transposed Form 구현의 bit-exact 기준선이다.
    Direct Form golden과 동일한 입력/출력 계약을 따른다.

    Args:
        x: 입력 신호. 1-D ndarray, signed Q1.15 int16.
        h: FIR 계수 배열. 1-D ndarray, signed Q1.15 int16.
           h.size가 곧 탭 수 (가변).

    Returns:
        full convolution 출력. dtype=np.int16.
        shape=(len(x) + len(h) - 1,).
        x가 빈 배열이면 빈 np.int16 배열을 반환한다.
    """
    x_arr = _validate_q1_15_int_array(x, name="x")
    h_arr = _validate_q1_15_int_array(h, name="h")

    if h_arr.size == 0:
        raise ValueError("h must not be empty.")

    if x_arr.size == 0:
        return np.array([], dtype=np.int16)

    num_taps = h_arr.size
    input_len = x_arr.size
    output_len = input_len + num_taps - 1

    y = np.zeros(output_len, dtype=np.int16)

    # z[k]: delay register, signed 48-bit Q2.30
    # int64로 표현 (48-bit 범위를 초과하지 않음이 worst-case 계산으로 확인됨)
    # 초기값 0 (RTL reset 시 state = 0 계약과 동일)
    z = np.zeros(num_taps, dtype=np.int64)

    for n in range(output_len):
        # full convolution: 입력 범위 밖은 0으로 처리
        # x_n을 np.int32로 명시 — RTL의 16-bit 입력 포트와 대응
        x_n = np.int32(x_arr[n]) if 0 <= n < input_len else np.int32(0)

        new_z = np.zeros(num_taps, dtype=np.int64)

        for k in range(num_taps - 1):
            # 16-bit × 16-bit → 32-bit 곱셈 후 48-bit sign-extend 누산
            # RTL: prod = signed 32-bit, z[k+1] = signed 48-bit
            prod = np.int64(np.int32(h_arr[k]) * x_n)
            new_z[k] = prod + z[k + 1]

        # k = N-1: z[k+1]이 없으므로 곱셈 결과만 저장
        new_z[num_taps - 1] = np.int64(np.int32(h_arr[num_taps - 1]) * x_n)

        # 출력: z[0] (Q2.30) → Q1.15, 반올림 1회, 포화 1회
        rounded = _round_shift_ties_away_from_zero(
            int(new_z[0]),
            shift_bits=Q1_15_FRACTIONAL_BITS,
        )
        y[n] = _saturate_to_q1_15(rounded)

        z = new_z

    return y
