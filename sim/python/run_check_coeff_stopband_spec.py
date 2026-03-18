from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from scipy.signal import freqz

from model.ideal.design_kaiser_coeff import design_kaiser_lpf
from model.q1_15 import count_clipped_q1_15, dequantize_q1_15, quantize_q1_15


DEFAULT_FS_IN_HZ = 100_000_000.0
DEFAULT_FP_HZ = 15_000_000.0
DEFAULT_FS_HZ = 25_000_000.0
DEFAULT_AS_DB = 60.0
DEFAULT_NUM_TAPS = [39, 41, 43]
DEFAULT_NUM_FREQ_SAMPLES = 524_288
_DB_EPSILON = 1e-300


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Check stopband attenuation from FIR coefficients only, independent of any input signal."
        ),
    )
    parser.add_argument(
        "--num-taps",
        type=int,
        nargs="+",
        default=DEFAULT_NUM_TAPS,
        help="One or more odd tap counts to analyze.",
    )
    parser.add_argument("--fs-in-hz", type=float, default=DEFAULT_FS_IN_HZ)
    parser.add_argument("--fp-hz", type=float, default=DEFAULT_FP_HZ)
    parser.add_argument("--fs-hz", type=float, default=DEFAULT_FS_HZ)
    parser.add_argument("--as-db", type=float, default=DEFAULT_AS_DB)
    parser.add_argument(
        "--num-freq-samples",
        type=int,
        default=DEFAULT_NUM_FREQ_SAMPLES,
        help="Dense half-band frequency grid size passed to scipy.signal.freqz.",
    )
    parser.add_argument(
        "--save-dir",
        type=Path,
        default=None,
        help=(
            "Directory to store outputs. Defaults to "
            "repo_root/sim/output/coeff_stopband_spec_n{tap_list}."
        ),
    )
    return parser


def _tap_stem(num_taps_list: Sequence[int]) -> str:
    joined = "_".join(f"n{num_taps}" for num_taps in num_taps_list)
    return f"coeff_stopband_spec_{joined}"


def _default_save_dir(num_taps_list: Sequence[int]) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "sim" / "output" / _tap_stem(num_taps_list)


def _magnitude_db(response: np.ndarray) -> np.ndarray:
    return 20.0 * np.log10(np.maximum(np.abs(response), _DB_EPSILON))


def _nearest_idx(freq_hz: np.ndarray, target_hz: float) -> int:
    return int(np.argmin(np.abs(freq_hz - target_hz)))


def _validate_num_taps_list(num_taps_list: Sequence[int]) -> list[int]:
    normalized = [int(num_taps) for num_taps in num_taps_list]
    if not normalized:
        raise ValueError("num_taps_list must not be empty.")
    if any(num_taps < 3 for num_taps in normalized):
        raise ValueError("All tap counts must be >= 3.")
    if len(set(normalized)) != len(normalized):
        raise ValueError("Tap counts must be unique.")
    return normalized


def analyze_frequency_response(
    *,
    freq_hz: np.ndarray,
    mag_db: np.ndarray,
    fp_hz: float,
    fs_hz: float,
    as_db: float,
) -> dict[str, float | bool]:
    freq_arr = np.asarray(freq_hz, dtype=np.float64)
    mag_arr = np.asarray(mag_db, dtype=np.float64)
    if freq_arr.shape != mag_arr.shape:
        raise ValueError("freq_hz and mag_db must have the same shape.")

    passband = freq_arr <= fp_hz
    stopband = freq_arr >= fs_hz
    if not np.any(passband):
        raise ValueError("Passband mask is empty.")
    if not np.any(stopband):
        raise ValueError("Stopband mask is empty.")

    fp_idx = _nearest_idx(freq_arr, fp_hz)
    fs_idx = _nearest_idx(freq_arr, fs_hz)
    stopband_mag_db = mag_arr[stopband]
    stopband_freq_hz = freq_arr[stopband]
    worst_stopband_idx = int(np.argmax(stopband_mag_db))
    stopband_max_db = float(stopband_mag_db[worst_stopband_idx])
    stopband_min_atten_db = float(-stopband_max_db)

    return {
        "dc_gain_db": float(mag_arr[0]),
        "passband_max_db": float(np.max(mag_arr[passband])),
        "passband_min_db": float(np.min(mag_arr[passband])),
        "passband_ripple_db_pp": float(np.max(mag_arr[passband]) - np.min(mag_arr[passband])),
        "at_fp_db": float(mag_arr[fp_idx]),
        "at_fs_db": float(mag_arr[fs_idx]),
        "stopband_max_db": stopband_max_db,
        "stopband_min_atten_db": stopband_min_atten_db,
        "stopband_margin_db": float(stopband_min_atten_db - as_db),
        "stopband_worst_freq_hz": float(stopband_freq_hz[worst_stopband_idx]),
        "meets_stopband_spec": bool(stopband_min_atten_db >= as_db),
    }


