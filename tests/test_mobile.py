"""Tests for PyDroid 3 / mobile support additions."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# kindle_sender: config-file fallback
# ---------------------------------------------------------------------------

class TestConfigFileFallback:
    """kindle_sender should read credentials from kindle.cfg when env vars
    are not set."""

    def _write_cfg(self, tmp_path: Path, content: str) -> Path:
        cfg = tmp_path / "kindle.cfg"
        cfg.write_text(content, encoding="utf-8")
        return cfg

    def test_credentials_from_config_file(self, tmp_path):
        """send_to_kindle reads credentials from kindle.cfg when env vars
        are absent."""
        from engines.kindle_sender import send_to_kindle, _CONFIG_SEARCH_PATHS

        cfg_path = self._write_cfg(tmp_path, (
            "[kindle]\n"
            "kindle_email = cfg@kindle.com\n"
            "sender_email = cfg@gmx.com\n"
            "sender_pass  = cfgpass\n"
        ))

        epub = tmp_path / "book.epub"
        epub.write_bytes(b"PK fake epub")

        # Clear env vars and point config search to our temp file
        env = {"KINDLE_EMAIL": "", "SENDER_EMAIL": "", "SENDER_PASS": ""}
        with patch.dict(os.environ, env, clear=False):
            for key in ("KINDLE_EMAIL", "SENDER_EMAIL", "SENDER_PASS"):
                os.environ.pop(key, None)

            with patch.object(
                __import__("engines.kindle_sender", fromlist=["_CONFIG_SEARCH_PATHS"]),
                "_CONFIG_SEARCH_PATHS",
                [cfg_path],
            ):
                with patch("engines.kindle_sender.smtplib.SMTP") as mock_smtp:
                    mock_server = MagicMock()
                    mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
                    mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

                    send_to_kindle(epub)

                    mock_server.login.assert_called_once_with("cfg@gmx.com", "cfgpass")

    def test_env_vars_override_config_file(self, tmp_path):
        """Environment variables take precedence over kindle.cfg."""
        from engines.kindle_sender import send_to_kindle, _CONFIG_SEARCH_PATHS

        cfg_path = self._write_cfg(tmp_path, (
            "[kindle]\n"
            "kindle_email = cfg@kindle.com\n"
            "sender_email = cfg@gmx.com\n"
            "sender_pass  = cfgpass\n"
        ))

        epub = tmp_path / "book.epub"
        epub.write_bytes(b"PK fake epub")

        env = {
            "KINDLE_EMAIL": "env@kindle.com",
            "SENDER_EMAIL": "env@gmx.com",
            "SENDER_PASS": "envpass",
        }
        with patch.dict(os.environ, env):
            with patch.object(
                __import__("engines.kindle_sender", fromlist=["_CONFIG_SEARCH_PATHS"]),
                "_CONFIG_SEARCH_PATHS",
                [cfg_path],
            ):
                with patch("engines.kindle_sender.smtplib.SMTP") as mock_smtp:
                    mock_server = MagicMock()
                    mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
                    mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

                    send_to_kindle(epub)

                    mock_server.login.assert_called_once_with("env@gmx.com", "envpass")

    def test_missing_config_and_env_raises(self, tmp_path):
        """Should raise ValueError when neither env vars nor config file
        provide credentials."""
        from engines.kindle_sender import send_to_kindle

        epub = tmp_path / "book.epub"
        epub.write_bytes(b"PK fake epub")

        with patch.dict(os.environ, {}, clear=False):
            for key in ("KINDLE_EMAIL", "SENDER_EMAIL", "SENDER_PASS"):
                os.environ.pop(key, None)

            with patch.object(
                __import__("engines.kindle_sender", fromlist=["_CONFIG_SEARCH_PATHS"]),
                "_CONFIG_SEARCH_PATHS",
                [tmp_path / "nonexistent.cfg"],
            ):
                with pytest.raises(ValueError, match="kindle.cfg"):
                    send_to_kindle(epub)


# ---------------------------------------------------------------------------
# kindle_sender: _load_config_file / _get_credential unit tests
# ---------------------------------------------------------------------------

class TestConfigHelpers:

    def test_load_config_file_returns_empty_when_no_file(self, tmp_path):
        from engines import kindle_sender

        with patch.object(kindle_sender, "_CONFIG_SEARCH_PATHS", [tmp_path / "nope.cfg"]):
            assert kindle_sender._load_config_file() == {}

    def test_get_credential_prefers_env(self):
        from engines.kindle_sender import _get_credential

        with patch.dict(os.environ, {"MY_KEY": "from_env"}):
            assert _get_credential("MY_KEY", {"my_key": "from_cfg"}) == "from_env"

    def test_get_credential_falls_back_to_config(self):
        from engines.kindle_sender import _get_credential

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MY_KEY", None)
            assert _get_credential("MY_KEY", {"my_key": "from_cfg"}) == "from_cfg"


# ---------------------------------------------------------------------------
# pdf_engine: Android font candidates
# ---------------------------------------------------------------------------

def test_android_font_paths_in_candidates():
    """setup_optional_fonts should include Android system font paths."""
    from engines.pdf_engine import setup_optional_fonts
    import inspect

    source = inspect.getsource(setup_optional_fonts)
    assert "/system/fonts/" in source, "Android font paths missing from candidates"


# ---------------------------------------------------------------------------
# mobile_publish: basic smoke test
# ---------------------------------------------------------------------------

def test_mobile_publish_main_missing_file(capsys):
    """mobile_publish.main() should print an error for a missing input file."""
    import mobile_publish

    with patch.object(mobile_publish, "INPUT_FILE", "/nonexistent/file.json"):
        mobile_publish.main()

    captured = capsys.readouterr()
    assert "[ERROR]" in captured.out
    assert "not found" in captured.out
