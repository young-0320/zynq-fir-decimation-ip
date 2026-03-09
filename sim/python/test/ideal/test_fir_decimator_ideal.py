import numpy as np
import pytest

from model.ideal.fir_decimator_ideal import run_fir_decimator_ideal


def test_run_fir_decimator_ideal_runs_fir_then_decimation() -> None:
    """FIR 이후 decimation 순서로 체인 출력이 계산되는지 확인한다."""
    x = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    h = np.array([0.5, 0.5], dtype=np.float64)

    y = run_fir_decimator_ideal(x, h, m=2, phase=0)

    expected = np.array([0.5, 2.5], dtype=np.float64)
    assert isinstance(y, np.ndarray)
    assert y.dtype == np.float64
    assert np.allclose(y, expected, atol=1e-12)


def test_run_fir_decimator_ideal_applies_phase_to_fir_output() -> None:
    """phase 인자가 FIR 출력의 시작 샘플 선택에 반영되는지 확인한다."""
    x = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    h = np.array([0.5, 0.5], dtype=np.float64)

    y = run_fir_decimator_ideal(x, h, m=2, phase=1)

    expected = np.array([1.5, 1.5], dtype=np.float64)
    assert np.allclose(y, expected, atol=1e-12)


def test_run_fir_decimator_ideal_can_return_intermediate_outputs() -> None:
    """옵션 활성화 시 FIR 출력과 decimation 출력을 함께 반환하는지 확인한다."""
    x = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    h = np.array([0.5, 0.5], dtype=np.float64)

    y_fir, y_decim = run_fir_decimator_ideal(
        x,
        h,
        m=2,
        phase=0,
        return_intermediate=True,
    )

    expected_fir = np.array([0.5, 1.5, 2.5, 1.5], dtype=np.float64)
    expected_decim = np.array([0.5, 2.5], dtype=np.float64)

    assert isinstance(y_fir, np.ndarray)
    assert isinstance(y_decim, np.ndarray)
    assert y_fir.dtype == np.float64
    assert y_decim.dtype == np.float64
    assert np.allclose(y_fir, expected_fir, atol=1e-12)
    assert np.allclose(y_decim, expected_decim, atol=1e-12)


def test_run_fir_decimator_ideal_rejects_non_bool_return_intermediate() -> None:
    """return_intermediate가 bool이 아니면 예외를 발생시키는지 확인한다."""
    x = np.array([1.0, 2.0], dtype=np.float64)
    h = np.array([1.0], dtype=np.float64)

    with pytest.raises(TypeError):
        run_fir_decimator_ideal(x, h, return_intermediate=0)
