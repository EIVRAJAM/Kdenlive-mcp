from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    available: bool
    returncode: int | None
    stdout: str
    stderr: str
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "command": self.command,
            "available": self.available,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error": self.error,
        }


def binary_exists(name: str) -> bool:
    return shutil.which(name) is not None


def run_command(command: list[str], timeout: float = 10.0) -> CommandResult:
    executable = command[0]
    if not binary_exists(executable):
        return CommandResult(
            command=command,
            available=False,
            returncode=None,
            stdout="",
            stderr="",
            error=f"Executable not found: {executable}",
        )

    try:
        completed = subprocess.run(
            command,
            shell=False,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command=command,
            available=True,
            returncode=None,
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
            error=f"Command timed out after {timeout} seconds",
        )

    return CommandResult(
        command=command,
        available=True,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        error=None if completed.returncode == 0 else "Command failed",
    )
