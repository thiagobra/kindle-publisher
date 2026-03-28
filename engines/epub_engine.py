#!/usr/bin/env python3
"""EPUB Engine

Converts the shared JSON content model into a Kindle-optimized EPUB file.
Uses ebooklib to assemble the EPUB with proper metadata, CSS, chapter
splitting, table of contents, and spine.

Supports the same block types as pdf_engine.py:
    h1, h2, h3, p, bullets, steps, code, table,
    note, tip, warning, caution, important,
    hr, pagebreak, spacer, footnotes, boxes
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from ebooklib import epub

# ---------------------------------------------------------------------------
# Kindle-optimised CSS
# ---------------------------------------------------------------------------

KINDLE_CSS = """\
body {
    font-family: Georgia, "Times New Roman", serif;
    line-height: 1.6;
    margin: 1em;
    color: #1a1a1a;
}

h1 {
    font-size: 1.8em;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
    border-bottom: 2px solid #333;
    padding-bottom: 0.3em;
}

h2 {
    font-size: 1.4em;
    margin-top: 1.2em;
    margin-bottom: 0.4em;
}

h3 {
    font-size: 1.2em;
    margin-top: 1em;
    margin-bottom: 0.3em;
}

p {
    margin: 0.6em 0;
    text-align: justify;
}

ul, ol {
    margin: 0.6em 0 0.6em 1.5em;
    padding: 0;
}

li {
    margin-bottom: 0.3em;
}

pre {
    font-family: "Courier New", Courier, monospace;
    font-size: 0.85em;
    background-color: #f4f4f4;
    border: 1px solid #ddd;
    padding: 0.8em;
    overflow-x: auto;
    white-space: pre-wrap;
    word-wrap: break-word;
    line-height: 1.4;
}

code {
    font-family: "Courier New", Courier, monospace;
    font-size: 0.9em;
    background-color: #f0f0f0;
    padding: 0.1em 0.3em;
}

pre code {
    background-color: transparent;
    padding: 0;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin: 0.8em 0;
    font-size: 0.9em;
}

th, td {
    border: 1px solid #999;
    padding: 0.4em 0.6em;
    text-align: left;
}

th {
    background-color: #e8e8e8;
    font-weight: bold;
}

tr:nth-child(even) {
    background-color: #f9f9f9;
}

.callout {
    margin: 1em 0;
    padding: 0.8em 1em;
    border-left: 4px solid #999;
    background-color: #fafafa;
}

