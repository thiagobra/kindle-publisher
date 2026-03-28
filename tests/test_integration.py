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
