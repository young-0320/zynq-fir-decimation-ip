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
OUTPUT_FFT_XLIM_MHZ = (0, OUTPUT_FS_HZ / 2 / 1e6)
PLOT_LAYOUT_RECT = (0, 0, 1, 0.88)
INPUT_MARKER_COLOR = "#2563eb"
OUTPUT_MARKER_COLOR = "#c2410c"
NYQUIST_MARKER_COLOR = "#7c3aed"


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


def _metadata_title(mode_name, freqs, source):
    """Build the shared plot title metadata.
    공통 plot 제목 metadata 문자열을 만듭니다.
    """
    return (
        f"{mode_name} | {source} | tones: {_format_tones(freqs)}\n"
        f"input fs: {_format_mhz(FS_HZ)} | output fs: {_format_mhz(OUTPUT_FS_HZ)}"
    )


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
            linestyle=":" if marker["nyquist_edge"] else "--",
            linewidth=1.0,
            alpha=0.85,
            label=legend_label if index == 0 else None,
        )
        _, x_max = ax.get_xlim()
        at_right_edge = np.isclose(marker["frequency_mhz"], x_max, rtol=0.0, atol=0.05)
        ax.annotate(
            marker["label"],
            xy=(marker["frequency_mhz"], 1.0),
            xycoords=("data", "axes fraction"),
            xytext=(-3, -4) if at_right_edge else (3, -4),
            textcoords="offset points",
            rotation=90,
            va="top",
            ha="right" if at_right_edge else "left",
            fontsize=8,
            color=marker_color,
        )
    ax.legend(loc="lower right", fontsize=8)


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
):
    """Render one FFT axis with optional tone markers.
    톤 marker를 포함할 수 있는 FFT 축 하나를 그립니다.
    """
    f, db = _fft_db(sig, fs, ref)
    ax.cla()
    ax.plot(f, db)
    ax.set_title(title)
    ax.set_xlabel("Frequency (MHz)")
    ax.set_ylabel("Magnitude (dB)")
    ax.set_xlim(*xlim)
    ax.set_ylim(-100, 5)
    ax.grid(True)
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

    for ax, sig, fs, title, xlim, markers, marker_color, marker_label in [
        (ax_l, sig_l, fs_l, title_l, xlim_l, markers_l, marker_color_l, marker_label_l),
        (ax_r, sig_r, fs_r, title_r, xlim_r, markers_r, marker_color_r, marker_label_r),
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
        )


