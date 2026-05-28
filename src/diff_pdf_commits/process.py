from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from .errors import DiffPdfCommitsError


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def decode_output(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def run_command(command: list[str], *, cwd: Path | None = None, check: bool = True) -> CommandResult:
    result = subprocess.run(command, cwd=cwd, check=False, capture_output=True)
    completed = CommandResult(result.returncode, decode_output(result.stdout), decode_output(result.stderr))
    if check and completed.returncode != 0:
        details = completed.stderr.strip() or completed.stdout.strip() or "no output"
        raise DiffPdfCommitsError(f"Command failed ({completed.returncode}): {' '.join(command)}\n{details}")
    return completed


def run_shell(command: str, *, cwd: Path, log_path: Path) -> CommandResult:
    result = subprocess.run(command, cwd=cwd, shell=True, check=False, capture_output=True)
    completed = CommandResult(result.returncode, decode_output(result.stdout), decode_output(result.stderr))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        f"$ {command}\n\n[stdout]\n{completed.stdout}\n\n[stderr]\n{completed.stderr}\n",
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise DiffPdfCommitsError(f"Build command failed ({completed.returncode}) in {cwd}. See log: {log_path}")
    return completed
