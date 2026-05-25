"""UART capture helpers for the FIR decimator board path.

English: Opens the serial port, sends tone commands, and receives raw Q1.15
board output packets.
Korean: 시리얼 포트를 열고 톤 명령을 보낸 뒤 원시 Q1.15 보드 출력
패킷을 수신합니다.

This module does not plot, compute metrics, or write report artifacts.
이 모듈은 plot, metric 계산, report artifact 저장을 하지 않습니다.
"""

from __future__ import annotations

import math
import struct
from typing import Sequence

import numpy as np
import numpy.typing as npt
import serial

MAGIC = 0xDEADBEEF
DEFAULT_UART_TIMEOUT_SEC = 15
DMA_ERROR_TEXT = {
    "1": "MM2S DMA timeout",
    "2": "S2MM DMA timeout",
    "3": "AXI DMA reset timeout",
}

Q15_SCALE = 32768.0
MAX_TONES = 8
MIN_TONE_FREQ_HZ = 1_000_000.0
MAX_TONE_FREQ_HZ = 50_000_000.0


def uart_open(port: str, baud: int, timeout: float):
    """Open a pyserial UART port for board capture.
    보드 캡처용 pyserial UART 포트를 엽니다.
    """
    return serial.Serial(port, baud, timeout=timeout)


def validate_tone_frequencies(freqs_hz: Sequence[float]) -> list[int]:
    """Validate tone frequencies and return integer-Hz command values.
    톤 주파수 계약을 검사하고 명령에 사용할 정수 Hz 값을 반환합니다.
    """
    if len(freqs_hz) == 0:
        raise ValueError("freqs_hz must contain at least one tone")
    if len(freqs_hz) > MAX_TONES:
        raise ValueError(f"freqs_hz must contain at most {MAX_TONES} tones")

    freqs_int = []
    for freq_hz in freqs_hz:
        freq = float(freq_hz)
        if not math.isfinite(freq):
            raise ValueError("freqs_hz must contain finite frequencies")
        if freq <= 0.0:
            raise ValueError("freqs_hz must contain positive frequencies")
        if freq < MIN_TONE_FREQ_HZ:
            raise ValueError(
                f"freqs_hz must be >= {MIN_TONE_FREQ_HZ:.0f} Hz "
                f"({MIN_TONE_FREQ_HZ / 1e6:g} MHz)"
            )
        if freq >= MAX_TONE_FREQ_HZ:
            raise ValueError(
                f"freqs_hz must be < {MAX_TONE_FREQ_HZ:.0f} Hz "
                f"({MAX_TONE_FREQ_HZ / 1e6:g} MHz input Nyquist)"
            )
        freqs_int.append(int(freq))

    return freqs_int


def uart_send_cmd(ser, freqs_hz: Sequence[float]) -> None:
    """Send a tone-frequency command line to the firmware.
    펌웨어에 톤 주파수 명령 문자열을 전송합니다.
    """
    freqs_int = validate_tone_frequencies(freqs_hz)
    cmd = f"{len(freqs_int)} " + " ".join(str(freq) for freq in freqs_int) + "\n"
    ser.write(cmd.encode())


def _recent_context(line: bytearray, recent_text: list[str]) -> str:
    """Build compact UART text context for error messages.
    오류 메시지에 넣을 최근 UART 텍스트를 정리합니다.
    """
    partial = line.decode(errors="replace").strip()
    context = recent_text[-16:]
    if partial:
        context = context + [partial]
    return " | ".join(context)


def _timeout_message(line: bytearray, recent_text: list[str]) -> str:
    """Create a timeout message with recent UART context.
    최근 UART 문맥을 포함한 timeout 메시지를 만듭니다.
    """
    context = _recent_context(line, recent_text)
    if context:
        return "보드 응답 없음 (timeout). 최근 UART 텍스트: " + context
    return "보드 응답 없음 (timeout). 연결 및 비트스트림을 확인하세요."