def run_check_coeff_stopband_spec(
    *,
    num_taps_list: Sequence[int] = DEFAULT_NUM_TAPS,
    fs_in_hz: float = DEFAULT_FS_IN_HZ,
    fp_hz: float = DEFAULT_FP_HZ,
    fs_hz: float = DEFAULT_FS_HZ,
    as_db: float = DEFAULT_AS_DB,
    num_freq_samples: int = DEFAULT_NUM_FREQ_SAMPLES,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    tap_counts = _validate_num_taps_list(num_taps_list)
    if num_freq_samples < 2:
        raise ValueError("num_freq_samples must be >= 2.")

    artifacts: dict[str, np.ndarray] = {}
    results: list[dict[str, Any]] = []
    freq_axis: np.ndarray | None = None

    for num_taps in tap_counts:
        coeff_float = design_kaiser_lpf(
            fs_in_hz=fs_in_hz,
            fp_hz=fp_hz,
            fs_hz=fs_hz,
            as_db=as_db,
            num_taps=num_taps,
        )
        coeff_clip_count_q15 = count_clipped_q1_15(coeff_float)
        coeff_q15 = quantize_q1_15(coeff_float, warn_on_clip=True)
        coeff_q15_float = dequantize_q1_15(coeff_q15)

        raw_freq_hz, raw_response_ideal = freqz(
            coeff_float,
            worN=num_freq_samples,
            fs=fs_in_hz,
        )
        raw_freq_hz_q, raw_response_quantized = freqz(
            coeff_q15_float,
            worN=num_freq_samples,
            fs=fs_in_hz,
        )
        # Normalize scipy outputs to concrete ndarrays for downstream numpy calls and typing.
        freq_hz = np.asarray(raw_freq_hz, dtype=np.float64)
        response_ideal = np.asarray(raw_response_ideal)
        freq_hz_q = np.asarray(raw_freq_hz_q, dtype=np.float64)
        response_quantized = np.asarray(raw_response_quantized)

        if freq_axis is None:
            freq_axis = freq_hz
        elif not np.allclose(freq_axis, freq_hz):
            raise RuntimeError("Inconsistent ideal frequency axis across tap counts.")
        if not np.allclose(freq_hz, freq_hz_q):
            raise RuntimeError("Ideal and quantized frequency axes do not match.")

        ideal_mag_db = _magnitude_db(response_ideal)
        quantized_mag_db = _magnitude_db(response_quantized)

        artifacts[f"n{num_taps}_coeff_float"] = coeff_float
        artifacts[f"n{num_taps}_coeff_q15"] = coeff_q15
        artifacts[f"n{num_taps}_coeff_q15_float"] = coeff_q15_float
        artifacts[f"n{num_taps}_ideal_mag_db"] = ideal_mag_db
        artifacts[f"n{num_taps}_quantized_mag_db"] = quantized_mag_db

        results.append(
            {
                "num_taps": num_taps,
                "coeff": {
                    "clip_count_q15": coeff_clip_count_q15,
                    "max_float": float(np.max(coeff_float)),
                    "min_float": float(np.min(coeff_float)),
                    "sum_float": float(np.sum(coeff_float)),
                    "abs_sum_float": float(np.sum(np.abs(coeff_float))),
                    "max_q15_float": float(np.max(coeff_q15_float)),
                    "min_q15_float": float(np.min(coeff_q15_float)),
                    "sum_q15_float": float(np.sum(coeff_q15_float)),
                    "abs_sum_q15_float": float(np.sum(np.abs(coeff_q15_float))),
                },
                "ideal": analyze_frequency_response(
                    freq_hz=freq_hz,
                    mag_db=ideal_mag_db,
                    fp_hz=fp_hz,
                    fs_hz=fs_hz,
                    as_db=as_db,
                ),
                "quantized": analyze_frequency_response(
                    freq_hz=freq_hz_q,
                    mag_db=quantized_mag_db,
                    fp_hz=fp_hz,
                    fs_hz=fs_hz,
                    as_db=as_db,
                ),
            },
        )

    assert freq_axis is not None
    artifacts["freq_hz"] = freq_axis

    summary: dict[str, Any] = {
        "config": {
            "num_taps": tap_counts,
            "fs_in_hz": fs_in_hz,
            "fp_hz": fp_hz,
            "fs_hz": fs_hz,
            "as_db": as_db,
            "num_freq_samples": num_freq_samples,
            "freq_resolution_hz": float(freq_axis[1] - freq_axis[0]),
            "stopband_criterion": "worst-case magnitude over f >= fs_hz",
        },
        "results": results,
    }
    return artifacts, summary


def _save_array(path: Path, array: np.ndarray) -> None:
    np.save(path, array)


def _write_summary_json(path: Path, summary: dict[str, Any]) -> None:
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="ascii")


