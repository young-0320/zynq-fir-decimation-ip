from pathlib import Path

import numpy as np
import pytest

from sim.python.export_rtl_bringup_vectors import (
    export_rtl_bringup_vectors,
    load_q15_vector,
    q15_array_to_hex_lines,
)


def test_q15_array_to_hex_lines_formats_signed_values_as_twos_complement() -> None:
    x_q15 = np.array([0, 1, 32767, -32768, -1], dtype=np.int16)

    assert q15_array_to_hex_lines(x_q15) == [
        "0000",
        "0001",
        "7fff",
        "8000",
        "ffff",
    ]


def test_load_q15_vector_rejects_non_integer_arrays(tmp_path: Path) -> None:
    path = tmp_path / "input_q15.npy"
    np.save(path, np.array([0.0, 1.0], dtype=np.float64))

    with pytest.raises(TypeError):
        load_q15_vector(path)


def test_export_rtl_bringup_vectors_writes_expected_hex_files(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    np.save(input_dir / "input_q15.npy", np.array([0, 1, -1], dtype=np.int16))
    np.save(input_dir / "coeff_q15.npy", np.array([88, 7069, 18455], dtype=np.int16))
    np.save(input_dir / "fixed_fir_q15.npy", np.array([0, 58, 4705], dtype=np.int16))
    np.save(input_dir / "fixed_decim_q15.npy", np.array([0, 4705, 7191], dtype=np.int16))

    exported_lengths = export_rtl_bringup_vectors(
        input_dir=input_dir,
        output_dir=output_dir,
    )

    assert exported_lengths == {
        "input_q15.hex": 3,
        "coeff_q15.hex": 3,
        "expected_fir_q15.hex": 3,
        "expected_decim_q15.hex": 3,
    }
    assert (output_dir / "input_q15.hex").read_text(encoding="ascii") == "0000\n0001\nffff\n"
    assert (output_dir / "coeff_q15.hex").read_text(encoding="ascii") == "0058\n1b9d\n4817\n"
    assert (output_dir / "expected_fir_q15.hex").read_text(encoding="ascii") == "0000\n003a\n1261\n"
    assert (output_dir / "expected_decim_q15.hex").read_text(encoding="ascii") == "0000\n1261\n1c17\n"
