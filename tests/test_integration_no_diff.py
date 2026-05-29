from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

from click.testing import CliRunner, Result
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


def init_repo(repo: Path) -> None:
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "test@example.invalid")
    git(repo, "config", "user.name", "Test User")


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


def make_two_revision_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    init_repo(repo)
    write_build_script(repo, b"%PDF-1.4\nleft\n%%EOF\n")
    commit(repo, "left")
    write_build_script(repo, b"%PDF-1.4\nright\n%%EOF\n")
    commit(repo, "right")
    return repo


def run_no_diff(repo: Path, output_dir: Path, *extra_args: str, pdf_path: str = "artifact.pdf") -> Result:
    build_command = f'"{sys.executable}" build.py'
    return CliRunner().invoke(
        main,
        [
            "HEAD~1",
            "HEAD",
            "--repo",
            str(repo),
            "--build",
            build_command,
            "--pdf",
            pdf_path,
            "--out",
            str(output_dir),
            "--no-diff",
            *extra_args,
        ],
    )


def test_no_diff_exports_built_pdfs_from_both_refs(tmp_path: Path) -> None:
    repo = make_two_revision_repo(tmp_path)

    output_dir = tmp_path / "out"
    result = run_no_diff(repo, output_dir)

    assert result.exit_code == 0, result.output
    pdfs_dir = output_dir / "HEAD_1__HEAD" / "pdfs"
    assert (pdfs_dir / "left-HEAD_1-artifact.pdf").read_bytes() == b"%PDF-1.4\nleft\n%%EOF\n"
    assert (pdfs_dir / "right-HEAD-artifact.pdf").read_bytes() == b"%PDF-1.4\nright\n%%EOF\n"


def test_rejects_parent_relative_pdf_path(tmp_path: Path) -> None:
    repo = make_two_revision_repo(tmp_path)

    result = run_no_diff(repo, tmp_path / "out", pdf_path="../artifact.pdf")

    assert result.exit_code == 2
    assert "Invalid --pdf" in result.output


def test_dirty_worktree_fails_by_default(tmp_path: Path) -> None:
    repo = make_two_revision_repo(tmp_path)
    (repo / "untracked.txt").write_text("dirty\n", encoding="utf-8")

    result = run_no_diff(repo, tmp_path / "out")

    assert result.exit_code == 2
    assert "uncommitted changes" in result.output


def test_dirty_allow_builds_despite_uncommitted_changes(tmp_path: Path) -> None:
    repo = make_two_revision_repo(tmp_path)
    (repo / "untracked.txt").write_text("dirty\n", encoding="utf-8")

    output_dir = tmp_path / "out"
    result = run_no_diff(repo, output_dir, "--dirty", "allow")

    assert result.exit_code == 0, result.output
    assert (output_dir / "HEAD_1__HEAD" / "pdfs" / "left-HEAD_1-artifact.pdf").is_file()


def test_removes_worktrees_after_success_by_default(tmp_path: Path) -> None:
    repo = make_two_revision_repo(tmp_path)
    output_dir = tmp_path / "out"

    result = run_no_diff(repo, output_dir)

    assert result.exit_code == 0, result.output
    worktrees_dir = output_dir / "HEAD_1__HEAD" / "worktrees"
    assert not (worktrees_dir / "left").exists()
    assert not (worktrees_dir / "right").exists()


def test_keep_worktrees_preserves_debug_worktrees(tmp_path: Path) -> None:
    repo = make_two_revision_repo(tmp_path)
    output_dir = tmp_path / "out"

    result = run_no_diff(repo, output_dir, "--keep-worktrees")

    assert result.exit_code == 0, result.output
    worktrees_dir = output_dir / "HEAD_1__HEAD" / "worktrees"
    assert (worktrees_dir / "left" / "build.py").is_file()
    assert (worktrees_dir / "right" / "build.py").is_file()


def test_no_diff_passes_env_to_build_command(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo(repo)

    (repo / "build.py").write_text(
        "\n".join(
            [
                "import os",
                "from pathlib import Path",
                "payload = os.environ['PDF_TEST_PAYLOAD'].encode('utf-8')",
                "Path('artifact.pdf').write_bytes(b'%PDF-1.4\\n' + payload + b'\\n%%EOF\\n')",
                "",
            ]
        ),
        encoding="utf-8",
    )
    commit(repo, "left")
    (repo / "marker.txt").write_text("right\n", encoding="utf-8")
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
            "--env",
            "PDF_TEST_PAYLOAD=from-env",
        ],
    )

    assert result.exit_code == 0, result.output
    pdfs_dir = output_dir / "HEAD_1__HEAD" / "pdfs"
    assert (pdfs_dir / "left-HEAD_1-artifact.pdf").read_bytes() == b"%PDF-1.4\nfrom-env\n%%EOF\n"
    assert (pdfs_dir / "right-HEAD-artifact.pdf").read_bytes() == b"%PDF-1.4\nfrom-env\n%%EOF\n"
    assert "PDF_TEST_PAYLOAD=from-env" in (output_dir / "HEAD_1__HEAD" / "logs" / "build-left.log").read_text(
        encoding="utf-8"
    )


def test_no_diff_copies_local_file_into_each_worktree_before_build(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo(repo)

    (repo / ".gitignore").write_text(".env\n", encoding="utf-8")
    (repo / ".env").write_text("payload=from-dotenv\n", encoding="utf-8")
    (repo / "build.py").write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "payload = Path('.env').read_text(encoding='utf-8').strip().split('=', 1)[1]",
                "Path('artifact.pdf').write_bytes(b'%PDF-1.4\\n' + payload.encode('utf-8') + b'\\n%%EOF\\n')",
                "",
            ]
        ),
        encoding="utf-8",
    )
    commit(repo, "left")
    (repo / "marker.txt").write_text("right\n", encoding="utf-8")
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
            "--copy",
            ".env",
        ],
    )

    assert result.exit_code == 0, result.output
    pdfs_dir = output_dir / "HEAD_1__HEAD" / "pdfs"
    assert (pdfs_dir / "left-HEAD_1-artifact.pdf").read_bytes() == b"%PDF-1.4\nfrom-dotenv\n%%EOF\n"
    assert (pdfs_dir / "right-HEAD-artifact.pdf").read_bytes() == b"%PDF-1.4\nfrom-dotenv\n%%EOF\n"


def docker_is_available() -> bool:
    if os.environ.get("DIFF_PDF_COMMITS_RUN_DOCKER_TESTS") != "1":
        return False
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


@pytest.mark.skipif(
    not docker_is_available(),
    reason="Docker integration tests require DIFF_PDF_COMMITS_RUN_DOCKER_TESTS=1 and Docker",
)
def test_no_diff_can_build_pdf_with_minimal_alpine_docker_image(tmp_path: Path) -> None:
    image_tag = build_docker_test_image()
    repo = tmp_path / "repo"
    output_dir = tmp_path / "out"
    try:
        init_repo(repo)

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


@pytest.mark.skipif(
    not docker_is_available(),
    reason="Docker integration tests require DIFF_PDF_COMMITS_RUN_DOCKER_TESTS=1 and Docker",
)
@pytest.mark.skipif(not diff_pdf_is_available(), reason="diff-pdf is not available")
def test_e2e_builds_two_commits_and_writes_visual_diff_with_docker(tmp_path: Path) -> None:
    image_tag = build_docker_test_image()
    repo = tmp_path / "repo"
    output_dir = tmp_path / "out"
    diff_output = output_dir / "visual-diff.pdf"
    try:
        init_repo(repo)

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
