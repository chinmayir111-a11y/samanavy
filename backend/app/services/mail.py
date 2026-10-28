"""Real SMTP email with a log row for every message (adapted from the
BHOOSHAKTI and JAMANAT email channel).

Messages are written to email_log first, then delivered by a background
thread so a slow SMTP server never blocks a request. Failures stay in the log
and the scheduler retries each once; the Admin can resend.

Demo users get plus-addresses of TEST_ALERT_EMAIL (see plus_address), so
every role's mail lands in one inbox. Synthetic institutions are never
emailed."""
from __future__ import annotations

import html
import logging
import smtplib
import ssl
import threading
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal
from ..models import EmailLog
from . import rules

log = logging.getLogger("samanvay.mail")
_lock = threading.Lock()


def plus_address(base: str, tag: str) -> str:
    """me@gmail.com + 'college' -> me+college@gmail.com"""
    if "@" not in base or not tag:
        return ""
    user, domain = base.split("@", 1)
    return f"{user.split('+')[0]}+{tag}@{domain}"


def queue(db: Session, *, to: str, subject: str, body: str, kind: str,
          case_id: int | None = None, action_url: str = "", action_label: str = "") -> EmailLog:
    text_body = body
    if action_url:
        text_body += f"\n\n{action_label or 'Open'}: {action_url}"
    text_body += "\n\n--\nSAMANVAY demo. Synthetic data, not an AICTE system."
    status, detail = "QUEUED", ""
    if not to:
        status, detail = "NO_ADDRESS", "No email address on file. Shown in the in-app inbox only."
    elif not settings.email_configured:
        status, detail = "NOT_CONFIGURED", "SMTP keys missing in .env. Logged, not sent."
    row = EmailLog(to_addr=to, subject=f"[SAMANVAY demo] {subject}", body=text_body,
                   html=_html(subject, body, action_url, action_label), kind=kind, case_id=case_id,
                   status=status, detail=detail, created_at=rules.now(db))
    db.add(row)
    db.flush()
    return row


def _html(subject: str, body: str, url: str, label: str) -> str:
    paras = "".join(f"<p style='margin:0 0 12px'>{html.escape(p)}</p>" for p in body.split("\n\n"))
    note = ""
    btn = (f"<p><a href='{html.escape(url)}' style='display:inline-block;background:#2D5A43;color:#fff;"
           f"padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:600'>"
           f"{html.escape(label or 'Open')}</a></p>") if url else ""
    return (f"<div style='font-family:Arial,sans-serif;font-size:16px;color:#1E3328;max-width:560px;background:#F7F8F3'>"
            f"<div style='background:#FFFFFF;color:#1E3328;padding:14px 18px;border:1px solid #D9E0D9;"
            f"border-bottom:2px solid #2D5A43;border-radius:8px 8px 0 0;font-family:Georgia,serif'>"
            f"<b>SAMANVAY</b> &middot; Institution complaint coordination (demo)</div>"
            f"<div style='background:#FFFFFF;border:1px solid #D9E0D9;border-top:0;padding:18px;border-radius:0 0 8px 8px'>"
            f"{note}<h2 style='font-size:19px;margin:0 0 12px;font-family:Georgia,serif'>{html.escape(subject)}</h2>{paras}{btn}"
            f"<p style='color:#55675C;font-size:13px;margin-top:20px'>Synthetic demo data. "
            f"This is not an AICTE system.</p></div></div>")


def _brevo_send(row: EmailLog) -> None:
    """Brevo transactional email over HTTPS (https://developers.brevo.com/reference/sendtransacemail).
    The sender address must be verified in Brevo."""
    import httpx
    name, addr = parseaddr(settings.smtp_from)
    r = httpx.post("https://api.brevo.com/v3/smtp/email", timeout=25,
                   headers={"api-key": settings.brevo_api_key, "accept": "application/json", "content-type": "application/json"},
                   json={"sender": {"name": name or "SAMANVAY demo", "email": addr or settings.smtp_user},
                         "to": [{"email": row.to_addr}], "subject": row.subject,
                         "htmlContent": row.html or html.escape(row.body), "textContent": row.body,
                         "headers": {"X-Samanvay-Kind": row.kind}})
    if r.status_code >= 300:
        raise RuntimeError(f"Brevo {r.status_code}: {r.text[:200]}")


def _send(row: EmailLog) -> str:
    if settings.email_provider == "brevo":
        _brevo_send(row)
        return "Accepted by Brevo (HTTPS API)"
    _smtp_send(row)
    return f"Accepted by {settings.smtp_host}"


def _smtp_send(row: EmailLog) -> None:
    msg = EmailMessage()
    name, addr = parseaddr(settings.smtp_from)
    msg["From"] = formataddr((name or "SAMANVAY demo", addr or settings.smtp_user))
    msg["To"] = row.to_addr
    msg["Subject"] = row.subject
    msg["X-Samanvay-Kind"] = row.kind
    msg.set_content(row.body)
    msg.add_alternative(row.html or html.escape(row.body), subtype="html")
    if settings.smtp_port == 465:
        with smtplib.SMTP_SSL(settings.smtp_host, 465, context=ssl.create_default_context(), timeout=25) as s:
            s.login(settings.smtp_user, settings.smtp_secret)
            s.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=25) as s:
            s.ehlo()
            if settings.smtp_starttls:
                s.starttls(context=ssl.create_default_context())
                s.ehlo()
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_secret)
            s.send_message(msg)


def deliver_one(db: Session, row: EmailLog) -> EmailLog:
    row.attempts += 1
    try:
        detail = _send(row)
    except Exception as exc:  # noqa: BLE001 - every failure is recorded
        row.status, row.detail = "FAILED", f"{type(exc).__name__}: {exc}"[:500]
        log.warning("email %s failed (attempt %s): %s", row.id, row.attempts, type(exc).__name__)
    else:
        row.status, row.detail, row.sent_at = "SENT", detail, rules.now(db)
        log.info("email %s sent (%s)", row.id, row.kind)
    db.flush()
    return row


def deliver_pending(retry_failed: bool = False) -> int:
    """Send every QUEUED message (and FAILED ones with attempts left)."""
    if not settings.email_configured:
        return 0
    with _lock:
        db = SessionLocal()
        try:
            statuses = ["QUEUED", "FAILED"] if retry_failed else ["QUEUED"]
            rows = db.execute(select(EmailLog).where(EmailLog.status.in_(statuses), EmailLog.attempts < 2)
                              .order_by(EmailLog.id)).scalars().all()
            for r in rows:
                deliver_one(db, r)
                db.commit()
            return len(rows)
        finally:
            db.close()


def kick() -> None:
    """Deliver queued mail in the background. Call after the request commits."""
    if settings.email_configured:
        threading.Thread(target=deliver_pending, daemon=True).start()
