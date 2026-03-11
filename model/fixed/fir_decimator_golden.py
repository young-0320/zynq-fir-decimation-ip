import numpy as np

from model.fixed.anti_alias_fir import anti_alias_fir_golden
from model.fixed.decimator import decimate_golden


def run_fir_decimator_golden(
    x: np.ndarray,
    h: np.ndarray,
    m: int = 2,
    phase: int = 0,
    return_intermediate: bool = False,
) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
    """Run the fixed-point golden chain in FIR -> decimation order."""
    if not isinstance(return_intermediate, bool):
        raise TypeError("return_intermediate must be a bool.")

    y_fir = anti_alias_fir_golden(x, h)
    y_decim = decimate_golden(y_fir, m=m, phase=phase)

    if return_intermediate:
        return y_fir, y_decim
    return y_decim
