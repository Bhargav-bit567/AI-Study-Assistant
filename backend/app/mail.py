"""Optional SMTP email helper."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Optional

from .config import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    SMTP_FROM,
    SMTP_STARTTLS,
    IS_SMTP_CONFIGURED,
)

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str, html: Optional[str] = None) -> bool:
    """Send an email using configured SMTP settings.

    Returns True if the email was accepted for delivery, False if SMTP is not
    configured or an error occurred. Errors are logged but never raised.
    """
    if not IS_SMTP_CONFIGURED:
        logger.info("SMTP not configured; skipping email to %s", to)
        return False

    msg = EmailMessage()
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject

    if html:
        msg.add_alternative(html, subtype="html")
        msg.set_content(body)
    else:
        msg.set_content(body)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            if SMTP_STARTTLS:
                server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        logger.info("Sent email to %s (subject: %s)", to, subject)
        return True
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to, exc)
        return False
