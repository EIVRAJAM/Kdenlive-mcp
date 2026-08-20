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


def extract_frames(
    input_path: Path,
    output_pattern: Path,
    every_seconds: float = 1.0,
    max_frames: int = 12,
) -> CommandResult:
    fps = 1 / every_seconds
    return run_command(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-i",
            str(input_path),
            "-vf",
            f"fps={fps:.6f}",
            "-frames:v",
            str(max_frames),
            "-q:v",
            "2",
            str(output_pattern),
        ],
        timeout=300.0,
    )


def generate_contact_sheet(
    input_path: Path,
    output_path: Path,
    every_seconds: float = 1.0,
    columns: int = 3,
    rows: int = 3,
    thumb_width: int = 320,
) -> CommandResult:
    fps = 1 / every_seconds
    return run_command(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-i",
            str(input_path),
            "-vf",
            f"fps={fps:.6f},scale={thumb_width}:-1,tile={columns}x{rows}",
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(output_path),
        ],
        timeout=300.0,
    )


def detect_black_frames(
    input_path: Path,
    minimum_duration: float = 0.5,
    picture_black_ratio: float = 0.98,
    pixel_black_threshold: float = 0.1,
) -> CommandResult:
    return run_command(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(input_path),
            "-vf",
            (
                f"blackdetect=d={minimum_duration}:"
                f"pic_th={picture_black_ratio}:"
                f"pix_th={pixel_black_threshold}"
            ),
            "-an",
            "-f",
            "null",
            "-",
        ],
        timeout=300.0,
    )
