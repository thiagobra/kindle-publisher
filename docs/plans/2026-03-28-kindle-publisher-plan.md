# Kindle Publisher Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a CLI tool that takes JSON/Markdown content and produces PDF + EPUB, optionally sending the EPUB to a Kindle via email — all in one command.

**Architecture:** Modular pipeline with three engines (pdf, epub, kindle_sender) orchestrated by a CLI entry point (`publish.py`). The PDF engine is copied from the pdf-doc skill. The EPUB engine generates reflowable HTML chapters from the same JSON content model. The sender uses SMTP via GMX with credentials from environment variables.

**Tech Stack:** Python 3, ReportLab (PDF), EbookLib (EPUB), smtplib (SMTP/email)

---

### Task 1: Project scaffolding and PDF engine

**Files:**
- Create: `engines/__init__.py`
- Create: `engines/pdf_engine.py` (copy from `C:\Users\thiag\.claude\skills\pdf-doc\scripts\pdf_engine_v4.py`)
- Create: `requirements.txt`
- Create: `CLAUDE.md`

**Step 1: Create the engines directory and __init__.py**

```bash
mkdir -p engines
touch engines/__init__.py
```

**Step 2: Copy the PDF engine**

```bash
cp "C:/Users/thiag/.claude/skills/pdf-doc/scripts/pdf_engine_v4.py" engines/pdf_engine.py
```

**Step 3: Create requirements.txt**

```
reportlab
ebooklib
```

**Step 4: Create CLAUDE.md**

```markdown
# kindle-publisher

CLI tool: JSON/Markdown content → PDF + EPUB → Send to Kindle.

## Structure
- `publish.py` — CLI entry point
- `engines/pdf_engine.py` — PDF generation (from pdf-doc skill)
- `engines/epub_engine.py` — EPUB generation via ebooklib
- `engines/kindle_sender.py` — SMTP sender (GMX)

## Environment Variables (required for --kindle)
- KINDLE_EMAIL — Kindle Send-to-Kindle address
- SENDER_EMAIL — GMX sender email
- SENDER_PASS — GMX password

## Usage
python publish.py content.json --pdf --kindle
```

**Step 5: Verify PDF engine works standalone**

```bash
pip install reportlab ebooklib -q
python -c "from engines.pdf_engine import build_pdf, load_content; print('PDF engine OK')"
```

Expected: `PDF engine OK`

**Step 6: Commit**

```bash
git add engines/__init__.py engines/pdf_engine.py requirements.txt CLAUDE.md
git commit -m "feat: scaffold project and add PDF engine"
```

---

### Task 2: EPUB engine

**Files:**
- Create: `engines/epub_engine.py`
- Create: `tests/test_epub_engine.py`

**Step 1: Write the failing test**

```python
# tests/test_epub_engine.py
import json
import os
import tempfile
from pathlib import Path

def test_epub_generates_file():
    """EPUB engine should create a valid .epub file from JSON content."""
    from engines.epub_engine import build_epub

    content = {
        "title": "Test Document",
        "subtitle": "A test subtitle",
        "lang": "en",
        "blocks": [
            {"type": "h1", "text": "Chapter One"},
            {"type": "p", "text": "This is a paragraph."},
            {"type": "bullets", "items": ["Item A", "Item B"]},
            {"type": "h1", "text": "Chapter Two"},
            {"type": "code", "lines": ["print('hello')", "x = 42"]},
            {"type": "warning", "text": "Be careful here."},
        ]
    }

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "test.epub"
        result = build_epub(content, out)
        assert result.exists()
        assert result.stat().st_size > 0


def test_epub_chapters_split_on_h1():
    """Each h1 block should produce a separate EPUB chapter."""
    from engines.epub_engine import build_epub
    from ebooklib import epub

    content = {
        "title": "Multi Chapter",
        "blocks": [
            {"type": "h1", "text": "First"},
            {"type": "p", "text": "Content 1"},
            {"type": "h1", "text": "Second"},
            {"type": "p", "text": "Content 2"},
            {"type": "h1", "text": "Third"},
            {"type": "p", "text": "Content 3"},
        ]
    }

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "chapters.epub"
        build_epub(content, out)
        book = epub.read_epub(str(out))
        docs = [item for item in book.get_items()
                if item.get_type() == 9]  # ITEM_DOCUMENT
        # At least 3 chapter documents
        assert len(docs) >= 3


def test_epub_with_table():
    """Tables should render as HTML tables in the EPUB."""
    from engines.epub_engine import build_epub

    content = {
        "title": "Table Test",
        "blocks": [
            {"type": "h1", "text": "Data"},
            {"type": "table", "headers": ["Name", "Value"],
             "rows": [["alpha", "1"], ["beta", "2"]]},
        ]
    }

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "table.epub"
        result = build_epub(content, out)
        assert result.exists()
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_epub_engine.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'engines.epub_engine'`

