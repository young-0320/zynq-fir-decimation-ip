import numpy as np

from model.ideal.anti_alias_fir import anti_alias_fir_ideal
from model.ideal.decimator import decimate


def run_fir_decimator_ideal(
    x: np.ndarray,
    h: np.ndarray,
    m: int = 2,
    phase: int = 0,
    return_intermediate: bool = False,
) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
    """Ideal FIR-Decimator 체인을 실행한다.

    Args:
        x: anti-alias FIR에 입력할 1-D 신호 배열.
        h: FIR 필터 배열.
        m: 디시메이션 계수. 기본값은 2.
        phase: decimation 시 몇 번째 샘플부터 선택할지 정하는 오프셋.
        return_intermediate: True이면 FIR 출력과 decimation 출력을 함께 반환한다.

    Returns:
        기본값(False)에서는 decimation 출력만 반환한다.
        True이면 `(y_fir, y_decim)` 튜플을 반환한다.
    """
    if not isinstance(return_intermediate, bool):
        raise TypeError("return_intermediate must be a bool.")

    y_fir = anti_alias_fir_ideal(x, h)
    y_decim = decimate(y_fir, m=m, phase=phase)

    if return_intermediate:
        return y_fir, y_decim
    return y_decim
