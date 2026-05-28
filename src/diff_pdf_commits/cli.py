from __future__ import annotations

from pathlib import Path
import sys

import click

from .config import DiffConfig, safe_label
from .errors import DiffPdfCommitsError
from .git import git_root
from .runner import DiffRunner


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("left_ref")
@click.argument("right_ref")
@click.option("--build", "build_command", required=True, help="Shell command that builds the PDF in each worktree.")
@click.option("--pdf", "pdf_path", required=True, type=click.Path(path_type=Path), help="PDF path relative to repo root.")
@click.option("--repo", type=click.Path(path_type=Path), default=Path.cwd(), help="Path inside the git repository.")
@click.option("--out", "output_dir", type=click.Path(path_type=Path), default=Path(".pdf-diff"), help="Output directory.")
@click.option("--diff-output", type=click.Path(path_type=Path), default=None, help="Write visual diff PDF to this path.")
@click.option("--view/--no-view", default=False, help="Open diff-pdf GUI viewer.")
@click.option("--no-diff", is_flag=True, help="Only build and export both PDFs; do not run diff-pdf.")
@click.option("--keep-worktrees", is_flag=True, help="Keep temporary git worktrees for debugging.")
@click.option("--dirty", type=click.Choice(["fail", "allow"]), default="fail", show_default=True)
def main(
    left_ref: str,
    right_ref: str,
    build_command: str,
    pdf_path: Path,
    repo: Path,
    output_dir: Path,
    diff_output: Path | None,
    view: bool,
    no_diff: bool,
    keep_worktrees: bool,
    dirty: str,
) -> None:
    """Build PDF from LEFT_REF and RIGHT_REF, then compare them with diff-pdf."""
    try:
        repo_root = git_root(repo.resolve())
        if not output_dir.is_absolute():
            output_dir = repo_root / output_dir
        if diff_output is None and not view and not no_diff:
            diff_output = output_dir / f"{Path(pdf_path).stem}_diff_{safe_label(left_ref)}__{safe_label(right_ref)}.pdf"
        elif diff_output is not None and not diff_output.is_absolute():
            diff_output = repo_root / diff_output

        config = DiffConfig(
            repo=repo_root,
            left_ref=left_ref,
            right_ref=right_ref,
            build_command=build_command,
            pdf_path=pdf_path,
            output_dir=output_dir,
            diff_output=diff_output,
            view=view,
            no_diff=no_diff,
            keep_worktrees=keep_worktrees,
            dirty=dirty,
        )
        raise SystemExit(DiffRunner(config).run())
    except DiffPdfCommitsError as error:
        click.echo(f"error: {error}", err=True)
        raise SystemExit(2) from error
    except KeyboardInterrupt:
        click.echo("Interrupted.", err=True)
        raise SystemExit(130)


if __name__ == "__main__":
    sys.exit(main())
