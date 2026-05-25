"""Official live demo entrypoint for the FIR decimator.

English: Runs the live FFT demo modes by forwarding to
``fir_decimator_fft_viewer.py`` while keeping this file as the user-facing demo
command.
Korean: 사용자에게 보이는 공식 live demo 명령으로 유지하면서 실제 FFT demo
mode 실행은 ``fir_decimator_fft_viewer.py``에 위임합니다.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from sw.fir_decimator_fft_viewer import *  # noqa: F403
    from sw.fir_decimator_fft_viewer import main
except ModuleNotFoundError:
    _REPO_ROOT = Path(__file__).resolve().parents[1]
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from sw.fir_decimator_fft_viewer import *  # noqa: F403
    from sw.fir_decimator_fft_viewer import main


if __name__ == "__main__":
    main()