**Step 3: Write the EPUB engine**

Create `engines/epub_engine.py`. This module:
- Takes the same JSON content dict as `pdf_engine.py`
- Splits on `h1` blocks to create chapters
- Converts each block type to HTML
- Embeds a CSS stylesheet for clean Kindle rendering
- Uses `ebooklib` to assemble the EPUB

Key implementation details:

```python
# engines/epub_engine.py
"""EPUB engine — generates reflowable EPUB from the JSON content model."""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

from ebooklib import epub


# -- Embedded CSS for Kindle-optimized rendering --

KINDLE_CSS = """
body { font-family: Georgia, serif; line-height: 1.6; margin: 1em; }
h1 { font-size: 1.8em; margin-top: 1.5em; margin-bottom: 0.5em; border-bottom: 1px solid #ccc; padding-bottom: 0.3em; }
h2 { font-size: 1.4em; margin-top: 1.2em; margin-bottom: 0.4em; }
h3 { font-size: 1.2em; margin-top: 1em; margin-bottom: 0.3em; }
p { margin: 0.6em 0; text-align: justify; }
pre { background: #f4f4f4; padding: 0.8em; font-family: monospace; font-size: 0.85em; white-space: pre-wrap; word-wrap: break-word; border: 1px solid #ddd; border-radius: 4px; }
code { font-family: monospace; font-size: 0.9em; background: #f4f4f4; padding: 0.1em 0.3em; border-radius: 2px; }
ul, ol { margin: 0.5em 0; padding-left: 1.5em; }
li { margin: 0.3em 0; }
table { border-collapse: collapse; width: 100%; margin: 0.8em 0; }
th { background: #2457a6; color: white; padding: 0.5em; text-align: left; font-weight: bold; }
td { padding: 0.4em 0.5em; border-bottom: 1px solid #ddd; }
tr:nth-child(even) td { background: #f8f8f8; }
.callout { padding: 0.8em; margin: 0.8em 0; border-left: 4px solid; border-radius: 4px; }
.callout-note { border-color: #2457a6; background: #eef3fc; }
.callout-tip { border-color: #2a8f57; background: #eef8f0; }
.callout-warning { border-color: #c48b00; background: #fef8e8; }
.callout-caution { border-color: #d44; background: #fef0f0; }
.callout-important { border-color: #7b4bbf; background: #f5f0ff; }
.callout-label { font-weight: bold; margin-bottom: 0.3em; text-transform: uppercase; font-size: 0.85em; }
.steps ol { list-style-type: decimal; }
.steps li { margin: 0.5em 0; }
"""

CALLOUT_TYPES = {"note", "tip", "warning", "caution", "important"}
CALLOUT_LABELS = {
    "note": "Note", "tip": "Tip", "warning": "Warning",
    "caution": "Caution", "important": "Important",
}


def _inline(text: str) -> str:
    """Convert **bold**, *italic*, and `code` markup to HTML."""
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    text = text.replace('<br/>', '<br />')
    return text


def _block_to_html(block: dict[str, Any]) -> str:
    """Convert a single JSON block to an HTML fragment."""
    btype = block.get("type", "")

    if btype in ("h1", "h2", "h3"):
        tag = btype
        return f"<{tag}>{_inline(block['text'])}</{tag}>\n"

    if btype == "p":
        return f"<p>{_inline(block['text'])}</p>\n"

    if btype == "bullets":
        items = "".join(f"<li>{_inline(i)}</li>" for i in block.get("items", []))
        return f"<ul>{items}</ul>\n"

    if btype == "steps":
        items = "".join(f"<li>{_inline(i)}</li>" for i in block.get("items", []))
        return f'<div class="steps"><ol>{items}</ol></div>\n'

    if btype == "code":
        lines = block.get("lines", [])
        code_text = "\n".join(lines)
        return f"<pre><code>{code_text}</code></pre>\n"

    if btype == "table":
        headers = block.get("headers", [])
        rows = block.get("rows", [])
        html = "<table>\n<thead><tr>"
        html += "".join(f"<th>{_inline(h)}</th>" for h in headers)
        html += "</tr></thead>\n<tbody>\n"
        for row in rows:
            html += "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in row) + "</tr>\n"
        html += "</tbody></table>\n"
        return html

    if btype in CALLOUT_TYPES:
        label = CALLOUT_LABELS[btype]
        return (f'<div class="callout callout-{btype}">'
                f'<div class="callout-label">{label}</div>'
                f'<p>{_inline(block["text"])}</p></div>\n')

    if btype == "hr":
        return "<hr />\n"

    if btype == "pagebreak":
        return ""  # No page breaks in reflowable EPUB

    if btype == "spacer":
        return "<br />\n"

    if btype == "footnotes":
        items = block.get("items", [])
        html = '<div class="footnotes"><hr />\n'
        for fn in items:
            html += f'<p><sup>{fn["n"]}</sup> {_inline(fn["text"])}</p>\n'
        html += "</div>\n"
        return html

    if btype == "boxes":
        # Render as a simple table since Kindle doesn't do fancy layouts
        items = block.get("items", [])
        html = '<table><tbody>\n'
        for item in items:
            color = item.get("color", "#2457a6")
            html += (f'<tr><td style="border-left: 4px solid {color}; padding: 0.5em;">'
                     f'<b>{_inline(item["title"])}</b>')
            if item.get("subtitle"):
                html += f'<br /><small>{_inline(item["subtitle"])}</small>'
            html += "</td></tr>\n"
        html += "</tbody></table>\n"
        return html

    return ""


def _split_chapters(blocks: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    """Split blocks into chapters at each h1 boundary."""
    chapters: list[tuple[str, list[dict[str, Any]]]] = []
    current_title = "Introduction"
    current_blocks: list[dict[str, Any]] = []

    for block in blocks:
        if block.get("type") == "h1":
            if current_blocks:
                chapters.append((current_title, current_blocks))
            current_title = block.get("text", "Untitled")
            current_blocks = [block]
        else:
            current_blocks.append(block)

    if current_blocks:
        chapters.append((current_title, current_blocks))

    return chapters


def build_epub(content: dict[str, Any], output_path: Path) -> Path:
    """Build an EPUB file from the JSON content model."""
    book = epub.EpubBook()

    # -- Metadata --
    uid = str(uuid.uuid4())
    title = content.get("title", "Untitled")
    lang = content.get("lang", "en")

    book.set_identifier(uid)
    book.set_title(title)
    book.set_language(lang)
    book.add_author(content.get("author", ""))

    # -- CSS --
    css = epub.EpubItem(
        uid="style", file_name="style/kindle.css",
        media_type="text/css", content=KINDLE_CSS.encode("utf-8"),
    )
    book.add_item(css)

    # -- Build chapters --
    blocks = content.get("blocks", [])
    chapter_groups = _split_chapters(blocks)
    epub_chapters = []

    for i, (ch_title, ch_blocks) in enumerate(chapter_groups):
        html_body = "".join(_block_to_html(b) for b in ch_blocks)
        chapter = epub.EpubHtml(
            title=ch_title,
            file_name=f"chapter_{i+1}.xhtml",
            lang=lang,
        )
        chapter.content = (
            f'<html><head><link rel="stylesheet" href="style/kindle.css" /></head>'
            f"<body>{html_body}</body></html>"
        ).encode("utf-8")
        chapter.add_item(css)
        book.add_item(chapter)
        epub_chapters.append(chapter)

    # -- Table of contents and spine --
    book.toc = epub_chapters
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav"] + epub_chapters

    # -- Write --
    output_path = Path(output_path)
    epub.write_epub(str(output_path), book)
    return output_path
```

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_epub_engine.py -v
```

Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add engines/epub_engine.py tests/test_epub_engine.py
git commit -m "feat: add EPUB engine with chapter splitting and Kindle CSS"
```

