"""Kindle sender — sends EPUB files to Kindle via GMX SMTP."""

from __future__ import annotations

import configparser
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

SMTP_HOST = "mail.gmx.com"
SMTP_PORT = 587

# Config file locations searched in order (first match wins).
_CONFIG_SEARCH_PATHS = [
    Path("kindle.cfg"),                          # project directory
    Path.home() / "kindle.cfg",                  # home directory
    Path("/storage/emulated/0/kindle.cfg"),      # Android shared storage
]


def _load_config_file() -> dict[str, str]:
    """Load credentials from the first kindle.cfg found on disk.

    The file uses INI format::

        [kindle]
        KINDLE_EMAIL = you@kindle.com
        SENDER_EMAIL = you@gmx.com
        SENDER_PASS  = yourpassword
    """
    for path in _CONFIG_SEARCH_PATHS:
        if path.is_file():
            cfg = configparser.ConfigParser()
            cfg.read(str(path), encoding="utf-8")
            if cfg.has_section("kindle"):
                return dict(cfg.items("kindle"))
    return {}


def _get_credential(name: str, config: dict[str, str]) -> str:
    """Return credential from env var first, then config file (case-insensitive)."""
    value = os.environ.get(name, "").strip()
    if value:
        return value
    return config.get(name.lower(), "").strip()


def send_to_kindle(filepath: Path, subject: str = "kindle document") -> None:
    """Send an EPUB file to the configured Kindle email via GMX SMTP.

    Credentials are read from environment variables first, then from
    ``kindle.cfg`` (INI format with a ``[kindle]`` section).

    Required keys:
        KINDLE_EMAIL — Kindle's Send-to-Kindle address
        SENDER_EMAIL — GMX sender address
        SENDER_PASS  — GMX password
    """
    config = _load_config_file()

    kindle_email = _get_credential("KINDLE_EMAIL", config)
    sender_email = _get_credential("SENDER_EMAIL", config)
    sender_pass = _get_credential("SENDER_PASS", config)

    missing = []
    if not kindle_email:
        missing.append("KINDLE_EMAIL")
    if not sender_email:
        missing.append("SENDER_EMAIL")
    if not sender_pass:
        missing.append("SENDER_PASS")
    if missing:
        raise ValueError(
            f"Missing required credential(s): {', '.join(missing)}. "
            "Set via environment variables or in a kindle.cfg file "
            "(see kindle.cfg.example)."
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
