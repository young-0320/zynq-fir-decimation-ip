import numpy as np
import pytest

from model.ideal.anti_alias_fir import anti_alias_fir_ideal


def test_anti_alias_fir_ideal_returns_float64_ndarray_with_full_length() -> None:
    """출력이 float64 ndarray이며 길이가 full convolution과 같은지 확인한다."""
    x = np.array([1, 2, 3, 4], dtype=np.int16)
    h = np.array([0.25, 0.5, 0.25], dtype=np.float32)

    y = anti_alias_fir_ideal(x, h)

    assert isinstance(y, np.ndarray)
    assert y.dtype == np.float64
    assert len(y) == len(x) + len(h) - 1


def test_anti_alias_fir_ideal_returns_empty_array_for_empty_input() -> None:
    """빈 입력 배열이 들어오면 빈 출력 배열을 반환하는지 확인한다."""
    x = np.array([], dtype=np.float64)
    h = np.array([0.2, 0.6, 0.2], dtype=np.float64)

    y = anti_alias_fir_ideal(x, h)

    assert isinstance(y, np.ndarray)
    assert y.dtype == np.float64
    assert y.size == 0


def test_anti_alias_fir_ideal_returns_raw_impulse_response() -> None:
    """첫 샘플 임펄스 입력에 대해 계수와 tail이 그대로 드러나는지 확인한다."""
    h = np.array([0.1, 0.3, 0.6], dtype=np.float64)
    x = np.zeros(5, dtype=np.float64)
    x[0] = 1.0

    y = anti_alias_fir_ideal(x, h)

    expected = np.array([0.1, 0.3, 0.6, 0.0, 0.0, 0.0, 0.0], dtype=np.float64)
    assert np.allclose(y, expected, atol=1e-12)


@pytest.mark.parametrize(
    ("x", "expected_exception"),
    [
        ([1.0, 2.0, 3.0], TypeError),
        (np.array([[1.0, 2.0, 3.0]], dtype=np.float64), ValueError),
        (np.array([1.0, np.nan], dtype=np.float64), ValueError),
        (np.array([1.0, np.inf], dtype=np.float64), ValueError),
    ],
)
def test_anti_alias_fir_ideal_rejects_invalid_x(
    x: np.ndarray,
    expected_exception: type[Exception],
) -> None:
    """x 입력의 타입, 차원, 유한값 조건을 검증하는지 확인한다."""
    h = np.array([1.0], dtype=np.float64)

    with pytest.raises(expected_exception):
        anti_alias_fir_ideal(x, h)


@pytest.mark.parametrize(
    ("h", "expected_exception"),
    [
        ([1.0], TypeError),
        (np.array([[1.0]], dtype=np.float64), ValueError),
        (np.array([], dtype=np.float64), ValueError),
        (np.array([1.0, np.nan], dtype=np.float64), ValueError),
        (np.array([1.0, -np.inf], dtype=np.float64), ValueError),
    ],
)
def test_anti_alias_fir_ideal_rejects_invalid_h(
    h: np.ndarray,
    expected_exception: type[Exception],
) -> None:
    """h 입력의 타입, 차원, 빈 배열, 유한값 조건을 검증하는지 확인한다."""
    x = np.array([1.0, 2.0, 3.0], dtype=np.float64)

    with pytest.raises(expected_exception):
        anti_alias_fir_ideal(x, h)
