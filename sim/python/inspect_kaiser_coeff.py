import argparse
import math

import numpy as np

from model.ideal.design_kaiser_coeff import design_kaiser_lpf, estimate_num_taps, kaiser_beta


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Design a Kaiser-windowed LPF and print debug information.",
    )
    parser.add_argument("--fs-in-hz", type=float, default=100_000_000.0)
    parser.add_argument("--fp-hz", type=float, default=15_000_000.0)
    parser.add_argument("--fs-hz", type=float, default=25_000_000.0)
    parser.add_argument("--as-db", type=float, default=60.0)
    parser.add_argument(
        "--num-taps",
        type=int,
        default=None,
        help="Override tap count. If omitted, Kaiser approximation is used.",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()

    transition_hz = args.fs_hz - args.fp_hz
    delta_omega = 2.0 * math.pi * transition_hz / args.fs_in_hz
    estimated_order = (args.as_db - 8.0) / (2.285 * delta_omega)
    estimated_num_taps = estimate_num_taps(
        fs_in_hz=args.fs_in_hz,
        fp_hz=args.fp_hz,
        fs_hz=args.fs_hz,
        as_db=args.as_db,
    )
    num_taps = args.num_taps if args.num_taps is not None else estimated_num_taps

    fc_hz = 0.5 * (args.fp_hz + args.fs_hz)
    fc_norm = fc_hz / args.fs_in_hz
    beta = kaiser_beta(args.as_db)
    window = np.kaiser(num_taps, beta)
    h = design_kaiser_lpf(
        fs_in_hz=args.fs_in_hz,
        fp_hz=args.fp_hz,
        fs_hz=args.fs_hz,
        as_db=args.as_db,
        num_taps=num_taps,
    )

    print("[Kaiser LPF Design]")
    print(f"fs_in_hz           : {args.fs_in_hz:.3f}")
    print(f"fp_hz              : {args.fp_hz:.3f}")
    print(f"fs_hz              : {args.fs_hz:.3f}")
    print(f"as_db              : {args.as_db:.3f}")
    print(f"transition_hz      : {transition_hz:.3f}")
    print(f"delta_omega        : {delta_omega:.9f}")
    print(f"estimated_order    : {estimated_order:.6f}")
    print(f"estimated_num_taps : {estimated_num_taps}")
    print(f"num_taps_used      : {num_taps}")
    print(f"cutoff_hz(midpoint): {fc_hz:.3f}")
    print(f"cutoff_norm        : {fc_norm:.9f}")
    print(f"kaiser_beta        : {beta:.6f}")
    print(f"window_max         : {np.max(window):.6f}")
    print(f"window_min         : {np.min(window):.6f}")
    print()
    print("[FIR Coefficients]")
    for idx, coeff in enumerate(h):
        print(f"h[{idx:03d}] = {coeff:+.12f}")
    print()
    print(f"계수 최대: {max(h):.6f}")
    print(f"계수 최소: {min(h):.6f}")
    print(f"계수 합산: {sum(h):.6f}")

# uv run --no-sync python -m sim.python.inspect_kaiser_coeff
if __name__ == "__main__":
    main()
