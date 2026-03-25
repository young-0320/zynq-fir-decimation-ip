from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FIRConfig:
    """Single source of truth for FIR-decimator model defaults and fixed-point spec."""

    input_width: int = 16  # 입력 데이터 비트폭
    coeff_width: int = 16  # 계수 비트폭
    output_width: int = 16  # 출력 데이터 비트폭
    fractional_bits: int = 15  # Q1.15 소수부 비트 수

    decimation_factor: int = 2  # 디시메이션 비율 M
    default_phase: int = 0  # 기본 decimation 시작 위상

    fs_in_hz: float = 100_000_000.0  # 입력 샘플링 주파수
    fp_hz: float = 15_000_000.0  # 통과대역 끝 주파수
    fs_hz: float = 25_000_000.0  # 저지대역 시작 주파수
    as_db: float = 60.0  # 목표 저지대역 감쇠량

    bringup_num_taps: int = 5  # bring-up 기본 탭 수
    tap_sweep: tuple[int, ...] = (39, 41, 43)  # 비교/평가용 탭 후보
    spec_num_taps: int = 43  # 현재 spec 충족 기준 탭 수
    bringup_num_samples: int = 8192  # bring-up 입력 샘플 길이
    bringup_tone_freqs_hz: tuple[float, ...] = (
        5_000_000.0,
        20_000_000.0,
        30_000_000.0,
    )  # bring-up 멀티톤 주파수 목록
    bringup_tone_amplitudes: tuple[float, ...] = (0.3, 0.3, 0.3)  # 각 tone 진폭
    bringup_tone_phases_rad: tuple[float, ...] = (0.0, 0.0, 0.0)  # 각 tone 초기 위상

    stopband_num_freq_samples: int = 524_288  # 주파수 응답 분석 샘플 수

    def __post_init__(self) -> None:
        widths = (self.input_width, self.coeff_width, self.output_width)
        if any(width < 2 for width in widths):
            raise ValueError("All fixed-point widths must be >= 2.")
        if self.fractional_bits < 1:
            raise ValueError("fractional_bits must be >= 1.")
        if self.fractional_bits >= min(widths):
            raise ValueError("fractional_bits must stay below the configured widths.")
        if self.decimation_factor < 1:
            raise ValueError("decimation_factor must be >= 1.")
        if not (0 <= self.default_phase < self.decimation_factor):
            raise ValueError("default_phase must satisfy 0 <= phase < decimation_factor.")
        if not (0.0 < self.fp_hz < self.fs_hz < self.fs_in_hz / 2.0):
            raise ValueError("Expected 0 < fp_hz < fs_hz < fs_in_hz / 2.")
        if self.as_db <= 0.0:
            raise ValueError("as_db must be positive.")
        if self.bringup_num_taps < 3:
            raise ValueError("bringup_num_taps must be >= 3.")
        if self.spec_num_taps not in self.tap_sweep:
            raise ValueError("spec_num_taps must be included in tap_sweep.")
        if self.bringup_num_samples < 1:
            raise ValueError("bringup_num_samples must be >= 1.")
        if len(self.tap_sweep) == 0:
            raise ValueError("tap_sweep must not be empty.")
        if len(set(self.tap_sweep)) != len(self.tap_sweep):
            raise ValueError("tap_sweep must contain unique tap counts.")
        if any(num_taps < 3 for num_taps in self.tap_sweep):
            raise ValueError("tap_sweep entries must be >= 3.")
        if not (
            len(self.bringup_tone_freqs_hz)
            == len(self.bringup_tone_amplitudes)
            == len(self.bringup_tone_phases_rad)
        ):
            raise ValueError("Bring-up tone frequencies, amplitudes, and phases must align.")
        if len(self.bringup_tone_freqs_hz) == 0:
            raise ValueError("At least one bring-up tone is required.")
        if self.stopband_num_freq_samples < 2:
            raise ValueError("stopband_num_freq_samples must be >= 2.")

    @property
    def q_scale(self) -> int:
        return 1 << self.fractional_bits

    @property
    def q_min(self) -> int:
        return -(1 << (self.input_width - 1))

    @property
    def q_max(self) -> int:
        return (1 << (self.input_width - 1)) - 1


FIR_CONFIG = FIRConfig()


__all__ = ["FIRConfig", "FIR_CONFIG"]