.callout-note { border-left-color: #2196F3; }
.callout-tip { border-left-color: #4CAF50; }
.callout-warning { border-left-color: #FF9800; }
.callout-caution { border-left-color: #f44336; }
.callout-important { border-left-color: #9C27B0; }

.callout-label {
    font-weight: bold;
    text-transform: uppercase;
    font-size: 0.85em;
    margin-bottom: 0.3em;
}

hr {
    border: none;
    border-top: 1px solid #ccc;
    margin: 1.5em 0;
}

.box {
    border: 1px solid #999;
    margin: 1em 0;
}

.box-title {
    background-color: #e8e8e8;
    padding: 0.4em 0.6em;
    font-weight: bold;
    border-bottom: 1px solid #999;
}

.box-body {
    padding: 0.6em;
}

.footnotes {
    margin-top: 2em;
    border-top: 1px solid #ccc;
    padding-top: 0.5em;
    font-size: 0.85em;
}
"""

# ---------------------------------------------------------------------------
# Inline markup: **bold**, *italic*, `code`
# ---------------------------------------------------------------------------

_INLINE_PATTERNS = [
    (re.compile(r"\*\*(.+?)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"\*(.+?)\*"), r"<em>\1</em>"),
    (re.compile(r"`(.+?)`"), r"<code>\1</code>"),
]


def _inline(text: str) -> str:
    """Convert lightweight markup to HTML inline elements."""
    text = escape(text)
    for pattern, replacement in _INLINE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


# ---------------------------------------------------------------------------
# Block -> HTML conversion
# ---------------------------------------------------------------------------

_CALLOUT_TYPES = {"note", "tip", "warning", "caution", "important"}


def _block_to_html(block: dict[str, Any]) -> str:
    """Convert a single content block to an HTML fragment."""
    btype = block.get("type", "p")

    if btype in ("h1", "h2", "h3"):
        tag = btype
        return f"<{tag}>{_inline(block['text'])}</{tag}>"

    if btype == "p":
        return f"<p>{_inline(block['text'])}</p>"

    if btype == "bullets":
        items = "".join(f"<li>{_inline(i)}</li>" for i in block["items"])
        return f"<ul>{items}</ul>"

    if btype == "steps":
        items = "".join(f"<li>{_inline(i)}</li>" for i in block["items"])
        return f"<ol>{items}</ol>"

    if btype == "code":
        lang = block.get("lang", "")
        lines = "\n".join(escape(line) for line in block["lines"])
        label = f"<p><strong>{escape(lang)}</strong></p>" if lang else ""
        return f'{label}<pre><code>{lines}</code></pre>'

    if btype == "table":
        headers = block.get("headers", [])
        rows = block.get("rows", [])
        html = "<table>"
        if headers:
            html += "<thead><tr>"
            html += "".join(f"<th>{_inline(h)}</th>" for h in headers)
            html += "</tr></thead>"
        html += "<tbody>"
        for row in rows:
            html += "<tr>"
            html += "".join(f"<td>{_inline(c)}</td>" for c in row)
            html += "</tr>"
        html += "</tbody></table>"
        return html

    if btype in _CALLOUT_TYPES:
        label = btype.upper()
        return (
            f'<div class="callout callout-{btype}">'
            f'<div class="callout-label">{label}</div>'
            f"<p>{_inline(block['text'])}</p>"
            f"</div>"
        )

    if btype == "hr":
        return "<hr/>"

    if btype == "pagebreak":
        # No-op in EPUB; Kindle handles page flow
        return ""

    if btype == "spacer":
        return "<p>&nbsp;</p>"

    if btype == "footnotes":
        items = block.get("items", [])
        html = '<div class="footnotes"><p><strong>Footnotes</strong></p><ol>'
        for fn in items:
            ref = escape(fn.get("ref", ""))
            text = _inline(fn.get("text", ""))
            html += f"<li><strong>[{ref}]</strong> {text}</li>"
        html += "</ol></div>"
        return html

    if btype == "boxes":
        items = block.get("items", [])
        parts = []
        for box in items:
            title = _inline(box.get("title", ""))
            body = _inline(box.get("body", ""))
            parts.append(
                f'<div class="box">'
                f'<div class="box-title">{title}</div>'
                f'<div class="box-body"><p>{body}</p></div>'
                f"</div>"
            )
        return "\n".join(parts)

    # Fallback: treat as paragraph
    text = block.get("text", "")
    if text:
        return f"<p>{_inline(text)}</p>"
    return ""


# ---------------------------------------------------------------------------
# Chapter splitting
# ---------------------------------------------------------------------------


def _split_chapters(blocks: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Split blocks into chapters at each h1 boundary.

    Blocks before the first h1 go into a preamble chapter.
    """
    chapters: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []

    for block in blocks:
        if block.get("type") == "h1" and current:
            chapters.append(current)
            current = []
        current.append(block)

    if current:
        chapters.append(current)

    return chapters


# ---------------------------------------------------------------------------
# EPUB assembly
# ---------------------------------------------------------------------------


def build_epub(content: dict[str, Any], output_path: Path) -> Path:
    """Build an EPUB file from the JSON content model.

    Args:
        content: Dict with keys title, subtitle (opt), lang (opt), blocks.
        output_path: Where to write the .epub file.

    Returns:
        The Path to the written file.
    """
    book = epub.EpubBook()

    # Metadata
    title = content.get("title", "Untitled")
    subtitle = content.get("subtitle", "")
    lang = content.get("lang", "en")
    book_id = str(uuid.uuid4())

    book.set_identifier(book_id)
    book.set_title(title)
    book.set_language(lang)
    author = content.get("author", "")
    if author:
        book.add_author(author)

    if subtitle:
        book.add_metadata("DC", "description", subtitle)

    # CSS stylesheet
    css = epub.EpubItem(
        uid="style",
        file_name="style/kindle.css",
        media_type="text/css",
        content=KINDLE_CSS.encode("utf-8"),
    )
    book.add_item(css)

    # Split blocks into chapters
    blocks = content.get("blocks", [])
    chapter_groups = _split_chapters(blocks)

    epub_chapters = []
    toc_entries = []
    spine = ["nav"]

    for i, chapter_blocks in enumerate(chapter_groups):
        # Determine chapter title from h1 or fallback
        first = chapter_blocks[0] if chapter_blocks else {}
        if first.get("type") == "h1":
            ch_title = first.get("text", f"Chapter {i + 1}")
        else:
            ch_title = f"Chapter {i + 1}" if i > 0 else "Preamble"

        file_name = f"chapter_{i:03d}.xhtml"
        ch = epub.EpubHtml(
            title=ch_title,
            file_name=file_name,
            lang=lang,
        )
        ch.add_item(css)

        # Build chapter HTML body
        body_parts = []
        for block in chapter_blocks:
            html = _block_to_html(block)
            if html:
                body_parts.append(html)

        ch.content = (
            f'<html xmlns="http://www.w3.org/1999/xhtml">\n'
            f"<head><title>{escape(ch_title)}</title></head>\n"
            f"<body>\n{''.join(body_parts)}\n</body>\n</html>"
        ).encode("utf-8")

        book.add_item(ch)
        epub_chapters.append(ch)
        toc_entries.append(ch)
        spine.append(ch)

    # Table of contents and navigation
    book.toc = toc_entries
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    # Write
    output_path = Path(output_path)
    epub.write_epub(str(output_path), book)
    return output_path
