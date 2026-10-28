from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import INTERNAL, OFFICERS, can_edit, load_case, must_edit, require
from ..models import OPEN_STATUSES, Case, CaseEvent, CaseLink, Category, Institution, OverlapAlert, Unit, User
from ..services import mail, overlap, rules, workflow
from ..services.workflow import WorkflowError
from ..views import alert_view, case_row, event_view, steps

router = APIRouter(tags=["cases"])
reader = require(*INTERNAL)
officer = require(*OFFICERS)


def _fail(e: WorkflowError):
    raise HTTPException(e.status, {"message": e.message, **e.detail} if e.detail else e.message)


def _done(db: Session):
    db.commit()
    mail.kick()


def overlap_case_ids(db: Session) -> set[int]:
    ids: set[int] = set()
    for (cids,) in db.execute(select(OverlapAlert.case_ids).where(OverlapAlert.status == "open")).all():
        ids.update(cids)
    return ids


@router.get("/meta")
def meta(db: Session = Depends(get_db), user: User = Depends(reader)):
    return {
        "units": [{"id": u.id, "code": u.code, "name": u.name} for u in db.execute(select(Unit).order_by(Unit.id)).scalars()],
        "categories": [{"id": c.id, "name": c.name, "topic": c.topic, "sla_days": c.sla_days}
                       for c in db.execute(select(Category).order_by(Category.name)).scalars()],
        "action_types": rules.ACTION_TYPES,
        "officers": [{"id": u.id, "name": u.name, "unit_id": u.unit_id, "role": u.role} for u in
                     db.execute(select(User).where(User.role.in_(OFFICERS), User.is_active).order_by(User.name)).scalars()],
        "regions": sorted({r for (r,) in db.execute(select(Institution.region)).all() if r}),
        "institutions": [{"id": i.id, "name": i.name, "aicte_id": i.aicte_id, "city": i.city}
                         for i in db.execute(select(Institution).order_by(Institution.name)).scalars()],
    }


@router.get("/cases")
def list_cases(q: str = "", unit: str = "", region: str = "", category: str = "", status: str = "",
               date_from: date | None = None, date_to: date | None = None, overdue: bool = False,
               has_overlap: bool = False, institution_id: int | None = None, mine: bool = False,
               limit: int = 500, db: Session = Depends(get_db), user: User = Depends(reader)):
    """Every filter is also a URL parameter in the web app, so a view can be shared."""
    stmt = select(Case).outerjoin(Institution, Case.institution_id == Institution.id)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Case.case_id.ilike(like), Case.source_ref.ilike(like), Institution.name.ilike(like),
                              Institution.aicte_id.ilike(like), Case.raw_institution_text.ilike(like)))
    if unit:
        stmt = stmt.join(Unit, Case.unit_id == Unit.id).where(Unit.code == unit)
    if region:
        stmt = stmt.where(Institution.region == region)
    if category:
        stmt = stmt.join(Category, Case.category_id == Category.id).where(Category.name == category)
    if status == "OPEN":
        stmt = stmt.where(Case.status.in_(OPEN_STATUSES))
    elif status:
        stmt = stmt.where(Case.status == status)
    if date_from:
        stmt = stmt.where(Case.received_on >= date_from)
    if date_to:
        stmt = stmt.where(Case.received_on <= date_to)
    today = rules.today(db)
    if overdue:
        stmt = stmt.where(Case.status.in_(OPEN_STATUSES), Case.expected_disposal_on < today)
    if institution_id:
        stmt = stmt.where(or_(Case.institution_id == institution_id, Case.suggested_institution_id == institution_id))
    if mine:
        stmt = stmt.where(Case.assigned_officer_id == user.id)
    ov = overlap_case_ids(db)
    if has_overlap:
        stmt = stmt.where(Case.id.in_(ov or {-1}))
    pcts = rules.get(db, "sla_alert_pcts")
    rows = db.execute(stmt.order_by(Case.received_on.desc(), Case.id.desc()).limit(min(limit, 2000))).scalars().unique().all()
    return [case_row(c, today, pcts, c.id in ov) for c in rows]


def _urgency(r: dict) -> tuple:
    s = r["sla"]
    return (not r["has_overlap"], not s["overdue"], s["days_left"], r["received_on"])


