from __future__ import annotations

from pathlib import Path
import shutil

from rich.console import Console
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn, TimeElapsedColumn
from rich.text import Text

from .config import DiffConfig, safe_label
from .errors import DiffPdfCommitsError
from .git import add_worktree, remove_worktree, require_clean_worktree, resolve_commit
from .process import run_command, run_shell


class DiffRunner:
    def __init__(self, config: DiffConfig) -> None:
        self.config = config
        self.console = Console()

    def run(self) -> int:
        cfg = self.config
        total_steps = 8 if not cfg.no_diff else 7
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console,
        ) as progress:
            task_id = progress.add_task("Preparing", total=total_steps)
            return self.run_with_progress(progress, task_id, total_steps)

    def run_with_progress(self, progress: Progress, task_id: int, total_steps: int) -> int:
        cfg = self.config
        if cfg.dirty == "fail":
            progress.update(task_id, description="Checking worktree")
            require_clean_worktree(cfg.repo)
        progress.advance(task_id)

        progress.update(task_id, description="Resolving refs")
        left_sha = resolve_commit(cfg.repo, cfg.left_ref)
        right_sha = resolve_commit(cfg.repo, cfg.right_ref)
        cfg.run_dir.mkdir(parents=True, exist_ok=True)
        cfg.pdfs_dir.mkdir(parents=True, exist_ok=True)
        progress.advance(task_id)

        left_tree = cfg.worktrees_dir / "left"
        right_tree = cfg.worktrees_dir / "right"

        try:
            progress.update(task_id, description=f"Creating worktree: {cfg.left_ref}")
            add_worktree(cfg.repo, left_tree, left_sha)
            progress.advance(task_id)

            progress.update(task_id, description=f"Creating worktree: {cfg.right_ref}")
            add_worktree(cfg.repo, right_tree, right_sha)
            progress.advance(task_id)

            self.copy_local_paths(left_tree)
            self.copy_local_paths(right_tree)
            progress.advance(task_id)

            progress.update(task_id, description=f"Building PDF: {cfg.left_ref}")
            left_pdf = self.build_one("left", cfg.left_ref, left_tree)
            progress.advance(task_id)

            progress.update(task_id, description=f"Building PDF: {cfg.right_ref}")
            right_pdf = self.build_one("right", cfg.right_ref, right_tree)
            progress.advance(task_id)

            if cfg.no_diff:
                self.console.print(f"PDFs saved in: {cfg.pdfs_dir}")
                progress.update(task_id, description="Done")
                return 0

            progress.update(task_id, description="Running diff-pdf")
            return self.diff(left_pdf, right_pdf)
        finally:
            if not cfg.keep_worktrees:
                progress.update(task_id, description="Cleaning worktrees")
                remove_worktree(cfg.repo, left_tree)
                remove_worktree(cfg.repo, right_tree)
            progress.update(task_id, completed=total_steps, description="Done")

    def copy_local_paths(self, worktree: Path) -> None:
        cfg = self.config
        for relative_path in cfg.copy_paths:
            source = cfg.repo / relative_path
            destination = worktree / relative_path
            if not source.exists():
                raise DiffPdfCommitsError(f"Cannot copy missing path into worktree: {source}")
            if source.is_dir():
                if destination.exists():
                    shutil.rmtree(destination)
                shutil.copytree(source, destination)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            self.console.print(f"Copied into worktree: {relative_path}")

    def build_one(self, side: str, ref: str, worktree: Path) -> Path:
        cfg = self.config
        run_shell(
            cfg.build_command,
            cwd=worktree,
            log_path=cfg.logs_dir / f"build-{side}.log",
            extra_env=cfg.build_env,
            live_output=lambda stream_name, text: self.print_build_output(side, stream_name, text),
        )
        source_pdf = worktree / cfg.pdf_path
        if not source_pdf.is_file():
            raise DiffPdfCommitsError(f"Build for {ref} did not create expected PDF: {source_pdf}")
        destination = cfg.pdfs_dir / f"{side}-{safe_label(ref)}-{cfg.pdf_path.name}"
        shutil.copy2(source_pdf, destination)
        self.console.print(f"Saved {side} PDF: {destination}")
        return destination

    def print_build_output(self, side: str, stream_name: str, text: str) -> None:
        prefix = Text(f"[{side} {stream_name}] ", style="cyan" if stream_name == "stdout" else "yellow")
        for line in text.splitlines() or [""]:
            self.console.print(prefix + Text(line))

    def diff(self, left_pdf: Path, right_pdf: Path) -> int:
        cfg = self.config
        returncode = 0
        if cfg.diff_output is not None:
            cfg.diff_output.parent.mkdir(parents=True, exist_ok=True)
            result = run_command(
                ["diff-pdf", f"--output-diff={cfg.diff_output}", str(left_pdf), str(right_pdf)],
                cwd=cfg.repo,
                check=False,
            )
            returncode = max(returncode, result.returncode)
            if result.returncode == 0:
                self.console.print(f"No visual differences. Diff output path: {cfg.diff_output}")
            elif result.returncode == 1:
                self.console.print(f"Visual diff saved: {cfg.diff_output}")
            else:
                raise DiffPdfCommitsError(result.stderr.strip() or result.stdout.strip() or "diff-pdf failed")
        if cfg.view:
            result = run_command(["diff-pdf", "--view", str(left_pdf), str(right_pdf)], cwd=cfg.repo, check=False)
            returncode = max(returncode, result.returncode)
            if result.returncode not in {0, 1}:
                raise DiffPdfCommitsError(result.stderr.strip() or result.stdout.strip() or "diff-pdf --view failed")
        return returncode
