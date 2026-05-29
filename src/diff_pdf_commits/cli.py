from __future__ import annotations

from pathlib import Path
import sys

import click

from .config import DiffConfig, parse_env_option, safe_label, validate_repo_relative_path
from .errors import DiffPdfCommitsError
from .file_config import FileConfig, load_file_config
from .git import git_root
from .runner import DiffRunner


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("left_ref")
@click.argument("right_ref")
@click.option("--build", "build_command", default=None, help="Shell command that builds the PDF in each worktree.")
@click.option(
    "--pdf", "pdf_path", default=None, type=click.Path(path_type=Path), help="PDF path relative to repo root."
)
@click.option("--repo", type=click.Path(path_type=Path), default=Path.cwd(), help="Path inside the git repository.")
@click.option("--out", "output_dir", type=click.Path(path_type=Path), default=None, help="Output directory.")
@click.option(
    "--diff-output", type=click.Path(path_type=Path), default=None, help="Write visual diff PDF to this path."
)
@click.option("--config", "config_path", type=click.Path(path_type=Path), default=None, help="Load options from TOML.")
@click.option("--view/--no-view", default=None, help="Open diff-pdf GUI viewer.")
@click.option("--no-diff", is_flag=True, default=None, help="Only build and export both PDFs; do not run diff-pdf.")
@click.option("--keep-worktrees", is_flag=True, default=None, help="Keep temporary git worktrees for debugging.")
@click.option("--dirty", type=click.Choice(["fail", "allow"]), default=None)
@click.option(
    "--env",
    "env_options",
    multiple=True,
    metavar="KEY=VALUE",
    help="Environment variable passed to the build command. Can be used more than once.",
)
@click.option(
    "--copy",
    "copy_paths",
    multiple=True,
    type=click.Path(path_type=Path),
    metavar="PATH",
    help="Copy a local file or directory into each worktree before building. Path is relative to repo root.",
)
def main(
    left_ref: str,
    right_ref: str,
    build_command: str | None,
    pdf_path: Path | None,
    repo: Path,
    output_dir: Path | None,
    diff_output: Path | None,
    config_path: Path | None,
    view: bool | None,
    no_diff: bool | None,
    keep_worktrees: bool | None,
    dirty: str | None,
    env_options: tuple[str, ...],
    copy_paths: tuple[Path, ...],
) -> None:
    """Build PDF from LEFT_REF and RIGHT_REF, then compare them with diff-pdf."""
    try:
        repo_root = git_root(repo.resolve())
        build_env: dict[str, str] = {}
        for env_option in env_options:
            try:
                key, value = parse_env_option(env_option)
            except ValueError as error:
                raise DiffPdfCommitsError(f"Invalid --env {env_option!r}: {error}") from error
            build_env[key] = value

        file_config = FileConfig()
        if config_path is not None:
            file_config = load_file_config(config_path, repo_root=repo_root, cli_env=build_env)

        build_command = build_command or file_config.build_command
        if build_command is None:
            raise DiffPdfCommitsError("Missing --build. Provide it on the command line or in --config.")

        pdf_path = pdf_path or file_config.pdf_path
        if pdf_path is None:
            raise DiffPdfCommitsError("Missing --pdf. Provide it on the command line or in --config.")
        try:
            pdf_path = validate_repo_relative_path(pdf_path)
        except ValueError as error:
            raise DiffPdfCommitsError(f"Invalid --pdf {str(pdf_path)!r}: {error}") from error

        merged_env = dict(file_config.build_env)
        merged_env.update(build_env)

        validated_copy_paths: list[Path] = []
        for copy_path in file_config.copy_paths:
            validated_copy_paths.append(copy_path)
        for copy_path in copy_paths:
            try:
                validated_copy_paths.append(validate_repo_relative_path(copy_path))
            except ValueError as error:
                raise DiffPdfCommitsError(f"Invalid --copy {str(copy_path)!r}: {error}") from error

        output_dir = output_dir or file_config.output_dir or Path(".pdf-diff")
        diff_output = diff_output or file_config.diff_output
        view = view if view is not None else (file_config.view if file_config.view is not None else False)
        no_diff = (
            no_diff if no_diff is not None else (file_config.no_diff if file_config.no_diff is not None else False)
        )
        keep_worktrees = (
            keep_worktrees
            if keep_worktrees is not None
            else (file_config.keep_worktrees if file_config.keep_worktrees is not None else False)
        )
        dirty = dirty or file_config.dirty or "fail"

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
            build_env=merged_env,
            copy_paths=tuple(validated_copy_paths),
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