---

### Task 3: Kindle sender

**Files:**
- Create: `engines/kindle_sender.py`
- Create: `tests/test_kindle_sender.py`

**Step 1: Write the failing test**

```python
# tests/test_kindle_sender.py
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_send_validates_env_vars():
    """Should raise ValueError if required env vars are missing."""
    from engines.kindle_sender import send_to_kindle
    import pytest

    with tempfile.NamedTemporaryFile(suffix=".epub") as f:
        # Clear all env vars
        env = {"KINDLE_EMAIL": "", "SENDER_EMAIL": "", "SENDER_PASS": ""}
        with patch.dict(os.environ, env, clear=False):
            # Remove the keys entirely
            for key in ("KINDLE_EMAIL", "SENDER_EMAIL", "SENDER_PASS"):
                os.environ.pop(key, None)
            with pytest.raises(ValueError, match="KINDLE_EMAIL"):
                send_to_kindle(Path(f.name))


def test_send_validates_file_exists():
    """Should raise FileNotFoundError for non-existent file."""
    from engines.kindle_sender import send_to_kindle
    import pytest

    env = {
        "KINDLE_EMAIL": "test@kindle.com",
        "SENDER_EMAIL": "test@gmx.com",
        "SENDER_PASS": "pass123",
    }
    with patch.dict(os.environ, env):
        with pytest.raises(FileNotFoundError):
            send_to_kindle(Path("/nonexistent/file.epub"))


def test_send_calls_smtp_correctly():
    """Should connect to GMX SMTP and send the file."""
    from engines.kindle_sender import send_to_kindle

    env = {
        "KINDLE_EMAIL": "user@kindle.com",
        "SENDER_EMAIL": "sender@gmx.com",
        "SENDER_PASS": "secret",
    }

    with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
        f.write(b"fake epub content")
        f.flush()
        filepath = Path(f.name)

    try:
        with patch.dict(os.environ, env):
            with patch("engines.kindle_sender.smtplib.SMTP") as mock_smtp:
                mock_server = MagicMock()
                mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
                mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
                send_to_kindle(filepath)

                mock_smtp.assert_called_once_with("mail.gmx.com", 587)
                mock_server.starttls.assert_called_once()
                mock_server.login.assert_called_once_with("sender@gmx.com", "secret")
                mock_server.send_message.assert_called_once()
    finally:
        filepath.unlink()
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_kindle_sender.py -v
```

Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the Kindle sender**

