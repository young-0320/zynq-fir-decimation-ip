import numpy as np
import pytest

from model.ideal.decimator import decimate


def test_decimate_keeps_even_index_samples_when_phase_is_zero() -> None:
    """phase=0이면 짝수 인덱스 샘플만 남기는지 확인한다."""
    x = np.array([0, 1, 2, 3, 4, 5], dtype=np.int16)

    y = decimate(x, m=2, phase=0)

    expected = np.array([0.0, 2.0, 4.0], dtype=np.float64)
    assert isinstance(y, np.ndarray)
    assert y.dtype == np.float64
    assert np.array_equal(y, expected)


def test_decimate_keeps_odd_index_samples_when_phase_is_one() -> None:
    """phase=1이면 홀수 인덱스 샘플만 남기는지 확인한다."""
    x = np.array([0, 1, 2, 3, 4, 5], dtype=np.int16)

    y = decimate(x, m=2, phase=1)

    expected = np.array([1.0, 3.0, 5.0], dtype=np.float64)
    assert isinstance(y, np.ndarray)
    assert y.dtype == np.float64
    assert np.array_equal(y, expected)


def test_decimate_returns_empty_array_for_empty_input() -> None:
    """빈 입력 배열이 들어오면 빈 출력 배열을 반환하는지 확인한다."""
    x = np.array([], dtype=np.float64)

    y = decimate(x, m=2, phase=0)

    assert isinstance(y, np.ndarray)
    assert y.dtype == np.float64
    assert y.size == 0


@pytest.mark.parametrize(
    ("x", "expected_exception"),
    [
        ([0.0, 1.0, 2.0], TypeError),
        (np.array([[0.0, 1.0, 2.0]], dtype=np.float64), ValueError),
        (np.array([0.0, np.nan], dtype=np.float64), ValueError),
        (np.array([0.0, np.inf], dtype=np.float64), ValueError),
    ],
)
def test_decimate_rejects_invalid_x(
    x: np.ndarray,
    expected_exception: type[Exception],
) -> None:
    """x 입력의 타입, 차원, 유한값 조건을 검증하는지 확인한다."""
    with pytest.raises(expected_exception):
        decimate(x, m=2, phase=0)


@pytest.mark.parametrize(
    ("m", "phase", "expected_exception"),
    [
        (0, 0, ValueError),
        (2, -1, ValueError),
        (2, 2, ValueError),
        (2.0, 0, TypeError),
        (2, 0.0, TypeError),
    ],
)
def test_decimate_rejects_invalid_m_or_phase(
    m: int,
    phase: int,
    expected_exception: type[Exception],
) -> None:
    """m과 phase 파라미터의 범위와 타입을 검증하는지 확인한다."""
    x = np.array([0.0, 1.0, 2.0, 3.0], dtype=np.float64)

    with pytest.raises(expected_exception):
        decimate(x, m=m, phase=phase)
