"""Runs last: moves the demo clock and tampers with the audit log."""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, text

from app.models import Case, EmailLog
from app.services import sla


class C:
    def __init__(self, received, days, status="UNDER_PROCESS"):
        self.received_on, self.sla_days, self.status, self.disposed_on = received, days, status, None
        self.expected_disposal_on = received + timedelta(days=days)


def test_sla_maths():
    t = date(2026, 10, 27)
    pcts = [75, 90, 100]
    assert sla.stage(C(t - timedelta(days=10), 30), t, pcts) == 0
    assert sla.stage(C(t - timedelta(days=23), 30), t, pcts) == 1       # 77%
    assert sla.stage(C(t - timedelta(days=27), 30), t, pcts) == 2       # 90%
    assert sla.stage(C(t - timedelta(days=30), 30), t, pcts) == 3       # due today
    assert sla.stage(C(t - timedelta(days=31), 30), t, pcts) == 4       # overdue
    assert [sla.bucket(a) for a in (0, 15, 16, 30, 31, 60, 61)] == ["0-15", "0-15", "16-30", "16-30", "31-60", "31-60", "60+"]


def test_demo_clock_sends_digests_and_escalates(client, h, db):
    before = db.execute(select(EmailLog)).scalars().all()
    r = client.post("/admin/clock", json={"days": 30}, headers=h["admin"]).json()
    assert r["offset_days"] == 30 and r["sla_alerts"] > 0 and r["escalations"] > 0
    rows = db.execute(select(EmailLog).where(EmailLog.kind.in_(("sla", "escalation")))).scalars().all()
    assert len(rows) > len([b for b in before if b.kind in ("sla", "escalation")])
    assert len(rows) <= 20, "one digest per person, not one email per case"
    assert all(x.status == "NOT_CONFIGURED" for x in rows), "SMTP is off in tests: logged, never sent"
    sah = db.execute(select(Case).where(Case.description.like("Teaching staff unpaid for four months%"))).scalars().first()
    assert sah.escalation_level == 3
    client.post("/admin/clock", json={"reset": True}, headers=h["admin"])


def test_audit_chain_verifies_and_catches_tampering(client, h, db):
    assert client.post("/audit/verify", headers=h["management"]).json()["ok"] is True
    db.execute(text("ALTER TABLE audit_log DISABLE TRIGGER audit_log_no_update"))
    rid = db.execute(text("SELECT id FROM audit_log ORDER BY id DESC OFFSET 3 LIMIT 1")).scalar()
    db.execute(text("UPDATE audit_log SET summary = summary || ' (edited)' WHERE id = :i"), {"i": rid})
    db.execute(text("ALTER TABLE audit_log ENABLE TRIGGER audit_log_no_update"))
    db.commit()
    v = client.post("/audit/verify", headers=h["management"]).json()
    assert v["ok"] is False and v["broken_id"] == rid


def test_audit_log_refuses_updates(db):
    import pytest
    from sqlalchemy.exc import DBAPIError
    with pytest.raises(DBAPIError):
        db.execute(text("DELETE FROM audit_log WHERE id = 1"))
