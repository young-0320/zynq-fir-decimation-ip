import numpy as np

from model.config import FIR_CONFIG
from model.fixed.transposed_form.anti_alias_fir import anti_alias_fir_transposed_golden
from model.fixed.decimator import decimate_golden


def run_fir_decimator_transposed_golden(
    x: np.ndarray,
    h: np.ndarray,
    m: int = FIR_CONFIG.decimation_factor,
    phase: int = FIR_CONFIG.default_phase,
    return_intermediate: bool = False,
) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
    """Transposed Form Q1.15 FIR-Decimator 체인을 실행한다.

    Transposed Form FIR 이후 decimation을 수행한다.
    decimator는 Direct Form golden과 동일한 decimate_golden을 재사용한다.

    Args:
        x: 입력 신호. 1-D ndarray, signed Q1.15 int16.
        h: FIR 계수 배열. 1-D ndarray, signed Q1.15 int16.
           h.size가 곧 탭 수 (가변).
        m: 디시메이션 계수. 기본값은 2.
        phase: decimation 시 몇 번째 샘플부터 선택할지 정하는 오프셋.
        return_intermediate: True이면 FIR 출력과 decimation 출력을 함께 반환한다.

    Returns:
        기본값(False)에서는 decimation 출력만 반환한다.
        True이면 (y_fir, y_decim) 튜플을 반환한다.
    """
    if not isinstance(return_intermediate, bool):
        raise TypeError("return_intermediate must be a bool.")

    y_fir = anti_alias_fir_transposed_golden(x, h)
    y_decim = decimate_golden(y_fir, m=m, phase=phase)

    if return_intermediate:
        return y_fir, y_decim
    return y_decim