@router.get("/today")
def today_register(db: Session = Depends(get_db), user: User = Depends(reader)):
    """'Today's register': the cases this person should act on, most urgent first,
    plus the one-sentence 'What to do now'."""
    today, pcts = rules.today(db), rules.get(db, "sla_alert_pcts")
    ov = overlap_case_ids(db)
    stmt = select(Case).where(Case.status.in_(OPEN_STATUSES))
    if user.role == "desk_officer":
        stmt = stmt.where(Case.unit_id == user.unit_id, or_(Case.assigned_officer_id == user.id, Case.assigned_officer_id.is_(None)))
    elif user.role == "unit_head":
        stmt = stmt.where(or_(Case.unit_id == user.unit_id, Case.transfer_to_unit_id == user.unit_id))
    elif user.role == "coordinator":
        stmt = stmt.where(or_(Case.id.in_(ov or {-1}), Case.escalation_level >= 2))
    elif user.role == "management":
        stmt = stmt.where(Case.escalation_level >= 3)
    rows = [case_row(c, today, pcts, c.id in ov) for c in db.execute(stmt).scalars().unique()]
    rows.sort(key=_urgency)
    need = [r for r in rows if r["sla"]["overdue"] or r["sla"]["days_left"] <= 3 or r["has_overlap"]
            or not r["officer"] or (r["transfer_to"] and user.role == "unit_head")]
    unmatched = 0
    if user.role in OFFICERS:
        unmatched = db.query(Case).filter(Case.unit_id == user.unit_id, Case.suggestion_status == "suggested",
                                          Case.status.in_(OPEN_STATUSES)).count()
    alerts = db.query(OverlapAlert).filter(OverlapAlert.status == "open").count()
    parts = []
    if need:
        parts.append(f"{len(need)} case{'s' if len(need) != 1 else ''} need action today")
    if user.role == "coordinator" and alerts:
        parts.append(f"{alerts} overlap alert{'s' if alerts != 1 else ''} to decide")
    if unmatched:
        parts.append(f"{unmatched} typed institution name{'s' if unmatched != 1 else ''} to confirm")
    overdue = sum(r["sla"]["overdue"] for r in rows)
    return {"rows": rows, "need_count": len(need), "overdue": overdue, "open_alerts": alerts, "unmatched": unmatched,
            "what_now": (", ".join(parts) + ".") if parts else "Nothing urgent today. Your register is up to date."}


class NewCase(BaseModel):
    category_id: int
    description: str
    institution_id: int | None = None
    raw_institution_text: str = ""
    received_on: date | None = None
    source_ref: str = ""
    priority: str = "Normal"
    complainant_name: str = ""
    complainant_email: str = ""
    officer_id: int | None = None


@router.post("/cases")
def create(body: NewCase, db: Session = Depends(get_db), user: User = Depends(officer)):
    try:
        c = workflow.create_case(db, user, unit_id=user.unit_id, **body.model_dump())
    except WorkflowError as e:
        _fail(e)
    _done(db)
    return {"case_id": c.case_id, "suggestion_status": c.suggestion_status}


@router.get("/cases/{ref}")
def detail(ref: str, db: Session = Depends(get_db), user: User = Depends(reader)):
    c = load_case(db, ref)
    today, pcts = rules.today(db), rules.get(db, "sla_alert_pcts")
    events = db.execute(select(CaseEvent).where(CaseEvent.case_id == c.id).order_by(CaseEvent.at, CaseEvent.id)).scalars().all()
    units = {u.id: u.code for u in db.execute(select(Unit)).scalars()}
    alerts = db.execute(select(OverlapAlert).where(OverlapAlert.case_ids.any(c.id)).order_by(OverlapAlert.id.desc())).scalars().all()
    links = db.execute(select(CaseLink).where(or_(CaseLink.a_case_id == c.id, CaseLink.b_case_id == c.id))).scalars().all()
    linked = []
    for lk in links:
        other = db.get(Case, lk.b_case_id if lk.a_case_id == c.id else lk.a_case_id)
        linked.append({"case_id": other.case_id, "unit": other.unit.code, "kind": lk.kind, "status": lk.status, "reason": lk.reason})
    related = []
    inst_id = c.institution_id or c.suggested_institution_id
    if inst_id:
        others = [x for x in overlap.institution_cases(db, inst_id) if x.id != c.id]
        scores = {p["b"] if p["a"] == c.id else p["a"]: p for p in overlap.score_pairs(db, [c, *others], cross_unit_only=False)
                  if c.id in (p["a"], p["b"])}
        related = [{**case_row(x, today, pcts), "pair": scores.get(x.id)} for x in others]
    row = case_row(c, today, pcts, any(a.status == "open" for a in alerts))
    return {**row, "description": c.description, "confidential": c.confidential,
            "complainant": c.complainant_name if user.role != "management" else None,
            "suggestion": {"score": c.suggestion_score, "reasons": c.suggestion_reasons,
                           "institution": row["suggested_institution"]} if c.suggestion_status == "suggested" else None,
            "transfer_reason": c.transfer_reason, "disposal_note": c.disposal_note,
            "steps": steps(c, {e.kind for e in events}), "events": [event_view(e) for e in events],
            "alerts": [alert_view(a, units) for a in alerts], "links": linked, "related": related,
            "recommendation": workflow.recommend(db, c),
            "can_edit": can_edit(user, c),
            "can_decide_transfer": user.role == "unit_head" and c.transfer_to_unit_id == user.unit_id}


