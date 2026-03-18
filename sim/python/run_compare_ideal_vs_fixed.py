from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from model.fixed.fir_decimator_golden import run_fir_decimator_golden
from model.ideal.design_kaiser_coeff import design_kaiser_lpf
from model.ideal.fir_decimator_ideal import run_fir_decimator_ideal
from model.ideal.gen_multitone import generate_multitone
from model.q1_15 import count_clipped_q1_15, dequantize_q1_15, quantize_q1_15


DEFAULT_FS_IN_HZ = 100_000_000.0
DEFAULT_FP_HZ = 15_000_000.0
DEFAULT_FS_HZ = 25_000_000.0
DEFAULT_AS_DB = 60.0
DEFAULT_NUM_TAPS = 5
DEFAULT_NUM_SAMPLES = 8192
DEFAULT_FREQS_HZ = [5_000_000.0, 20_000_000.0, 30_000_000.0]
DEFAULT_AMPLITUDES = [0.3, 0.3, 0.3]
DEFAULT_PHASES_RAD = [0.0, 0.0, 0.0]
DEFAULT_DECIMATION = 2
DEFAULT_PHASE = 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare ideal(float64) and fixed(Q1.15) FIR-decimator outputs "
            "using the bring-up multitone stimulus."
        ),
    )
    parser.add_argument("--num-taps", type=int, default=DEFAULT_NUM_TAPS)
    parser.add_argument("--num-samples", type=int, default=DEFAULT_NUM_SAMPLES)
    parser.add_argument("--fs-in-hz", type=float, default=DEFAULT_FS_IN_HZ)
    parser.add_argument("--fp-hz", type=float, default=DEFAULT_FP_HZ)
    parser.add_argument("--fs-hz", type=float, default=DEFAULT_FS_HZ)
    parser.add_argument("--as-db", type=float, default=DEFAULT_AS_DB)
    parser.add_argument("--m", type=int, default=DEFAULT_DECIMATION)
    parser.add_argument("--phase", type=int, default=DEFAULT_PHASE)
    parser.add_argument(
        "--save-dir",
        type=Path,
        default=None,
        help="Directory to store outputs. Defaults to repo_root/sim/output/ideal_vs_fixed_n{N}.",
    )
    return parser


def _default_save_dir(num_taps: int) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "sim" / "output" / f"ideal_vs_fixed_n{num_taps}"


def _rms(x: np.ndarray) -> float:
    x_arr = np.asarray(x, dtype=np.float64)
    return float(np.sqrt(np.mean(x_arr * x_arr)))


def compute_error_metrics(reference: np.ndarray, candidate: np.ndarray) -> dict[str, float | int]:
    ref_arr = np.asarray(reference, dtype=np.float64)
    cand_arr = np.asarray(candidate, dtype=np.float64)
    if ref_arr.shape != cand_arr.shape:
        raise ValueError("reference and candidate must have the same shape.")

    diff = cand_arr - ref_arr
    abs_diff = np.abs(diff)
    mse = float(np.mean(diff * diff))
    rmse = float(math.sqrt(mse))
    signal_power = float(np.mean(ref_arr * ref_arr))

    if mse == 0.0:
        snr_db = float("inf")
    elif signal_power == 0.0:
        snr_db = float("-inf")
    else:
        snr_db = float(10.0 * math.log10(signal_power / mse))

    return {
        "num_samples": int(ref_arr.size),
        "mae": float(np.mean(abs_diff)),
        "mse": mse,
        "rmse": rmse,
        "max_abs_err": float(np.max(abs_diff)) if ref_arr.size > 0 else 0.0,
        "mean_err": float(np.mean(diff)) if ref_arr.size > 0 else 0.0,
        "snr_db": snr_db,
    }


