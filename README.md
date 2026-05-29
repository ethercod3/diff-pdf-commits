# diff-pdf-commits

[![CI](https://github.com/ethercod3/diff-pdf-commits/actions/workflows/ci.yml/badge.svg)](https://github.com/ethercod3/diff-pdf-commits/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/diff-pdf-commits.svg)](https://pypi.org/project/diff-pdf-commits/)
[![Python](https://img.shields.io/pypi/pyversions/diff-pdf-commits.svg)](https://pypi.org/project/diff-pdf-commits/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/ethercod3/diff-pdf-commits/blob/main/LICENSE)
[![Run with uvx](https://img.shields.io/badge/run%20with-uvx-5E5CE6)](https://docs.astral.sh/uv/guides/tools/)

Build a PDF from two Git revisions and compare the results.

`diff-pdf-commits` creates detached `git worktree` checkouts for two refs, runs your build command in each checkout, saves both generated PDFs, and optionally runs `diff-pdf` to create or open a visual diff.

It does not assume LaTeX, Typst, Make, Docker, or any project layout. A project supplies its own build command and PDF path, either on the command line or through `diff_config.toml`.

## Install

Run without installing:

```bash
uvx diff-pdf-commits HEAD~1 HEAD --config diff_config.toml
```

Or install it:

```bash
pipx install diff-pdf-commits
```

```bash
python -m pip install diff-pdf-commits
```

## Quick Start

For repeated use in a repository, add `diff_config.toml`:

```toml
[diff_pdf]
build = "make pdf"
pdf = "build/report.pdf"
view = true
```

Then compare two refs:

```bash
diff-pdf-commits HEAD~1 HEAD --config diff_config.toml
```

Generated artifacts are written to `.pdf-diff/<left>__<right>/` by default.

## Config File

`--config` is the canonical way to store project-specific behavior: build command, PDF path, copied local files, and environment variables.

```toml
[diff_pdf]
build = "docker compose --profile latex run --build --rm latex"
env_file = ".env"
pdf_from_target = true
view = true

[diff_pdf.env]
PYTHONIOENCODING = "utf-8"
PYTHONUTF8 = "1"
TARGET = { from_env = "TARGET" }
VAULT_PATH = { from_env = "VAULT_PATH" }
VAULT_OS_PATH = { from_env = "VAULT_OS_PATH", resolve = true }

[diff_pdf.copy]
paths = [
  ".env",
  "docker-compose.yaml",
  "docker/latex.dockerfile",
]
```

Supported `[diff_pdf]` keys:

- `build`: shell command run in each temporary worktree.
- `pdf`: PDF path relative to the worktree root. It can also be `{ from_env = "TARGET", replace_suffix = ".pdf" }`.
- `pdf_from_target`: derive the PDF path from `TARGET` by replacing `.tex` with `.pdf`.
- `env_file`: `.env`-style file used while expanding config values.
- `out`: output directory, default `.pdf-diff`.
- `diff_output`: explicit visual diff PDF path.
- `view`: open the `diff-pdf` GUI viewer.
- `no_diff`: only build and export both PDFs.
- `keep_worktrees`: keep temporary worktrees for debugging.
- `dirty`: `fail` or `allow`.

Supported `[diff_pdf.env]` values:

```toml
STATIC_VALUE = "value"
FROM_ENV = { from_env = "SOURCE_NAME" }
WITH_DEFAULT = { from_env = "OPTIONAL_NAME", default = "fallback" }
ABSOLUTE_PATH = { from_env = "RELATIVE_OR_ABSOLUTE_PATH", resolve = true }
```

Command-line options override config values. Repeated `--env` options override matching `[diff_pdf.env]` keys. Repeated `--copy` options are appended to configured copy paths.

## One-Shot Usage

You can also pass everything on the command line:

```bash
diff-pdf-commits HEAD~1 HEAD \
  --build "latexmk -pdf main.tex" \
  --pdf main.pdf
```

Only build both revisions and export the PDFs:

```bash
diff-pdf-commits v1.0.0 HEAD \
  --build "typst compile main.typ main.pdf" \
  --pdf main.pdf \
  --no-diff
```

Save a visual diff PDF to a specific path:

```bash
diff-pdf-commits HEAD~1 HEAD \
  --build "task pdf" \
  --pdf dist/report.pdf \
  --diff-output review/report-diff.pdf
```

Pass local build inputs into both temporary worktrees:

```bash
diff-pdf-commits HEAD~1 HEAD \
  --build "task pdf" \
  --pdf report.pdf \
  --env SOURCE_DATE_EPOCH=0 \
  --copy .env \
  --copy config/local.json
```

## Output Layout

By default, each run writes to `.pdf-diff/<left>__<right>/`:

```text
.pdf-diff/
  HEAD_1__HEAD/
    logs/
      build-left.log
      build-right.log
    pdfs/
      left-HEAD_1-report.pdf
      right-HEAD-report.pdf
    worktrees/
      left/
      right/
```

Temporary worktrees are removed after the run unless `--keep-worktrees` is set. Logs and copied PDFs are kept.

## Requirements

Required:

- Python 3.10+
- Git
- The tools needed by your build command

Optional:

- `diff-pdf` on `PATH` for visual comparison
- `uv` if you want to run with `uvx`

`diff-pdf` is not needed when `--no-diff` is set.

## Command Reference

```text
Usage: diff-pdf-commits [OPTIONS] LEFT_REF RIGHT_REF

Options:
  --build TEXT          Shell command that builds the PDF in each worktree.
  --pdf PATH            PDF path relative to repo root.
  --repo PATH           Path inside the git repository.
  --out PATH            Output directory.
  --diff-output PATH    Write visual diff PDF to this path.
  --config PATH         Load options from TOML.
  --view / --no-view    Open diff-pdf GUI viewer.
  --no-diff             Only build and export both PDFs; do not run diff-pdf.
  --keep-worktrees      Keep temporary git worktrees for debugging.
  --dirty [fail|allow]
  --env KEY=VALUE       Environment variable passed to the build command.
  --copy PATH           Copy a local file or directory into each worktree.
  -h, --help            Show help.
```

`diff-pdf-commits` is the canonical command. `pdf-commit-diff` is kept as a compatibility alias.

## Security

`--build` is executed with `shell=True` in each temporary worktree. This is intentional so projects can use commands such as `make pdf`, `task pdf`, `latexmk`, `typst`, or `docker compose`.

Do not pass untrusted build strings.

## Development

```bash
uv sync --extra dev
uv run black --check --diff src tests
uv run pytest
uv build
```

Docker-based integration tests are opt-in:

```bash
DIFF_PDF_COMMITS_RUN_DOCKER_TESTS=1 uv run pytest
```

Run the local checkout through `uvx`:

```bash
uvx --refresh --from . diff-pdf-commits HEAD~1 HEAD --config diff_config.toml
```
