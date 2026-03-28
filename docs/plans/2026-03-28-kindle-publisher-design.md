# Kindle Publisher — Design Document

**Date:** 2026-03-28
**Status:** Approved

## Purpose

A CLI tool and Claude Code skill that automates: JSON/Markdown content → PDF + EPUB → send EPUB to Kindle via email. One command, fully automated.

## Architecture

Modular pipeline with separate engines:

```
content.json ──┬──→ pdf_engine.py  ──→ output.pdf  (archival/print)
               │
               └──→ epub_engine.py ──→ output.epub ──→ kindle_sender.py ──→ Kindle
```

## Project Structure

```
kindle-publisher/
├── publish.py              # CLI entry point / orchestrator
├── engines/
│   ├── pdf_engine.py       # pdf_engine_v4.py (from pdf-doc skill)
│   ├── epub_engine.py      # JSON content → EPUB via ebooklib
│   └── kindle_sender.py    # SMTP sender (GMX, env vars)
├── docs/plans/
├── CLAUDE.md
└── requirements.txt        # reportlab, ebooklib
```

## CLI Interface

```bash
python publish.py content.json --pdf --kindle   # Full pipeline
python publish.py content.json --pdf            # PDF only
python publish.py content.json --epub           # EPUB only (no send)
python publish.py content.json --kindle         # EPUB + send to Kindle
python publish.py guide.md --kindle             # Markdown input
```

## Components

### publish.py (Orchestrator)
- Parses CLI args (input file, --pdf, --epub, --kindle)
- Detects input type (JSON vs Markdown/text)
- Calls engines as needed
- Reports results

### pdf_engine.py
- Copy of pdf_engine_v4.py from pdf-doc skill
- No modifications needed — used as-is

### epub_engine.py
- Reads same JSON content model as PDF engine
- Uses `ebooklib` to generate reflowable EPUB
- Maps JSON blocks to HTML chapters:
  - h1 → new chapter
  - h2/h3 → headings within chapter
  - p → paragraphs
  - bullets/steps → HTML lists
  - code → `<pre><code>` blocks with styling
  - table → HTML tables
  - callouts → styled divs
- Includes embedded CSS for clean Kindle rendering
- Generates proper metadata (title, author, language)

### kindle_sender.py
- Reads env vars: KINDLE_EMAIL, SENDER_EMAIL, SENDER_PASS
- SMTP via mail.gmx.com:587 with STARTTLS
- Sends EPUB as email attachment
- Clear error messages if env vars missing

## Configuration

Credentials stored in Windows environment variables (set once via `setx`):
- `KINDLE_EMAIL` — Kindle's Send-to-Kindle address
- `SENDER_EMAIL` — GMX sender address
- `SENDER_PASS` — GMX account password

## Dependencies

- `reportlab` — PDF generation
- `ebooklib` — EPUB generation
- Python stdlib `smtplib` + `email` — SMTP sending

## Known Limitations

- No embedded images in either PDF or EPUB
- PDF engine limitations carry over (see pdf-doc skill docs)
- GMX SMTP rate limits may apply for bulk sending
