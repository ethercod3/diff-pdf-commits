from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - covered on Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

from .config import validate_repo_relative_path
from .errors import DiffPdfCommitsError


@dataclass(frozen=True)
class FileConfig:
    build_command: str | None = None
    pdf_path: Path | None = None
    output_dir: Path | None = None
    diff_output: Path | None = None
    view: bool | None = None
    no_diff: bool | None = None
    keep_worktrees: bool | None = None
    dirty: str | None = None
    build_env: dict[str, str] = field(default_factory=dict)
    copy_paths: tuple[Path, ...] = ()


def load_file_config(path: Path, *, repo_root: Path, cli_env: dict[str, str]) -> FileConfig:
    config_path = path if path.is_absolute() else repo_root / path
    if not config_path.is_file():
        raise DiffPdfCommitsError(f"Config file not found: {config_path}")

    try:
        with config_path.open("rb") as config_file:
            data = tomllib.load(config_file)
    except tomllib.TOMLDecodeError as error:
        raise DiffPdfCommitsError(f"Invalid TOML config {config_path}: {error}") from error
    section = data.get("diff_pdf", data)
    if not isinstance(section, dict):
        raise DiffPdfCommitsError("Config must contain a [diff_pdf] table or top-level options.")

    config_dir = config_path.parent
    file_env = read_env_file(section.get("env_file"), config_dir=config_dir)
    value_env = {**file_env, **os.environ, **cli_env}

    build_command = optional_string(section.get("build"), "diff_pdf.build")
    pdf_path = resolve_pdf_path(section, value_env)
    output_dir = optional_path(section.get("out"), "diff_pdf.out")
    diff_output = optional_path(section.get("diff_output"), "diff_pdf.diff_output")
    view = optional_bool(section.get("view"), "diff_pdf.view")
    no_diff = optional_bool(section.get("no_diff"), "diff_pdf.no_diff")
    keep_worktrees = optional_bool(section.get("keep_worktrees"), "diff_pdf.keep_worktrees")
    dirty = optional_choice(section.get("dirty"), "diff_pdf.dirty", {"fail", "allow"})
    build_env = resolve_env_table(section.get("env", {}), value_env, base_dir=repo_root)
    copy_paths = resolve_copy_paths(section.get("copy", []))

    return FileConfig(
        build_command=build_command,
        pdf_path=pdf_path,
        output_dir=output_dir,
        diff_output=diff_output,
        view=view,
        no_diff=no_diff,
        keep_worktrees=keep_worktrees,
        dirty=dirty,
        build_env=build_env,
        copy_paths=copy_paths,
    )


def read_env_file(value: object, *, config_dir: Path) -> dict[str, str]:
    if value is None:
        return {}
    path = optional_path(value, "diff_pdf.env_file")
    assert path is not None
    env_path = path if path.is_absolute() else config_dir / path
    if not env_path.is_file():
        raise DiffPdfCommitsError(f"env_file not found: {env_path}")

    parsed: dict[str, str] = {}
    for line_number, line in enumerate(env_path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, separator, raw_value = stripped.partition("=")
        if not separator or not key:
            raise DiffPdfCommitsError(f"Invalid env_file line {env_path}:{line_number}: expected KEY=VALUE")
        parsed[key.strip()] = unquote_env_value(raw_value.strip())
    return parsed


def unquote_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def optional_string(value: object, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise DiffPdfCommitsError(f"{name} must be a non-empty string.")
    return value


def optional_path(value: object, name: str) -> Path | None:
    text = optional_string(value, name)
    return Path(text) if text is not None else None


def optional_bool(value: object, name: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise DiffPdfCommitsError(f"{name} must be a boolean.")
    return value


def optional_choice(value: object, name: str, choices: set[str]) -> str | None:
    text = optional_string(value, name)
    if text is not None and text not in choices:
        raise DiffPdfCommitsError(f"{name} must be one of: {', '.join(sorted(choices))}.")
    return text


def resolve_pdf_path(section: dict[str, Any], env: dict[str, str]) -> Path | None:
    if "pdf" in section:
        value = section["pdf"]
        if isinstance(value, str):
            return Path(value)
        if isinstance(value, dict):
            source = optional_string(value.get("from_env"), "diff_pdf.pdf.from_env")
            assert source is not None
            env_value = env.get(source)
            if not env_value:
                raise DiffPdfCommitsError(f"Environment variable {source} is required by diff_pdf.pdf.")
            suffix = optional_string(value.get("replace_suffix"), "diff_pdf.pdf.replace_suffix")
            if suffix is not None:
                return Path(env_value).with_suffix(suffix)
            return Path(env_value)
        raise DiffPdfCommitsError("diff_pdf.pdf must be a string or a table.")

    if section.get("pdf_from_target") is True:
        target = env.get("TARGET")
        if not target:
            raise DiffPdfCommitsError("diff_pdf.pdf_from_target requires TARGET from env_file, environment, or --env.")
        return Path(target).with_suffix(".pdf")

    return None


def resolve_env_table(value: object, env: dict[str, str], *, base_dir: Path) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise DiffPdfCommitsError("diff_pdf.env must be a table.")

    resolved: dict[str, str] = {}
    for key, spec in value.items():
        if not isinstance(key, str) or not key:
            raise DiffPdfCommitsError("diff_pdf.env keys must be non-empty strings.")
        resolved[key] = resolve_env_value(key, spec, env, base_dir=base_dir)
    return resolved


def resolve_env_value(key: str, spec: object, env: dict[str, str], *, base_dir: Path) -> str:
    if isinstance(spec, str):
        return spec
    if not isinstance(spec, dict):
        raise DiffPdfCommitsError(f"diff_pdf.env.{key} must be a string or a table.")

    source = optional_string(spec.get("from_env"), f"diff_pdf.env.{key}.from_env")
    default = spec.get("default")
    value = env.get(source) if source is not None else None
    if value is None:
        value = default
    if value is None:
        raise DiffPdfCommitsError(f"Environment variable {source} is required by diff_pdf.env.{key}.")
    if not isinstance(value, str):
        raise DiffPdfCommitsError(f"diff_pdf.env.{key}.default must be a string.")
    if optional_bool(spec.get("resolve"), f"diff_pdf.env.{key}.resolve"):
        path = Path(value)
        value = str(path.resolve() if path.is_absolute() else (base_dir / path).resolve())
    return value


def resolve_copy_paths(value: object) -> tuple[Path, ...]:
    if isinstance(value, dict):
        value = value.get("paths", [])
    if value is None:
        return ()
    if not isinstance(value, list):
        raise DiffPdfCommitsError("diff_pdf.copy must be a list or a table with paths.")

    paths: list[Path] = []
    for item in value:
        path = optional_path(item, "diff_pdf.copy[]")
        assert path is not None
        try:
            paths.append(validate_repo_relative_path(path))
        except ValueError as error:
            raise DiffPdfCommitsError(f"Invalid config copy path {str(path)!r}: {error}") from error
    return tuple(paths)
