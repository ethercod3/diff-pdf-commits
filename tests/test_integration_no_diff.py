from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

from click.testing import CliRunner
import pytest

from diff_pdf_commits.cli import main


def git(repo: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stderr or result.stdout


def write_build_script(repo: Path, content: bytes) -> None:
    (repo / "build.py").write_text(
        "\n".join(
            [
                "from pathlib import Path",
                f"Path('artifact.pdf').write_bytes({content!r})",
                "",
            ]
        ),
        encoding="utf-8",
    )


def commit(repo: Path, message: str) -> None:
    git(repo, "add", ".")
    git(repo, "commit", "-m", message)


def test_no_diff_exports_built_pdfs_from_both_refs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "test@example.invalid")
    git(repo, "config", "user.name", "Test User")

    write_build_script(repo, b"%PDF-1.4\nleft\n%%EOF\n")
    commit(repo, "left")
    write_build_script(repo, b"%PDF-1.4\nright\n%%EOF\n")
    commit(repo, "right")

    output_dir = tmp_path / "out"
    build_command = f'"{sys.executable}" build.py'
    result = CliRunner().invoke(
        main,
        [
            "HEAD~1",
            "HEAD",
            "--repo",
            str(repo),
            "--build",
            build_command,
            "--pdf",
            "artifact.pdf",
            "--out",
            str(output_dir),
            "--no-diff",
        ],
    )

    assert result.exit_code == 0, result.output
    pdfs_dir = output_dir / "HEAD_1__HEAD" / "pdfs"
    assert (pdfs_dir / "left-HEAD_1-artifact.pdf").read_bytes() == b"%PDF-1.4\nleft\n%%EOF\n"
    assert (pdfs_dir / "right-HEAD-artifact.pdf").read_bytes() == b"%PDF-1.4\nright\n%%EOF\n"


def docker_is_available() -> bool:
    try:
        result = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return False
    return result.returncode == 0


def diff_pdf_is_available() -> bool:
    return shutil.which("diff-pdf") is not None


def build_docker_test_image() -> str:
    image_tag = f"diff-pdf-commits-test-groff:{uuid.uuid4().hex}"
    fixture_dir = Path(__file__).parent / "fixtures" / "docker-groff-pdf"
    result = subprocess.run(
        ["docker", "build", "-t", image_tag, str(fixture_dir)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        pytest.skip(f"Could not build Docker test image: {result.stderr or result.stdout}")
    return image_tag


def write_groff_document(repo: Path, title: str, body: str) -> None:
    (repo / "document.ms").write_text(
        "\n".join(
            [
                ".TL",
                title,
                ".AU",
                "diff-pdf-commits test",
                ".PP",
                body,
                "",
            ]
        ),
        encoding="utf-8",
    )


def docker_build_command(image_tag: str) -> str:
    if os.name == "nt":
        mount = r"%CD%:/work"
    else:
        mount = "$PWD:/work"
    return f'docker run --rm -v "{mount}" -w /work {image_tag} document.ms artifact.pdf'


@pytest.mark.skipif(not docker_is_available(), reason="Docker daemon is not available")
def test_no_diff_can_build_pdf_with_minimal_alpine_docker_image(tmp_path: Path) -> None:
    image_tag = build_docker_test_image()
    repo = tmp_path / "repo"
    output_dir = tmp_path / "out"
    try:
        repo.mkdir()
        git(repo, "init")
        git(repo, "config", "user.email", "test@example.invalid")
        git(repo, "config", "user.name", "Test User")

        write_groff_document(repo, "Left PDF", "Generated from the left revision.")
        commit(repo, "left")
        write_groff_document(repo, "Right PDF", "Generated from the right revision.")
        commit(repo, "right")

        result = CliRunner().invoke(
            main,
            [
                "HEAD~1",
                "HEAD",
                "--repo",
                str(repo),
                "--build",
                docker_build_command(image_tag),
                "--pdf",
                "artifact.pdf",
                "--out",
                str(output_dir),
                "--no-diff",
            ],
        )

        assert result.exit_code == 0, result.output
        pdfs_dir = output_dir / "HEAD_1__HEAD" / "pdfs"
        left_pdf = pdfs_dir / "left-HEAD_1-artifact.pdf"
        right_pdf = pdfs_dir / "right-HEAD-artifact.pdf"
        assert left_pdf.read_bytes().startswith(b"%PDF")
        assert right_pdf.read_bytes().startswith(b"%PDF")
        assert left_pdf.stat().st_size > 1000
        assert right_pdf.stat().st_size > 1000
    finally:
        subprocess.run(["docker", "image", "rm", "-f", image_tag], check=False, capture_output=True)


@pytest.mark.skipif(not docker_is_available(), reason="Docker daemon is not available")
@pytest.mark.skipif(not diff_pdf_is_available(), reason="diff-pdf is not available")
def test_e2e_builds_two_commits_and_writes_visual_diff_with_docker(tmp_path: Path) -> None:
    image_tag = build_docker_test_image()
    repo = tmp_path / "repo"
    output_dir = tmp_path / "out"
    diff_output = output_dir / "visual-diff.pdf"
    try:
        repo.mkdir()
        git(repo, "init")
        git(repo, "config", "user.email", "test@example.invalid")
        git(repo, "config", "user.name", "Test User")

        write_groff_document(
            repo,
            "Left Revision",
            "This paragraph only appears in the left revision.",
        )
        commit(repo, "left")
        write_groff_document(
            repo,
            "Right Revision",
            "This paragraph is intentionally different in the right revision.",
        )
        commit(repo, "right")

        result = CliRunner().invoke(
            main,
            [
                "HEAD~1",
                "HEAD",
                "--repo",
                str(repo),
                "--build",
                docker_build_command(image_tag),
                "--pdf",
                "artifact.pdf",
                "--out",
                str(output_dir),
                "--diff-output",
                str(diff_output),
            ],
        )

        assert result.exit_code == 1, result.output
        assert diff_output.read_bytes().startswith(b"%PDF")
        assert diff_output.stat().st_size > 1000
        pdfs_dir = output_dir / "HEAD_1__HEAD" / "pdfs"
        assert (pdfs_dir / "left-HEAD_1-artifact.pdf").is_file()
        assert (pdfs_dir / "right-HEAD-artifact.pdf").is_file()
    finally:
        subprocess.run(["docker", "image", "rm", "-f", image_tag], check=False, capture_output=True)
