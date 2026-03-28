# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A CLI tool that transforms JSON/Markdown content into PDF + EPUB and optionally sends the EPUB to a Kindle via email. One command, fully automated.

## Commands

```bash
# Run all tests
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_epub_engine.py -v

# Run a specific test
python -m pytest tests/test_epub_engine.py::test_epub_chapters_split_on_h1 -v

# Install dependencies
pip install -r requirements.txt

# CLI usage
python publish.py content.json --pdf              # PDF only
python publish.py content.json --epub             # EPUB only
python publish.py content.json --kindle           # EPUB + send to Kindle
python publish.py content.json --pdf --kindle     # Full pipeline
python publish.py guide.md --kindle               # Markdown input
```

## Architecture

**Pipeline flow:** Input file → `load_content()` (from pdf_engine) → unified content dict → engines → output files.

```
publish.py (orchestrator)
    ├── engines/pdf_engine.py   → PDF via ReportLab
    ├── engines/epub_engine.py  → EPUB via EbookLib
    └── engines/kindle_sender.py → SMTP via GMX (mail.gmx.com:587)
```

Key design decisions:
- **pdf_engine.py is copied from the pdf-doc skill** (pdf_engine_v4.py, 2259 lines). It provides both `build_pdf()` and `load_content()` — the latter is reused by the orchestrator to parse JSON and Markdown inputs for all engines.
- **EPUB splits chapters at h1 boundaries.** Each `h1` block starts a new EPUB chapter. Blocks before the first h1 become an "Introduction" chapter.
- **Engines are independent.** PDF and EPUB generation have no dependency on each other. The sender only needs a file path.
- **`--kindle` implies EPUB generation.** No need to pass `--epub --kindle` — `--kindle` alone generates the EPUB and sends it.

## Content Model

Both engines consume the same JSON content dict. The `blocks` array is flat (no nesting). Supported block types: `h1`, `h2`, `h3`, `p`, `bullets`, `steps`, `code`, `table`, `note`, `tip`, `warning`, `caution`, `important`, `boxes`, `footnotes`, `hr`, `spacer`, `pagebreak`.

Inline markup in text fields: `**bold**`, `*italic*`, `` `code` ``.

## Environment Variables (for --kindle)

- `KINDLE_EMAIL` — Kindle's Send-to-Kindle address
- `SENDER_EMAIL` — GMX sender email
- `SENDER_PASS` — GMX password

Set once via `setx` on Windows. The sender email must be in Amazon's Approved Personal Document E-mail List.

## Testing Conventions

- SMTP is always mocked — no real emails sent during tests
- Tests use `tempfile.TemporaryDirectory()` or pytest's `tmp_path` for output isolation
- Environment variables in tests are patched via `unittest.mock.patch.dict(os.environ, ...)`
- Test fixtures use fake emails (`test@kindle.com`, `sender@gmx.com`) with dummy passwords