```python
# engines/kindle_sender.py
"""Kindle sender — sends EPUB files to Kindle via GMX SMTP."""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

SMTP_HOST = "mail.gmx.com"
SMTP_PORT = 587


def send_to_kindle(filepath: Path, subject: str = "kindle document") -> None:
    """Send an EPUB file to the configured Kindle email via GMX SMTP.

    Required environment variables:
        KINDLE_EMAIL — Kindle's Send-to-Kindle address
        SENDER_EMAIL — GMX sender address
        SENDER_PASS  — GMX password
    """
    # -- Validate env vars --
    kindle_email = os.environ.get("KINDLE_EMAIL", "").strip()
    sender_email = os.environ.get("SENDER_EMAIL", "").strip()
    sender_pass = os.environ.get("SENDER_PASS", "").strip()

    missing = []
    if not kindle_email:
        missing.append("KINDLE_EMAIL")
    if not sender_email:
        missing.append("SENDER_EMAIL")
    if not sender_pass:
        missing.append("SENDER_PASS")
    if missing:
        raise ValueError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Set them with: setx VAR_NAME value"
        )

    # -- Validate file --
    filepath = Path(filepath)
    if not filepath.is_file():
        raise FileNotFoundError(f"File not found: {filepath}")

    # -- Build email --
    msg = EmailMessage()
    msg["From"] = sender_email
    msg["To"] = kindle_email
    msg["Subject"] = subject

    mime_type = "application/epub+zip"
    with open(filepath, "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype="application",
            subtype="epub+zip",
            filename=filepath.name,
        )

    # -- Send --
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(sender_email, sender_pass)
        server.send_message(msg)
```

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_kindle_sender.py -v
```

Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add engines/kindle_sender.py tests/test_kindle_sender.py
git commit -m "feat: add Kindle sender with GMX SMTP support"
```

---

### Task 4: CLI orchestrator (publish.py)

**Files:**
- Create: `publish.py`
- Create: `tests/test_publish.py`

**Step 1: Write the failing test**

