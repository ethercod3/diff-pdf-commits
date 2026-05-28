# diff-pdf-commits

Build the same PDF from two git commits and compare the results with `diff-pdf`.

This repository was extracted from a diploma LaTeX project where the original helper compared generated PDFs between commits. The standalone version is intentionally project-agnostic: it does not know about LaTeX, Docker, Taskfile, or a specific PDF name. You pass the build command and the PDF path explicitly.

## Status

Alpha scaffold. The MVP is implemented, but the first real repository should still be tested against a throwaway Git repo before publishing.

## Install and Run

From a published package:

```bash
uvx diff-pdf-commits HEAD~1 HEAD --build "latexmk -lualatex main.tex" --pdf main.pdf
```

From GitHub before publishing to PyPI:

```bash
uvx --from git+https://github.com/ethercod3/diff-pdf-commits diff-pdf-commits HEAD~1 HEAD --build "task latex:local" --pdf thesis.pdf
```

Local development:

```bash
uv sync --extra dev
uv run diff-pdf-commits --help
uv run pytest
```

Run the local checkout through `uvx`, the same way another repository would consume it:

```bash
uvx --from . diff-pdf-commits HEAD~1 HEAD --build "make pdf" --pdf build/main.pdf
```

From another local repository before publishing:

```bash
uvx --from ../diff-pdf-commits diff-pdf-commits HEAD~1 HEAD --build "task latex:local" --pdf thesis.pdf
```

## Basic Usage

Save a visual diff PDF:

```bash
diff-pdf-commits HEAD~1 HEAD \
  --build "task latex:local" \
  --pdf "thesis.pdf"
```

Open the `diff-pdf` GUI viewer:

```bash
diff-pdf-commits v1 v2 --build "make pdf" --pdf build/main.pdf --view
```

Only build and export both PDFs without running `diff-pdf`:

```bash
diff-pdf-commits main feature/pdf-change --build "latexmk -pdf main.tex" --pdf main.pdf --no-diff
```

Pass environment variables to the build command:

```bash
diff-pdf-commits HEAD~1 HEAD \
  --build "task latex:local" \
  --pdf thesis.pdf \
  --env UV_PYTHON=/path/to/python
```

Copy local ignored files needed by the build into each temporary worktree:

```bash
diff-pdf-commits HEAD~1 HEAD \
  --build "task build" \
  --pdf thesis.pdf \
  --copy .env
```

On Windows this is useful when another application ships a `python.exe` earlier on `PATH`:

```powershell
uvx --from git+https://github.com/ethercod3/diff-pdf-commits diff-pdf-commits HEAD~1 HEAD `
  --build "task build" `
  --pdf "Куприянов_И221_диплом.pdf" `
  --env "UV_PYTHON=C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe" `
  --copy .env
```

Use it from the original diploma project:

```bash
uvx --from ../diff-pdf-commits diff-pdf-commits HEAD~1 HEAD \
  --build "task latex:local" \
  --pdf "Куприянов_И221_диплом.pdf" \
  --out ".pdf-diff"
```

## How It Works

1. Finds the git repository root.
2. Refuses to run on a dirty worktree by default.
3. Creates two detached temporary git worktrees under `.pdf-diff/.../worktrees`.
4. Runs the provided build command in each worktree.
5. Copies the requested PDF from each worktree into `.pdf-diff/.../pdfs`.
6. Runs `diff-pdf` unless `--no-diff` is passed.
7. Removes temporary worktrees unless `--keep-worktrees` is passed.

The current working tree is not checked out to another commit. That is the main design improvement over the original project-local script.

## Requirements

Required:

- Python 3.10+
- Git
- `uv` if you want `uvx`
- whatever your build command needs

Required for visual comparison:

- `diff-pdf` on `PATH`

## Important Design Decisions

- The build command is a shell command by design. This is practical for `task`, `make`, `latexmk`, Docker Compose, Typst, etc. Do not pass untrusted strings to `--build`.
- The PDF path is explicit and relative to each checked-out worktree root.
- The current worktree is not mutated; temporary `git worktree` checkouts are used instead.
- Build logs are saved under `.pdf-diff/.../logs`.

## Next Steps Before Publishing

- Add integration tests that create a temporary git repo and build fake PDFs.
- Decide whether the canonical command should be `diff-pdf-commits` or `pdf-commit-diff`; both entry points currently exist.
- Add GitHub Actions for Linux, Windows, and macOS.
- Consider `--env KEY=VALUE` for build commands.
- Consider `--timeout` for long builds.
- Consider alternative backends such as ImageMagick or plain export-only mode.
