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
    raw_bytes = filepath.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
        try:
            raw = raw_bytes.decode(enc)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
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
