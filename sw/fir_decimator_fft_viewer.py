"""Live FFT viewer for the FIR decimator board demo.

English: Generates demo tones, captures board output through capture helpers,
and displays input/output FFT plots.
Korean: 데모 톤을 만들고 capture helper로 보드 출력을 받아 입력/출력
FFT 그래프를 표시합니다.

This script does not compute metrics or write report files.
이 스크립트는 metric 계산이나 report 파일 생성을 하지 않습니다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt

try:
    from sw.fir_decimator_capture import (
        DEFAULT_UART_TIMEOUT_SEC,
        MAX_TONE_FREQ_HZ,
        MAX_TONES,
        MIN_TONE_FREQ_HZ,
        uart_open,
        uart_recv_result,
        uart_send_cmd,
        validate_tone_frequencies,
    )
except ModuleNotFoundError:
    _REPO_ROOT = Path(__file__).resolve().parents[1]
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from sw.fir_decimator_capture import (
        DEFAULT_UART_TIMEOUT_SEC,
        MAX_TONE_FREQ_HZ,
        MAX_TONES,
        MIN_TONE_FREQ_HZ,
        uart_open,
        uart_recv_result,
        uart_send_cmd,
        validate_tone_frequencies,
    )


N_IN = 8192
N_OUT = 4096
FS_HZ = 100e6

FIR_COEFFS_Q15 = np.array([
    10, 0, -33, -32, 47, 107, 0, -197, -159, 206,
    425, 0, -674, -522, 654, 1336, 0, -2258, -1939, 2995,
    9864, 13109, 9864, 2995, -1939, -2258, 0, 1336, 654, -522,
    -674, 0, 425, 206, -159, -197, 0, 107, 47, -32,
    -33, 0, 10
], dtype=np.int16)
FIR_COEFFS = FIR_COEFFS_Q15.astype(np.float64) / 32768.0

SCENARIO0_FREQS = [7e6, 15e6, 30e6, 45e6]
PRESET_1_1 = [5e6, 20e6, 30e6]
PRESET_1_2 = [7e6, 15e6, 25e6, 45e6]
INPUT_FFT_XLIM_MHZ = (0, FS_HZ / 2 / 1e6)
OUTPUT_FS_HZ = FS_HZ / 2
OUTPUT_FFT_VALID_XLIM_MHZ = (0, OUTPUT_FS_HZ / 2 / 1e6)
OUTPUT_FFT_DISPLAY_XLIM_MHZ = INPUT_FFT_XLIM_MHZ
OUTPUT_FFT_XLIM_MHZ = OUTPUT_FFT_DISPLAY_XLIM_MHZ
OUTPUT_INVALID_REGION_MHZ = (OUTPUT_FFT_VALID_XLIM_MHZ[1], OUTPUT_FFT_DISPLAY_XLIM_MHZ[1])
FIR_PASSBAND_MAX_MHZ = 15
FIR_STOPBAND_MIN_MHZ = 25
FIR_TRANSITION_BAND_MHZ = (FIR_PASSBAND_MAX_MHZ, FIR_STOPBAND_MIN_MHZ)
INPUT_BAND_BOUNDARIES_MHZ = (
    {"frequency_mhz": FIR_PASSBAND_MAX_MHZ, "label": "pass edge 15 MHz"},
    {"frequency_mhz": FIR_STOPBAND_MIN_MHZ, "label": "stop edge 25 MHz"},
)

# Plot tuning knobs. Edit these constants to adjust the viewer/report figures.
PAIR_FIGSIZE = (18, 7)
SCENARIO0_FIGSIZE = (21, 7)
FIG_SUPTITLE_FONTSIZE = 17
FIG_SUPTITLE_Y = 0.985
FIG_SUBTITLE_FONTSIZE = 11
FIG_SUBTITLE_Y = 0.94
FIG_SUBTITLE_COLOR = "#374151"
PLOT_LAYOUT_RECT = (0, 0, 1, 0.88)
PLOT_YLIM_DB = (-100, 5)
PLOT_LINEWIDTH = 1.5
GRID_ENABLED = True

INPUT_MARKER_COLOR = "#2563eb"
OUTPUT_MARKER_COLOR = "#c2410c"
NYQUIST_MARKER_COLOR = "#7c3aed"
TONE_MARKER_LINEWIDTH = 1.0
TONE_MARKER_ALPHA = 0.85
TONE_MARKER_LABEL_FONTSIZE = 8
TONE_MARKER_LABEL_OFFSET = (3, -4)
TONE_MARKER_EDGE_LABEL_OFFSET = (-3, -4)
TONE_MARKER_EDGE_ATOL_MHZ = 0.05
TONE_MARKER_LINESTYLE = "--"
NYQUIST_MARKER_LINESTYLE = ":"
LEGEND_LOCATION = "lower right"
LEGEND_FONTSIZE = 8

BAND_BOUNDARY_COLOR = "#111827"
BAND_BOUNDARY_LINESTYLE = "-."
BAND_BOUNDARY_LINEWIDTH = 1.0
BAND_BOUNDARY_ALPHA = 0.7
BAND_BOUNDARY_LABEL_FONTSIZE = 8
BAND_BOUNDARY_LABEL_Y = 0.02
BAND_BOUNDARY_LABEL_OFFSET = (3, 4)

INVALID_REGION_COLOR = "#e5e7eb"
INVALID_REGION_EDGE_COLOR = "#6b7280"
INVALID_REGION_ALPHA = 0.45
INVALID_REGION_EDGE_ALPHA = 0.9
INVALID_REGION_EDGE_LINEWIDTH = 1.0
INVALID_REGION_EDGE_LINESTYLE = "-"
INVALID_REGION_LABEL = "invalid after {start_mhz:g} MHz"
INVALID_REGION_LABEL_FONTSIZE = 8
INVALID_REGION_LABEL_OFFSET = (4, -4)


def gen_multitone(freqs: Sequence[float]) -> npt.NDArray[np.float64]:
    """Generate a normalized multitone input waveform.
    정규화된 멀티톤 입력 파형을 생성합니다.
    """
    n = np.arange(N_IN, dtype=np.float64)
    amp = 0.9 / len(freqs)
    sig = np.zeros(N_IN, dtype=np.float64)
    for f in freqs:
        sig += amp * np.sin(2 * np.pi * float(f) / FS_HZ * n)
    return sig


def _fft_db(sig, fs, ref):
    """Compute one-sided FFT frequency and magnitude in dB.
    단측 FFT 주파수 축과 dB 크기를 계산합니다.
    """
    f = np.fft.rfftfreq(len(sig), d=1.0 / fs) / 1e6
    db = 20 * np.log10(np.abs(np.fft.rfft(sig)) / ref + 1e-12)
    return f, db


def _format_mhz(value_hz):
    """Format a frequency in Hz as MHz text.
    Hz 단위 주파수를 MHz 문자열로 포맷합니다.
    """
    mhz = value_hz / 1e6
    if float(mhz).is_integer():
        return f"{int(mhz)} MHz"
    return f"{mhz:.3f} MHz"


def _format_tones(freqs):
    """Format a tone list for plot titles.
    plot 제목에 넣을 톤 목록 문자열을 만듭니다.
    """
    return ", ".join(_format_mhz(freq) for freq in freqs)


def _format_mhz_compact(value_hz):
    """Format MHz text without the unit suffix.
    단위 suffix 없이 MHz 값을 포맷합니다.
    """
    return _format_mhz(value_hz).replace(" MHz", "")


def _format_mhz_range_value(value_hz):
    """Format a MHz range endpoint without losing small positive values.
    작은 양수 값을 잃지 않도록 MHz 범위 끝값을 포맷합니다.
    """
    mhz = float(value_hz) / 1e6
    if mhz.is_integer():
        return str(int(mhz))
    return f"{mhz:.6f}".rstrip("0").rstrip(".")


def _format_mhz_span(span_mhz):
    """Format a frequency span already expressed in MHz.
    MHz 단위 구간을 간결한 문자열로 포맷합니다.
    """
    start_mhz, end_mhz = span_mhz
    return f"{_format_mhz_compact(start_mhz * 1e6)}-{_format_mhz_compact(end_mhz * 1e6)} MHz"


def _metadata_title(mode_name, freqs, source=None):
    """Build the main figure title.
    figure 상단의 핵심 제목 문자열을 만듭니다.
    """
    return f"{mode_name} - tones: {_format_tones(freqs)}"


def _metadata_subtitle():
    """Build the shared figure subtitle for output FFT interpretation.
    출력 FFT 해석에 필요한 공통 subtitle 문자열을 만듭니다.
    """
    transition_band = _format_mhz_span(FIR_TRANSITION_BAND_MHZ)
    valid_band = _format_mhz_span(OUTPUT_FFT_VALID_XLIM_MHZ)
    shaded_band = _format_mhz_span(OUTPUT_INVALID_REGION_MHZ)
    return (
        f"Input bands: pass <= {FIR_PASSBAND_MAX_MHZ:g} MHz, "
        f"transition {transition_band}, stop >= {FIR_STOPBAND_MIN_MHZ:g} MHz | "
        f"Output valid: {valid_band}; shaded {shaded_band} is comparison-only"
    )


def _set_figure_header(fig, mode_name, freqs):
    """Apply the shared title/subtitle figure header.
    공통 title/subtitle figure header를 적용합니다.
    """
    fig.suptitle(_metadata_title(mode_name, freqs), fontsize=FIG_SUPTITLE_FONTSIZE, y=FIG_SUPTITLE_Y)
    fig.text(
        0.5,
        FIG_SUBTITLE_Y,
        _metadata_subtitle(),
        ha="center",
        va="top",
        fontsize=FIG_SUBTITLE_FONTSIZE,
        color=FIG_SUBTITLE_COLOR,
    )


def _fft_axis_title(label, fs_hz):
    """Build an FFT subplot title with sample rate and Nyquist frequency.
    sample rate와 Nyquist 주파수를 포함한 FFT subplot 제목을 만듭니다.
    """
    return f"{label} - fs={_format_mhz(fs_hz)}, Nyq={_format_mhz(fs_hz / 2)}"


def _fold_frequency_hz(frequency_hz, sample_rate_hz):
    """Fold a tone into the Nyquist band for marker placement.
    marker 표시를 위해 톤을 Nyquist 대역 안으로 접습니다.
    """
    folded = abs(float(frequency_hz)) % float(sample_rate_hz)
    nyquist_hz = sample_rate_hz / 2.0
    if folded > nyquist_hz:
        folded = sample_rate_hz - folded
    return folded


def _tone_marker_specs(freqs, sample_rate_hz):
    """Build FFT marker specs for original and aliased tones.
    원 주파수와 alias 주파수용 FFT marker 정보를 만듭니다.
    """
    nyquist_hz = sample_rate_hz / 2.0
    grouped = {}
    for tone_hz in freqs:
        tone_hz = float(tone_hz)
        marker_hz = _fold_frequency_hz(tone_hz, sample_rate_hz)
        is_alias = not bool(np.isclose(abs(tone_hz), marker_hz, rtol=0.0, atol=1.0))
        is_nyquist = bool(np.isclose(marker_hz, nyquist_hz, rtol=0.0, atol=1.0))

        if is_alias:
            label = f"{_format_mhz_compact(tone_hz)}->{_format_mhz_compact(marker_hz)} MHz"
        else:
            label = _format_mhz(marker_hz)
        if is_nyquist:
            label += " Nyq"

        key = round(marker_hz / 1e6, 6)
        if key not in grouped:
            grouped[key] = {
                "frequency_mhz": marker_hz / 1e6,
                "labels": [],
                "nyquist_edge": False,
            }
        grouped[key]["labels"].append(label)
        grouped[key]["nyquist_edge"] = grouped[key]["nyquist_edge"] or is_nyquist

    return [
        {
            "frequency_mhz": item["frequency_mhz"],
            "label": " / ".join(item["labels"]),
            "nyquist_edge": item["nyquist_edge"],
        }
        for item in sorted(grouped.values(), key=lambda row: row["frequency_mhz"])
    ]


def _add_tone_markers(ax, markers, *, color, legend_label):
    """Draw tone markers and labels on an FFT axis.
    FFT 축에 톤 marker와 label을 그립니다.
    """
    if not markers:
        return

    for index, marker in enumerate(markers):
        marker_color = NYQUIST_MARKER_COLOR if marker["nyquist_edge"] else color
        ax.axvline(
            marker["frequency_mhz"],
            color=marker_color,
            linestyle=NYQUIST_MARKER_LINESTYLE if marker["nyquist_edge"] else TONE_MARKER_LINESTYLE,
            linewidth=TONE_MARKER_LINEWIDTH,
            alpha=TONE_MARKER_ALPHA,
            label=legend_label if index == 0 else None,
        )
        _, x_max = ax.get_xlim()
        at_right_edge = np.isclose(
            marker["frequency_mhz"], x_max, rtol=0.0, atol=TONE_MARKER_EDGE_ATOL_MHZ
        )
        ax.annotate(
            marker["label"],
            xy=(marker["frequency_mhz"], 1.0),
            xycoords=("data", "axes fraction"),
            xytext=TONE_MARKER_EDGE_LABEL_OFFSET if at_right_edge else TONE_MARKER_LABEL_OFFSET,
            textcoords="offset points",
            rotation=90,
            va="top",
            ha="right" if at_right_edge else "left",
            fontsize=TONE_MARKER_LABEL_FONTSIZE,
            color=marker_color,
        )
    ax.legend(loc=LEGEND_LOCATION, fontsize=LEGEND_FONTSIZE)


def _add_band_boundaries(ax, boundaries):
    """Draw FIR pass/transition/stop design boundaries.
    FIR pass/transition/stop 설계 경계선을 그립니다.
    """
    if not boundaries:
        return

    x_min, x_max = ax.get_xlim()
    for boundary in boundaries:
        frequency_mhz = float(boundary["frequency_mhz"])
        if frequency_mhz < x_min or frequency_mhz > x_max:
            continue
        ax.axvline(
            frequency_mhz,
            color=BAND_BOUNDARY_COLOR,
            linestyle=BAND_BOUNDARY_LINESTYLE,
            linewidth=BAND_BOUNDARY_LINEWIDTH,
            alpha=BAND_BOUNDARY_ALPHA,
            zorder=1,
        )
        ax.annotate(
            boundary["label"],
            xy=(frequency_mhz, BAND_BOUNDARY_LABEL_Y),
            xycoords=("data", "axes fraction"),
            xytext=BAND_BOUNDARY_LABEL_OFFSET,
            textcoords="offset points",
            rotation=90,
            va="bottom",
            ha="left",
            fontsize=BAND_BOUNDARY_LABEL_FONTSIZE,
            color=BAND_BOUNDARY_COLOR,
        )


def _add_invalid_region(ax, invalid_region_mhz, *, label=INVALID_REGION_LABEL):
    """Shade a frequency range that is outside the valid FFT band.
    유효 FFT 대역 밖의 주파수 구간을 음영으로 표시합니다.
    """
    if invalid_region_mhz is None:
        return

    start_mhz, end_mhz = invalid_region_mhz
    x_min, x_max = ax.get_xlim()
    shade_start = max(float(start_mhz), float(x_min))
    shade_end = min(float(end_mhz), float(x_max))
    if shade_end <= shade_start:
        return

    ax.axvspan(
        shade_start,
        shade_end,
        color=INVALID_REGION_COLOR,
        alpha=INVALID_REGION_ALPHA,
        linewidth=0,
        zorder=0,
    )
    ax.axvline(
        shade_start,
        color=INVALID_REGION_EDGE_COLOR,
        linestyle=INVALID_REGION_EDGE_LINESTYLE,
        linewidth=INVALID_REGION_EDGE_LINEWIDTH,
        alpha=INVALID_REGION_EDGE_ALPHA,
        zorder=1,
    )
    ax.annotate(
        label.format(start_mhz=shade_start, end_mhz=shade_end),
        xy=(shade_start, 1.0),
        xycoords=("data", "axes fraction"),
        xytext=INVALID_REGION_LABEL_OFFSET,
        textcoords="offset points",
        va="top",
        ha="left",
        fontsize=INVALID_REGION_LABEL_FONTSIZE,
        color=INVALID_REGION_EDGE_COLOR,
    )


def build_scenario0_signals():
    """Build PC-only input, naive decimated, and FIR-decimated signals.
    PC에서만 입력, 단순 decimation, FIR decimation 신호를 만듭니다.
    """
    sig_in = gen_multitone(SCENARIO0_FREQS)
    naive = sig_in[::2]
    filtered = np.convolve(sig_in, FIR_COEFFS, mode="same")[::2]
    return sig_in, naive, filtered


def _plot_fft_axis(
    ax,
    sig,
    fs,
    title,
    *,
    ref,
    xlim,
    markers=None,
    marker_color=INPUT_MARKER_COLOR,
    marker_label="tone target",
    invalid_region_mhz=None,
    band_boundaries_mhz=None,
):
    """Render one FFT axis with optional tone markers.
    톤 marker를 포함할 수 있는 FFT 축 하나를 그립니다.
    """
    f, db = _fft_db(sig, fs, ref)
    ax.cla()
    ax.plot(f, db, linewidth=PLOT_LINEWIDTH)
    ax.set_title(title)
    ax.set_xlabel("Frequency (MHz)")
    ax.set_ylabel("Magnitude (dB)")
    ax.set_xlim(*xlim)
    ax.set_ylim(*PLOT_YLIM_DB)
    _add_band_boundaries(ax, band_boundaries_mhz)
    _add_invalid_region(ax, invalid_region_mhz)
    ax.grid(GRID_ENABLED)
    _add_tone_markers(ax, markers, color=marker_color, legend_label=marker_label)


def plot_fft_pair(
    ax_l,
    ax_r,
    sig_l,
    fs_l,
    sig_r,
    fs_r,
    title_l,
    title_r,
    ref=None,
    xlim_l=None,
    xlim_r=None,
    markers_l=None,
    markers_r=None,
    marker_label_l="tone target",
    marker_label_r="tone target",
    marker_color_l=INPUT_MARKER_COLOR,
    marker_color_r=OUTPUT_MARKER_COLOR,
    invalid_region_l=None,
    invalid_region_r=None,
    band_boundaries_l=None,
    band_boundaries_r=None,
):
    """Render paired input/output FFT axes.
    입력/출력 FFT 축 쌍을 그립니다.
    """
    if ref is None:
        ref = np.abs(np.fft.rfft(sig_l)).max()
    if ref == 0:
        ref = 1.0
    if xlim_l is None:
        xlim_l = (0, fs_l / 2 / 1e6)
    if xlim_r is None:
        xlim_r = (0, fs_r / 2 / 1e6)

    for ax, sig, fs, title, xlim, markers, marker_color, marker_label, invalid_region, band_boundaries in [
        (
            ax_l, sig_l, fs_l, title_l, xlim_l, markers_l, marker_color_l, marker_label_l,
            invalid_region_l, band_boundaries_l,
        ),
        (
            ax_r, sig_r, fs_r, title_r, xlim_r, markers_r, marker_color_r, marker_label_r,
            invalid_region_r, band_boundaries_r,
        ),
    ]:
        _plot_fft_axis(
            ax,
            sig,
            fs,
            title,
            ref=ref,
            xlim=xlim,
            markers=markers,
            marker_color=marker_color,
            marker_label=marker_label,
            invalid_region_mhz=invalid_region,
            band_boundaries_mhz=band_boundaries,
        )


def run_scenario0():
    """Run the PC-only aliasing comparison scenario.
    PC-only aliasing 비교 시나리오를 실행합니다.
    """
    sig_in, naive, filtered = build_scenario0_signals()
    ref = np.abs(np.fft.rfft(sig_in)).max()
    input_markers = _tone_marker_specs(SCENARIO0_FREQS, FS_HZ)
    output_markers = _tone_marker_specs(SCENARIO0_FREQS, OUTPUT_FS_HZ)

    fig, (ax_in, ax_naive, ax_fir) = plt.subplots(1, 3, figsize=SCENARIO0_FIGSIZE)
    _set_figure_header(fig, "Scenario 0", SCENARIO0_FREQS)
    _plot_fft_axis(
        ax_in,
        sig_in,
        FS_HZ,
        _fft_axis_title("Input FFT", FS_HZ),
        ref=ref,
        xlim=INPUT_FFT_XLIM_MHZ,
        markers=input_markers,
        marker_color=INPUT_MARKER_COLOR,
        marker_label="input tone target",
        band_boundaries_mhz=INPUT_BAND_BOUNDARIES_MHZ,
    )
    _plot_fft_axis(
        ax_naive,
        naive,
        OUTPUT_FS_HZ,
        _fft_axis_title("Downsample only", OUTPUT_FS_HZ),
        ref=ref,
        xlim=OUTPUT_FFT_DISPLAY_XLIM_MHZ,
        markers=output_markers,
        marker_color=OUTPUT_MARKER_COLOR,
        marker_label="output alias target",
        invalid_region_mhz=OUTPUT_INVALID_REGION_MHZ,
    )
    _plot_fft_axis(
        ax_fir,
        filtered,
        OUTPUT_FS_HZ,
        _fft_axis_title("FIR + decimation", OUTPUT_FS_HZ),
        ref=ref,
        xlim=OUTPUT_FFT_DISPLAY_XLIM_MHZ,
        markers=output_markers,
        marker_color=OUTPUT_MARKER_COLOR,
        marker_label="output alias target",
        invalid_region_mhz=OUTPUT_INVALID_REGION_MHZ,
    )
    fig.tight_layout(rect=PLOT_LAYOUT_RECT)
    plt.show()


def run_scenario1(mode_name, freqs, ser):
    """Run a fixed board scenario and show its FFT output.
    고정 보드 시나리오를 실행하고 FFT 출력을 표시합니다.
    """
    sig_in = gen_multitone(freqs)
    uart_send_cmd(ser, freqs)
    sig_out = uart_recv_result(ser)
    input_markers = _tone_marker_specs(freqs, FS_HZ)
    output_markers = _tone_marker_specs(freqs, OUTPUT_FS_HZ)

    fig, (ax_l, ax_r) = plt.subplots(1, 2, figsize=PAIR_FIGSIZE)
    _set_figure_header(fig, mode_name, freqs)
    plot_fft_pair(
        ax_l, ax_r,
        sig_in, FS_HZ,
        sig_out, OUTPUT_FS_HZ,
        _fft_axis_title("Input FFT", FS_HZ),
        _fft_axis_title("Output FFT after FIR", OUTPUT_FS_HZ),
        xlim_l=INPUT_FFT_XLIM_MHZ,
        xlim_r=OUTPUT_FFT_DISPLAY_XLIM_MHZ,
        markers_l=input_markers,
        markers_r=output_markers,
        marker_label_l="input tone target",
        marker_label_r="output alias target",
        invalid_region_r=OUTPUT_INVALID_REGION_MHZ,
        band_boundaries_l=INPUT_BAND_BOUNDARIES_MHZ,
    )
    fig.tight_layout(rect=PLOT_LAYOUT_RECT)
    plt.show()


def run_interactive(ser):
    """Run one user-selected board FFT capture.
    사용자가 선택한 주파수 조합을 보드에서 1회 캡처해 FFT를 표시합니다.
    """
    print(
        "주파수 입력 형식: 'f1 f2 ...' "
        f"(MHz, 공백으로 구분, 범위 "
        f"[{_format_mhz_range_value(MIN_TONE_FREQ_HZ)}, "
        f"{_format_mhz_range_value(MAX_TONE_FREQ_HZ)}) MHz, 최대 {MAX_TONES}개) "
        "| 보드 실행 1회 | 종료: Ctrl+C"
    )

    while True:
        try:
            line = input("주파수 (MHz): ").strip()
            if not line:
                continue
            freqs = [float(x) * 1e6 for x in line.split()]
            validate_tone_frequencies(freqs)
            break
        except (KeyboardInterrupt, EOFError):
            print("\n종료")
            return
        except ValueError as e:
            print(f"예외 발생: {e}")

    try:
        sig_in = gen_multitone(freqs)
        uart_send_cmd(ser, freqs)
        sig_out = uart_recv_result(ser)
    except (TimeoutError, RuntimeError, OSError) as e:
        print(f"예외 발생: {e}")
        return

    input_markers = _tone_marker_specs(freqs, FS_HZ)
    output_markers = _tone_marker_specs(freqs, OUTPUT_FS_HZ)

    fig, (ax_l, ax_r) = plt.subplots(1, 2, figsize=PAIR_FIGSIZE)
    _set_figure_header(fig, "Scenario 2", freqs)
    plot_fft_pair(
        ax_l, ax_r,
        sig_in, FS_HZ,
        sig_out, OUTPUT_FS_HZ,
        _fft_axis_title("Input FFT", FS_HZ),
        _fft_axis_title("Output FFT after FIR", OUTPUT_FS_HZ),
        xlim_l=INPUT_FFT_XLIM_MHZ,
        xlim_r=OUTPUT_FFT_DISPLAY_XLIM_MHZ,
        markers_l=input_markers,
        markers_r=output_markers,
        marker_label_l="input tone target",
        marker_label_r="output alias target",
        invalid_region_r=OUTPUT_INVALID_REGION_MHZ,
        band_boundaries_l=INPUT_BAND_BOUNDARIES_MHZ,
    )
    fig.tight_layout(rect=PLOT_LAYOUT_RECT)
    plt.show()


def main():
    """Parse CLI arguments and dispatch the selected viewer mode.
    CLI 인자를 해석하고 선택된 viewer mode를 실행합니다.
    """
    parser = argparse.ArgumentParser(description="FIR 데시메이터 FFT viewer")
    parser.add_argument("--mode", required=True, choices=["0", "1-1", "1-2", "2"],
                        help="0=앨리어싱 비교, 1-1/1-2=고정 프리셋, 2=사용자 입력 1회")
    parser.add_argument("--port", default="/dev/ttyUSB1", help="UART 포트")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (기본값 115200)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_UART_TIMEOUT_SEC,
                        help=f"UART read timeout seconds (기본값 {DEFAULT_UART_TIMEOUT_SEC})")
    args = parser.parse_args()

    if args.mode == "0":
        run_scenario0()
        return

    ser = uart_open(args.port, args.baud, args.timeout)
    try:
        if args.mode == "1-1":
            run_scenario1("Scenario 1-1", PRESET_1_1, ser)
        elif args.mode == "1-2":
            run_scenario1("Scenario 1-2", PRESET_1_2, ser)
        elif args.mode == "2":
            run_interactive(ser)
    finally:
        ser.close()


if __name__ == "__main__":
    main()
