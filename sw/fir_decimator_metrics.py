"""Board-free numeric metrics for the FIR decimator pipeline.

English: Generates fixed-point references and computes sample/FFT metrics from
numpy arrays.
Korean: numpy 배열을 입력으로 받아 fixed-point reference를 만들고 sample/FFT
metric을 계산합니다.

This module does not open UART ports, plot figures, or write files.
이 모듈은 UART open, plot, 파일 저장을 하지 않습니다.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, Mapping, Sequence, TypedDict, cast

import numpy as np
import numpy.typing as npt

from model.config import FIR_CONFIG
from model.fixed.transposed_form.fir_decimator_golden import run_fir_decimator_transposed_golden
from model.q1_15 import Q1_15_MAX, Q1_15_MIN, count_clipped_q1_15, quantize_q1_15

Q15Array = npt.NDArray[np.int16]
FloatArray = npt.NDArray[np.float64]
AnyArray = npt.NDArray[Any]

DEFAULT_TONE_AMPLITUDE = 0.9
DEFAULT_PEAK_DELTA_PASS_DB = 1.0
TRANSITION_LIMITATION = "Transition-band tones are reported as INFO, not hard PASS criteria."


class PeakNearResult(TypedDict):
    bin_index: int
    frequency_hz: float
    frequency_mhz: float
    magnitude: float
    peak_db: float


class FftPeakRow(TypedDict):
    target_hz: float
    target_mhz: float
    peak_frequency_hz: float
    peak_frequency_mhz: float
    peak_db: float
    magnitude: float
    bin_index: int


class FixedReferenceResult(TypedDict):
    input_q15: Q15Array
    fixed_q15_reference: Q15Array
    full_fixed_q15_reference: Q15Array
    input_clipping_count: int
    golden_saturation_count: int
    decimation: int
    phase: int


class SampleMetrics(TypedDict):
    n_samples_compared: int
    max_abs_error_lsb: int
    rmse_lsb: float
    snr_db: float
    correlation: float
    mean_error_lsb: float
    max_error_lsb: int
    min_error_lsb: int
    saturation_count: int
    clipping_count: int
    latency_aligned: bool
    trim_head_samples: int
    trim_tail_samples: int


class TonePeakMetric(TypedDict):
    tone_hz: float
    tone_mhz: float
    expected_output_hz: float
    expected_output_mhz: float
    region: str
    input_peak_db: float
    board_peak_db: float
    golden_peak_db: float
    board_vs_golden_peak_delta_db: float
    board_attenuation_db: float
    golden_attenuation_db: float
    verdict: str


class ReportSummary(TypedDict):
    verdict_counts: dict[str, int]
    overall_verdict: str


class ReportArtifacts(TypedDict):
    fft_plot_path: str | None


class MetricsReport(TypedDict):
    mode: str
    input_tones_hz: list[float]
    n_in: int
    n_out: int
    fs_in_hz: float
    fs_out_hz: float
    sample_metrics: SampleMetrics
    tone_metrics: list[TonePeakMetric]
    summary: ReportSummary
    artifacts: ReportArtifacts
    known_limitations: list[str]


__all__ = [
    "DEFAULT_PEAK_DELTA_PASS_DB",
    "DEFAULT_TONE_AMPLITUDE",
    "TRANSITION_LIMITATION",
    "FftPeakRow",
    "FixedReferenceResult",
    "MetricsReport",
    "PeakNearResult",
    "SampleMetrics",
    "TonePeakMetric",
    "build_report",
    "compare_samples",
    "compare_tone_peaks",
    "compute_fft_peaks",
    "fft_peak_near_db",
    "fold_frequency_hz",
    "generate_fixed_reference",
]


def _as_1d_array(values: npt.ArrayLike, *, name: str) -> AnyArray:
    """Validate input as a non-empty 1-D numpy array.
    입력을 비어 있지 않은 1차원 numpy 배열로 검증합니다.
    """
    arr = np.asarray(values)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be a 1-D sequence")
    if arr.size == 0:
        raise ValueError(f"{name} must not be empty")
    return arr


def _as_q15_int16(values: npt.ArrayLike, *, name: str) -> Q15Array:
    """Validate and coerce integer samples into int16 Q1.15.
    정수 샘플을 int16 Q1.15 범위로 검증하고 변환합니다.
    """
    arr = _as_1d_array(values, name=name)
    if not np.issubdtype(arr.dtype, np.integer):
        raise TypeError(f"{name} must contain integer Q1.15 samples")

    min_value = int(np.min(arr))
    max_value = int(np.max(arr))
    if min_value < Q1_15_MIN or max_value > Q1_15_MAX:
        raise ValueError(f"{name} must stay within signed Q1.15/int16 range")
    return cast(Q15Array, arr.astype(np.int16, copy=False))


def _signal_for_fft(values: npt.ArrayLike, *, name: str) -> FloatArray:
    """Convert numeric samples to float64 for FFT analysis.
    FFT 분석용으로 numeric 샘플을 float64로 변환합니다.
    """
    arr = _as_1d_array(values, name=name)
    if not (np.issubdtype(arr.dtype, np.integer) or np.issubdtype(arr.dtype, np.floating)):
        raise TypeError(f"{name} must contain numeric samples")
    return cast(FloatArray, arr.astype(np.float64, copy=False))


def _gen_multitone_float(
    tones_hz: Sequence[float],
    *,
    n_in: int,
    fs_hz: float,
    amplitude: float,
) -> FloatArray:
    """Generate a float multitone waveform before Q15 quantization.
    Q15 양자화 전 float 멀티톤 파형을 생성합니다.
    """
    if not tones_hz:
        raise ValueError("tones_hz must not be empty")
    if n_in <= 0:
        raise ValueError("n_in must be positive")
    if fs_hz <= 0:
        raise ValueError("fs_hz must be positive")

    n = np.arange(n_in, dtype=np.float64)
    tone_amp = amplitude / len(tones_hz)
    sig = np.zeros(n_in, dtype=np.float64)
    for tone_hz in tones_hz:
        sig += tone_amp * np.sin(2.0 * np.pi * float(tone_hz) / fs_hz * n)
    return cast(FloatArray, sig)


def _rail_count(samples_q15: Q15Array) -> int:
    """Count samples sitting on Q1.15 rails.
    Q1.15 최댓값/최솟값에 걸린 샘플 수를 셉니다.
    """
    return int(np.count_nonzero((samples_q15 == Q1_15_MIN) | (samples_q15 == Q1_15_MAX)))


def fold_frequency_hz(frequency_hz: float, sample_rate_hz: float) -> float:
    """Fold a frequency into the first Nyquist band.
    주파수를 첫 번째 Nyquist 대역 안으로 접습니다.
    """

    if sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be positive")

    folded = abs(float(frequency_hz)) % float(sample_rate_hz)
    nyquist_hz = sample_rate_hz / 2.0
    if folded > nyquist_hz:
        folded = sample_rate_hz - folded
    return folded


def fft_peak_near_db(
    samples: npt.ArrayLike,
    sample_rate_hz: float,
    *,
    target_hz: float,
    search_hz: float | None = None,
    ref: float | None = None,
) -> PeakNearResult:
    """Find the strongest FFT bin near a target frequency.
    목표 주파수 근처에서 가장 강한 FFT bin을 찾습니다.
    """

    sig = _signal_for_fft(samples, name="samples")
    if sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be positive")

    nyquist_hz = sample_rate_hz / 2.0
    if target_hz < 0 or target_hz > nyquist_hz:
        raise ValueError("target_hz must be inside the Nyquist band")

    bin_hz = sample_rate_hz / sig.size
    if search_hz is None:
        search_hz = max(2.0 * bin_hz, 1.0)
    if search_hz < 0:
        raise ValueError("search_hz must be non-negative")

    freqs_hz = np.fft.rfftfreq(sig.size, d=1.0 / sample_rate_hz)
    magnitude = np.abs(np.fft.rfft(sig))
    mask = np.abs(freqs_hz - target_hz) <= search_hz
    if not np.any(mask):
        nearest = int(np.argmin(np.abs(freqs_hz - target_hz)))
        mask = np.zeros_like(freqs_hz, dtype=bool)
        mask[nearest] = True

    candidate_indices = np.flatnonzero(mask)
    peak_index = int(candidate_indices[np.argmax(magnitude[candidate_indices])])
    peak_mag = float(magnitude[peak_index])

    if ref is None:
        ref = float(magnitude.max())
    ref = float(ref)
    if ref <= 0.0:
        ref = 1.0

    peak_db = 20.0 * math.log10(peak_mag / ref + 1e-12)
    return {
        "bin_index": peak_index,
        "frequency_hz": float(freqs_hz[peak_index]),
        "frequency_mhz": float(freqs_hz[peak_index] / 1e6),
        "magnitude": peak_mag,
        "peak_db": peak_db,
    }


def compute_fft_peaks(
    samples: npt.ArrayLike,
    sample_rate_hz: float,
    tones_hz: Sequence[float],
    *,
    search_hz: float | None = None,
    ref: float | None = None,
) -> list[FftPeakRow]:
    """Extract FFT peak rows for requested tone targets.
    요청한 tone target별 FFT peak row를 추출합니다.
    """

    if not tones_hz:
        raise ValueError("tones_hz must not be empty")

    rows: list[FftPeakRow] = []
    for tone_hz in tones_hz:
        target_hz = float(tone_hz)
        peak = fft_peak_near_db(
            samples,
            sample_rate_hz,
            target_hz=target_hz,
            search_hz=search_hz,
            ref=ref,
        )
        rows.append(
            {
                "target_hz": target_hz,
                "target_mhz": target_hz / 1e6,
                "peak_frequency_hz": peak["frequency_hz"],
                "peak_frequency_mhz": peak["frequency_mhz"],
                "peak_db": peak["peak_db"],
                "magnitude": peak["magnitude"],
                "bin_index": peak["bin_index"],
            }
        )
    return rows


def generate_fixed_reference(
    tones_hz: Sequence[float],
    *,
    n_in: int,
    fs_hz: float,
    coeffs_q15: npt.ArrayLike,
    n_out: int | None = None,
    decimation: int = FIR_CONFIG.decimation_factor,
    phase: int = FIR_CONFIG.default_phase,
    amplitude: float = DEFAULT_TONE_AMPLITUDE,
) -> FixedReferenceResult:
    """Generate Q1.15 input and fixed FIR-decimator reference output.
    Q1.15 입력과 fixed FIR decimator 기준 출력을 생성합니다.
    """

    if decimation < 1:
        raise ValueError("decimation must be >= 1")
    if not (0 <= phase < decimation):
        raise ValueError("phase must satisfy 0 <= phase < decimation")
    if n_out is not None and n_out < 1:
        raise ValueError("n_out must be positive when provided")

    coeff_arr = _as_q15_int16(coeffs_q15, name="coeffs_q15")
    sig_float = _gen_multitone_float(tones_hz, n_in=n_in, fs_hz=fs_hz, amplitude=amplitude)
    input_q15 = quantize_q1_15(sig_float)
    full_reference = cast(
        Q15Array,
        run_fir_decimator_transposed_golden(
            input_q15,
            coeff_arr,
            m=decimation,
            phase=phase,
        ),
    )

    if n_out is None:
        reference = full_reference
    else:
        if n_out > full_reference.size:
            raise ValueError("n_out exceeds available fixed-point golden output")
        reference = full_reference[:n_out]

    fixed_reference = cast(Q15Array, reference.astype(np.int16, copy=False))
    full_fixed_reference = cast(Q15Array, full_reference.astype(np.int16, copy=False))
    return {
        "input_q15": cast(Q15Array, input_q15),
        "fixed_q15_reference": fixed_reference,
        "full_fixed_q15_reference": full_fixed_reference,
        "input_clipping_count": count_clipped_q1_15(sig_float),
        "golden_saturation_count": _rail_count(fixed_reference),
        "decimation": decimation,
        "phase": phase,
    }


def compare_samples(
    board_out: npt.ArrayLike,
    golden_out: npt.ArrayLike,
    *,
    latency_aligned: bool = True,
    trim_head_samples: int = 0,
    trim_tail_samples: int = 0,
) -> SampleMetrics:
    """Compare board and golden samples in LSB units.
    보드 출력과 golden 출력을 LSB 단위로 비교합니다.
    """

    board = _as_q15_int16(board_out, name="board_out")
    golden = _as_q15_int16(golden_out, name="golden_out")
    if board.shape != golden.shape:
        raise ValueError("board_out and golden_out must have the same length")
    if not isinstance(trim_head_samples, int) or isinstance(trim_head_samples, bool):
        raise TypeError("trim_head_samples must be an int")
    if not isinstance(trim_tail_samples, int) or isinstance(trim_tail_samples, bool):
        raise TypeError("trim_tail_samples must be an int")
    if trim_head_samples < 0 or trim_tail_samples < 0:
        raise ValueError("trim sample counts must be non-negative")

    start_idx = trim_head_samples
    stop_idx = board.size - trim_tail_samples
    if start_idx >= stop_idx:
        raise ValueError("trim sample counts must leave at least one sample to compare")

    board_cmp = board[start_idx:stop_idx]
    golden_cmp = golden[start_idx:stop_idx]

    error = board_cmp.astype(np.int32) - golden_cmp.astype(np.int32)
    abs_error = np.abs(error)
    error_float = error.astype(np.float64)
    golden_float = golden_cmp.astype(np.float64)
    error_power = float(np.sum(error_float**2))
    signal_power = float(np.sum(golden_float**2))

    if error_power == 0.0:
        snr_db = math.inf
    elif signal_power == 0.0:
        snr_db = -math.inf
    else:
        snr_db = 10.0 * math.log10(signal_power / error_power)

    board_float = board_cmp.astype(np.float64)
    if np.array_equal(board_cmp, golden_cmp):
        correlation = 1.0
    elif float(np.std(board_float)) == 0.0 or float(np.std(golden_float)) == 0.0:
        correlation = math.nan
    else:
        correlation = float(np.corrcoef(board_float, golden_float)[0, 1])

    saturation_count = _rail_count(board_cmp)
    return {
        "n_samples_compared": int(board_cmp.size),
        "max_abs_error_lsb": int(np.max(abs_error)),
        "rmse_lsb": float(np.sqrt(np.mean(error_float**2))),
        "snr_db": snr_db,
        "correlation": correlation,
        "mean_error_lsb": float(np.mean(error)),
        "max_error_lsb": int(np.max(error)),
        "min_error_lsb": int(np.min(error)),
        "saturation_count": saturation_count,
        "clipping_count": saturation_count,
        "latency_aligned": bool(latency_aligned),
        "trim_head_samples": int(trim_head_samples),
        "trim_tail_samples": int(trim_tail_samples),
    }


def _region_for_tone(tone_hz: float, regions: Mapping[float, str] | None) -> str:
    """Look up the report region label for a tone.
    톤에 대응하는 report region label을 조회합니다.
    """
    if not regions:
        return "unknown"
    if tone_hz in regions:
        return regions[tone_hz]
    for key, value in regions.items():
        if math.isclose(float(key), tone_hz, rel_tol=0.0, abs_tol=1.0):
            return value
    return "unknown"


def _tone_verdict(region: str, peak_delta_db: float) -> str:
    """Classify a tone metric as PASS, WARN, or INFO.
    tone metric을 PASS, WARN, INFO로 분류합니다.
    """
    if region == "transition":
        return "INFO"
    if abs(peak_delta_db) <= DEFAULT_PEAK_DELTA_PASS_DB:
        return "PASS"
    return "WARN"


def compare_tone_peaks(
    sig_in: npt.ArrayLike,
    board_out: npt.ArrayLike,
    golden_out: npt.ArrayLike,
    tones_hz: Sequence[float],
    *,
    fs_in_hz: float,
    fs_out_hz: float,
    regions: Mapping[float, str] | None = None,
    search_hz: float | None = None,
) -> list[TonePeakMetric]:
    """Compare input, board, and golden FFT peaks at expected bins.
    예상 bin에서 입력, 보드, golden FFT peak를 비교합니다.
    """

    input_sig = _signal_for_fft(sig_in, name="sig_in")
    board = _as_q15_int16(board_out, name="board_out")
    golden = _as_q15_int16(golden_out, name="golden_out")
    if board.shape != golden.shape:
        raise ValueError("board_out and golden_out must have the same length")
    if fs_in_hz <= 0 or fs_out_hz <= 0:
        raise ValueError("sample rates must be positive")
    if not tones_hz:
        raise ValueError("tones_hz must not be empty")

    input_ref = float(np.abs(np.fft.rfft(input_sig)).max())
    if input_ref <= 0.0:
        input_ref = 1.0

    rows: list[TonePeakMetric] = []
    for tone_hz_raw in tones_hz:
        tone_hz = float(tone_hz_raw)
        input_target_hz = fold_frequency_hz(tone_hz, fs_in_hz)
        output_target_hz = fold_frequency_hz(tone_hz, fs_out_hz)

        input_peak = compute_fft_peaks(
            input_sig,
            fs_in_hz,
            [input_target_hz],
            search_hz=search_hz,
            ref=input_ref,
        )[0]
        board_peak = compute_fft_peaks(
            board,
            fs_out_hz,
            [output_target_hz],
            search_hz=search_hz,
            ref=input_ref,
        )[0]
        golden_peak = compute_fft_peaks(
            golden,
            fs_out_hz,
            [output_target_hz],
            search_hz=search_hz,
            ref=input_ref,
        )[0]

        input_peak_db = input_peak["peak_db"]
        board_peak_db = board_peak["peak_db"]
        golden_peak_db = golden_peak["peak_db"]
        peak_delta_db = board_peak_db - golden_peak_db
        region = _region_for_tone(tone_hz, regions)

        rows.append(
            {
                "tone_hz": tone_hz,
                "tone_mhz": tone_hz / 1e6,
                "expected_output_hz": output_target_hz,
                "expected_output_mhz": output_target_hz / 1e6,
                "region": region,
                "input_peak_db": input_peak_db,
                "board_peak_db": board_peak_db,
                "golden_peak_db": golden_peak_db,
                "board_vs_golden_peak_delta_db": peak_delta_db,
                "board_attenuation_db": board_peak_db - input_peak_db,
                "golden_attenuation_db": golden_peak_db - input_peak_db,
                "verdict": _tone_verdict(region, peak_delta_db),
            }
        )
    return rows


def build_report(
    mode: str,
    freqs_hz: Sequence[float],
    sig_in: npt.ArrayLike,
    board_out: npt.ArrayLike,
    golden_out: npt.ArrayLike,
    *,
    fs_in_hz: float,
    fs_out_hz: float,
    regions: Mapping[float, str] | None = None,
    search_hz: float | None = None,
    latency_aligned: bool = True,
    trim_head_samples: int = 0,
    trim_tail_samples: int = 0,
    fft_plot_path: str | None = None,
    known_limitations: Sequence[str] | None = None,
) -> MetricsReport:
    """Build an in-memory metrics report dictionary for wrappers.
    wrapper가 저장/출력할 수 있는 메모리상 metric report dict를 만듭니다.
    """

    input_q15 = _as_q15_int16(sig_in, name="sig_in")
    board = _as_q15_int16(board_out, name="board_out")
    golden = _as_q15_int16(golden_out, name="golden_out")

    sample_metrics = compare_samples(
        board,
        golden,
        latency_aligned=latency_aligned,
        trim_head_samples=trim_head_samples,
        trim_tail_samples=trim_tail_samples,
    )
    tone_metrics = compare_tone_peaks(
        input_q15,
        board,
        golden,
        freqs_hz,
        fs_in_hz=fs_in_hz,
        fs_out_hz=fs_out_hz,
        regions=regions,
        search_hz=search_hz,
    )
    verdict_counts = dict(Counter(row["verdict"] for row in tone_metrics))
    limitations = list(known_limitations or [])
    has_transition_tone = any(row["region"] == "transition" for row in tone_metrics)
    if has_transition_tone and TRANSITION_LIMITATION not in limitations:
        limitations.append(TRANSITION_LIMITATION)

    return {
        "mode": mode,
        "input_tones_hz": [float(freq) for freq in freqs_hz],
        "n_in": int(input_q15.size),
        "n_out": int(board.size),
        "fs_in_hz": float(fs_in_hz),
        "fs_out_hz": float(fs_out_hz),
        "sample_metrics": sample_metrics,
        "tone_metrics": tone_metrics,
        "summary": {
            "verdict_counts": verdict_counts,
            "overall_verdict": "WARN" if "WARN" in verdict_counts else "PASS",
        },
        "artifacts": {
            "fft_plot_path": fft_plot_path,
        },
        "known_limitations": limitations,
    }
