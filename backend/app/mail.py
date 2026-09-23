"""Optional email helper supporting Resend (preferred) and SMTP fallback."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Optional

from datetime import datetime, timezone

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


APP_NAME = "AI Study Assistant"
SENDER_NAME = "AI Study Assistant"


def _email_wrapper(title: str, preview: str, content_html: str) -> str:
    """Wrap content in a branded, responsive HTML email template."""
    year = datetime.now(timezone.utc).year
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <style>
    @media only screen and (max-width: 620px) {{
      .container {{ width: 100% !important; padding: 20px !important; }}
      .brand {{ font-size: 22px !important; }}
    }}
  </style>
</head>
<body style="margin:0;padding:0;background-color:#f4f6fb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#f4f6fb;padding:40px 0;">
    <tr>
      <td align="center">
        <table class="container" role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="background-color:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,0.06);">
          <tr>
            <td style="background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%);padding:40px 40px 32px;text-align:center;">
              <div class="brand" style="color:#ffffff;font-size:26px;font-weight:700;letter-spacing:-0.5px;">🎓 AI Study Assistant</div>
              <p style="color:rgba(255,255,255,0.85);margin:10px 0 0;font-size:14px;">{preview}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:36px 40px 28px;color:#1f2937;font-size:16px;line-height:1.7;">
              {content_html}
            </td>
          </tr>
          <tr>
            <td style="padding:0 40px 28px;">
              <p style="border-top:1px solid #e5e7eb;padding-top:20px;margin:0;color:#6b7280;font-size:13px;line-height:1.6;">
                You received this because you have an account on {APP_NAME}.<br/>
                &copy; {year} {APP_NAME}. All rights reserved.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _button(href: str, label: str) -> str:
    return f"""<a href="{href}" style="display:inline-block;background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%);color:#ffffff;text-decoration:none;padding:14px 28px;border-radius:10px;font-weight:600;font-size:15px;margin:8px 0;">{label}</a>"""


def send_welcome_email(to: str) -> bool:
    """Send a styled welcome email after signup."""
    subject = "Welcome to AI Study Assistant 🎉"
    body = (
        f"Hi there,\n\n"
        f"Welcome to {APP_NAME}! We're excited to help you learn smarter and faster.\n\n"
        f"Here's what you can do next:\n"
        f"- Upload a PDF and get an instant summary\n"
        f"- Generate MCQs to test your knowledge\n"
        f"- Track your study history and quiz scores\n\n"
        f"Get started now: https://barebrawn.store\n\n"
        f"Happy learning,\nThe {APP_NAME} Team"
    )
    html = _email_wrapper(
        title="Welcome",
        preview="Your AI-powered study companion is ready",
        content_html=f"""
          <p style="margin-top:0;">Hi there,</p>
          <p>Welcome to <strong>{APP_NAME}</strong>! We're thrilled to have you on board and excited to help you learn smarter, not harder.</p>
          <div style="background:#f9fafb;border-radius:12px;padding:20px;margin:24px 0;">
            <h3 style="margin-top:0;color:#4f46e5;font-size:16px;">What you can do next</h3>
            <ul style="margin:0;padding-left:20px;color:#374151;">
              <li>Upload any PDF and get a clear, structured summary</li>
              <li>Generate MCQs to test your understanding</li>
              <li>Track your study history and quiz scores</li>
            </ul>
          </div>
          <p style="text-align:center;margin:28px 0;">
            {_button("https://barebrawn.store", "Start Learning")}
          </p>
          <p style="margin-bottom:0;">Happy learning,<br/><strong>The {APP_NAME} Team</strong></p>
        """
    )
    return send_email(to=to, subject=subject, body=body, html=html)


def send_login_notification_email(to: str) -> bool:
    """Send a styled login alert email."""
    subject = "New sign-in to your AI Study Assistant account"
    body = (
        f"Hi there,\n\n"
        f"We noticed a successful sign-in to your {APP_NAME} account ({to}).\n\n"
        f"If this was you, you can safely ignore this email.\n\n"
        f"If this wasn't you, please change your password immediately.\n\n"
        f"— The {APP_NAME} Team"
    )
    html = _email_wrapper(
        title="Sign-in Alert",
        preview="We noticed a new sign-in to your account",
        content_html=f"""
          <p style="margin-top:0;">Hi there,</p>
          <p>We noticed a successful sign-in to your <strong>{APP_NAME}</strong> account:</p>
          <div style="background:#f9fafb;border-radius:12px;padding:20px;margin:24px 0;text-align:center;">
            <p style="margin:0;color:#374151;font-size:14px;">Signed in as</p>
            <p style="margin:8px 0 0;font-weight:600;color:#111827;font-size:16px;">{to}</p>
          </div>
          <p>If this was you, you can safely ignore this email.</p>
          <p>If you don't recognize this activity, please <strong>change your password immediately</strong>.</p>
          <p style="margin-bottom:0;">— <strong>The {APP_NAME} Team</strong></p>
        """
    )
    return send_email(to=to, subject=subject, body=body, html=html)


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
