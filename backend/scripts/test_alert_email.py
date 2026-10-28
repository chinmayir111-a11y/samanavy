#!/usr/bin/env python3
"""Send one real email to TEST_ALERT_EMAIL through the app's own sender and
confirm it is in the Email log as SENT. Fails loudly otherwise.

    python scripts/test_alert_email.py                 # local database + .env
    python scripts/test_alert_email.py --api URL       # a deployed backend (admin demo login)"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def local() -> int:
    from sqlalchemy import select

    from app.config import settings
    from app.db import session_scope
    from app.models import EmailLog
    from app.services import mail
    if not settings.email_configured or not settings.test_alert_email:
        print("FAIL: email is not configured (SMTP_* or BREVO_API_KEY, and TEST_ALERT_EMAIL, in .env).")
        return 1
    with session_scope() as db:
        row = mail.queue(db, to=settings.test_alert_email, kind="test", subject="Delivery test",
                         body="This is a delivery test from the SAMANVAY demo. If you can read it, email alerts work.")
        mail.deliver_one(db, row)
        rid = row.id
    with session_scope() as db:
        row = db.execute(select(EmailLog).where(EmailLog.id == rid)).scalar_one()
        print(f"Email log #{row.id} to {row.to_addr} via {settings.email_provider}: {row.status} ({row.detail})")
        return 0 if row.status == "SENT" else 1


def remote(api: str) -> int:
    import httpx
    with httpx.Client(base_url=api.rstrip("/"), timeout=60) as c:
        tok = c.post("/auth/demo-login", json={"username": "admin"}).json()["token"]
        r = c.post("/emails/test", headers={"Authorization": f"Bearer {tok}"}).json()
    print(f"{api}: email log #{r.get('id')}: {r.get('status')} ({r.get('detail')})")
    return 0 if r.get("status") == "SENT" else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--api")
    a = ap.parse_args()
    code = remote(a.api) if a.api else local()
    if code:
        print("EMAIL TEST FAILED", file=sys.stderr)
    sys.exit(code)
