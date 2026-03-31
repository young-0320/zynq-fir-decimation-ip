from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from model.config import FIR_CONFIG

DEFAULT_NUM_TAPS = FIR_CONFIG.bringup_num_taps
Q15_MIN = FIR_CONFIG.q_min
Q15_MAX = FIR_CONFIG.q_max

ARTIFACT_FILE_MAP = {
    "input_q15.npy": "input_q15.hex",
    "coeff_q15.npy": "coeff_q15.hex",
    "fixed_fir_q15.npy": "expected_fir_q15.hex",
    "fixed_decim_q15.npy": "expected_decim_q15.hex",
}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export Q1.15 bring-up vectors from sim/output/ideal_vs_fixed_n{N} "
            "into RTL-friendly hex files."
        ),
    )
    parser.add_argument("--num-taps", type=int, default=DEFAULT_NUM_TAPS)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=None,
        help=(
            "Directory containing input_q15.npy, coeff_q15.npy, "
            "fixed_fir_q15.npy, and fixed_decim_q15.npy."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Directory to store exported hex vectors. "
            "Defaults to repo_root/sim/vectors/direct_form/bringup_n5."
        ),
    )
    return parser


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_input_dir(num_taps: int) -> Path:
    return _repo_root() / "sim" / "output" / f"ideal_vs_fixed_n{num_taps}"


def _default_output_dir() -> Path:
    return _repo_root() / "sim" / "vectors" / "direct_form" / "bringup_n5"


def load_q15_vector(path: Path) -> np.ndarray:
    array = np.load(path)
    if array.ndim != 1:
        raise ValueError(f"{path.name} must be a 1-D array.")
    if not np.issubdtype(array.dtype, np.integer):
        raise TypeError(f"{path.name} must contain integer values.")

    array_i64 = np.asarray(array, dtype=np.int64)
    if array_i64.size > 0:
        x_min = int(np.min(array_i64))
        x_max = int(np.max(array_i64))
        if x_min < Q15_MIN or x_max > Q15_MAX:
            raise ValueError(f"{path.name} must stay within signed Q1.15/int16 range.")

    return array_i64.astype(np.int16, copy=False)


def q15_array_to_hex_lines(x_q15: np.ndarray) -> list[str]:
    array = np.asarray(x_q15)
    if array.ndim != 1:
        raise ValueError("x_q15 must be a 1-D array.")
    if not np.issubdtype(array.dtype, np.integer):
        raise TypeError("x_q15 must contain integer values.")

    return [f"{int(sample) & 0xFFFF:04x}" for sample in array]


def write_hex_file(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def export_rtl_bringup_vectors(*, input_dir: Path, output_dir: Path) -> dict[str, int]:
    output_dir.mkdir(parents=True, exist_ok=True)

    exported_lengths: dict[str, int] = {}
    for npy_name, hex_name in ARTIFACT_FILE_MAP.items():
        vector = load_q15_vector(input_dir / npy_name)
        lines = q15_array_to_hex_lines(vector)
        write_hex_file(output_dir / hex_name, lines)
        exported_lengths[hex_name] = len(vector)

    return exported_lengths


def main() -> None:
    args = build_arg_parser().parse_args()

    input_dir = args.input_dir if args.input_dir is not None else _default_input_dir(args.num_taps)
    output_dir = args.output_dir if args.output_dir is not None else _default_output_dir()

    exported_lengths = export_rtl_bringup_vectors(
        input_dir=input_dir,
        output_dir=output_dir,
    )

    print(f"input_dir  : {input_dir}")
    print(f"output_dir : {output_dir}")
    for hex_name, length in exported_lengths.items():
        print(f"{hex_name:22s} {length}")


if __name__ == "__main__":
    main()
