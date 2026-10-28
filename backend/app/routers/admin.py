"""Admin: users and invitations, units, categories and SLA days, matching
and alert rules, the demo clock, the email log and the audit log."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import INTERNAL, require
from ..models import AuditLog, Category, EmailLog, Notification, Unit, User
from ..services import audit, mail, rules, sla, sms
from .auth import issue_link

router = APIRouter(tags=["admin"])
admin = require("admin")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


@router.get("/admin/overview")
def overview(db: Session = Depends(get_db), user: User = Depends(admin)):
    return {
        "rules": rules.all_rules(db),
        "users": [{"id": u.id, "name": u.name, "email": u.email, "role": u.role, "title": u.title,
                   "unit": u.unit.code if u.unit else None, "active": u.is_active, "invited": not u.password_hash}
                  for u in db.execute(select(User).order_by(User.role, User.name)).scalars()],
        "units": [{"id": u.id, "code": u.code, "name": u.name, "description": u.description}
                  for u in db.execute(select(Unit).order_by(Unit.id)).scalars()],
        "categories": [{"id": c.id, "name": c.name, "topic": c.topic, "sla_days": c.sla_days}
                       for c in db.execute(select(Category).order_by(Category.name)).scalars()],
        "email": {"configured": settings.email_configured, "provider": settings.email_provider},
        "sms": sms.status(),
        "scheduler_heartbeat": rules.get(db, "scheduler_heartbeat"),
        "last_daily_run": rules.get(db, "last_daily_run"),
    }


class RulesIn(BaseModel):
    values: dict


@router.put("/admin/rules")
def put_rules(body: RulesIn, db: Session = Depends(get_db), user: User = Depends(admin)):
    old = rules.all_rules(db)
    for k, v in body.values.items():
        if k not in rules.EDITABLE:
            raise HTTPException(400, f"'{k}' cannot be edited.")
        if k in ("name_match_threshold", "overlap_alert_threshold") and not (40 <= float(v) <= 100):
            raise HTTPException(400, "Thresholds must be between 40 and 100.")
        rules.put(db, k, v)
    audit.record(db, actor=user, action="rules_changed", entity="setting", entity_id=None,
                 summary="Rules changed: " + ", ".join(body.values), old={k: old[k] for k in body.values}, new=body.values)
    db.commit()
    return rules.all_rules(db)


class CategoryIn(BaseModel):
    sla_days: int


@router.put("/admin/categories/{cid}")
def put_category(cid: int, body: CategoryIn, db: Session = Depends(get_db), user: User = Depends(admin)):
    c = db.get(Category, cid)
    if c is None or not (1 <= body.sla_days <= 365):
        raise HTTPException(400, "SLA must be 1 to 365 days.")
    old = c.sla_days
    c.sla_days = body.sla_days
    audit.record(db, actor=user, action="sla_changed", entity="category", entity_id=c.id,
                 summary=f"SLA for '{c.name}' changed from {old} to {body.sla_days} days (new cases only).")
    db.commit()
    return {"ok": True}


class UnitIn(BaseModel):
    name: str
    description: str = ""


@router.put("/admin/units/{uid}")
def put_unit(uid: int, body: UnitIn, db: Session = Depends(get_db), user: User = Depends(admin)):
    u = db.get(Unit, uid)
    if u is None or len(body.name.strip()) < 3:
        raise HTTPException(400, "Give the unit a name.")
    u.name, u.description = body.name.strip(), body.description
    audit.record(db, actor=user, action="unit_changed", entity="unit", entity_id=u.id, summary=f"Unit {u.code} renamed to {u.name}.")
    db.commit()
    return {"ok": True}


class Invite(BaseModel):
    name: str
    email: str
    role: str
    unit_id: int | None = None
    title: str = ""


@router.post("/admin/invite")
def invite(body: Invite, db: Session = Depends(get_db), user: User = Depends(admin)):
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Enter a valid email address.")
    if body.role not in ("desk_officer", "unit_head", "coordinator", "management", "admin"):
        raise HTTPException(400, "Choose a role.")
    if body.role in ("desk_officer", "unit_head") and not body.unit_id:
        raise HTTPException(400, "Officers belong to a unit: choose one.")
    if db.execute(select(User).where(func.lower(User.email) == email)).scalars().first():
        raise HTTPException(409, "Someone already uses this email.")
    u = User(email=email, username=email, name=body.name.strip(), title=body.title or body.role.replace("_", " ").title(),
             role=body.role, unit_id=body.unit_id if body.role in ("desk_officer", "unit_head") else None,
             is_active=False, created_at=rules.real_now())
    db.add(u)
    db.flush()
    link = issue_link(db, u, "invite")
    row = mail.queue(db, to=u.email, kind="invite", subject="You are invited to SAMANVAY",
                     body=f"Dear {u.name},\n\n{user.name} invited you to SAMANVAY as {u.title}. Open the link to choose "
                          f"your password. It works for 7 days.", action_url=link, action_label="Accept the invitation")
    audit.record(db, actor=user, action="user_invited", entity="user", entity_id=u.id, summary=f"Invited {u.email} as {u.role}.")
    db.commit()
    mail.kick()
    return {"ok": True, "email_status": row.status}


@router.post("/admin/users/{uid}/active")
def toggle_user(uid: int, db: Session = Depends(get_db), user: User = Depends(admin)):
    u = db.get(User, uid)
    if u is None or u.id == user.id:
        raise HTTPException(400, "You cannot change your own account here.")
    u.is_active = not u.is_active
    audit.record(db, actor=user, action="user_toggled", entity="user", entity_id=u.id,
                 summary=f"{u.email} {'enabled' if u.is_active else 'disabled'}.")
    db.commit()
    return {"active": u.is_active}


class Clock(BaseModel):
    days: int = 0
    reset: bool = False


@router.post("/admin/clock")
def demo_clock(body: Clock, db: Session = Depends(get_db), user: User = Depends(admin)):
    """U6: +7/+30/+90 days. Runs the daily SLA and escalation job at once so
    reminders and escalations appear without waiting."""
    if not settings.demo_mode:
        raise HTTPException(404, "Demo clock is off.")
    if body.days not in (0, 1, 7, 30, 90) and not body.reset:
        raise HTTPException(400, "Use +1, +7, +30 or +90 days.")
    old = rules.offset_days(db)
    new = 0 if body.reset else old + body.days
    rules.put(db, "demo_offset_days", new)
    audit.record(db, actor=user, action="demo_clock", entity="setting", entity_id=None,
                 summary=f"Demo clock moved from +{old} to +{new} days.")
    out = sla.run_daily(db)
    db.commit()
    mail.kick()
    return {"offset_days": new, "today": rules.today(db).isoformat(), **out}


@router.get("/emails")
def emails(db: Session = Depends(get_db), user: User = Depends(require("admin", "management", "coordinator"))):
    rows = db.execute(select(EmailLog).order_by(EmailLog.id.desc()).limit(300)).scalars()
    return [{"id": r.id, "to": r.to_addr, "subject": r.subject, "kind": r.kind, "status": r.status, "detail": r.detail,
             "attempts": r.attempts, "created_at": r.created_at.isoformat(),
             "sent_at": r.sent_at.isoformat() if r.sent_at else None} for r in rows]


@router.post("/emails/{eid}/resend")
def resend(eid: int, db: Session = Depends(get_db), user: User = Depends(admin)):
    r = db.get(EmailLog, eid)
    if r is None:
        raise HTTPException(404, "No such email.")
    if not settings.email_configured:
        raise HTTPException(400, "Email is not set up on this server.")
    mail.deliver_one(db, r)
    audit.record(db, actor=user, action="email_resent", entity="email", entity_id=r.id, summary=f"Email #{r.id} resent: {r.status}.")
    db.commit()
    return {"status": r.status, "detail": r.detail}


@router.post("/emails/test")
def test_email(db: Session = Depends(get_db), user: User = Depends(admin)):
    """Send one real email to TEST_ALERT_EMAIL through the same sender, synchronously."""
    if not settings.test_alert_email:
        raise HTTPException(400, "TEST_ALERT_EMAIL is not set.")
    r = mail.queue(db, to=settings.test_alert_email, kind="test", subject="Test email from SAMANVAY",
                   body="This is a delivery test from the SAMANVAY demo. If you can read it, email alerts work.")
    if r.status == "QUEUED":
        mail.deliver_one(db, r)
    db.commit()
    return {"id": r.id, "status": r.status, "detail": r.detail}


@router.get("/audit")
def audit_log(limit: int = 200, db: Session = Depends(get_db), user: User = Depends(require(*INTERNAL))):
    rows = db.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit, 1000))).scalars()
    return [{"id": r.id, "at": r.at_demo.isoformat(), "actor": r.actor, "action": r.action, "entity": r.entity,
             "entity_id": r.entity_id, "summary": r.summary, "hash": r.hash[:12]} for r in rows]


@router.post("/audit/verify")
def audit_verify(db: Session = Depends(get_db), user: User = Depends(require(*INTERNAL))):
    return audit.verify_chain(db)


@router.get("/inbox")
def inbox(db: Session = Depends(get_db), user: User = Depends(require(*INTERNAL))):
    rows = db.execute(select(Notification).where(Notification.user_id == user.id).order_by(Notification.id.desc()).limit(200)).scalars()
    from ..models import Case
    out = []
    for n in rows:
        ref = db.get(Case, n.case_id).case_id if n.case_id else None
        out.append({"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "case_id": ref, "alert_id": n.alert_id,
                    "at": n.created_at.isoformat(), "read": n.read_at is not None})
    return out


@router.post("/inbox/read")
def inbox_read(db: Session = Depends(get_db), user: User = Depends(require(*INTERNAL))):
    for n in db.execute(select(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))).scalars():
        n.read_at = rules.now(db)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------ college links and AICTE regions

@router.get("/admin/links")
def pending_links(db: Session = Depends(get_db), user: User = Depends(require("admin", "unit_head"))):
    rows = db.execute(select(User).where(User.role == "college", User.institution_link == "pending")).scalars()
    return [{"id": u.id, "name": u.name, "email": u.email, "user_type": u.user_type,
             "institution": u.institution.name if u.institution else "", "aicte_id": u.institution.aicte_id if u.institution else ""}
            for u in rows]


class LinkDecision(BaseModel):
    approve: bool


@router.post("/admin/links/{uid}")
def decide_link(uid: int, body: LinkDecision, db: Session = Depends(get_db), user: User = Depends(require("admin", "unit_head"))):
    u = db.get(User, uid)
    if u is None or u.institution_link != "pending":
        raise HTTPException(404, "No pending link for this person.")
    u.institution_link = "approved" if body.approve else "rejected"
    audit.record(db, actor=user, action="link_" + u.institution_link, entity="user", entity_id=u.id,
                 summary=f"{u.email} link to {u.institution.name if u.institution else '?'} {u.institution_link}.")
    db.commit()
    return {"link": u.institution_link}


@router.get("/admin/regions")
def get_regions(db: Session = Depends(get_db), user: User = Depends(admin)):
    from ..services import location
    return {"regions": location.regions(db), "names": location.REGION_NAMES, "states": location.states()}


class RegionsIn(BaseModel):
    regions: dict


@router.put("/admin/regions")
def put_regions(body: RegionsIn, db: Session = Depends(get_db), user: User = Depends(admin)):
    from ..services import location
    old = location.regions(db)
    for st, v in body.regions.items():
        if v.get("region") not in location.REGION_NAMES:
            raise HTTPException(400, f"Unknown region for {st}.")
    merged = {**old, **{k: {"region": v["region"], "basis": "set by Admin"} for k, v in body.regions.items()}}
    rules.put(db, "aicte_regions", merged)
    audit.record(db, actor=user, action="regions_changed", entity="setting", entity_id=None,
                 summary="AICTE region mapping changed: " + ", ".join(f"{k} -> {v['region']}" for k, v in body.regions.items()))
    db.commit()
    return merged
