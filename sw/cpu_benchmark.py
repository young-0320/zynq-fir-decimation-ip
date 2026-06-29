"""CPU FIR benchmark for CPU vs FPGA comparison.

numpy float64 FIR을 기준으로 처리 시간을 측정합니다.
보드 타이밍(board_time_us)을 인자로 받아 비교 표와 바 차트를 출력합니다.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import psutil

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from sw.fir_decimator_capture import DEFAULT_UART_TIMEOUT_SEC, capture_output_q15
from sw.fir_decimator_fft_viewer import FIR_COEFFS_Q15, N_IN, N_OUT, FS_HZ, PRESET_1_2
from sw.fir_decimator_metrics import generate_fixed_reference
from model.config import FIR_CONFIG

_SCENARIO_FREQS = PRESET_1_2   # [7e6, 15e6, 25e6, 45e6]
_WARMUP = 10
_MIN_RUNS = 30
_MAX_RUNS = 500
_CV_THRESHOLD = 0.02

_FPGA_DSP48 = 16
_FPGA_LUT = 1827


def _run_cpu_fir(x_f64: np.ndarray, h_f64: np.ndarray) -> np.ndarray:
    return np.convolve(x_f64, h_f64)[::2]


def benchmark_cpu() -> dict:
    """numpy float64 FIR 처리 시간을 CV 수렴 기준으로 측정한다."""
    ref = generate_fixed_reference(
        _SCENARIO_FREQS,
        n_in=N_IN,
        fs_hz=FS_HZ,
        coeffs_q15=FIR_COEFFS_Q15,
        decimation=FIR_CONFIG.decimation_factor,
    )
    x_f64 = ref["input_q15"].astype(np.float64) / 32768.0
    h_f64 = FIR_COEFFS_Q15.astype(np.float64) / 32768.0

    for _ in range(_WARMUP):
        _run_cpu_fir(x_f64, h_f64)

    psutil.cpu_percent(interval=None)  # 첫 호출은 baseline 설정용

    # 배치 측정: OS jitter를 희석하기 위해 10회씩 묶어 평균
    _BATCH = 10
    times_us: list[float] = []
    while True:
        t0 = time.perf_counter()
        for _ in range(_BATCH):
            _run_cpu_fir(x_f64, h_f64)
        t1 = time.perf_counter()
        times_us.append((t1 - t0) * 1e6 / _BATCH)

        n = len(times_us)
        if n >= _MIN_RUNS:
            arr = np.array(times_us)
            cv = float(np.std(arr) / np.mean(arr))
            if cv < _CV_THRESHOLD or n >= _MAX_RUNS:
                break

    cpu_usage = psutil.cpu_percent(interval=0.1)

    arr = np.array(times_us)
    mean_us = float(np.mean(arr))
    median_us = float(np.median(arr))
    final_cv = float(np.std(arr) / mean_us * 100)
    converged = final_cv < _CV_THRESHOLD * 100
    return {
        "runs": len(times_us),
        "converged": converged,
        "mean_us": mean_us,
        "median_us": median_us,
        "min_us": float(np.min(arr)),
        "max_us": float(np.max(arr)),
        "std_us": float(np.std(arr)),
        "cv_pct": final_cv,
        "throughput_msps": N_IN / median_us,
        "cpu_usage_pct": cpu_usage,
    }


def print_cpu_result(r: dict) -> None:
    print("=== CPU FIR Benchmark ===")
    print(f"Input:  {N_IN} samples, Scenario 1-2 (7/15/25/45 MHz)")
    print(f"Filter: N={FIR_CONFIG.spec_num_taps} taps, M={FIR_CONFIG.decimation_factor} decimation, numpy float64")
    print()
    converge_note = f"CV converged < {_CV_THRESHOLD*100:.0f}%" if r["converged"] else "max runs reached"
    print(f"Runs: {r['runs']} ({converge_note})")
    print(f"  Median: {r['median_us']:.1f} us  ← comparison 기준")
    print(f"  Mean:   {r['mean_us']:.1f} us")
    print(f"  Min:    {r['min_us']:.1f} us")
    print(f"  Max:    {r['max_us']:.1f} us")
    print(f"  Std:    {r['std_us']:.1f} us")
    print(f"  CV:     {r['cv_pct']:.1f} % (Windows OS jitter)")
    print(f"  Throughput: {r['throughput_msps']:.1f} M samples/sec  (median 기준)")
    print()
    print(f"CPU usage: {r['cpu_usage_pct']:.1f} %")


def print_comparison(cpu: dict, board_time_us: float) -> None:
    board_throughput = N_IN / board_time_us
    speedup = cpu["median_us"] / board_time_us

    print()
    print("=== CPU vs FPGA Comparison ===")
    print(f"Input: {N_IN} samples, N={FIR_CONFIG.spec_num_taps} FIR, M={FIR_CONFIG.decimation_factor} decimation")
    print()
    print(f"{'':22s}{'CPU (laptop)':20s}{'FPGA (board)':20s}")
    print(f"{'Implementation:':22s}{'numpy float64':20s}{'Q1.15 fixed-point':20s}")
    print(f"{'Processing time:':22s}{cpu['median_us']:<20.1f}{board_time_us:<20.1f}(us, CPU=median)")
    print(f"{'Throughput:':22s}{cpu['throughput_msps']:<20.1f}{board_throughput:<20.1f}(M samp/s)")
    print(f"{'Speedup:':22s}{'1x':20s}{speedup:.1f}x")
    print()
    print("Resources:")
    print(f"  CPU:   1 core, {cpu['cpu_usage_pct']:.1f}% usage")
    print(f"  FPGA:  {_FPGA_DSP48} DSP48, {_FPGA_LUT} LUT (Vivado utilization report 기준)")


def save_comparison_chart(cpu: dict, board_time_us: float, out_path: Path) -> None:
    labels = ["CPU\n(numpy float64)", "FPGA\n(Q1.15 fixed-point)"]
    values = [cpu["median_us"], board_time_us]
    colors = ["#4c72b0", "#dd8452"]

    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(labels, values, color=colors, width=0.5)
    ax.set_ylabel("Processing Time (µs)")
    ax.set_title(
        f"CPU vs FPGA FIR Processing Time\n"
        f"N=43 taps, M=2, 8192 samples"
    )
    for bar, val in zip(bars, values, strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() * 1.02,
            f"{val:.1f} µs",
            ha="center", va="bottom", fontsize=10,
        )
    ax.set_ylim(0, max(values) * 1.2)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"\nChart saved: {out_path}")


def capture_board_time_us(port: str, baud: int, timeout: float) -> float:
    """보드에 Scenario 1-2 커맨드를 보내고 FIR_TIME_US 실측값을 수신한다."""
    print(f"Connecting to board on {port} ({baud} baud)...")
    result = capture_output_q15(
        port, baud, timeout,
        _SCENARIO_FREQS,
        expected_samples=N_OUT,
    )
    if result.board_time_us is None:
        raise RuntimeError(
            "보드가 FIR_TIME_US를 전송하지 않았습니다. "
            "fir_decimator_demo.c 재빌드 여부를 확인하세요."
        )
    print(f"Board FIR_TIME_US: {result.board_time_us} us")
    return float(result.board_time_us)


def main() -> None:
    parser = argparse.ArgumentParser(description="CPU FIR benchmark and CPU vs FPGA comparison")
    board_group = parser.add_mutually_exclusive_group()
    board_group.add_argument(
        "--port",
        type=str,
        default=None,
        metavar="PORT",
        help="Serial port for automatic board timing capture (e.g. COM3, /dev/ttyUSB0)",
    )
    board_group.add_argument(
        "--board-time-us",
        type=float,
        default=None,
        metavar="US",
        help="Board FIR processing time in microseconds (manual fallback)",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
        metavar="BAUD",
        help="UART baud rate (default: 115200)",
    )
    parser.add_argument(
        "--uart-timeout",
        type=float,
        default=DEFAULT_UART_TIMEOUT_SEC,
        metavar="SEC",
        help=f"UART receive timeout in seconds (default: {DEFAULT_UART_TIMEOUT_SEC})",
    )
    parser.add_argument(
        "--chart-out",
        type=Path,
        default=Path("docs/report/fir_n43/plot/cpu_vs_fpga_timing.png"),
        metavar="PATH",
        help="Output path for comparison bar chart",
    )
    args = parser.parse_args()

    cpu = benchmark_cpu()
    print_cpu_result(cpu)

    board_time_us: float | None = None
    if args.port is not None:
        board_time_us = capture_board_time_us(args.port, args.baud, args.uart_timeout)
    elif args.board_time_us is not None:
        board_time_us = args.board_time_us

    if board_time_us is not None:
        print_comparison(cpu, board_time_us)
        save_comparison_chart(cpu, board_time_us, args.chart_out)


if __name__ == "__main__":
    main()
