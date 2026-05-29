# diff-pdf-commits

[![CI](https://github.com/ethercod3/diff-pdf-commits/actions/workflows/ci.yml/badge.svg)](https://github.com/ethercod3/diff-pdf-commits/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/diff-pdf-commits.svg)](https://pypi.org/project/diff-pdf-commits/)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/ethercod3/diff-pdf-commits/blob/main/LICENSE)
[![Run with uvx](https://img.shields.io/badge/run%20with-uvx-5E5CE6)](https://docs.astral.sh/uv/guides/tools/)

Compare PDFs produced by two Git revisions.

`diff-pdf-commits` creates temporary detached worktrees for two refs, runs your PDF build command in each worktree, copies the requested PDF artifacts, and optionally runs `diff-pdf` to produce a visual diff.

It is intentionally build-system agnostic. Use it with LaTeX, Typst, Make, Task, Docker Compose, or any other command that can build a PDF from a checked-out Git tree.

## Features

- Builds the same PDF from two Git refs without changing your current checkout.
- Uses `git worktree` instead of `git checkout`, so your working tree is not mutated.
- Accepts any shell build command through `--build`.
- Exports both generated PDFs for inspection.
- Can save a visual diff PDF with `diff-pdf`.
- Can open the `diff-pdf` GUI viewer.
- Supports extra build environment variables with `--env`.
- Supports copying local ignored files, such as `.env`, into both worktrees with `--copy`.
- Refuses dirty worktrees by default, with an explicit `--dirty allow` override.

## Installation

Run directly with `uvx`:

```bash
uvx diff-pdf-commits HEAD~1 HEAD \
  --build "latexmk -pdf main.tex" \
  --pdf main.pdf
```

Install it with `pipx`:

```bash
pipx install diff-pdf-commits
```

Install it with `pip`:

```bash
python -m pip install diff-pdf-commits
```

Run from a local checkout:

```bash
uvx --from . diff-pdf-commits HEAD~1 HEAD \
  --build "make pdf" \
  --pdf build/main.pdf
```

Run from GitHub source:

```bash
uvx --from git+https://github.com/ethercod3/diff-pdf-commits diff-pdf-commits HEAD~1 HEAD \
  --build "make pdf" \
  --pdf build/main.pdf
```

## Requirements

Required:

- Python 3.10+
- Git
- The tools needed by your build command

Optional:

- `diff-pdf` on `PATH` for visual comparison
- `uv` if you want to run the package with `uvx`

`diff-pdf` is not required when using `--no-diff`; in that mode the command only builds both revisions and exports the generated PDFs.

## Usage

Save a visual diff PDF:

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

Open the `diff-pdf` viewer:

```bash
diff-pdf-commits main feature/report-layout \
  --build "make pdf" \
  --pdf build/report.pdf \
  --view
```

Write the visual diff to a specific path:

```bash
diff-pdf-commits HEAD~1 HEAD \
  --build "task pdf" \
  --pdf dist/report.pdf \
  --diff-output review/report-diff.pdf
```

Pass environment variables to the build:

```bash
diff-pdf-commits HEAD~1 HEAD \
  --build "task pdf" \
  --pdf report.pdf \
  --env TEXMFVAR=.tex-cache \
  --env SOURCE_DATE_EPOCH=0
```

Copy local files into both worktrees before building:

```bash
diff-pdf-commits HEAD~1 HEAD \
  --build "task pdf" \
  --pdf report.pdf \
  --copy .env \
  --copy config/local.json
```

Allow a dirty current worktree:

```bash
diff-pdf-commits HEAD~1 HEAD \
  --build "make pdf" \
  --pdf build/main.pdf \
  --dirty allow
```

Keep temporary worktrees for debugging:

```bash
diff-pdf-commits HEAD~1 HEAD \
  --build "make pdf" \
  --pdf build/main.pdf \
  --keep-worktrees
```

## Output

By default, artifacts are written under `.pdf-diff/<left>__<right>/`:

```text
.pdf-diff/
  HEAD_1__HEAD/
    logs/
      build-left.log
      build-right.log
    pdfs/
      left-HEAD_1-main.pdf
      right-HEAD-main.pdf
    worktrees/
      left/
      right/
```

Temporary worktrees are removed after the run unless `--keep-worktrees` is passed. Build logs and copied PDFs are kept.

## Command Reference

```text
Usage: diff-pdf-commits [OPTIONS] LEFT_REF RIGHT_REF

Options:
  --build TEXT          Shell command that builds the PDF in each worktree.
  --pdf PATH            PDF path relative to repo root.
  --repo PATH           Path inside the git repository.
  --out PATH            Output directory.
  --diff-output PATH    Write visual diff PDF to this path.
  --view / --no-view    Open diff-pdf GUI viewer.
  --no-diff             Only build and export both PDFs; do not run diff-pdf.
  --keep-worktrees      Keep temporary git worktrees for debugging.
  --dirty [fail|allow]  Refuse or allow a dirty current worktree.
  --env KEY=VALUE       Environment variable passed to the build command.
  --copy PATH           Copy a local file or directory into each worktree.
  -h, --help            Show help.
```

There is also a `pdf-commit-diff` console script that points to the same command.

## Security

`--build` is executed as a shell command in each temporary worktree. This is deliberate, because real PDF projects commonly use commands such as `make pdf`, `task pdf`, `latexmk`, `typst`, or `docker compose`.

Do not pass untrusted build strings.

## Development

```bash
uv sync --extra dev
uv run black --check --diff src tests
uv run pytest
```

Docker-based integration tests are opt-in:

```bash
DIFF_PDF_COMMITS_RUN_DOCKER_TESTS=1 uv run pytest
```

Run the local checkout through `uvx`:

```bash
uvx --from . diff-pdf-commits HEAD~1 HEAD --build "make pdf" --pdf build/main.pdf
```