class Act(BaseModel):
    action_type: str
    remarks: str = ""
    next_action: str = ""
    ack_reason: str = ""
    suggested: str = ""


class Reason(BaseModel):
    reason: str = ""


class Assign(BaseModel):
    officer_id: int


class Transfer(BaseModel):
    to_unit_id: int
    reason: str


class Decide(BaseModel):
    accept: bool
    note: str = ""


class Confirm(BaseModel):
    institution_id: int | None = None
    accept: bool = True


class Link(BaseModel):
    other: str
    kind: str = "same_issue"
    reason: str = ""


def _run(db: Session, fn, *args, **kw):
    try:
        out = fn(db, *args, **kw)
    except WorkflowError as e:
        db.rollback()
        _fail(e)
    _done(db)
    return out or {"ok": True}


@router.post("/cases/{ref}/action")
def act(ref: str, body: Act, db: Session = Depends(get_db), user: User = Depends(officer)):
    c = load_case(db, ref)
    must_edit(user, c)
    return _run(db, workflow.record_action, user, c, **body.model_dump())


@router.post("/cases/{ref}/assign")
def assign(ref: str, body: Assign, db: Session = Depends(get_db), user: User = Depends(officer)):
    c = load_case(db, ref)
    must_edit(user, c)
    return _run(db, workflow.assign, user, c, body.officer_id)


@router.post("/cases/{ref}/remark")
async def remark(ref: str, text: str = Form(""), file: UploadFile | None = File(None), db: Session = Depends(get_db),
                 user: User = Depends(officer)):
    c = load_case(db, ref)
    must_edit(user, c)
    att = None
    if file is not None and file.filename:
        data = await file.read()
        if len(data) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(413, f"Files up to {settings.max_upload_mb} MB only.")
        ext = Path(file.filename).suffix.lower()
        if ext not in (".pdf", ".png", ".jpg", ".jpeg", ".txt", ".docx"):
            raise HTTPException(400, "Attach a PDF, image, text or Word file.")
        name = f"{uuid.uuid4().hex}{ext}"
        Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
        (Path(settings.upload_dir) / name).write_bytes(data)
        att = (file.filename[:200], name)
    return _run(db, workflow.remark, user, c, text, att)


@router.get("/cases/{ref}/attachment/{event_id}")
def attachment(ref: str, event_id: int, db: Session = Depends(get_db), user: User = Depends(reader)):
    c = load_case(db, ref)
    ev = db.get(CaseEvent, event_id)
    if ev is None or ev.case_id != c.id or not ev.attachment_path:
        raise HTTPException(404, "No such attachment.")
    return FileResponse(Path(settings.upload_dir) / ev.attachment_path, filename=ev.attachment_name)


@router.post("/cases/{ref}/transfer")
def transfer(ref: str, body: Transfer, db: Session = Depends(get_db), user: User = Depends(officer)):
    c = load_case(db, ref)
    must_edit(user, c)
    return _run(db, workflow.request_transfer, user, c, body.to_unit_id, body.reason)


@router.post("/cases/{ref}/transfer/decide")
def transfer_decide(ref: str, body: Decide, db: Session = Depends(get_db), user: User = Depends(officer)):
    return _run(db, workflow.decide_transfer, user, load_case(db, ref), body.accept, body.note)


@router.post("/cases/{ref}/escalate")
def escalate(ref: str, body: Reason, db: Session = Depends(get_db), user: User = Depends(officer)):
    c = load_case(db, ref)
    must_edit(user, c)
    return _run(db, workflow.escalate, user, c, body.reason)


@router.post("/cases/{ref}/dispose")
def dispose(ref: str, body: Reason, db: Session = Depends(get_db), user: User = Depends(officer)):
    c = load_case(db, ref)
    must_edit(user, c)
    return _run(db, workflow.dispose, user, c, body.reason)


@router.post("/cases/{ref}/confirm-institution")
def confirm(ref: str, body: Confirm, db: Session = Depends(get_db), user: User = Depends(require(*OFFICERS, "coordinator"))):
    c = load_case(db, ref)
    if user.role != "coordinator":
        must_edit(user, c)
    return _run(db, workflow.confirm_institution, user, c, body.institution_id, body.accept)


@router.post("/cases/{ref}/link")
def link(ref: str, body: Link, db: Session = Depends(get_db), user: User = Depends(require(*OFFICERS, "coordinator"))):
    a, b = load_case(db, ref), load_case(db, body.other)
    if user.role != "coordinator":
        must_edit(user, a)
    _run(db, workflow.link_cases, user, a, b, body.kind, body.reason)
    return {"ok": True}