def run_scenario0():
    """Run the PC-only aliasing comparison scenario.
    PC-only aliasing 비교 시나리오를 실행합니다.
    """
    sig_in, naive, filtered = build_scenario0_signals()
    ref = np.abs(np.fft.rfft(sig_in)).max()
    input_markers = _tone_marker_specs(SCENARIO0_FREQS, FS_HZ)
    output_markers = _tone_marker_specs(SCENARIO0_FREQS, OUTPUT_FS_HZ)

    fig, (ax_in, ax_naive, ax_fir) = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle(_metadata_title("Scenario 0", SCENARIO0_FREQS, "PC-only"))
    _plot_fft_axis(
        ax_in,
        sig_in,
        FS_HZ,
        f"Input FFT (fs={_format_mhz(FS_HZ)})",
        ref=ref,
        xlim=INPUT_FFT_XLIM_MHZ,
        markers=input_markers,
        marker_color=INPUT_MARKER_COLOR,
        marker_label="input tone target",
    )
    _plot_fft_axis(
        ax_naive,
        naive,
        OUTPUT_FS_HZ,
        f"Downsample only (aliasing, fs={_format_mhz(OUTPUT_FS_HZ)})",
        ref=ref,
        xlim=OUTPUT_FFT_XLIM_MHZ,
        markers=output_markers,
        marker_color=OUTPUT_MARKER_COLOR,
        marker_label="output alias target",
    )
    _plot_fft_axis(
        ax_fir,
        filtered,
        OUTPUT_FS_HZ,
        f"FIR + decimation (fs={_format_mhz(OUTPUT_FS_HZ)})",
        ref=ref,
        xlim=OUTPUT_FFT_XLIM_MHZ,
        markers=output_markers,
        marker_color=OUTPUT_MARKER_COLOR,
        marker_label="output alias target",
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

    fig, (ax_l, ax_r) = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle(_metadata_title(mode_name, freqs, "board-measured"))
    plot_fft_pair(
        ax_l, ax_r,
        sig_in, FS_HZ,
        sig_out, OUTPUT_FS_HZ,
        f"Input FFT (fs={_format_mhz(FS_HZ)})",
        f"Output FFT (after FIR, fs={_format_mhz(OUTPUT_FS_HZ)})",
        xlim_l=INPUT_FFT_XLIM_MHZ,
        xlim_r=OUTPUT_FFT_XLIM_MHZ,
        markers_l=input_markers,
        markers_r=output_markers,
        marker_label_l="input tone target",
        marker_label_r="output alias target",
    )
    fig.tight_layout(rect=PLOT_LAYOUT_RECT)
    plt.show()


def run_interactive(ser):
    """Run the interactive board FFT viewer loop.
    인터랙티브 보드 FFT viewer 루프를 실행합니다.
    """
    plt.ion()
    fig, (ax_l, ax_r) = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle(
        f"Scenario 2 | board-measured | tones: waiting for input\n"
        f"input fs: {_format_mhz(FS_HZ)} | output fs: {_format_mhz(OUTPUT_FS_HZ)}"
    )
    fig.tight_layout(rect=PLOT_LAYOUT_RECT)

    print(
        "주파수 입력 형식: 'f1 f2 ...' "
        f"(MHz, 공백 구분, 범위 {_format_mhz_range_value(MIN_TONE_FREQ_HZ)}.."
        f"{_format_mhz_range_value(MAX_TONE_FREQ_HZ)} MHz, 최대 {MAX_TONES}개) "
        "| 종료: Ctrl+C"
    )

    while True:
        try:
            line = input("주파수 (MHz): ").strip()
            if not line:
                continue
            freqs = [float(x) * 1e6 for x in line.split()]
            validate_tone_frequencies(freqs)

            sig_in = gen_multitone(freqs)
            uart_send_cmd(ser, freqs)
            sig_out = uart_recv_result(ser)
            input_markers = _tone_marker_specs(freqs, FS_HZ)
            output_markers = _tone_marker_specs(freqs, OUTPUT_FS_HZ)

            fig.suptitle(_metadata_title("Scenario 2", freqs, "board-measured"))
            plot_fft_pair(
                ax_l, ax_r,
                sig_in, FS_HZ,
                sig_out, OUTPUT_FS_HZ,
                f"Input FFT (fs={_format_mhz(FS_HZ)})",
                f"Output FFT (after FIR, fs={_format_mhz(OUTPUT_FS_HZ)})",
                xlim_l=INPUT_FFT_XLIM_MHZ,
                xlim_r=OUTPUT_FFT_XLIM_MHZ,
                markers_l=input_markers,
                markers_r=output_markers,
                marker_label_l="input tone target",
                marker_label_r="output alias target",
            )
            fig.tight_layout(rect=PLOT_LAYOUT_RECT)
            fig.canvas.draw()
            fig.canvas.flush_events()

        except (KeyboardInterrupt, EOFError):
            print("\n종료")
            break
        except (TimeoutError, ValueError, RuntimeError, OSError) as e:
            print(f"예외 발생: {e}")


def main():
    """Parse CLI arguments and dispatch the selected viewer mode.
    CLI 인자를 해석하고 선택된 viewer mode를 실행합니다.
    """
    parser = argparse.ArgumentParser(description="FIR 데시메이터 FFT viewer")
    parser.add_argument("--mode", required=True, choices=["0", "1-1", "1-2", "2"],
                        help="0=앨리어싱 비교, 1-1/1-2=고정 프리셋, 2=인터랙티브")
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
