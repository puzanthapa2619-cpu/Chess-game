"""SMTP email sender for verification codes.

Reads credentials from .env. Falls back to writing the email to logs/emails/
if SMTP is not configured, so the app still runs during development.
"""
import os
import smtplib
import ssl
from email.message import EmailMessage
from datetime import datetime

from utils.paths import ROOT, ENV_FILE, LOGS
from utils.logger import get_logger

log = get_logger("mailer")


def _load_env():
    """Minimal .env loader (avoids the python-dotenv hard dependency)."""
    if not os.path.exists(ENV_FILE):
        return
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(ENV_FILE)
        return
    except Exception:
        pass
    with open(ENV_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()


def _fallback_log(to: str, subject: str, body: str) -> str:
    d = os.path.join(LOGS, "emails")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(
        d, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{to.replace('@','_at_')}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"To: {to}\nSubject: {subject}\n\n{body}\n")
    log.info("SMTP not configured; verification email saved to %s", path)
    return path


def send_verification_email(to_email: str, username: str, code: str) -> dict:
    """Send verification email; returns {'sent': bool, 'fallback': path_or_none}."""
    subject = "ChessMaster - Verify your email"
    body = (
        f"Hi {username},\n\n"
        f"Welcome to ChessMaster!\n\n"
        f"Your verification code is:  {code}\n\n"
        f"Enter this code in the app to verify your account.\n\n"
        f"If you did not sign up, you can safely ignore this email.\n\n"
        f"— The ChessMaster Team\n"
    )

    host = os.environ.get("SMTP_HOST", "").strip()
    port = int(os.environ.get("SMTP_PORT", "587").strip() or 587)
    user = os.environ.get("SMTP_USER", "").strip()
    pw   = os.environ.get("SMTP_PASS", "").strip()
    sender = os.environ.get("SMTP_FROM", user or "no-reply@chessmaster.local").strip()

    if not (host and user and pw):
        path = _fallback_log(to_email, subject, body)
        return {"sent": False, "fallback": path, "code": code}

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        ctx = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=20) as s:
                s.login(user, pw)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as s:
                s.ehlo()
                s.starttls(context=ctx)
                s.ehlo()
                s.login(user, pw)
                s.send_message(msg)
        log.info("Verification email sent to %s", to_email)
        return {"sent": True, "fallback": None, "code": code}
    except Exception as e:
        log.error("SMTP send failed: %s", e)
        path = _fallback_log(to_email, subject, body)
        return {"sent": False, "fallback": path, "code": code, "error": str(e)}