def _write_summary_text(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "[Coefficient Stopband Spec Check]",
        f"num_taps                     : {summary['config']['num_taps']}",
        f"fs_in_hz                     : {summary['config']['fs_in_hz']:.1f}",
        f"fp_hz                        : {summary['config']['fp_hz']:.1f}",
        f"fs_hz                        : {summary['config']['fs_hz']:.1f}",
        f"as_db                        : {summary['config']['as_db']:.1f}",
        f"num_freq_samples             : {summary['config']['num_freq_samples']}",
        f"freq_resolution_hz           : {summary['config']['freq_resolution_hz']:.12f}",
        f"stopband_criterion           : {summary['config']['stopband_criterion']}",
        "",
    ]
    for result in summary["results"]:
        num_taps = result["num_taps"]
        lines.extend(
            [
                f"[N={num_taps}]",
                f"coeff_clip_count_q15         : {result['coeff']['clip_count_q15']}",
                f"ideal_at_fs_db               : {result['ideal']['at_fs_db']:.12f}",
                f"ideal_stopband_min_atten_db  : {result['ideal']['stopband_min_atten_db']:.12f}",
                f"ideal_stopband_margin_db     : {result['ideal']['stopband_margin_db']:.12f}",
                f"ideal_stopband_worst_freq_hz : {result['ideal']['stopband_worst_freq_hz']:.3f}",
                f"ideal_passband_ripple_db_pp  : {result['ideal']['passband_ripple_db_pp']:.12f}",
                f"ideal_meets_stopband_spec    : {result['ideal']['meets_stopband_spec']}",
                f"quant_at_fs_db               : {result['quantized']['at_fs_db']:.12f}",
                f"quant_stopband_min_atten_db  : {result['quantized']['stopband_min_atten_db']:.12f}",
                f"quant_stopband_margin_db     : {result['quantized']['stopband_margin_db']:.12f}",
                f"quant_stopband_worst_freq_hz : {result['quantized']['stopband_worst_freq_hz']:.3f}",
                f"quant_passband_ripple_db_pp  : {result['quantized']['passband_ripple_db_pp']:.12f}",
                f"quant_meets_stopband_spec    : {result['quantized']['meets_stopband_spec']}",
                "",
            ],
        )
    path.write_text("\n".join(lines), encoding="ascii")


def main() -> None:
    args = build_arg_parser().parse_args()
    save_dir = args.save_dir if args.save_dir is not None else _default_save_dir(args.num_taps)
    save_dir.mkdir(parents=True, exist_ok=True)

    artifacts, summary = run_check_coeff_stopband_spec(
        num_taps_list=args.num_taps,
        fs_in_hz=args.fs_in_hz,
        fp_hz=args.fp_hz,
        fs_hz=args.fs_hz,
        as_db=args.as_db,
        num_freq_samples=args.num_freq_samples,
    )

    for name, array in artifacts.items():
        _save_array(save_dir / f"{name}.npy", array)

    _write_summary_json(save_dir / "summary.json", summary)
    _write_summary_text(save_dir / "summary.txt", summary)

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
