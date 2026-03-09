import numpy as np
import pytest

from model.ideal.design_kaiser_coeff import design_kaiser_lpf


FS_IN_HZ = 100e6
FP_HZ = 15e6
FS_HZ = 25e6
AS_DB = 60.0


def test_design_kaiser_lpf_returns_float64_array_with_requested_length() -> None:
    """설계 함수가 요청한 탭 길이의 float64 계수 배열을 반환하는지 확인한다."""
    h = design_kaiser_lpf(
        fs_in_hz=FS_IN_HZ,
        fp_hz=FP_HZ,
        fs_hz=FS_HZ,
        as_db=AS_DB,
        num_taps=41,
    )

    assert isinstance(h, np.ndarray)
    assert h.dtype == np.float64
    assert len(h) == 41


def test_design_kaiser_lpf_normalizes_dc_gain_to_one() -> None:
    """설계된 계수의 합이 1에 가깝게 정규화되는지 확인한다."""
    h = design_kaiser_lpf(
        fs_in_hz=FS_IN_HZ,
        fp_hz=FP_HZ,
        fs_hz=FS_HZ,
        as_db=AS_DB,
        num_taps=41,
    )

    assert np.isclose(np.sum(h), 1.0, atol=1e-12)


def test_design_kaiser_lpf_produces_symmetric_coefficients() -> None:
    """카이저 기반 LPF 계수가 중심을 기준으로 대칭인지 확인한다."""
    h = design_kaiser_lpf(
        fs_in_hz=FS_IN_HZ,
        fp_hz=FP_HZ,
        fs_hz=FS_HZ,
        as_db=AS_DB,
        num_taps=41,
    )

    assert np.allclose(h, h[::-1], atol=1e-12)


@pytest.mark.parametrize(
    ("fs_in_hz", "fp_hz", "fs_hz", "as_db", "num_taps"),
    [
        (0.0, FP_HZ, FS_HZ, AS_DB, 41),
        (FS_IN_HZ, 30e6, 25e6, AS_DB, 41),
        (FS_IN_HZ, FP_HZ, 60e6, AS_DB, 41),
        (FS_IN_HZ, FP_HZ, FS_HZ, 0.0, 41),
        (FS_IN_HZ, FP_HZ, FS_HZ, AS_DB, 1),
    ],
)
def test_design_kaiser_lpf_rejects_invalid_parameters(
    fs_in_hz: float,
    fp_hz: float,
    fs_hz: float,
    as_db: float,
    num_taps: int,
) -> None:
    """잘못된 설계 파라미터 입력에 대해 예외를 발생시키는지 확인한다."""
    with pytest.raises(ValueError):
        design_kaiser_lpf(
            fs_in_hz=fs_in_hz,
            fp_hz=fp_hz,
            fs_hz=fs_hz,
            as_db=as_db,
            num_taps=num_taps,
        )
