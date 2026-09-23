"""Optional email helper supporting Resend (preferred) and SMTP fallback."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Optional

from .config import (
    RESEND_API_KEY,
    RESEND_FROM_EMAIL,
    IS_RESEND_CONFIGURED,
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
    """Send an email using Resend if configured, otherwise SMTP.

    Returns True if the email was accepted for delivery, False otherwise.
    Errors are logged but never raised.
    """
    if IS_RESEND_CONFIGURED:
        return _send_resend(to, subject, body, html)

    if IS_SMTP_CONFIGURED:
        return _send_smtp(to, subject, body, html)

    logger.info("Email not configured; skipping email to %s", to)
    return False


def _send_resend(to: str, subject: str, body: str, html: Optional[str] = None) -> bool:
    try:
        import resend
    except ImportError as exc:
        logger.warning("Resend package not installed; skipping email to %s: %s", to, exc)
        return False

    resend.api_key = RESEND_API_KEY

    params = {
        "from": RESEND_FROM_EMAIL,
        "to": [to],
        "subject": subject,
    }
    if html:
        params["html"] = html
        params["text"] = body
    else:
        params["text"] = body

    try:
        response = resend.Emails.send(params)
        logger.info("Sent Resend email to %s (subject: %s), id=%s", to, subject, response.get("id", "unknown"))
        return True
    except Exception as exc:
        logger.warning("Failed to send Resend email to %s: %s", to, exc)
        return False


def _send_smtp(to: str, subject: str, body: str, html: Optional[str] = None) -> bool:
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
        logger.info("Sent SMTP email to %s (subject: %s)", to, subject)
        return True
    except Exception as exc:
        logger.warning("Could not send SMTP email to %s: %s", to, exc)
        return False
