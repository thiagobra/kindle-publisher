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
