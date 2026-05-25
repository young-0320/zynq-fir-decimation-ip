"""Save-only report pipeline for FIR N43 board evidence.

English: Captures fixed board scenarios, computes metrics, and saves PNG/JSON/
Markdown artifacts under ``docs/report/fir_n43``.
Korean: 고정 보드 시나리오를 캡처하고 metric을 계산한 뒤
``docs/report/fir_n43`` 아래에 PNG/JSON/Markdown 산출물을 저장합니다.

This script never calls ``plt.show()``. Use ``fir_decimator_fft_viewer.py`` for
interactive FFT windows.
이 스크립트는 ``plt.show()``를 호출하지 않습니다. PC 화면 FFT 확인은
``fir_decimator_fft_viewer.py``를 사용합니다.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from sw import fir_decimator_metrics as metrics
from sw.fir_decimator_capture import DEFAULT_UART_TIMEOUT_SEC, capture_output_q15, q15_to_float
from sw.fir_decimator_fft_viewer import (
    FIR_COEFFS_Q15,
    FS_HZ,
    INPUT_FFT_XLIM_MHZ,
    INPUT_BAND_BOUNDARIES_MHZ,
    INPUT_MARKER_COLOR,
    N_IN,
    N_OUT,
    OUTPUT_FFT_DISPLAY_XLIM_MHZ,
    OUTPUT_FS_HZ,
    OUTPUT_INVALID_REGION_MHZ,
    OUTPUT_MARKER_COLOR,
    PAIR_FIGSIZE,
    PLOT_LAYOUT_RECT,
    PRESET_1_1,
    PRESET_1_2,
    _fft_axis_title,
    _set_figure_header,
    _tone_marker_specs,
    plot_fft_pair,
)

DEFAULT_SAVE_DIR = Path("docs/report/fir_n43")
PLOT_DIR_NAME = "plot"
METRICS_DIR_NAME = "metrics"
SUMMARY_DIR_NAME = "summary"
BOARD_RESET_LIMITATION = "Run one report scenario per board reset."


@dataclass(frozen=True)
class ScenarioConfig:
    """Describe one fixed board-report scenario.
    고정 보드 리포트 시나리오 하나를 설명합니다.
    """

    mode: str
    title: str
    slug: str
    freqs_hz: tuple[float, ...]
    regions: Mapping[float, str]


@dataclass(frozen=True)
class OutputPaths:
    """Hold output paths for one scenario artifact set.
    시나리오 하나의 산출물 경로 묶음을 보관합니다.
    """

    plot_path: Path
    metrics_path: Path
    summary_path: Path


@dataclass(frozen=True)
class ScenarioResult:
    """Hold saved paths and metrics for one completed scenario.
    완료된 시나리오 하나의 저장 경로와 metric을 보관합니다.
    """

    scenario: ScenarioConfig
    metrics_report: metrics.MetricsReport
    paths: OutputPaths


SCENARIOS: dict[str, ScenarioConfig] = {
    "1-1": ScenarioConfig(
        mode="1-1",
        title="Scenario 1-1",
        slug="scenario1_1",
        freqs_hz=tuple(float(freq) for freq in PRESET_1_1),
        regions={
            5e6: "passband",
            20e6: "transition",
            30e6: "stopband",
        },
    ),
    "1-2": ScenarioConfig(
        mode="1-2",
        title="Scenario 1-2",
        slug="scenario1_2",
        freqs_hz=tuple(float(freq) for freq in PRESET_1_2),
        regions={
            7e6: "passband",
            15e6: "passband",
            25e6: "transition",
            45e6: "stopband",
        },
    ),
}


def _json_safe(value: Any) -> Any:
    """Convert numpy and non-finite values into strict JSON-safe values.
    numpy 값과 non-finite 값을 strict JSON으로 저장 가능한 값으로 변환합니다.
    """
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float):
        if math.isinf(value):
            return "inf" if value > 0.0 else "-inf"
        if math.isnan(value):
            return "nan"
        return value
    return value


def _format_number(value: Any, digits: int = 3) -> str:
    """Format report table values compactly.
    리포트 표에 넣을 숫자를 간결하게 포맷합니다.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, (np.integer, int)):
        return str(int(value))
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float):
        if math.isinf(value):
            return "inf" if value > 0.0 else "-inf"
        if math.isnan(value):
            return "nan"
        return f"{value:.{digits}f}"
    return str(value)


