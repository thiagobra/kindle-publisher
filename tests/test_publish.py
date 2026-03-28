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