```python
# tests/test_publish.py
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_publish_pdf_only(tmp_path):
    """--pdf should generate a PDF file."""
    content = {
        "title": "CLI Test",
        "blocks": [
            {"type": "h1", "text": "Hello"},
            {"type": "p", "text": "World"},
        ]
    }
    content_file = tmp_path / "content.json"
    content_file.write_text(json.dumps(content))

    from publish import run

    result = run(str(content_file), pdf=True, epub=False, kindle=False,
                 output_dir=str(tmp_path))

    assert result["pdf"] is not None
    assert Path(result["pdf"]).exists()


def test_publish_epub_only(tmp_path):
    """--epub should generate an EPUB file."""
    content = {
        "title": "EPUB Test",
        "blocks": [
            {"type": "h1", "text": "Chapter"},
            {"type": "p", "text": "Text"},
        ]
    }
    content_file = tmp_path / "content.json"
    content_file.write_text(json.dumps(content))

    from publish import run

    result = run(str(content_file), pdf=False, epub=True, kindle=False,
                 output_dir=str(tmp_path))

    assert result["epub"] is not None
    assert Path(result["epub"]).exists()


def test_publish_kindle_generates_epub_and_sends(tmp_path):
    """--kindle should generate EPUB and call send_to_kindle."""
    content = {
        "title": "Kindle Test",
        "blocks": [
            {"type": "h1", "text": "Chapter"},
            {"type": "p", "text": "Text"},
        ]
    }
    content_file = tmp_path / "content.json"
    content_file.write_text(json.dumps(content))

    from publish import run

    with patch("publish.send_to_kindle") as mock_send:
        result = run(str(content_file), pdf=False, epub=False, kindle=True,
                     output_dir=str(tmp_path))

        assert result["epub"] is not None
        assert Path(result["epub"]).exists()
        mock_send.assert_called_once()
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_publish.py -v
```

Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write publish.py**

```python
#!/usr/bin/env python3
"""kindle-publisher — Create PDF + EPUB, send to Kindle.

Usage:
    python publish.py content.json --pdf --kindle
    python publish.py content.json --pdf
    python publish.py content.json --epub
    python publish.py content.json --kindle
    python publish.py guide.md --kindle
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engines.epub_engine import build_epub
from engines.kindle_sender import send_to_kindle
from engines.pdf_engine import build_pdf, load_content


def _detect_format(filepath: Path) -> str:
    """Detect input format from file extension."""
    suffix = filepath.suffix.lower()
    if suffix == ".json":
        return "json"
    return "text"


def _derive_output_name(content: dict, suffix: str) -> str:
    """Derive output filename from content or title."""
    if content.get("filename"):
        base = Path(content["filename"]).stem
        return f"{base}{suffix}"
    title = content.get("title", "output")
    safe = "".join(c if c.isalnum() or c in " -_" else "" for c in title)
    safe = safe.strip().replace(" ", "-").lower()
    return f"{safe or 'output'}{suffix}"


def run(
    input_path: str,
    pdf: bool = False,
    epub: bool = False,
    kindle: bool = False,
    output_dir: str | None = None,
) -> dict[str, str | None]:
    """Run the publish pipeline. Returns dict with paths to generated files."""
    filepath = Path(input_path)
    if not filepath.is_file():
        raise FileNotFoundError(f"Input file not found: {filepath}")

    fmt = _detect_format(filepath)
    raw = filepath.read_text(encoding="utf-8")
    content = load_content(raw, fmt)

    out_dir = Path(output_dir) if output_dir else filepath.parent
    result: dict[str, str | None] = {"pdf": None, "epub": None, "sent": None}

    # -- PDF --
    if pdf:
        pdf_name = _derive_output_name(content, ".pdf")
        pdf_path = out_dir / pdf_name
        build_pdf(content, pdf_path)
        result["pdf"] = str(pdf_path)
        print(f"PDF created: {pdf_path}")

    # -- EPUB (explicit or needed for Kindle) --
    need_epub = epub or kindle
    epub_path = None
    if need_epub:
        epub_name = _derive_output_name(content, ".epub")
        epub_path = out_dir / epub_name
        build_epub(content, epub_path)
        result["epub"] = str(epub_path)
        print(f"EPUB created: {epub_path}")

    # -- Send to Kindle --
    if kindle and epub_path:
        title = content.get("title", "document")
        send_to_kindle(epub_path, subject=title)
        result["sent"] = "ok"
        print(f"Sent to Kindle!")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="kindle-publisher: PDF + EPUB + Send to Kindle"
    )
    parser.add_argument("input", help="Input file (JSON, Markdown, or text)")
    parser.add_argument("--pdf", action="store_true", help="Generate PDF")
    parser.add_argument("--epub", action="store_true", help="Generate EPUB (without sending)")
    parser.add_argument("--kindle", action="store_true", help="Generate EPUB and send to Kindle")
    parser.add_argument("-o", "--output-dir", help="Output directory (default: same as input)")

    args = parser.parse_args()

    if not (args.pdf or args.epub or args.kindle):
        parser.error("Specify at least one of: --pdf, --epub, --kindle")

    run(args.input, pdf=args.pdf, epub=args.epub, kindle=args.kindle,
        output_dir=args.output_dir)


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_publish.py -v
```

Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add publish.py tests/test_publish.py
git commit -m "feat: add CLI orchestrator with --pdf, --epub, --kindle flags"
```

---

### Task 5: Integration test — full pipeline

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write integration test**

```python
# tests/test_integration.py
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from publish import run


