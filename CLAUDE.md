# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A CLI tool that transforms JSON/Markdown content into PDF + EPUB and optionally sends the EPUB to a Kindle via email. One command, fully automated.

## Requirements

- **Python 3.10+** — the codebase uses PEP 604 union syntax (`str | None`) and built-in generic subscripting (`dict[str, str | None]`). Earlier versions will fail at import with a `TypeError`.

## Commands

The test suite lives under `tests/` and is split across four files: `test_epub_engine.py`, `test_kindle_sender.py`, `test_publish.py`, and `test_integration.py`.

```bash
# Run all tests
python -m pytest tests/ -v

# Run a single test file (any of the four)
python -m pytest tests/test_publish.py -v

# Run a specific test
python -m pytest tests/test_epub_engine.py::test_epub_chapters_split_on_h1 -v

# Install runtime dependencies
pip install -r requirements.txt

# Install dev dependencies (adds pytest + ruff)
pip install -r requirements-dev.txt

# Lint & format (config in pyproject.toml; engines/pdf_engine.py is excluded as vendored)
ruff check .
ruff format .

# CLI usage
python publish.py content.json --pdf              # PDF only
python publish.py content.json --epub             # EPUB only
python publish.py content.json --kindle           # EPUB + send to Kindle
python publish.py content.json --pdf --kindle     # Full pipeline
python publish.py guide.md --kindle               # Markdown input
python publish.py book.epub --send                # Send existing EPUB directly
python publish.py content.json --pdf -o ./out     # Write outputs to a specific directory
```

Outputs default to the input file's parent directory; pass `-o` / `--output-dir` to override. The directory must already exist.

`ruff check .` will surface a small baseline of pre-existing violations (unused imports, import order in `tests/`, one long line). They are tracked separately and not gating; new code should be clean.

## Architecture

**Pipeline flow:** Input file → `load_content()` (from pdf_engine) → unified content dict → engines → output files.

```
publish.py (orchestrator)
    ├── engines/pdf_engine.py   → PDF via ReportLab
    ├── engines/epub_engine.py  → EPUB via EbookLib
    └── engines/kindle_sender.py → SMTP via GMX (mail.gmx.com:587)
```

Key design decisions:
- **`engines/pdf_engine.py` is vendored from the `pdf-doc` skill.** Treat it as upstream code and avoid local edits. It provides both `build_pdf()` and `load_content()` — the latter is reused by the orchestrator to parse JSON and Markdown inputs for all engines.
- **EPUB splits chapters at h1 boundaries.** Each `h1` block starts a new EPUB chapter. Blocks before the first h1 become an "Introduction" chapter.
- **Engines are independent.** PDF and EPUB generation have no dependency on each other. The sender only needs a file path.
- **`--kindle` implies EPUB generation.** No need to pass `--epub --kindle` — `--kindle` alone generates the EPUB and sends it.
- **`--send` bypasses the entire pipeline.** It takes a ready `.epub` file and sends it directly to Kindle — no parsing, no conversion. Rejects non-`.epub` inputs.
- **Inputs are decoded with a fallback chain.** `publish.py` tries `utf-8-sig` → `utf-8` → `utf-16` → `latin-1` and uses the first decoder that succeeds. This lets BOM-prefixed and Notepad-saved UTF-16 files Just Work.

## Content Model

Both engines consume the same JSON content dict. The `blocks` array is flat (no nesting). Supported block types: `h1`, `h2`, `h3`, `p`, `bullets`, `steps`, `code`, `table`, `note`, `tip`, `warning`, `caution`, `important`, `boxes`, `footnotes`, `hr`, `spacer`, `pagebreak`.

Inline markup in text fields: `**bold**`, `*italic*`, `` `code` ``.

See `sample.json` at the repo root for a working example exercising several block types (`h1`, `p`, `tip`, `bullets`, `code`). Try it with `python publish.py sample.json --pdf --epub`.

## Environment Variables (for --kindle)

- `KINDLE_EMAIL` — Kindle's Send-to-Kindle address
- `SENDER_EMAIL` — GMX sender email
- `SENDER_PASS` — GMX password

The sender email must be in Amazon's Approved Personal Document E-mail List.

Set the variables once per machine:

```bash
# Linux / macOS (bash, zsh) — persist by appending to ~/.bashrc or ~/.zshrc
export KINDLE_EMAIL=you@kindle.com
export SENDER_EMAIL=you@gmx.com
export SENDER_PASS=your-gmx-password
```

```powershell
# Windows PowerShell — persist with [Environment]::SetEnvironmentVariable(..., 'User')
$env:KINDLE_EMAIL = 'you@kindle.com'
$env:SENDER_EMAIL = 'you@gmx.com'
$env:SENDER_PASS  = 'your-gmx-password'
```

```cmd
:: Windows cmd — setx persists to the user environment (new shells only)
setx KINDLE_EMAIL you@kindle.com
setx SENDER_EMAIL you@gmx.com
setx SENDER_PASS your-gmx-password
```

## Troubleshooting (Kindle delivery)

- **SMTP auth fails.** Verify `SENDER_EMAIL` / `SENDER_PASS`. GMX may require an app-specific password if 2FA is enabled.
- **Email is "delivered" but nothing reaches the Kindle.** The sender address must be on Amazon's Approved Personal Document E-mail List in your Amazon account settings.
- **`KINDLE_EMAIL` rejected.** It must be the `@kindle.com` address from your Amazon "Manage Your Content and Devices" page — not your personal email.
- **Different SMTP provider.** The host is hardcoded to `mail.gmx.com:587` in `engines/kindle_sender.py`. Switching providers requires editing that file.

## Testing Conventions

- SMTP is always mocked — no real emails sent during tests
- Tests use `tempfile.TemporaryDirectory()` or pytest's `tmp_path` for output isolation
- Environment variables in tests are patched via `unittest.mock.patch.dict(os.environ, ...)`
- Test fixtures use fake emails (`test@kindle.com`, `sender@gmx.com`) with dummy passwords
