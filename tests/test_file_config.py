from __future__ import annotations

from pathlib import Path

from diff_pdf_commits.file_config import load_file_config


def test_load_file_config_resolves_env_file_and_target_pdf(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".env").write_text(
        "\n".join(
            [
                'TARGET="report.tex"',
                'VAULT_OS_PATH="../vault"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    config_path = repo / "diff_config.toml"
    config_path.write_text(
        "\n".join(
            [
                "[diff_pdf]",
                'build = "task pdf"',
                'env_file = ".env"',
                "pdf_from_target = true",
                "view = true",
                "",
                "[diff_pdf.env]",
                'PYTHONUTF8 = "1"',
                'TARGET = { from_env = "TARGET" }',
                'VAULT_OS_PATH = { from_env = "VAULT_OS_PATH", resolve = true }',
                "",
                "[diff_pdf.copy]",
                'paths = [".env", "docker-compose.yaml"]',
                "",
            ]
        ),
        encoding="utf-8",
    )

    config = load_file_config(config_path, repo_root=repo, cli_env={})

    assert config.build_command == "task pdf"
    assert config.pdf_path == Path("report.pdf")
    assert config.view is True
    assert config.build_env["PYTHONUTF8"] == "1"
    assert config.build_env["TARGET"] == "report.tex"
    assert config.build_env["VAULT_OS_PATH"] == str((tmp_path / "vault").resolve())
    assert config.copy_paths == (Path(".env"), Path("docker-compose.yaml"))


def test_cli_env_overrides_env_file_for_config_values(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".env").write_text('TARGET="main.tex"\n', encoding="utf-8")
    config_path = repo / "diff_config.toml"
    config_path.write_text(
        "\n".join(
            [
                "[diff_pdf]",
                'build = "task pdf"',
                'env_file = ".env"',
                "pdf_from_target = true",
                "",
                "[diff_pdf.env]",
                'TARGET = { from_env = "TARGET" }',
                "",
            ]
        ),
        encoding="utf-8",
    )

    config = load_file_config(config_path, repo_root=repo, cli_env={"TARGET": "diff.tex"})

    assert config.pdf_path == Path("diff.pdf")
    assert config.build_env["TARGET"] == "diff.tex"
