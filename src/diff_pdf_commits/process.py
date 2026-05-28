from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
from threading import Thread
from collections.abc import Callable

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


def run_shell(
    command: str,
    *,
    cwd: Path,
    log_path: Path,
    extra_env: dict[str, str] | None = None,
    live_output: Callable[[str, str], None] | None = None,
) -> CommandResult:
    env = None
    if extra_env:
        env = os.environ.copy()
        env.update(extra_env)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    env_lines = "".join(f"{key}={value}\n" for key, value in sorted((extra_env or {}).items()))
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []

    process = subprocess.Popen(
        command,
        cwd=cwd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    with log_path.open("w", encoding="utf-8", errors="replace") as log_file:
        log_file.write(f"$ {command}\n\n[env]\n{env_lines}\n[output]\n")
        log_file.flush()

        def read_stream(stream: object, name: str, parts: list[str]) -> None:
            assert stream is not None
            while True:
                chunk = stream.readline()
                if not chunk:
                    break
                text = decode_output(chunk)
                parts.append(text)
                log_file.write(f"[{name}] {text}")
                log_file.flush()
                if live_output is not None:
                    live_output(name, text)

        stdout_thread = Thread(target=read_stream, args=(process.stdout, "stdout", stdout_parts), daemon=True)
        stderr_thread = Thread(target=read_stream, args=(process.stderr, "stderr", stderr_parts), daemon=True)
        stdout_thread.start()
        stderr_thread.start()
        returncode = process.wait()
        stdout_thread.join()
        stderr_thread.join()

    completed = CommandResult(returncode, "".join(stdout_parts), "".join(stderr_parts))
    if completed.returncode != 0:
        raise DiffPdfCommitsError(f"Build command failed ({completed.returncode}) in {cwd}. See log: {log_path}")
    return completed
