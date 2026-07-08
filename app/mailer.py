"""Outgoing mail via the papaki mailbox SMTP (same pattern as the
studying-greece site). Fire-and-forget for notifications, synchronous for
password reset; everything is off until the SMTP_* env vars are set."""
from __future__ import annotations

import smtplib
import threading
from email.message import EmailMessage
from email.utils import formataddr

from app.config import settings


def is_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USER
                and settings.SMTP_PASSWORD and settings.NOTIFY_TO)


def send_email(subject: str, body: str, to: str | None = None) -> bool:
    if not is_configured():
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr(("DreamCatcher", settings.SMTP_FROM or settings.SMTP_USER))
    msg["To"] = to or settings.NOTIFY_TO
    msg.set_content(body)
    try:
        if settings.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as s:
                s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                s.send_message(msg)
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as s:
                s.starttls()
                s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                s.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001 - mail must never break a request
        print(f"mailer: send failed: {exc!r}")
        return False


def send_async(subject: str, body: str, to: str | None = None) -> None:
    threading.Thread(target=send_email, args=(subject, body, to),
                     daemon=True).start()
