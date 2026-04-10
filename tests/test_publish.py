import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


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


def test_send_forwards_existing_epub_to_kindle(tmp_path):
    """--send should send an existing .epub directly without conversion."""
    epub_file = tmp_path / "mybook.epub"
    epub_file.write_bytes(b"fake epub content")

    from publish import run

    with patch("publish.send_to_kindle") as mock_send:
        result = run(str(epub_file), send=True)

        mock_send.assert_called_once_with(epub_file, subject="mybook")
        assert result["sent"] == "ok"
        # No PDF or EPUB should be generated
        assert result["pdf"] is None
        assert result["epub"] is None


def test_send_rejects_non_epub_file(tmp_path):
    """--send should reject files that are not .epub."""
    json_file = tmp_path / "content.json"
    json_file.write_text('{"title": "test"}')

    from publish import run

    with pytest.raises(ValueError, match=r"\.epub"):
        run(str(json_file), send=True)


def test_send_rejects_missing_file():
    """--send should raise FileNotFoundError for non-existent file."""
    from publish import run

    with pytest.raises(FileNotFoundError):
        run("/nonexistent/book.epub", send=True)