def test_full_pipeline_pdf_and_kindle(tmp_path):
    """Full pipeline: --pdf --kindle should produce both files and call send."""
    content = {
        "title": "Integration Test Guide",
        "subtitle": "Testing the full pipeline",
        "lang": "en",
        "toc": True,
        "doc_kind": "howto",
        "blocks": [
            {"type": "h1", "text": "Getting Started"},
            {"type": "p", "text": "This is the introduction."},
            {"type": "steps", "items": ["Install dependencies", "Configure settings", "Run the tool"]},
            {"type": "h1", "text": "Configuration"},
            {"type": "table", "headers": ["Variable", "Purpose"],
             "rows": [["KINDLE_EMAIL", "Kindle address"], ["SENDER_EMAIL", "GMX address"]]},
            {"type": "warning", "text": "Never share your credentials."},
            {"type": "h1", "text": "Advanced Usage"},
            {"type": "code", "lines": ["python publish.py guide.json --pdf --kindle"]},
            {"type": "tip", "text": "Use --epub to just generate the file without sending."},
        ]
    }

    content_file = tmp_path / "integration.json"
    content_file.write_text(json.dumps(content))

    with patch("publish.send_to_kindle") as mock_send:
        result = run(str(content_file), pdf=True, kindle=True, output_dir=str(tmp_path))

    assert Path(result["pdf"]).exists(), "PDF was not created"
    assert Path(result["epub"]).exists(), "EPUB was not created"
    assert result["sent"] == "ok", "Kindle send was not triggered"
    mock_send.assert_called_once()

    # Verify file sizes are reasonable
    assert Path(result["pdf"]).stat().st_size > 1000, "PDF seems too small"
    assert Path(result["epub"]).stat().st_size > 500, "EPUB seems too small"
```

**Step 2: Run the integration test**

```bash
python -m pytest tests/test_integration.py -v
```

Expected: PASS

**Step 3: Run all tests together**

```bash
python -m pytest tests/ -v
```

Expected: All tests PASS

**Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration test for full pipeline"
```

---

### Task 6: Manual end-to-end verification

**Step 1: Create a sample content.json**

```bash
python -c "
import json
content = {
    'title': 'Kindle Publisher Test',
    'subtitle': 'End-to-end verification',
    'lang': 'en',
    'toc': True,
    'blocks': [
        {'type': 'h1', 'text': 'Welcome'},
        {'type': 'p', 'text': 'This document was generated by kindle-publisher.'},
        {'type': 'tip', 'text': 'If you are reading this on your Kindle, the pipeline works!'},
    ]
}
with open('sample.json', 'w') as f:
    json.dump(content, f, indent=2)
"
```

**Step 2: Generate PDF + EPUB (without sending)**

```bash
python publish.py sample.json --pdf --epub
```

Expected: `sample.pdf` and `sample.epub` created in current directory. Verify both files open correctly.

**Step 3: Send to Kindle (live test)**

```bash
python publish.py sample.json --kindle
```

Expected: EPUB sent to Kindle. Check device in a few minutes.

**Step 4: Final commit**

```bash
git add sample.json
git commit -m "docs: add sample content for testing"
```
