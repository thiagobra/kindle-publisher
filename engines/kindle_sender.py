"""Kindle sender — sends EPUB files to Kindle via GMX SMTP."""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

SMTP_HOST = "mail.gmx.com"
SMTP_PORT = 587


def send_to_kindle(filepath: Path, subject: str = "kindle document") -> None:
    """Send an EPUB file to the configured Kindle email via GMX SMTP.

    Required environment variables:
        KINDLE_EMAIL — Kindle's Send-to-Kindle address
        SENDER_EMAIL — GMX sender address
        SENDER_PASS  — GMX password
    """
    # -- Validate env vars --
    kindle_email = os.environ.get("KINDLE_EMAIL", "").strip()
    sender_email = os.environ.get("SENDER_EMAIL", "").strip()
    sender_pass = os.environ.get("SENDER_PASS", "").strip()

    missing = []
    if not kindle_email:
        missing.append("KINDLE_EMAIL")
    if not sender_email:
        missing.append("SENDER_EMAIL")
    if not sender_pass:
        missing.append("SENDER_PASS")
    if missing:
        raise ValueError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Set them with: setx VAR_NAME value"
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
