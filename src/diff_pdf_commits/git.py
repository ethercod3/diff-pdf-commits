from __future__ import annotations

from pathlib import Path
import shutil

from .errors import DiffPdfCommitsError
from .process import run_command


def git_root(cwd: Path) -> Path:
    result = run_command(["git", "rev-parse", "--show-toplevel"], cwd=cwd)
    return Path(result.stdout.strip()).resolve()


def require_clean_worktree(repo: Path) -> None:
    result = run_command(["git", "status", "--porcelain"], cwd=repo)
    if result.stdout.strip():
        raise DiffPdfCommitsError(
            "The git worktree has uncommitted changes. Commit/stash them, or pass --dirty allow."
        )


def resolve_commit(repo: Path, ref: str) -> str:
    result = run_command(["git", "rev-parse", "--verify", ref], cwd=repo)
    return result.stdout.strip()


def add_worktree(repo: Path, path: Path, ref: str) -> None:
    if path.exists():
        shutil.rmtree(path)
    run_command(["git", "worktree", "add", "--detach", str(path), ref], cwd=repo)


def remove_worktree(repo: Path, path: Path) -> None:
    if not path.exists():
        return
    result = run_command(["git", "worktree", "remove", "--force", str(path)], cwd=repo, check=False)
    if result.returncode != 0 and path.exists():
        shutil.rmtree(path)
    run_command(["git", "worktree", "prune"], cwd=repo, check=False)
