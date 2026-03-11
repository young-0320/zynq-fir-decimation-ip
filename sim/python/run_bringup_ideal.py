import argparse
from pathlib import Path

import numpy as np

from model.ideal.design_kaiser_coeff import design_kaiser_lpf
from model.ideal.fir_decimator_ideal import run_fir_decimator_ideal
from model.ideal.gen_multitone import generate_multitone, quantize_q1_15
from sim.python.downsample_only_ideal import run_downsample_only_ideal


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
        description="Generate the bring-up multitone and run the ideal FIR-decimator chain.",
    )
    parser.add_argument("--num-taps", type=int, default=DEFAULT_NUM_TAPS)
    parser.add_argument("--num-samples", type=int, default=DEFAULT_NUM_SAMPLES)
    parser.add_argument("--fs-in-hz", type=float, default=DEFAULT_FS_IN_HZ)
    parser.add_argument("--fp-hz", type=float, default=DEFAULT_FP_HZ)
    parser.add_argument("--fs-hz", type=float, default=DEFAULT_FS_HZ)
    parser.add_argument("--as-db", type=float, default=DEFAULT_AS_DB)
    parser.add_argument(
        "--save-dir",
        type=Path,
        default=None,
        help="Directory to store generated vectors. Defaults to repo_root/sim/output.",
    )
    return parser


def _default_save_dir() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "sim" / "output"


def _rms(x: np.ndarray) -> float:
    x_arr = np.asarray(x, dtype=np.float64)
    return float(np.sqrt(np.mean(x_arr * x_arr)))


def _save_array(path: Path, array: np.ndarray) -> None:
    np.save(path, array)


def _write_summary(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def main() -> None:
    args = build_arg_parser().parse_args()

    save_dir = args.save_dir if args.save_dir is not None else _default_save_dir()
    save_dir.mkdir(parents=True, exist_ok=True)

    x_float = generate_multitone(
        num_samples=args.num_samples,
        fs_hz=args.fs_in_hz,
        tone_freqs_hz=DEFAULT_FREQS_HZ,
        amplitudes=DEFAULT_AMPLITUDES,
        phases_rad=DEFAULT_PHASES_RAD,
    )
    x_q15 = quantize_q1_15(x_float)

    h = design_kaiser_lpf(
        fs_in_hz=args.fs_in_hz,
        fp_hz=args.fp_hz,
        fs_hz=args.fs_hz,
        as_db=args.as_db,
        num_taps=args.num_taps,
    )

    y_fir, y_decim = run_fir_decimator_ideal(
        x=x_float,
        h=h,
        m=DEFAULT_DECIMATION,
        phase=DEFAULT_PHASE,
        return_intermediate=True,
    )
    y_downsample_only = run_downsample_only_ideal(
        x=x_float,
        m=DEFAULT_DECIMATION,
        phase=DEFAULT_PHASE,
    )

    stem = f"bringup_n{args.num_taps}"
    _save_array(save_dir / f"{stem}_input_float.npy", x_float)
    _save_array(save_dir / f"{stem}_input_q15.npy", x_q15)
    _save_array(save_dir / f"{stem}_coeff.npy", h)
    _save_array(save_dir / f"{stem}_fir.npy", y_fir)
    _save_array(save_dir / f"{stem}_decim.npy", y_decim)
    _save_array(save_dir / f"{stem}_downsample_only.npy", y_downsample_only)

    summary_lines = [
        "[Bring-up Ideal Run]",
        f"num_taps              : {args.num_taps}",
        f"num_samples           : {args.num_samples}",
        f"fs_in_hz              : {args.fs_in_hz:.1f}",
        f"fp_hz                 : {args.fp_hz:.1f}",
        f"fs_hz                 : {args.fs_hz:.1f}",
        f"as_db                 : {args.as_db:.1f}",
        f"input_dtype_float     : {x_float.dtype}",
        f"input_dtype_q15       : {x_q15.dtype}",
        f"coeff_dtype           : {h.dtype}",
        f"fir_dtype             : {y_fir.dtype}",
        f"decim_dtype           : {y_decim.dtype}",
        f"input_peak            : {np.max(np.abs(x_float)):.9f}",
        f"input_rms             : {_rms(x_float):.9f}",
        f"coeff_sum             : {np.sum(h):.9f}",
        f"coeff_abs_sum         : {np.sum(np.abs(h)):.9f}",
        f"fir_len               : {len(y_fir)}",
        f"decim_len             : {len(y_decim)}",
        f"downsample_only_len   : {len(y_downsample_only)}",
        f"save_dir              : {save_dir}",
    ]
    _write_summary(save_dir / f"{stem}_summary.txt", summary_lines)

    print("\n".join(summary_lines))
    print()
    print("input_float[:10] =", x_float[:10])
    print("input_q15[:10]   =", x_q15[:10])
    print("coeff[:10]       =", h[:10])
    print("fir[:10]         =", y_fir[:10])
    print("decim[:10]       =", y_decim[:10])


if __name__ == "__main__":
    main()