def run_compare_ideal_vs_fixed(
    *,
    num_taps: int = DEFAULT_NUM_TAPS,
    num_samples: int = DEFAULT_NUM_SAMPLES,
    fs_in_hz: float = DEFAULT_FS_IN_HZ,
    fp_hz: float = DEFAULT_FP_HZ,
    fs_hz: float = DEFAULT_FS_HZ,
    as_db: float = DEFAULT_AS_DB,
    m: int = DEFAULT_DECIMATION,
    phase: int = DEFAULT_PHASE,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    x_float = generate_multitone(
        num_samples=num_samples,
        fs_hz=fs_in_hz,
        tone_freqs_hz=DEFAULT_FREQS_HZ,
        amplitudes=DEFAULT_AMPLITUDES,
        phases_rad=DEFAULT_PHASES_RAD,
    )
    h_float = design_kaiser_lpf(
        fs_in_hz=fs_in_hz,
        fp_hz=fp_hz,
        fs_hz=fs_hz,
        as_db=as_db,
        num_taps=num_taps,
    )

    input_clip_count = count_clipped_q1_15(x_float)
    coeff_clip_count = count_clipped_q1_15(h_float)
    x_q15 = quantize_q1_15(x_float, warn_on_clip=True)
    h_q15 = quantize_q1_15(h_float, warn_on_clip=True)
    x_q15_float = dequantize_q1_15(x_q15)
    h_q15_float = dequantize_q1_15(h_q15)

    ideal_raw_fir, ideal_raw_decim = run_fir_decimator_ideal(
        x=x_float,
        h=h_float,
        m=m,
        phase=phase,
        return_intermediate=True,
    )
    ideal_quantized_ref_fir, ideal_quantized_ref_decim = run_fir_decimator_ideal(
        x=x_q15_float,
        h=h_q15_float,
        m=m,
        phase=phase,
        return_intermediate=True,
    )
    fixed_fir_q15, fixed_decim_q15 = run_fir_decimator_golden(
        x=x_q15,
        h=h_q15,
        m=m,
        phase=phase,
        return_intermediate=True,
    )
    fixed_fir_float = dequantize_q1_15(fixed_fir_q15)
    fixed_decim_float = dequantize_q1_15(fixed_decim_q15)

    artifacts = {
        "input_float": x_float,
        "input_q15": x_q15,
        "input_q15_float": x_q15_float,
        "coeff_float": h_float,
        "coeff_q15": h_q15,
        "coeff_q15_float": h_q15_float,
        "ideal_raw_fir": ideal_raw_fir,
        "ideal_raw_decim": ideal_raw_decim,
        "ideal_quantized_ref_fir": ideal_quantized_ref_fir,
        "ideal_quantized_ref_decim": ideal_quantized_ref_decim,
        "fixed_fir_q15": fixed_fir_q15,
        "fixed_decim_q15": fixed_decim_q15,
        "fixed_fir_float": fixed_fir_float,
        "fixed_decim_float": fixed_decim_float,
        "diff_vs_ideal_raw_fir": fixed_fir_float - ideal_raw_fir,
        "diff_vs_ideal_raw_decim": fixed_decim_float - ideal_raw_decim,
        "diff_vs_quantized_ref_fir": fixed_fir_float - ideal_quantized_ref_fir,
        "diff_vs_quantized_ref_decim": fixed_decim_float - ideal_quantized_ref_decim,
    }

    summary: dict[str, Any] = {
        "config": {
            "num_taps": num_taps,
            "num_samples": num_samples,
            "fs_in_hz": fs_in_hz,
            "fp_hz": fp_hz,
            "fs_hz": fs_hz,
            "as_db": as_db,
            "m": m,
            "phase": phase,
            "tone_freqs_hz": DEFAULT_FREQS_HZ,
            "amplitudes": DEFAULT_AMPLITUDES,
            "phases_rad": DEFAULT_PHASES_RAD,
        },
        "input": {
            "input_peak": float(np.max(np.abs(x_float))),
            "input_rms": _rms(x_float),
            "input_clip_count_q15": input_clip_count,
            "input_q15_peak": int(np.max(np.abs(x_q15.astype(np.int32)))),
        },
        "coeff": {
            "coeff_sum_float": float(np.sum(h_float)),
            "coeff_abs_sum_float": float(np.sum(np.abs(h_float))),
            "coeff_sum_q15_float": float(np.sum(h_q15_float)),
            "coeff_abs_sum_q15_float": float(np.sum(np.abs(h_q15_float))),
            "coeff_clip_count_q15": coeff_clip_count,
        },
        "metrics": {
            "vs_ideal_raw": {
                "fir": compute_error_metrics(ideal_raw_fir, fixed_fir_float),
                "decim": compute_error_metrics(ideal_raw_decim, fixed_decim_float),
            },
            "vs_quantized_reference": {
                "fir": compute_error_metrics(ideal_quantized_ref_fir, fixed_fir_float),
                "decim": compute_error_metrics(ideal_quantized_ref_decim, fixed_decim_float),
            },
        },
    }
    return artifacts, summary


def _save_array(path: Path, array: np.ndarray) -> None:
    np.save(path, array)


def _write_summary_json(path: Path, summary: dict[str, Any]) -> None:
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="ascii")


def _write_summary_text(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "[Ideal vs Fixed Compare]",
        f"num_taps                     : {summary['config']['num_taps']}",
        f"num_samples                  : {summary['config']['num_samples']}",
        f"input_clip_count_q15         : {summary['input']['input_clip_count_q15']}",
        f"coeff_clip_count_q15         : {summary['coeff']['coeff_clip_count_q15']}",
        f"vs_ideal_raw_fir_rmse        : {summary['metrics']['vs_ideal_raw']['fir']['rmse']:.12e}",
        f"vs_ideal_raw_decim_rmse      : {summary['metrics']['vs_ideal_raw']['decim']['rmse']:.12e}",
        f"vs_quant_ref_fir_rmse        : {summary['metrics']['vs_quantized_reference']['fir']['rmse']:.12e}",
        f"vs_quant_ref_decim_rmse      : {summary['metrics']['vs_quantized_reference']['decim']['rmse']:.12e}",
        f"vs_ideal_raw_fir_snr_db      : {summary['metrics']['vs_ideal_raw']['fir']['snr_db']:.6f}",
        f"vs_ideal_raw_decim_snr_db    : {summary['metrics']['vs_ideal_raw']['decim']['snr_db']:.6f}",
        f"vs_quant_ref_fir_snr_db      : {summary['metrics']['vs_quantized_reference']['fir']['snr_db']:.6f}",
        f"vs_quant_ref_decim_snr_db    : {summary['metrics']['vs_quantized_reference']['decim']['snr_db']:.6f}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def main() -> None:
    args = build_arg_parser().parse_args()
    save_dir = args.save_dir if args.save_dir is not None else _default_save_dir(args.num_taps)
    save_dir.mkdir(parents=True, exist_ok=True)

    artifacts, summary = run_compare_ideal_vs_fixed(
        num_taps=args.num_taps,
        num_samples=args.num_samples,
        fs_in_hz=args.fs_in_hz,
        fp_hz=args.fp_hz,
        fs_hz=args.fs_hz,
        as_db=args.as_db,
        m=args.m,
        phase=args.phase,
    )

    for name, array in artifacts.items():
        _save_array(save_dir / f"{name}.npy", array)

    _write_summary_json(save_dir / "summary.json", summary)
    _write_summary_text(save_dir / "summary.txt", summary)

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