def _validate_sample_count(
    n_samples: int,
    *,
    expected_samples: int | None,
    max_samples: int | None,
) -> None:
    """Validate the packet sample count before reading the payload.
    payload를 읽기 전에 packet sample count를 검증합니다.
    """
    if expected_samples is not None:
        if expected_samples < 1:
            raise ValueError("expected_samples must be positive when provided")
        if n_samples != expected_samples:
            raise ValueError(f"board packet sample count {n_samples} != expected {expected_samples}")
    if max_samples is not None:
        if max_samples < 1:
            raise ValueError("max_samples must be positive when provided")
        if n_samples > max_samples:
            raise ValueError(f"board packet sample count {n_samples} exceeds max_samples {max_samples}")


def uart_recv_result_q15(
    ser,
    *,
    expected_samples: int | None = None,
    max_samples: int | None = None,
) -> npt.NDArray[np.int16]:
    """Receive one board result packet as raw int16 Q1.15 samples.
    보드 결과 패킷 하나를 원시 int16 Q1.15 샘플로 수신합니다.
    """
    magic_bytes = struct.pack("<I", MAGIC)
    buf = b""
    line = bytearray()
    recent_text: list[str] = []

    while True:
        b = ser.read(1)
        if not b:
            raise TimeoutError(_timeout_message(line, recent_text))
        buf += b
        if len(buf) >= 4 and buf[-4:] == magic_bytes:
            break
        if b in (b"\r", b"\n"):
            text = line.decode(errors="replace").strip()
            if text:
                recent_text.append(text)
            if text.startswith("ERR:"):
                code = text.split(":", 1)[1]
                detail = DMA_ERROR_TEXT.get(code, "unknown board error")
                context = _recent_context(line, recent_text)
                if context:
                    raise RuntimeError(f"보드 DMA 오류 {text}: {detail}. 최근 UART 텍스트: {context}")
                raise RuntimeError(f"보드 DMA 오류 {text}: {detail}")
            line.clear()
        else:
            line += b
            if len(line) > 64:
                del line[:-64]

    n_data = ser.read(4)
    if len(n_data) < 4:
        raise TimeoutError("패킷 수신 중 timeout.")
    n = struct.unpack("<I", n_data)[0]
    _validate_sample_count(n, expected_samples=expected_samples, max_samples=max_samples)
    raw = ser.read(n * 2)
    if len(raw) < n * 2:
        raise TimeoutError("샘플 수신 중 timeout.")
    return np.frombuffer(raw, dtype=np.int16).copy()


def q15_to_float(samples_q15: npt.ArrayLike) -> npt.NDArray[np.float64]:
    """Convert signed Q1.15 samples to normalized float64.
    부호 있는 Q1.15 샘플을 정규화된 float64로 변환합니다.
    """
    return np.asarray(samples_q15, dtype=np.int16).astype(np.float64) / Q15_SCALE


def uart_recv_result(
    ser,
    *,
    expected_samples: int | None = None,
    max_samples: int | None = None,
) -> npt.NDArray[np.float64]:
    """Receive board output and return normalized float samples.
    보드 출력을 수신해 정규화된 float 샘플로 반환합니다.
    """

    return q15_to_float(
        uart_recv_result_q15(
            ser,
            expected_samples=expected_samples,
            max_samples=max_samples,
        )
    )


def capture_output_q15(
    port: str,
    baud: int,
    timeout: float,
    freqs_hz: Sequence[float],
    *,
    expected_samples: int | None = None,
    max_samples: int | None = None,
) -> npt.NDArray[np.int16]:
    """Open UART, send tones, and capture raw Q1.15 output.
    UART를 열고 톤 명령을 보낸 뒤 원시 Q1.15 출력을 캡처합니다.
    """
    ser = uart_open(port, baud, timeout)
    try:
        uart_send_cmd(ser, freqs_hz)
        return uart_recv_result_q15(
            ser,
            expected_samples=expected_samples,
            max_samples=max_samples,
        )
    finally:
        ser.close()


def capture_output_float(
    port: str,
    baud: int,
    timeout: float,
    freqs_hz: Sequence[float],
    *,
    expected_samples: int | None = None,
    max_samples: int | None = None,
) -> npt.NDArray[np.float64]:
    """Capture board output and return normalized float samples.
    보드 출력을 캡처해 정규화된 float 샘플로 반환합니다.
    """
    return q15_to_float(
        capture_output_q15(
            port,
            baud,
            timeout,
            freqs_hz,
            expected_samples=expected_samples,
            max_samples=max_samples,
        )
    )
