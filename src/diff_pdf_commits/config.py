from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def safe_label(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value)


@dataclass(frozen=True)
class DiffConfig:
    repo: Path
    left_ref: str
    right_ref: str
    build_command: str
    pdf_path: Path
    output_dir: Path
    diff_output: Path | None
    view: bool
    no_diff: bool
    keep_worktrees: bool
    dirty: str

    @property
    def run_dir(self) -> Path:
        return self.output_dir / f"{safe_label(self.left_ref)}__{safe_label(self.right_ref)}"

    @property
    def worktrees_dir(self) -> Path:
        return self.run_dir / "worktrees"

    @property
    def logs_dir(self) -> Path:
        return self.run_dir / "logs"

    @property
    def pdfs_dir(self) -> Path:
        return self.run_dir / "pdfs"
