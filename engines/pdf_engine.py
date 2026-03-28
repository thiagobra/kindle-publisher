#!/usr/bin/env python3
"""PDF Engine v4.0.0

A polished, ReportLab-only PDF generator for technical documentation.

What it does well
- Keeps backward compatibility with the older JSON content model.
- Accepts pasted full text directly: run the script, paste once, finish with EOF.
- Also accepts JSON files, text/Markdown files, and stdin.
- Builds real PDF outlines and a real table of contents with page numbers.
- Produces clean A4 technical PDFs with callouts, steps, tables, code blocks,
  footnotes, page breaks, and optional box diagrams.
- Adds PDF-safe emoji-style icon badges using reliable symbol glyphs instead of
  fragile color-emoji fonts.

Recommended usage
    python pdf_engine_v4.py content.json
    python pdf_engine_v4.py guide.txt -o guide.pdf
    python pdf_engine_v4.py --stdin -o guide.pdf
    python pdf_engine_v4.py --paste -o guide.pdf
    pbpaste | python pdf_engine_v4.py --stdin -o guide.pdf

Paste mode
    If you run the script without an input path and without piped stdin,
    the script automatically enters paste mode.

Plain-text / Markdown-lite input highlights
- First short line can become the document title automatically.
- Optional top metadata lines, for example:
      Title: Release runbook
      Subtitle: Safe staging deployments
      Audience: Platform engineers
      Updated: 2026-03-27
      Summary: This guide explains the release workflow.
      Prerequisites:
      - Repo access
      - Staging credentials
      Result: The new build is live in staging.
      Toc: yes
      Numbered: no
- Markdown-ish structure is supported:
      # Heading
      ## Subheading
      - bullets
      1. ordered steps
      ```python
      print("hello")
      ```
      | Col | Col |
      | --- | --- |
      | A   | B   |
      Note: explanatory callout text
      [[pagebreak]]

Accessibility note
    This script improves structure, contrast, bookmarks, language metadata,
    and navigation. It does not create fully tagged PDF/UA documents.
    Strict accessible-PDF compliance still requires tagged-PDF workflows and
    post-processing tools.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from math import ceil
from pathlib import Path
from typing import Any, Iterable
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    HRFlowable,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents


# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

ICON_FONT = "Helvetica"
ICON_FONT_AVAILABLE = False


def _try_register_font(alias: str, candidates: Iterable[str]) -> bool:
    for candidate in candidates:
        path = Path(candidate)
        if not path.is_file():
            continue
        try:
            pdfmetrics.registerFont(TTFont(alias, str(path)))
            return True
        except Exception:
            continue
    return False


def setup_optional_fonts() -> None:
    """Register an optional symbol-capable font for PDF-safe emoji-style icons."""
    global ICON_FONT, ICON_FONT_AVAILABLE
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansSymbols-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode MS.ttf",
        "C:/Windows/Fonts/arialuni.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ]
    if _try_register_font("PDFEngineIcon", candidates):
        ICON_FONT = "PDFEngineIcon"
        ICON_FONT_AVAILABLE = True


setup_optional_fonts()


# ---------------------------------------------------------------------------
# Layout + theme
# ---------------------------------------------------------------------------

PAGE_W, PAGE_H = A4
MARGIN_H = 22 * mm
MARGIN_V = 18 * mm
HEADER_H = 12 * mm
FOOTER_H = 12 * mm
CONTENT_W = PAGE_W - (2 * MARGIN_H)

BLUE_DARK = HexColor("#16324f")
BLUE_MID = HexColor("#2457a6")
BLUE_LIGHT = HexColor("#eaf2ff")
GREEN_MID = HexColor("#2a8f57")
GREEN_LIGHT = HexColor("#e7f6ec")
AMBER_MID = HexColor("#c48b00")
AMBER_LIGHT = HexColor("#fff8df")
ORANGE_MID = HexColor("#d66b00")
ORANGE_LIGHT = HexColor("#fff0e3")
RED_MID = HexColor("#c9342c")
RED_LIGHT = HexColor("#fdeceb")
GRAY_BG = HexColor("#f6f7f9")
GRAY_TEXT = HexColor("#5a5f66")
GRAY_BORDER = HexColor("#cfd6df")
BODY_TEXT = HexColor("#20242a")
ALT_ROW = HexColor("#f5f7fb")
META_BG = HexColor("#f7f9fc")

CODE_BG = HexColor("#1e1e2e")
CODE_TEXT = HexColor("#e6e9ef")
CODE_NUM = HexColor("#8b93a6")

CALL_OUTS: dict[str, dict[str, Any]] = {
    "note": {
        "label": "Note",
        "bg": BLUE_LIGHT,
        "border": BLUE_MID,
        "text": BLUE_DARK,
        "icon": "ℹ",
        "fallback": "i",
    },
    "tip": {
        "label": "Tip",
        "bg": GREEN_LIGHT,
        "border": GREEN_MID,
        "text": HexColor("#19563a"),
        "icon": "★",
        "fallback": "*",
    },
    "warning": {
        "label": "Warning",
        "bg": AMBER_LIGHT,
        "border": AMBER_MID,
        "text": HexColor("#6f5200"),
        "icon": "⚠",
        "fallback": "!",
    },
    "caution": {
        "label": "Caution",
        "bg": ORANGE_LIGHT,
        "border": ORANGE_MID,
        "text": HexColor("#7f3d00"),
        "icon": "⚠",
        "fallback": "!",
    },
    "important": {
        "label": "Important",
        "bg": RED_LIGHT,
        "border": RED_MID,
        "text": HexColor("#7a1712"),
        "icon": "✦",
        "fallback": "+",
    },
}

DECORATIVE_ICONS: dict[str, tuple[str, str]] = {
    "summary": ("✎", "~"),
    "contents": ("☰", "#"),
    "prereq": ("☑", "-"),
    "result": ("✓", "+"),
}

DOC_KIND_LABELS = {
    "tutorial": "Tutorial",
    "howto": "How-to guide",
    "reference": "Reference",
    "explanation": "Explanation",
}

SUPPORTED_BLOCKS = {
    "h1",
    "h2",
    "h3",
    "p",
    "bullets",
    "steps",
    "table",
    "tip",
    "note",
    "warning",
    "caution",
    "important",
    "code",
    "boxes",
    "spacer",
    "hr",
    "footnotes",
    "pagebreak",
}

BOOLEAN_TRUE = {"1", "true", "yes", "y", "on"}
BOOLEAN_FALSE = {"0", "false", "no", "n", "off"}

TOP_METADATA_ALIASES = {
    "title": "title",
    "subtitle": "subtitle",
    "audience": "audience",
    "updated": "updated",
    "author": "author",
    "subject": "subject",
    "footer": "footer",
    "lang": "lang",
    "language": "lang",
    "keywords": "keywords",
    "toc": "toc",
    "contents": "toc",
    "numbered": "numbered",
    "filename": "filename",
    "summary": "summary",
    "result": "result",
    "outcome": "result",
    "prerequisites": "prerequisites",
    "before you begin": "prerequisites",
    "doc kind": "doc_kind",
    "dockind": "doc_kind",
    "kind": "doc_kind",
    "type": "doc_kind",
    "target pages": "target_pages",
    "target_pages": "target_pages",
    "emoji budget": "emoji_budget",
    "emoji_budget": "emoji_budget",
}


# ---------------------------------------------------------------------------
# Style system
# ---------------------------------------------------------------------------


def make_style(
    name: str,
    *,
    font: str = "Helvetica",
    size: float = 11,
    color: Color = BODY_TEXT,
    leading: float = 16,
    align: int = TA_LEFT,
    before: float = 0,
    after: float = 6,
    left: float = 0,
    keep_next: bool = False,
) -> ParagraphStyle:
    style = ParagraphStyle(
        name=name,
        fontName=font,
        fontSize=size,
        textColor=color,
        leading=leading,
        alignment=align,
        spaceBefore=before,
        spaceAfter=after,
        leftIndent=left,
    )
    style.keepWithNext = 1 if keep_next else 0
    return style


STYLES = {
    "title": make_style(
        "title",
        font="Helvetica-Bold",
        size=24,
        color=BLUE_DARK,
        leading=30,
        align=TA_CENTER,
        after=4,
        keep_next=True,
    ),
    "subtitle": make_style(
        "subtitle",
        font="Helvetica-Oblique",
        size=12,
        color=GRAY_TEXT,
        leading=18,
        align=TA_CENTER,
        after=12,
    ),
    "meta": make_style(
        "meta",
        font="Helvetica",
        size=9.5,
        color=GRAY_TEXT,
        leading=13,
        align=TA_CENTER,
        after=10,
    ),
    "summary": make_style(
        "summary",
        font="Helvetica",
        size=11,
        color=BODY_TEXT,
        leading=16,
        after=10,
    ),
    "h1": make_style(
        "h1",
        font="Helvetica-Bold",
        size=17,
        color=BLUE_MID,
        leading=22,
        before=14,
        after=6,
        keep_next=True,
    ),
    "h2": make_style(
        "h2",
        font="Helvetica-Bold",
        size=13.5,
        color=BLUE_DARK,
        leading=18,
        before=12,
        after=4,
        keep_next=True,
    ),
    "h3": make_style(
        "h3",
        font="Helvetica-Bold",
        size=11.5,
        color=BLUE_DARK,
        leading=16,
        before=10,
        after=3,
        keep_next=True,
    ),
    "front_h1": make_style(
        "front_h1",
        font="Helvetica-Bold",
        size=17,
        color=BLUE_MID,
        leading=22,
        before=14,
        after=6,
        keep_next=True,
    ),
    "front_h2": make_style(
        "front_h2",
        font="Helvetica-Bold",
        size=13.5,
        color=BLUE_DARK,
        leading=18,
        before=12,
        after=4,
        keep_next=True,
    ),
    "body": make_style(
        "body",
        font="Helvetica",
        size=11,
        color=BODY_TEXT,
        leading=16,
    ),
    "bullet": make_style(
        "bullet",
        font="Helvetica",
        size=11,
        color=BODY_TEXT,
        leading=16,
    ),
    "table_head": make_style(
        "table_head",
        font="Helvetica-Bold",
        size=9.7,
        color=colors.white,
        leading=13,
        align=TA_CENTER,
    ),
    "table_body": make_style(
        "table_body",
        font="Helvetica",
        size=9.7,
        color=BODY_TEXT,
        leading=13,
    ),
    "footer": make_style(
        "footer",
        font="Helvetica",
        size=9,
        color=GRAY_TEXT,
        leading=12,
        align=TA_CENTER,
    ),
    "fn_title": make_style(
        "fn_title",
        font="Helvetica-Bold",
        size=9,
        color=BODY_TEXT,
        leading=12,
        after=3,
    ),
    "fn_body": make_style(
        "fn_body",
        font="Helvetica",
        size=9,
        color=GRAY_TEXT,
        leading=12,
        after=2,
    ),
    "toc1": make_style(
        "toc1",
        font="Helvetica-Bold",
        size=11,
        color=BLUE_DARK,
        leading=15,
        after=2,
    ),
    "toc2": make_style(
        "toc2",
        font="Helvetica",
        size=10,
        color=BODY_TEXT,
        leading=14,
        left=10,
        after=2,
    ),
    "toc3": make_style(
        "toc3",
        font="Helvetica",
        size=10,
        color=GRAY_TEXT,
        leading=14,
        left=20,
        after=2,
    ),
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")



def color_hex(color: Color) -> str:
    return getattr(color, "hexval", lambda: "#000000")()



def parse_bool(value: Any, default: bool | None = None) -> bool | None:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in BOOLEAN_TRUE:
        return True
    if text in BOOLEAN_FALSE:
        return False
    return default



def parse_int(value: Any, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default



def slugify_filename(text: str, default: str = "document") -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or default



def plain_text(text: Any) -> str:
    raw = "" if text is None else str(text)
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.IGNORECASE)
    raw = re.sub(r"<[^>]+>", "", raw)
    return re.sub(r"\s+", " ", raw).strip()



def split_csvish(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[;,]", value) if part.strip()]



def split_lines_to_items(value: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"\n+|[;,]", value) if part.strip()]
    return parts



def normalize_doc_kind(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower().replace("-", "")
    mapping = {
        "tutorial": "tutorial",
        "tutorials": "tutorial",
        "howto": "howto",
        "howtoguide": "howto",
        "guide": "howto",
        "reference": "reference",
        "ref": "reference",
        "explanation": "explanation",
        "explain": "explanation",
        "concept": "explanation",
    }
    return mapping.get(text)



def icon_markup(name: str, color: Color, size: float = 11) -> str:
    glyph, fallback = DECORATIVE_ICONS.get(name, ("", ""))
    value = glyph if ICON_FONT_AVAILABLE else fallback
    if not value:
        return ""
    return f'<font name="{ICON_FONT}" color="{color_hex(color)}" size="{size}">{value}</font>'



def callout_icon_markup(variant: str, size: float = 12) -> str:
    cfg = CALL_OUTS[variant]
    value = cfg["icon"] if ICON_FONT_AVAILABLE else cfg["fallback"]
    return f'<font name="{ICON_FONT}" color="{color_hex(cfg["border"])}" size="{size}">{value}</font>'



def make_icon_heading(text: str, icon_key: str, color: Color, budget: "EmojiBudget | None") -> str:
    prefix = ""
    if budget and budget.use():
        icon = icon_markup(icon_key, color, size=11.5)
        if icon:
            prefix = icon + " "
    return prefix + sanitize_inline(text)



def make_icon_label(label: str, variant: str, budget: "EmojiBudget | None") -> str:
    prefix = ""
    if budget and budget.use():
        prefix = callout_icon_markup(variant, size=12) + " "
    return f"{prefix}<b>{escape(label)}</b>"



def sanitize_inline(text: Any) -> str:
    """Escape raw text while preserving a tiny, deliberate formatting subset.

    Supported input styles
    - existing inline tags: <b>, </b>, <i>, </i>, <u>, </u>, <br>, <br/>
    - Markdown-like emphasis: **bold**, __bold__, *italic*, _italic_
    - inline code: `code`
    """
    raw = "" if text is None else str(text)
    raw = normalize_newlines(raw)
    placeholders: dict[str, str] = {}

    def stash(html: str) -> str:
        key = f"ZZPDFPLACEHOLDER{len(placeholders)}ZZ"
        placeholders[key] = html
        return key

    # Preserve explicit allowed inline tags before escaping.
    allowed_tag_pattern = re.compile(r"</?(?:b|i|u)>|<br\s*/?>", re.IGNORECASE)
    raw = allowed_tag_pattern.sub(lambda m: stash(m.group(0).replace("<br>", "<br/>").replace("<BR>", "<br/>")), raw)

    # Convert inline code spans first.
    raw = re.sub(
        r"`([^`\n]+)`",
        lambda m: stash(f'<font name="Courier">{escape(m.group(1))}</font>'),
        raw,
    )

    # Markdown-like bold / italic.
    raw = re.sub(
        r"\*\*([^*\n][^*\n]*?)\*\*",
        lambda m: stash(f"<b>{escape(m.group(1))}</b>"),
        raw,
    )
    raw = re.sub(
        r"__([^_\n][^_\n]*?)__",
        lambda m: stash(f"<b>{escape(m.group(1))}</b>"),
        raw,
    )
    raw = re.sub(
        r"(?<!\*)\*([^*\n]+?)\*(?!\*)",
        lambda m: stash(f"<i>{escape(m.group(1))}</i>"),
        raw,
    )
    raw = re.sub(
        r"(?<!_)_([^_\n]+?)_(?!_)",
        lambda m: stash(f"<i>{escape(m.group(1))}</i>"),
        raw,
    )

    escaped = escape(raw)
    for token, html in placeholders.items():
        escaped = escaped.replace(escape(token), html)

    return escaped.replace("\n", "<br/>")



def normalize_keywords(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return split_csvish(str(value))



def normalize_prerequisites(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return split_lines_to_items(str(value))


class EmojiBudget:
    def __init__(self, limit: int = 5) -> None:
        self.limit = max(0, int(limit))
        self.used = 0

    def use(self) -> bool:
        if self.used >= self.limit:
            return False
        self.used += 1
        return True


class SectionCounter:
    def __init__(self) -> None:
        self.values = [0, 0, 0]

    def next(self, level: int) -> str:
        self.values[level] += 1
        for index in range(level + 1, 3):
            self.values[index] = 0
        return ".".join(str(self.values[index]) for index in range(level + 1))


# ---------------------------------------------------------------------------
# Flowables
# ---------------------------------------------------------------------------


class Callout(Flowable):
    PAD_X = 12
    PAD_Y = 10
    BAR_W = 4

    def __init__(
        self,
        text: str,
        *,
        variant: str = "note",
        width: float = CONTENT_W,
        label: str | None = None,
        budget: EmojiBudget | None = None,
    ) -> None:
        super().__init__()
        self.text = text
        self.variant = variant
        self.width = width
        self.height = 0.0
        self.para: Paragraph | None = None
        self.label = label or CALL_OUTS[variant]["label"]
        self.budget = budget

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        self.width = min(self.width, avail_width)
        cfg = CALL_OUTS[self.variant]
        style = ParagraphStyle(
            "callout-body",
            parent=STYLES["body"],
            textColor=cfg["text"],
            spaceAfter=0,
            spaceBefore=0,
            leading=15.5,
        )
        label_markup = make_icon_label(self.label, self.variant, self.budget)
        content = f"{label_markup} {sanitize_inline(self.text)}"
        self.para = Paragraph(content, style)
        inner_width = self.width - (2 * self.PAD_X) - self.BAR_W - 2
        _, para_height = self.para.wrap(inner_width, avail_height)
        self.height = para_height + (2 * self.PAD_Y)
        return self.width, self.height

    def draw(self) -> None:
        cfg = CALL_OUTS[self.variant]
        c = self.canv
        c.saveState()
        c.setFillColor(cfg["bg"])
        c.setStrokeColor(cfg["border"])
        c.setLineWidth(1)
        c.roundRect(0, 0, self.width, self.height, 6, fill=1, stroke=1)
        c.setFillColor(cfg["border"])
        c.roundRect(0, 0, self.BAR_W + 1, self.height, 6, fill=1, stroke=0)
        if self.para:
            self.para.drawOn(c, self.PAD_X + self.BAR_W + 1, self.PAD_Y - 1)
        c.restoreState()


class CodeBlock(Flowable):
    PAD_X = 10
    PAD_Y = 10
    LINE_H = 13.5
    GUTTER = 34
    FONT_NAME = "Courier"
    FONT_SIZE = 9.2

    def __init__(self, lines: list[str], width: float = CONTENT_W) -> None:
        super().__init__()
        self.source_lines = [str(line).rstrip("\n") for line in lines]
        self.width = width
        self.height = 0.0
        self.rendered_lines: list[tuple[str, str]] = []

    def _wrap_source_lines(self, width: float) -> list[tuple[str, str]]:
        text_width = max(20.0, width - self.GUTTER - (2 * self.PAD_X))
        char_width = max(1.0, pdfmetrics.stringWidth("M", self.FONT_NAME, self.FONT_SIZE))
        max_chars = max(18, int(text_width / char_width))
        wrapped: list[tuple[str, str]] = []

        for lineno, raw_line in enumerate(self.source_lines, start=1):
            line = raw_line.replace("\t", "    ")
            chunks = textwrap.wrap(
                line,
                width=max_chars,
                replace_whitespace=False,
                drop_whitespace=False,
                break_long_words=True,
                break_on_hyphens=False,
            ) or [""]
            for chunk_index, chunk in enumerate(chunks):
                wrapped.append((str(lineno) if chunk_index == 0 else "", chunk))
        return wrapped

    def wrap(self, avail_width: float, _avail_height: float) -> tuple[float, float]:
        self.width = min(self.width, avail_width)
        self.rendered_lines = self._wrap_source_lines(self.width)
        self.height = (len(self.rendered_lines) * self.LINE_H) + (2 * self.PAD_Y)
        return self.width, self.height

    def draw(self) -> None:
        c = self.canv
        c.saveState()
        c.setFillColor(CODE_BG)
        c.roundRect(0, 0, self.width, self.height, 6, fill=1, stroke=0)

        for index, (line_no, text_value) in enumerate(self.rendered_lines):
            y = self.height - self.PAD_Y - ((index + 1) * self.LINE_H) + 2.5
            c.setFont(self.FONT_NAME, 8.3)
            c.setFillColor(CODE_NUM)
            if line_no:
                c.drawRightString(self.GUTTER - 6, y, line_no)
            c.setFont(self.FONT_NAME, self.FONT_SIZE)
            c.setFillColor(CODE_TEXT)
            c.drawString(self.GUTTER, y, text_value)

        c.restoreState()


class BoxDiagram(Flowable):
    """Responsive, multi-row box diagram.

    JSON block format
        {
            "type": "boxes",
            "items": [
                {"title": "Prepare", "subtitle": "Check repo status", "color": "#2457a6"},
                {"title": "Deploy", "subtitle": "Push to staging", "color": "#2a8f57"},
            ]
        }

    Plain-text block format
        [[boxes]]
        Prepare | Check repo status | #2457a6
        Deploy  | Push to staging   | #2a8f57
        [[/boxes]]
    """

    GAP = 8
    BOX_H = 84
    MAX_COLS = 4
    MIN_BOX_W = 110

    def __init__(self, items: list[dict[str, str]], width: float = CONTENT_W) -> None:
        super().__init__()
        self.items = items
        self.width = width
        self.height = 0.0
        self.cols = 1
        self.rows = 1
        self.box_w = width

    def wrap(self, avail_width: float, _avail_height: float) -> tuple[float, float]:
        self.width = min(self.width, avail_width)
        if not self.items:
            self.height = 0
            return self.width, self.height

        max_cols = min(self.MAX_COLS, len(self.items))
        cols = 1
        for candidate in range(max_cols, 0, -1):
            usable = self.width - ((candidate - 1) * self.GAP)
            box_w = usable / candidate
            if box_w >= self.MIN_BOX_W or candidate == 1:
                cols = candidate
                break

        self.cols = cols
        self.rows = int(ceil(len(self.items) / self.cols))
        self.box_w = (self.width - ((self.cols - 1) * self.GAP)) / self.cols
        self.height = (self.rows * self.BOX_H) + ((self.rows - 1) * self.GAP)
        return self.width, self.height

    def draw(self) -> None:
        c = self.canv
        c.saveState()

        for index, item in enumerate(self.items):
            row = index // self.cols
            col = index % self.cols
            x = col * (self.box_w + self.GAP)
            y = self.height - ((row + 1) * self.BOX_H) - (row * self.GAP)
            color = HexColor(str(item.get("color", "#2457a6")))

            c.setFillColor(color)
            c.roundRect(x, y, self.box_w, self.BOX_H, 8, fill=1, stroke=0)

            title = plain_text(item.get("title", ""))
            subtitle = plain_text(item.get("subtitle", ""))

            title_lines = textwrap.wrap(title, width=max(8, int(self.box_w / 8.5)))[:2]
            subtitle_lines = textwrap.wrap(subtitle, width=max(12, int(self.box_w / 7.0)))[:4]

            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 10.5)
            title_y = y + self.BOX_H - 18
            for line_index, line in enumerate(title_lines):
                c.drawCentredString(x + (self.box_w / 2), title_y - (line_index * 12), line)

            c.setFont("Helvetica", 8.2)
            subtitle_y = y + self.BOX_H - 42 - (max(0, len(title_lines) - 1) * 10)
            for line_index, line in enumerate(subtitle_lines):
                c.drawCentredString(x + (self.box_w / 2), subtitle_y - (line_index * 10), line)

        c.restoreState()


# ---------------------------------------------------------------------------
# Document template
# ---------------------------------------------------------------------------


class PDFDoc(BaseDocTemplate):
    def __init__(self, filename: str, content: dict[str, Any]) -> None:
        super().__init__(
            filename,
            pagesize=A4,
            leftMargin=MARGIN_H,
            rightMargin=MARGIN_H,
            topMargin=MARGIN_V + HEADER_H,
            bottomMargin=MARGIN_V + FOOTER_H,
            title=content.get("title", "Document"),
            author=content.get("author", ""),
            subject=content.get("subject", ""),
        )
        self.content = content
        self.bookmark_id = 0
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="body")
        self.addPageTemplates([
            PageTemplate(id="default", frames=[frame], onPage=self.draw_chrome)
        ])

    def beforeDocument(self) -> None:  # noqa: N802 - ReportLab callback name
        self.bookmark_id = 0
        super().beforeDocument()

    def draw_chrome(self, canvas, doc) -> None:
        canvas.saveState()
        title = plain_text(self.content.get("title", "Documentation"))
        doc_kind = self.content.get("doc_kind")
        doc_kind_label = DOC_KIND_LABELS.get(str(doc_kind), "")
        target_pages = parse_int(self.content.get("target_pages"))

        canvas.setTitle(title)
        canvas.setAuthor(str(self.content.get("author", "")))
        canvas.setSubject(str(self.content.get("subject", "")))
        canvas.setCreator("PDF Engine v4.0.0")
        keywords = normalize_keywords(self.content.get("keywords"))
        if keywords:
            canvas.setKeywords(", ".join(keywords))
        try:
            canvas._doc.Catalog.Lang = self.content.get("lang", "en")
        except Exception:
            pass

        canvas.setStrokeColor(GRAY_BORDER)
        canvas.setLineWidth(0.5)

        y_header = PAGE_H - MARGIN_V - 4 * mm
        canvas.line(MARGIN_H, y_header, PAGE_W - MARGIN_H, y_header)
        canvas.setFont("Helvetica", 8.4)
        canvas.setFillColor(GRAY_TEXT)
        canvas.drawString(MARGIN_H, y_header + 2.4 * mm, title[:75])
        if doc_kind_label:
            canvas.drawRightString(PAGE_W - MARGIN_H, y_header + 2.4 * mm, doc_kind_label)

        y_footer = MARGIN_V + 8 * mm
        canvas.line(MARGIN_H, y_footer, PAGE_W - MARGIN_H, y_footer)
        canvas.drawCentredString(PAGE_W / 2, y_footer - 6, f"{doc.page}")

        if target_pages and doc.page > target_pages:
            print(
                f"\r  [!] Warning: rendering exceeded target limit of {target_pages} pages (currently {doc.page}).",
                end="",
                flush=True,
            )

        canvas.restoreState()

    def afterFlowable(self, flowable: Flowable) -> None:  # noqa: N802 - ReportLab callback name
        if not isinstance(flowable, Paragraph):
            return
        levels = {"h1": 0, "h2": 1, "h3": 2}
        style_name = flowable.style.name
        if style_name not in levels:
            return
        level = levels[style_name]
        text = plain_text(flowable.getPlainText())
        bookmark = f"bm_{self.bookmark_id}"
        self.bookmark_id += 1
        self.canv.bookmarkPage(bookmark)
        self.canv.addOutlineEntry(text, bookmark, level=level, closed=False)
        self.notify("TOCEntry", (level, text, self.page, bookmark))


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------



def read_paste_mode() -> str:
    print(
        "Paste your content below. Finish with Ctrl-D (Linux/macOS) or Ctrl-Z then Enter (Windows).",
        file=sys.stderr,
    )
    return sys.stdin.read()



def read_input_text(args: argparse.Namespace) -> tuple[str, str]:
    if args.content and args.paste:
        sys.exit("Error: use either a content path or --paste, not both.")
    if args.content and args.stdin_mode:
        sys.exit("Error: use either a content path or --stdin, not both.")

    if args.content:
        if args.content == "-":
            return sys.stdin.read(), "stdin"
        source_path = Path(args.content)
        if not source_path.is_file():
            sys.exit(f"Error: content file not found: {source_path}")
        try:
            return source_path.read_text(encoding="utf-8"), str(source_path)
        except UnicodeDecodeError:
            sys.exit(f"Error: could not decode UTF-8 text from: {source_path}")

    if args.stdin_mode:
        return sys.stdin.read(), "stdin"

    if not sys.stdin.isatty():
        return sys.stdin.read(), "stdin"

    # Automatic paste mode: simplest possible workflow.
    return read_paste_mode(), "pasted text"



def detect_input_format(raw_text: str, source_name: str, explicit: str) -> str:
    if explicit in {"json", "text"}:
        return explicit
    if source_name.lower().endswith(".json"):
        return "json"
    stripped = raw_text.lstrip()
    if stripped.startswith("{"):
        try:
            json.loads(stripped)
            return "json"
        except json.JSONDecodeError:
            pass
    return "text"


# ---------------------------------------------------------------------------
# Plain-text parser
# ---------------------------------------------------------------------------



def normalize_meta_key(key: str) -> str | None:
    cleaned = re.sub(r"\s+", " ", key.strip().lower())
    return TOP_METADATA_ALIASES.get(cleaned)



def looks_like_json(text: str) -> bool:
    stripped = text.lstrip()
    return stripped.startswith("{") and stripped.endswith("}")



def is_blank(line: str) -> bool:
    return not line.strip()



def is_hr_line(line: str) -> bool:
    stripped = line.strip()
    return bool(re.fullmatch(r"(?:-{3,}|\*{3,}|_{3,})", stripped))



def is_pagebreak_line(line: str) -> bool:
    return line.strip().lower() == "[[pagebreak]]"



def markdown_heading(line: str) -> tuple[int, str] | None:
    match = re.match(r"^(#{1,3})\s+(.+?)\s*$", line)
    if not match:
        return None
    return len(match.group(1)), match.group(2).strip()



def is_pipe_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.count("|") >= 2 and len([part for part in stripped.split("|") if part.strip()]) >= 2



def is_tsv_table_line(line: str) -> bool:
    return "\t" in line.strip()



def split_pipe_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]



def is_alignment_row(cells: list[str]) -> bool:
    if not cells:
        return False
    for cell in cells:
        if not re.fullmatch(r":?-{3,}:?", cell.strip()):
            return False
    return True



def parse_table_rows(raw_rows: list[list[str]]) -> dict[str, Any] | None:
    if not raw_rows:
        return None
    headers = raw_rows[0]
    rows = raw_rows[1:]
    if rows and is_alignment_row(rows[0]):
        rows = rows[1:]
    if not headers:
        return None

    clean_headers = [cell.strip() or f"Column {index + 1}" for index, cell in enumerate(headers)]
    clean_rows: list[list[str]] = []
    width = len(clean_headers)
    for row in rows:
        normalized = [cell.strip() for cell in row]
        if len(normalized) < width:
            normalized.extend([""] * (width - len(normalized)))
        elif len(normalized) > width:
            normalized = normalized[:width]
        clean_rows.append(normalized)
    return {"type": "table", "headers": clean_headers, "rows": clean_rows}



def pipe_table_at(lines: list[str], index: int) -> bool:
    if not is_pipe_table_line(lines[index]):
        return False
    if index + 1 >= len(lines):
        return False
    return is_pipe_table_line(lines[index + 1])



def tsv_table_at(lines: list[str], index: int) -> bool:
    if not is_tsv_table_line(lines[index]):
        return False
    if index + 1 >= len(lines):
        return False
    return is_tsv_table_line(lines[index + 1])



def callout_match(line: str) -> tuple[str, str] | None:
    pattern = re.compile(
        r"^\s*(?:(?:💡|ℹ️?|📝|✨|⚠️?|🚨|📌|❗)\s*)?(note|info|tip|warning|caution|important)\s*[:\-]\s*(.*)$",
        re.IGNORECASE,
    )
    match = pattern.match(line)
    if not match:
        return None
    raw_label = match.group(1).lower()
    mapping = {
        "note": "note",
        "info": "note",
        "tip": "tip",
        "warning": "warning",
        "caution": "caution",
        "important": "important",
    }
    return mapping[raw_label], match.group(2).strip()



def bullet_match(line: str) -> str | None:
    match = re.match(r"^\s*(?:[-*•])\s+(.+)$", line)
    return match.group(1).strip() if match else None



def step_match(line: str) -> str | None:
    match = re.match(r"^\s*(?:\d+[\.)]|step\s+\d+\s*[:\-\.)]?)\s+(.+)$", line, re.IGNORECASE)
    return match.group(1).strip() if match else None



def is_boxes_start(line: str) -> bool:
    return line.strip().lower() == "[[boxes]]"



def is_boxes_end(line: str) -> bool:
    return line.strip().lower() == "[[/boxes]]"



def parse_box_row(line: str) -> dict[str, str] | None:
    parts = [part.strip() for part in line.split("|")]
    if len(parts) < 2:
        return None
    title = parts[0]
    subtitle = parts[1]
    color = parts[2] if len(parts) >= 3 and parts[2] else "#2457a6"
    return {"title": title, "subtitle": subtitle, "color": color}



def is_block_boundary(line: str) -> bool:
    if is_blank(line):
        return True
    if markdown_heading(line):
        return True
    if line.strip().startswith("```"):
        return True
    if is_pagebreak_line(line) or is_hr_line(line) or is_boxes_start(line):
        return True
    if callout_match(line):
        return True
    if bullet_match(line) or step_match(line):
        return True
    return False



def looks_like_standalone_heading(line: str, title_already_known: bool) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if is_top_metadata_line(stripped):
        return False
    if not title_already_known:
        return False
    if stripped.endswith((".", "?", "!")):
        return False
    if len(stripped) > 65:
        return False
    if len(stripped.split()) > 9:
        return False
    if any(ch in stripped for ch in "|`[]"):
        return False
    if bullet_match(stripped) or step_match(stripped) or callout_match(stripped):
        return False
    return True



def consume_fenced_code(lines: list[str], index: int) -> tuple[list[str], int]:
    fence_line = lines[index].strip()
    fence = "```"
    if fence_line.startswith("~~~"):
        fence = "~~~"
    index += 1
    code_lines: list[str] = []
    while index < len(lines):
        if lines[index].strip().startswith(fence):
            return code_lines, index + 1
        code_lines.append(lines[index].rstrip("\n"))
        index += 1
    return code_lines, index



def consume_pipe_table(lines: list[str], index: int) -> tuple[dict[str, Any] | None, int]:
    rows: list[list[str]] = []
    while index < len(lines) and is_pipe_table_line(lines[index]):
        rows.append(split_pipe_row(lines[index]))
        index += 1
    return parse_table_rows(rows), index



def consume_tsv_table(lines: list[str], index: int) -> tuple[dict[str, Any] | None, int]:
    rows: list[list[str]] = []
    while index < len(lines) and is_tsv_table_line(lines[index]):
        rows.append([cell.strip() for cell in lines[index].split("\t")])
        index += 1
    return parse_table_rows(rows), index



def consume_boxes(lines: list[str], index: int) -> tuple[list[dict[str, str]], int]:
    items: list[dict[str, str]] = []
    while index < len(lines):
        if is_boxes_end(lines[index]):
            return items, index + 1
        if lines[index].strip():
            row = parse_box_row(lines[index])
            if row:
                items.append(row)
        index += 1
    return items, index



def consume_multiline_callout(lines: list[str], index: int, variant: str, first_text: str) -> tuple[str, int]:
    parts = [first_text] if first_text else []
    index += 1
    while index < len(lines) and not is_blank(lines[index]):
        if is_block_boundary(lines[index]) and not lines[index].startswith((" ", "\t")):
            break
        parts.append(lines[index].strip())
        index += 1
    return " ".join(part for part in parts if part).strip(), index



def consume_list(lines: list[str], index: int, ordered: bool) -> tuple[list[str], int]:
    items: list[str] = []
    matcher = step_match if ordered else bullet_match
    alternate = bullet_match if ordered else step_match

    while index < len(lines):
        match = matcher(lines[index])
        if match is None:
            break
        current = [match]
        index += 1
        while index < len(lines):
            line = lines[index]
            if is_blank(line):
                # Allow a blank line only if the next non-blank line continues the same list item with indentation.
                lookahead = index + 1
                while lookahead < len(lines) and is_blank(lines[lookahead]):
                    lookahead += 1
                if lookahead < len(lines) and lines[lookahead].startswith((" ", "\t")):
                    index = lookahead
                    current.append(lines[index].strip())
                    index += 1
                    continue
                break
            if matcher(line) is not None or alternate(line) is not None:
                break
            if markdown_heading(line) or line.strip().startswith("```") or is_hr_line(line) or is_pagebreak_line(line) or callout_match(line):
                break
            if pipe_table_at(lines, index) or tsv_table_at(lines, index) or is_boxes_start(line):
                break
            current.append(line.strip())
            index += 1
        items.append(" ".join(part for part in current if part).strip())
        while index < len(lines) and is_blank(lines[index]):
            # Stop if the blank line is followed by something other than another item of the same list type.
            lookahead = index + 1
            while lookahead < len(lines) and is_blank(lines[lookahead]):
                lookahead += 1
            if lookahead < len(lines) and matcher(lines[lookahead]) is not None:
                index = lookahead
                break
            return items, lookahead
    return items, index



def consume_paragraph(lines: list[str], index: int, title_already_known: bool) -> tuple[str, int]:
    parts: list[str] = []
    while index < len(lines):
        line = lines[index]
        if is_blank(line):
            break
        if index != 0 and (
            markdown_heading(line)
            or line.strip().startswith("```")
            or is_hr_line(line)
            or is_pagebreak_line(line)
            or callout_match(line)
            or bullet_match(line)
            or step_match(line)
            or pipe_table_at(lines, index)
            or tsv_table_at(lines, index)
            or is_boxes_start(line)
        ):
            break
        if parts and looks_like_standalone_heading(line, title_already_known):
            break
        parts.append(line.strip())
        index += 1
    return " ".join(part for part in parts if part).strip(), index



def parse_simple_front_matter(lines: list[str]) -> tuple[dict[str, Any], int]:
    if not lines or lines[0].strip() != "---":
        return {}, 0

    meta: dict[str, Any] = {}
    index = 1
    current_key: str | None = None
    while index < len(lines):
        line = lines[index]
        if line.strip() == "---":
            return meta, index + 1
        match = re.match(r"^\s*([^:]+?)\s*:\s*(.*)$", line)
        if match:
            key = normalize_meta_key(match.group(1))
            value = match.group(2).strip()
            current_key = key
            if key is None:
                current_key = None
            elif value:
                apply_meta(meta, key, value)
            else:
                if key in {"keywords", "prerequisites"}:
                    meta[key] = []
                else:
                    meta[key] = ""
            index += 1
            continue

        if current_key and isinstance(meta.get(current_key), list):
            bullet = bullet_match(line)
            if bullet is not None:
                meta[current_key].append(bullet)
            elif line.strip():
                meta[current_key].append(line.strip())
            index += 1
            continue

        if current_key and isinstance(meta.get(current_key), str):
            if line.strip():
                meta[current_key] = (str(meta[current_key]) + " " + line.strip()).strip()
            index += 1
            continue

        index += 1

    return {}, 0



def apply_meta(content: dict[str, Any], key: str, value: Any) -> None:
    if key == "keywords":
        content[key] = normalize_keywords(value)
    elif key == "prerequisites":
        content[key] = normalize_prerequisites(value)
    elif key == "doc_kind":
        normalized = normalize_doc_kind(value)
        if normalized:
            content[key] = normalized
    elif key in {"toc", "numbered"}:
        parsed = parse_bool(value)
        if parsed is not None:
            content[key] = parsed
    elif key in {"target_pages", "emoji_budget"}:
        parsed = parse_int(value)
        if parsed is not None:
            content[key] = parsed
    else:
        content[key] = str(value).strip()



def is_top_metadata_line(line: str) -> bool:
    match = re.match(r"^\s*([^:]+?)\s*:\s*(.*)$", line)
    return bool(match and normalize_meta_key(match.group(1)) is not None)



def consume_top_meta_bullets(lines: list[str], index: int) -> tuple[list[str], int]:
    items: list[str] = []
    while index < len(lines):
        line = lines[index]
        if is_blank(line):
            lookahead = index + 1
            while lookahead < len(lines) and is_blank(lines[lookahead]):
                lookahead += 1
            if lookahead < len(lines) and bullet_match(lines[lookahead]) is not None:
                index = lookahead
                continue
            return items, lookahead

        if is_top_metadata_line(line) and not line.startswith((" ", "	")):
            break

        bullet = bullet_match(line)
        if bullet is None:
            break

        current = [bullet]
        index += 1
        while index < len(lines):
            line = lines[index]
            if is_blank(line):
                break
            if bullet_match(line) is not None:
                break
            if is_top_metadata_line(line) and not line.startswith((" ", "	")):
                break
            if line.startswith((" ", "	")):
                current.append(line.strip())
                index += 1
                continue
            break
        items.append(" ".join(part for part in current if part).strip())

    return items, index



def parse_top_metadata(lines: list[str], start: int) -> tuple[dict[str, Any], int]:
    meta: dict[str, Any] = {}
    index = start

    while index < len(lines):
        line = lines[index]
        if is_blank(line):
            index += 1
            continue

        match = re.match(r"^\s*([^:]+?)\s*:\s*(.*)$", line)
        if not match:
            break
        key = normalize_meta_key(match.group(1))
        if key is None:
            break

        value = match.group(2).strip()

        if key == "prerequisites" and not value:
            items, next_index = consume_top_meta_bullets(lines, index + 1)
            meta[key] = items
            index = next_index
            continue

        if key in {"summary", "result"} and not value:
            para, next_index = consume_paragraph(lines, index + 1, title_already_known=True)
            meta[key] = para
            index = next_index
            continue

        apply_meta(meta, key, value)
        index += 1

    return meta, index



def infer_title_and_subtitle(lines: list[str], start: int, content: dict[str, Any]) -> int:
    index = start
    while index < len(lines) and is_blank(lines[index]):
        index += 1

    if not content.get("title") and index < len(lines):
        heading = markdown_heading(lines[index])
        if heading and heading[0] == 1:
            content["title"] = heading[1]
            index += 1
        elif (
            not is_block_boundary(lines[index])
            and len(lines[index].strip()) <= 90
            and len(lines[index].strip().split()) <= 12
        ):
            content["title"] = lines[index].strip()
            index += 1

    title_seen = bool(content.get("title"))
    if title_seen:
        # Subtitle only if it follows immediately as another short, plain line.
        while index < len(lines) and is_blank(lines[index]):
            index += 1
        if not content.get("subtitle") and index < len(lines):
            line = lines[index].strip()
            if line.startswith(">") and len(line[1:].strip()) <= 120:
                content["subtitle"] = line[1:].strip()
                index += 1
            elif (
                line
                and not markdown_heading(line)
                and not is_block_boundary(line)
                and len(line) <= 120
                and len(line.split()) <= 16
            ):
                content["subtitle"] = line
                index += 1

    return index



def infer_doc_kind(content: dict[str, Any]) -> str:
    if content.get("doc_kind") in DOC_KIND_LABELS:
        return str(content["doc_kind"])
    blocks = content.get("blocks", [])
    if any(block.get("type") == "steps" for block in blocks):
        return "howto"
    if any(block.get("type") == "table" for block in blocks) and any(block.get("type") == "code" for block in blocks):
        return "reference"
    if len([block for block in blocks if block.get("type") in {"h1", "h2", "h3"}]) >= 3:
        return "explanation"
    return "howto"



def parse_text_input(raw_text: str) -> dict[str, Any]:
    text = normalize_newlines(raw_text).strip("\n")
    lines = text.split("\n") if text else []

    content: dict[str, Any] = {
        "lang": "en",
        "numbered": False,
        "emoji_budget": 5,
        "blocks": [],
    }

    front_matter, index = parse_simple_front_matter(lines)
    content.update(front_matter)

    top_meta, index = parse_top_metadata(lines, index)
    content.update(top_meta)

    index = infer_title_and_subtitle(lines, index, content)

    blocks: list[dict[str, Any]] = []
    while index < len(lines):
        line = lines[index]
        if is_blank(line):
            index += 1
            continue

        heading = markdown_heading(line)
        if heading:
            level, title = heading
            blocks.append({"type": f"h{level}", "text": title})
            index += 1
            continue

        if is_top_metadata_line(line):
            match = re.match(r"^\s*([^:]+?)\s*:\s*(.*)$", line)
            if match:
                meta_key = normalize_meta_key(match.group(1))
                meta_value = match.group(2).strip()
                if meta_key == "footer":
                    content["footer"] = meta_value
                    index += 1
                    continue

        if looks_like_standalone_heading(line, bool(content.get("title"))):
            blocks.append({"type": "h2", "text": line.strip().rstrip(":")})
            index += 1
            continue

        if line.strip().startswith(("```", "~~~")):
            code_lines, index = consume_fenced_code(lines, index)
            blocks.append({"type": "code", "lines": code_lines})
            continue

        if is_pagebreak_line(line):
            blocks.append({"type": "pagebreak"})
            index += 1
            continue

        if is_hr_line(line):
            blocks.append({"type": "hr"})
            index += 1
            continue

        if is_boxes_start(line):
            items, index = consume_boxes(lines, index + 1)
            if items:
                blocks.append({"type": "boxes", "items": items})
            continue

        if pipe_table_at(lines, index):
            table_block, index = consume_pipe_table(lines, index)
            if table_block:
                blocks.append(table_block)
            continue

        if tsv_table_at(lines, index):
            table_block, index = consume_tsv_table(lines, index)
            if table_block:
                blocks.append(table_block)
            continue

        callout = callout_match(line)
        if callout:
            variant, first_text = callout
            full_text, index = consume_multiline_callout(lines, index, variant, first_text)
            blocks.append({"type": variant, "text": full_text})
            continue

        if bullet_match(line):
            items, index = consume_list(lines, index, ordered=False)
            blocks.append({"type": "bullets", "items": items})
            continue

        if step_match(line):
            items, index = consume_list(lines, index, ordered=True)
            blocks.append({"type": "steps", "items": items})
            continue

        paragraph, index = consume_paragraph(lines, index, bool(content.get("title")))
        if paragraph:
            blocks.append({"type": "p", "text": paragraph})
        else:
            index += 1

    content["blocks"] = blocks

    if not content.get("title"):
        content["title"] = "Document"
    if "toc" not in content:
        heading_count = sum(1 for block in blocks if block.get("type") in {"h1", "h2", "h3"})
        content["toc"] = heading_count >= 3
    if "doc_kind" not in content:
        content["doc_kind"] = infer_doc_kind(content)
    if "filename" not in content:
        content["filename"] = slugify_filename(str(content.get("title", "document"))) + ".pdf"
    if "keywords" not in content:
        content["keywords"] = []
    if "prerequisites" not in content:
        content["prerequisites"] = []

    return content


# ---------------------------------------------------------------------------
# Content normalization + validation
# ---------------------------------------------------------------------------



def normalize_content(content: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(content)
    normalized.setdefault("title", "Document")
    normalized.setdefault("blocks", [])
    normalized.setdefault("lang", "en")
    normalized.setdefault("toc", False)
    normalized.setdefault("numbered", False)
    normalized.setdefault("emoji_budget", 5)
    normalized.setdefault("keywords", [])
    normalized.setdefault("prerequisites", [])

    normalized["keywords"] = normalize_keywords(normalized.get("keywords"))
    normalized["prerequisites"] = normalize_prerequisites(normalized.get("prerequisites"))

    doc_kind = normalize_doc_kind(normalized.get("doc_kind"))
    if doc_kind:
        normalized["doc_kind"] = doc_kind

    emoji_budget = parse_int(normalized.get("emoji_budget"), default=5)
    normalized["emoji_budget"] = 5 if emoji_budget is None else max(0, emoji_budget)

    toc = parse_bool(normalized.get("toc"), default=False)
    numbered = parse_bool(normalized.get("numbered"), default=False)
    normalized["toc"] = bool(toc)
    normalized["numbered"] = bool(numbered)

    target_pages = parse_int(normalized.get("target_pages"), default=None)
    if target_pages is not None:
        normalized["target_pages"] = target_pages

    filename = str(normalized.get("filename", "")).strip()
    if not filename:
        filename = slugify_filename(str(normalized["title"])) + ".pdf"
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    normalized["filename"] = filename

    return normalized



def validate_content(content: dict[str, Any]) -> None:
    if not isinstance(content, dict):
        raise ValueError("Top-level content must be an object.")

    title = str(content.get("title", "")).strip()
    if not title:
        raise ValueError("Missing required field: title")

    blocks = content.get("blocks")
    if not isinstance(blocks, list):
        raise ValueError("Field 'blocks' must be a list.")

    doc_kind = content.get("doc_kind")
    if doc_kind and doc_kind not in DOC_KIND_LABELS:
        raise ValueError(f"Invalid doc_kind: {doc_kind}")

    for index, block in enumerate(blocks, start=1):
        if not isinstance(block, dict):
            raise ValueError(f"Block #{index} must be an object.")

        block_type = str(block.get("type", "p"))
        if block_type not in SUPPORTED_BLOCKS:
            raise ValueError(f"Unsupported block type in block #{index}: {block_type}")

        if block_type in {"h1", "h2", "h3", "p", "tip", "note", "warning", "caution", "important"}:
            if "text" not in block:
                raise ValueError(f"Block #{index} ({block_type}) requires 'text'.")

        if block_type in {"bullets", "steps"}:
            items = block.get("items")
            if not isinstance(items, list):
                raise ValueError(f"Block #{index} ({block_type}) requires 'items' as a list.")

        if block_type == "code":
            lines = block.get("lines")
            if not isinstance(lines, list):
                raise ValueError(f"Block #{index} (code) requires 'lines' as a list.")

        if block_type == "table":
            headers = block.get("headers")
            rows = block.get("rows")
            if not isinstance(headers, list) or not isinstance(rows, list):
                raise ValueError(f"Block #{index} (table) requires 'headers' and 'rows' lists.")
            if not headers:
                raise ValueError(f"Block #{index} (table) requires at least one header.")
            for row_index, row in enumerate(rows, start=1):
                if not isinstance(row, list):
                    raise ValueError(f"Table block #{index}, row #{row_index}: row must be a list.")
                if len(row) != len(headers):
                    raise ValueError(
                        f"Table block #{index}, row #{row_index}: expected {len(headers)} cells, got {len(row)}."
                    )

        if block_type == "boxes":
            items = block.get("items")
            if not isinstance(items, list):
                raise ValueError(f"Block #{index} (boxes) requires 'items' as a list.")
            for item_index, item in enumerate(items, start=1):
                if not isinstance(item, dict):
                    raise ValueError(f"Boxes block #{index}, item #{item_index}: each item must be an object.")

        if block_type == "footnotes":
            items = block.get("items")
            if not isinstance(items, list):
                raise ValueError(f"Block #{index} (footnotes) requires 'items' as a list.")


# ---------------------------------------------------------------------------
# Table helpers
# ---------------------------------------------------------------------------



def infer_col_ratios(headers: list[str], rows: list[list[Any]]) -> list[float]:
    samples: list[list[str]] = [headers] + [[str(cell) for cell in row] for row in rows]
    weights: list[float] = []
    n_cols = len(headers)

    for col in range(n_cols):
        column_values = [plain_text(row[col]) for row in samples if col < len(row)]
        max_len = max((len(value) for value in column_values), default=8)
        avg_len = sum(len(value) for value in column_values) / max(1, len(column_values))
        header = headers[col].strip().lower()

        if max_len <= 8 or header in {"id", "no", "qty", "count", "date", "day", "status", "ok", "done"}:
            weight = max(8.0, max_len * 0.9)
        else:
            weight = min(42.0, max(10.0, (max_len * 0.65) + (avg_len * 0.35)))
        weights.append(weight)

    total = sum(weights) or float(n_cols)
    return [weight / total for weight in weights]



def normalize_ratios(ratios: list[float], headers: list[str], rows: list[list[Any]]) -> list[float]:
    if len(ratios) != len(headers) or any(value <= 0 for value in ratios):
        return infer_col_ratios(headers, rows)
    total = sum(ratios)
    if total <= 0:
        return infer_col_ratios(headers, rows)
    return [value / total for value in ratios]



def guess_column_alignment(header: str, values: list[str]) -> str:
    header_clean = header.strip().lower()
    short = max((len(plain_text(value)) for value in values), default=0) <= 12
    numeric = values and all(
        re.fullmatch(r"[+-]?(?:\d+(?:[.,]\d+)?|\d{1,3}(?:,\d{3})*(?:\.\d+)?)%?", plain_text(value) or "")
        for value in values
        if plain_text(value)
    )

    if numeric:
        return "RIGHT"
    if short or header_clean in {"status", "date", "day", "id", "no", "qty", "ok", "done", "owner"}:
        return "CENTER"
    return "LEFT"



def build_table(block: dict[str, Any]) -> Table | Spacer:
    headers = [str(header) for header in block.get("headers", [])]
    rows = [[str(cell) for cell in row] for row in block.get("rows", [])]
    if not headers:
        return Spacer(1, 8)
    ratios = normalize_ratios(list(block.get("col_ratios", [])), headers, rows)
    col_widths = [CONTENT_W * ratio for ratio in ratios]

    data: list[list[Any]] = [[Paragraph(sanitize_inline(header), STYLES["table_head"]) for header in headers]]
    for row in rows:
        data.append([Paragraph(sanitize_inline(cell), STYLES["table_body"]) for cell in row])

    table = Table(data, colWidths=col_widths, repeatRows=1, splitByRow=1)
    base_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE_MID),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, GRAY_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
    ])

    for row_index in range(1, len(data)):
        base_style.add("BACKGROUND", (0, row_index), (-1, row_index), colors.white if row_index % 2 else ALT_ROW)

    for col_index, header in enumerate(headers):
        values = [row[col_index] for row in rows if col_index < len(row)]
        alignment = str(block.get("alignments", [""] * len(headers))[col_index]).strip().upper() if isinstance(block.get("alignments"), list) and col_index < len(block.get("alignments", [])) else guess_column_alignment(header, values)
        if alignment not in {"LEFT", "CENTER", "RIGHT"}:
            alignment = guess_column_alignment(header, values)
        base_style.add("ALIGN", (col_index, 1), (col_index, -1), alignment)

    table.setStyle(base_style)
    return table


# ---------------------------------------------------------------------------
# Story builders
# ---------------------------------------------------------------------------



def build_toc() -> TableOfContents:
    toc = TableOfContents()
    toc.levelStyles = [STYLES["toc1"], STYLES["toc2"], STYLES["toc3"]]
    return toc



def build_list(items: list[str], ordered: bool = False) -> ListFlowable:
    flow_items = [ListItem(Paragraph(sanitize_inline(item), STYLES["bullet"])) for item in items]
    kwargs: dict[str, Any] = {
        "leftIndent": 18,
        "bulletFontName": "Helvetica-Bold" if ordered else "Helvetica",
        "bulletFontSize": 10,
        "bulletColor": BLUE_MID if ordered else BODY_TEXT,
    }
    if ordered:
        kwargs["bulletType"] = "1"
        kwargs["start"] = "1"
    else:
        kwargs["bulletType"] = "bullet"
    return ListFlowable(flow_items, **kwargs)



def build_footnotes(items: list[dict[str, Any]]) -> list[Flowable]:
    out: list[Flowable] = [
        Spacer(1, 6),
        HRFlowable(width="35%", thickness=0.5, color=GRAY_BORDER, spaceAfter=4),
        Paragraph("Footnotes", STYLES["fn_title"]),
    ]
    for item in items:
        number = plain_text(item.get("n", ""))
        text_value = sanitize_inline(item.get("text", ""))
        out.append(Paragraph(f"<b>[{number}]</b> {text_value}", STYLES["fn_body"]))
    return out



def build_lead(content: dict[str, Any], budget: EmojiBudget) -> list[Flowable]:
    story: list[Flowable] = []
    story.append(Paragraph(sanitize_inline(content["title"]), STYLES["title"]))
    if content.get("subtitle"):
        story.append(Paragraph(sanitize_inline(content["subtitle"]), STYLES["subtitle"]))

    meta_bits: list[str] = []
    if content.get("doc_kind") in DOC_KIND_LABELS:
        meta_bits.append(DOC_KIND_LABELS[str(content["doc_kind"])])
    if content.get("audience"):
        meta_bits.append(f"Audience: {plain_text(content['audience'])}")
    if content.get("updated"):
        meta_bits.append(f"Updated: {plain_text(content['updated'])}")
    if meta_bits:
        story.append(Paragraph(" · ".join(meta_bits), STYLES["meta"]))

    story.append(HRFlowable(width="100%", thickness=1.5, color=BLUE_MID, spaceAfter=12))

    if content.get("summary"):
        story.append(
            Callout(
                str(content["summary"]),
                variant="note",
                label="Summary",
                budget=budget,
            )
        )
        story.append(Spacer(1, 6))

    prerequisites = normalize_prerequisites(content.get("prerequisites"))
    if prerequisites:
        story.append(Paragraph(make_icon_heading("Before you begin", "prereq", BLUE_DARK, budget), STYLES["front_h2"]))
        story.append(build_list(prerequisites, ordered=False))

    if content.get("result"):
        story.append(
            Callout(
                str(content["result"]),
                variant="important",
                label="Outcome",
                budget=budget,
            )
        )
        story.append(Spacer(1, 4))

    return story



def render_block(block: dict[str, Any], counter: SectionCounter | None, budget: EmojiBudget) -> list[Flowable]:
    block_type = str(block.get("type", "p"))

    if block_type == "h1":
        text_value = sanitize_inline(block.get("text", ""))
        if counter:
            text_value = f"{counter.next(0)}. {text_value}"
        return [
            KeepTogether(
                [
                    Paragraph(text_value, STYLES["h1"]),
                    HRFlowable(width="40%", thickness=0.8, color=BLUE_MID, spaceAfter=6),
                ]
            )
        ]

    if block_type == "h2":
        text_value = sanitize_inline(block.get("text", ""))
        if counter:
            text_value = f"{counter.next(1)} {text_value}"
        return [Paragraph(text_value, STYLES["h2"])]

    if block_type == "h3":
        text_value = sanitize_inline(block.get("text", ""))
        if counter:
            text_value = f"{counter.next(2)} {text_value}"
        return [Paragraph(text_value, STYLES["h3"])]

    if block_type == "p":
        return [Paragraph(sanitize_inline(block.get("text", "")), STYLES["body"])]

    if block_type == "bullets":
        return [build_list([str(item) for item in block.get("items", [])], ordered=False)]

    if block_type == "steps":
        return [build_list([str(item) for item in block.get("items", [])], ordered=True)]

    if block_type == "table":
        return [build_table(block)]

    if block_type in CALL_OUTS:
        return [Callout(str(block.get("text", "")), variant=block_type, budget=budget)]

    if block_type == "code":
        return [CodeBlock([str(line) for line in block.get("lines", [])])]

    if block_type == "boxes":
        return [BoxDiagram(block.get("items", []))]

    if block_type == "spacer":
        return [Spacer(1, float(block.get("height", 10)))]

    if block_type == "hr":
        return [
            HRFlowable(
                width=block.get("width", "100%"),
                thickness=float(block.get("thickness", 1)),
                color=GRAY_BORDER,
                spaceAfter=8,
            )
        ]

    if block_type == "footnotes":
        return build_footnotes(block.get("items", []))

    if block_type == "pagebreak":
        return [PageBreak()]

    return [Paragraph(sanitize_inline(block.get("text", "")), STYLES["body"])]



def build_pdf(content: dict[str, Any], output_path: Path) -> Path:
    content = normalize_content(content)
    validate_content(content)

    budget = EmojiBudget(parse_int(content.get("emoji_budget"), default=5) or 5)
    doc = PDFDoc(str(output_path), content)

    story: list[Flowable] = []
    story.extend(build_lead(content, budget))

    if content.get("toc"):
        story.append(Paragraph(make_icon_heading("Contents", "contents", BLUE_DARK, budget), STYLES["front_h1"]))
        story.append(build_toc())
        story.append(Spacer(1, 8))

    counter = SectionCounter() if content.get("numbered") else None
    for block in content.get("blocks", []):
        story.extend(render_block(block, counter, budget))

    footer = str(content.get("footer", "")).strip()
    if footer:
        story.append(Spacer(1, 12))
        story.append(HRFlowable(width="35%", thickness=0.5, color=GRAY_BORDER, spaceAfter=4))
        story.append(Paragraph(sanitize_inline(footer), STYLES["footer"]))

    doc.multiBuild(story)
    return output_path


# ---------------------------------------------------------------------------
# CLI orchestration
# ---------------------------------------------------------------------------



def load_content(raw_text: str, fmt: str) -> dict[str, Any]:
    if fmt == "json":
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("Top-level JSON must be an object.")
        return payload
    return parse_text_input(raw_text)



def apply_cli_overrides(content: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    updated = dict(content)
    if args.title:
        updated["title"] = args.title
    if args.subtitle:
        updated["subtitle"] = args.subtitle
    if args.lang:
        updated["lang"] = args.lang
    if args.toc is not None:
        updated["toc"] = args.toc
    if args.numbered is not None:
        updated["numbered"] = args.numbered
    if args.emoji_budget is not None:
        updated["emoji_budget"] = args.emoji_budget
    if args.target_pages is not None:
        updated["target_pages"] = args.target_pages
    return updated



def build_output_path(content: dict[str, Any], requested: Path | None) -> Path:
    if requested is not None:
        return requested if requested.is_absolute() else Path.cwd() / requested
    filename = str(content.get("filename", "")).strip()
    if not filename:
        filename = slugify_filename(str(content.get("title", "document"))) + ".pdf"
    output = Path(filename)
    return output if output.is_absolute() else Path.cwd() / output



def maybe_dump_json(content: dict[str, Any], path: Path | None) -> None:
    if path is None:
        return
    destination = path if path.is_absolute() else Path.cwd() / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a polished technical PDF from JSON, text files, stdin, or pasted full content.",
    )
    parser.add_argument(
        "content",
        nargs="?",
        help="Optional input path. Use a JSON file, text/Markdown file, or '-' for stdin. Omit it to paste content directly.",
    )
    parser.add_argument("-o", "--output", type=Path, help="Optional output PDF path.")
    parser.add_argument("--paste", action="store_true", help="Force paste mode.")
    parser.add_argument("--stdin", dest="stdin_mode", action="store_true", help="Read input from stdin.")
    parser.add_argument(
        "--format",
        choices=["auto", "json", "text"],
        default="auto",
        help="Input format. Defaults to auto-detection.",
    )
    parser.add_argument("--title", help="Override the title.")
    parser.add_argument("--subtitle", help="Override the subtitle.")
    parser.add_argument("--lang", help="Override the document language metadata. Default: en")
    parser.add_argument("--toc", dest="toc", action="store_true", default=None, help="Force-enable the table of contents.")
    parser.add_argument("--no-toc", dest="toc", action="store_false", help="Force-disable the table of contents.")
    parser.add_argument("--numbered", dest="numbered", action="store_true", default=None, help="Force-enable heading numbering.")
    parser.add_argument("--not-numbered", dest="numbered", action="store_false", help="Force-disable heading numbering.")
    parser.add_argument("--emoji-budget", type=int, help="Maximum decorative emoji-style icons per document. Default: 5")
    parser.add_argument("--target-pages", type=int, help="Optional soft page-count target; prints a warning if exceeded.")
    parser.add_argument("--dump-json", type=Path, help="Write the normalized parsed content model to a JSON file.")
    return parser.parse_args()



def main() -> None:
    args = parse_args()

    if args.paste and not sys.stdin.isatty() and not args.content:
        # When stdin is piped, stdin should win; --paste does not make sense there.
        print("[!] --paste ignored because stdin is already piped.", file=sys.stderr)

    raw_text, source_name = read_input_text(args)
    if not raw_text.strip():
        sys.exit("Error: no input content was provided.")

    input_format = detect_input_format(raw_text, source_name, args.format)

    try:
        content = load_content(raw_text, input_format)
        content = apply_cli_overrides(content, args)
        content = normalize_content(content)
        validate_content(content)
        maybe_dump_json(content, args.dump_json)

        output_path = build_output_path(content, args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result = build_pdf(content, output_path)
        print(f"PDF generated: {result.resolve()}")
    except Exception as exc:
        sys.exit(f"Failed to build PDF: {exc}")


if __name__ == "__main__":
    main()
