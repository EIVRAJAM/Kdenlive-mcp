from __future__ import annotations

from pathlib import Path

from kdenlive_mcp.adapters.commands import CommandResult, run_command


def generate_thumbnail(input_path: Path, output_path: Path, timestamp: float = 1.0) -> CommandResult:
    return run_command(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            str(input_path),
            "-frames:v",
            "1",
            "-update",
            "1",
            str(output_path),
        ],
        timeout=60.0,
    )


def extract_audio(input_path: Path, output_path: Path) -> CommandResult:
    return run_command(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "48000",
            str(output_path),
        ],
        timeout=300.0,
    )


def detect_silence(input_path: Path, threshold_db: float = -35.0, minimum_duration: float = 0.8) -> CommandResult:
    return run_command(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(input_path),
            "-af",
            f"silencedetect=noise={threshold_db}dB:d={minimum_duration}",
            "-f",
            "null",
            "-",
        ],
        timeout=300.0,
    )