def _ensure_output_dirs(save_dir: Path) -> tuple[Path, Path, Path]:
    """Create report root, plot, metrics, and summary directories when missing.
    report root, plot, metrics, summary 디렉터리가 없으면 생성합니다.
    """
    plot_dir = save_dir / PLOT_DIR_NAME
    metrics_dir = save_dir / METRICS_DIR_NAME
    summary_dir = save_dir / SUMMARY_DIR_NAME
    plot_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)
    summary_dir.mkdir(parents=True, exist_ok=True)
    return plot_dir, metrics_dir, summary_dir


def _output_paths(save_dir: Path, scenario: ScenarioConfig) -> OutputPaths:
    """Return the PNG and JSON paths for one scenario.
    시나리오 하나의 PNG 및 JSON 저장 경로를 반환합니다.
    """
    plot_dir, metrics_dir, summary_dir = _ensure_output_dirs(save_dir)
    return OutputPaths(
        plot_path=plot_dir / f"{scenario.slug}_fft.png",
        metrics_path=metrics_dir / f"{scenario.slug}_metrics.json",
        summary_path=summary_dir / f"{scenario.slug}_summary.md",
    )


def _save_fft_png(
    path: Path,
    scenario: ScenarioConfig,
    input_q15: npt.ArrayLike,
    board_output_q15: npt.ArrayLike,
) -> None:
    """Save input/output FFT PNG without opening a GUI window.
    GUI 창을 열지 않고 입력/출력 FFT PNG를 저장합니다.
    """
    sig_in = q15_to_float(input_q15)
    sig_out = q15_to_float(board_output_q15)
    input_markers = _tone_marker_specs(scenario.freqs_hz, FS_HZ)
    output_markers = _tone_marker_specs(scenario.freqs_hz, OUTPUT_FS_HZ)

    fig, (ax_l, ax_r) = plt.subplots(1, 2, figsize=PAIR_FIGSIZE)
    _set_figure_header(fig, scenario.title, scenario.freqs_hz)
    plot_fft_pair(
        ax_l,
        ax_r,
        sig_in,
        FS_HZ,
        sig_out,
        OUTPUT_FS_HZ,
        _fft_axis_title("Input FFT", FS_HZ),
        _fft_axis_title("Output FFT after FIR", OUTPUT_FS_HZ),
        xlim_l=INPUT_FFT_XLIM_MHZ,
        xlim_r=OUTPUT_FFT_DISPLAY_XLIM_MHZ,
        markers_l=input_markers,
        markers_r=output_markers,
        marker_label_l="input tone target",
        marker_label_r="output alias target",
        marker_color_l=INPUT_MARKER_COLOR,
        marker_color_r=OUTPUT_MARKER_COLOR,
        invalid_region_r=OUTPUT_INVALID_REGION_MHZ,
        band_boundaries_l=INPUT_BAND_BOUNDARIES_MHZ,
    )
    fig.tight_layout(rect=PLOT_LAYOUT_RECT)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _write_metrics_json(path: Path, report: metrics.MetricsReport) -> None:
    """Write one metrics report as strict JSON.
    metric report 하나를 strict JSON 파일로 저장합니다.
    """
    path.write_text(
        json.dumps(_json_safe(report), indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _tone_list_mhz(freqs_hz: Sequence[float]) -> str:
    """Format scenario tone frequencies in MHz.
    시나리오 tone 주파수 목록을 MHz 단위 문자열로 만듭니다.
    """
    return ", ".join(_format_number(float(freq) / 1e6, digits=0) for freq in freqs_hz)



def _markdown_link(from_dir: Path, target: Path) -> str:
    """Return a POSIX relative link from one output directory to a target.
    출력 디렉터리 하나를 기준으로 target까지의 POSIX 상대 링크를 반환합니다.
    """
    return Path(os.path.relpath(target, from_dir)).as_posix()


def _write_scenario_summary(path: Path, result: ScenarioResult) -> Path:
    """Write one scenario Markdown summary next to the report artifacts.
    report 산출물과 함께 시나리오별 Markdown summary를 저장합니다.
    """
    report = result.metrics_report
    sample = report["sample_metrics"]
    summary = report["summary"]
    tone_regions = result.scenario.regions
    base_dir = path.parent
    plot_rel = _markdown_link(base_dir, result.paths.plot_path)
    metrics_rel = _markdown_link(base_dir, result.paths.metrics_path)

    lines = [
        f"# FIR N43 Board Evidence - {result.scenario.title}",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|---|---:|",
        f"| Scenario | {result.scenario.title} |",
        f"| Tones (MHz) | {_tone_list_mhz(result.scenario.freqs_hz)} |",
        f"| Overall | {summary['overall_verdict']} |",
        f"| Max Error (LSB) | {sample['max_abs_error_lsb']} |",
        f"| RMSE (LSB) | {_format_number(sample['rmse_lsb'])} |",
        f"| SNR (dB) | {_format_number(sample['snr_db'])} |",
        f"| Correlation | {_format_number(sample['correlation'], digits=6)} |",
        f"| FFT PNG | [{plot_rel}]({plot_rel}) |",
        f"| Metrics JSON | [{metrics_rel}]({metrics_rel}) |",
        "",
        "## Tone Regions",
        "",
        "| Tone (MHz) | Region |",
        "|---:|---|",
    ]
    for tone_hz, region in sorted(tone_regions.items()):
        lines.append(f"| {_format_number(float(tone_hz) / 1e6, digits=0)} | {region} |")

    limitations = report["known_limitations"]
    if limitations:
        lines.extend(["", "## Known Limitations", ""])
        lines.extend(f"- {limitation}" for limitation in limitations)
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _capture_and_report_scenario(
    scenario: ScenarioConfig,
    *,
    port: str,
    baud: int,
    timeout: float,
    save_dir: Path,
) -> ScenarioResult:
    """Capture one board scenario, compute metrics, and save artifacts.
    보드 시나리오 하나를 캡처하고 metric 계산 및 산출물 저장을 수행합니다.
    """
    paths = _output_paths(save_dir, scenario)
    board_output_q15 = capture_output_q15(
        port,
        baud,
        timeout,
        scenario.freqs_hz,
        expected_samples=N_OUT,
    )
    if board_output_q15.size != N_OUT:
        raise ValueError(f"expected {N_OUT} output samples, got {board_output_q15.size}")

    reference = metrics.generate_fixed_reference(
        scenario.freqs_hz,
        n_in=N_IN,
        fs_hz=FS_HZ,
        coeffs_q15=FIR_COEFFS_Q15,
        n_out=N_OUT,
    )
    report = metrics.build_report(
        scenario.mode,
        scenario.freqs_hz,
        reference["input_q15"],
        board_output_q15,
        reference["fixed_q15_reference"],
        fs_in_hz=FS_HZ,
        fs_out_hz=OUTPUT_FS_HZ,
        regions=scenario.regions,
        fft_plot_path=str(paths.plot_path),
        known_limitations=[BOARD_RESET_LIMITATION],
    )

    result = ScenarioResult(scenario=scenario, metrics_report=report, paths=paths)
    _save_fft_png(paths.plot_path, scenario, reference["input_q15"], board_output_q15)
    _write_metrics_json(paths.metrics_path, report)
    _write_scenario_summary(paths.summary_path, result)
    return result


def run_report(
    *,
    mode: str,
    port: str,
    baud: int,
    timeout: float,
    save_dir: Path,
) -> list[ScenarioResult]:
    """Run one report scenario and save its scenario summary.
    report 시나리오 하나를 실행하고 해당 시나리오 summary를 저장합니다.
    """
    save_dir.mkdir(parents=True, exist_ok=True)
    result = _capture_and_report_scenario(
        SCENARIOS[mode],
        port=port,
        baud=baud,
        timeout=timeout,
        save_dir=save_dir,
    )
    return [result]


def main() -> None:
    """Parse CLI arguments and run the save-only report pipeline.
    CLI 인자를 해석하고 저장 전용 report pipeline을 실행합니다.
    """
    parser = argparse.ArgumentParser(description="FIR N43 board evidence report generator")
    parser.add_argument(
        "--mode",
        required=True,
        choices=["1-1", "1-2"],
        help="Single report scenario to capture. Reset the board before each scenario.",
    )
    parser.add_argument("--port", default="/dev/ttyUSB1", help="UART port")
    parser.add_argument("--baud", type=int, default=115200, help="UART baud rate")
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_UART_TIMEOUT_SEC,
        help=f"UART read timeout seconds (default: {DEFAULT_UART_TIMEOUT_SEC})",
    )
    parser.add_argument(
        "--save-dir",
        type=Path,
        default=DEFAULT_SAVE_DIR,
        help=f"Report output root (default: {DEFAULT_SAVE_DIR})",
    )
    args = parser.parse_args()

    results = run_report(
        mode=args.mode,
        port=args.port,
        baud=args.baud,
        timeout=args.timeout,
        save_dir=args.save_dir,
    )
    for result in results:
        print(f"{result.scenario.title}: {result.metrics_report['summary']['overall_verdict']}")
        print(f"  plot: {result.paths.plot_path}")
        print(f"  metrics: {result.paths.metrics_path}")
        print(f"  summary: {result.paths.summary_path}")


if __name__ == "__main__":
    main()
