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
        ],
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
        ],
    }

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "chapters.epub"
        build_epub(content, out)
        book = epub.read_epub(str(out))
        docs = [item for item in book.get_items() if item.get_type() == 9]  # ITEM_DOCUMENT
        # At least 3 chapter documents
        assert len(docs) >= 3


def test_epub_with_table():
    """Tables should render as HTML tables in the EPUB."""
    from engines.epub_engine import build_epub

    content = {
        "title": "Table Test",
        "blocks": [
            {"type": "h1", "text": "Data"},
            {
                "type": "table",
                "headers": ["Name", "Value"],
                "rows": [["alpha", "1"], ["beta", "2"]],
            },
        ],
    }

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "table.epub"
        result = build_epub(content, out)
        assert result.exists()
