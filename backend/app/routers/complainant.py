"""College users: file and track their own complaints, and location lookup for sign-up.

The system, not the complainant, picks the unit (from the category) and runs overlap
detection. Complainants see only their own complaints, unit names (never officers),
plain-language messages and the decision; never internal remarks or other complaints."""
from __future__ import annotations

import io
import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import rate_limit, require
from ..models import Case, CaseEvent, Category, Institution, Unit, User
from ..services import location, mail, matching, rules, sla, workflow
from ..services.workflow import WorkflowError
from ..views import steps

router = APIRouter(tags=["complainant"])
college = require("college")

# Short list for first-time users -> (internal category, unit that handles it).
CATEGORIES = [
    {"key": "fees", "label": "Fees and refunds", "example": "Extra fees, no receipt, refund not paid after leaving", "category": "Excess fee / refund", "unit": "PGRC"},
    {"key": "faculty", "label": "Faculty and teaching", "example": "No teachers for a subject, classes not held", "category": "Faculty shortage / qualification", "unit": "PGRC"},
    {"key": "facilities", "label": "Facilities", "example": "Labs, library, hostel or classrooms missing or unsafe", "category": "Infrastructure deficiency", "unit": "RB"},
    {"key": "certificates", "label": "Certificates and documents", "example": "Original certificates or transfer certificate held back", "category": "Certificates withheld", "unit": "PGRC"},
    {"key": "approval", "label": "Approval or affiliation", "example": "Course may not be approved, college changed name or place", "category": "Approval / affiliation dispute", "unit": "AB"},
    {"key": "harassment", "label": "Harassment or safety", "example": "Ragging, threats, harassment by staff or students", "category": "Harassment / ragging", "unit": "PGRC"},
    {"key": "other", "label": "Other", "example": "Anything else about your college", "category": "Other grievance", "unit": "PGRC"},
]
MAX_FILE_MB, MAX_FILES = 5, 5
MAGIC = {".pdf": [b"%PDF"], ".png": [b"\x89PNG"], ".jpg": [b"\xff\xd8\xff"], ".jpeg": [b"\xff\xd8\xff"]}
PLAIN = {
    "Letter sent to institution seeking reply": "AICTE has written to the college and asked for a reply.",
    "Reminder sent to institution": "AICTE has reminded the college to reply.",
    "Reply received from institution": "The college has replied. AICTE is checking the reply.",
    "Documents called for": "AICTE has asked the college for documents.",
    "Hearing scheduled": "A hearing has been fixed with the college.",
    "Inspection ordered": "AICTE has ordered an inspection of the college.",
    "Show-cause notice issued": "AICTE has asked the college to explain itself (show-cause notice).",
    "Complainant informed": "AICTE has sent you an update by email.",
}


@router.get("/my/categories")
def categories():
    return [{k: c[k] for k in ("key", "label", "example")} for c in CATEGORIES]


class NewComplaint(BaseModel):
    category_key: str
    description: str
    happened_on: date | None = None


@router.post("/my/complaints")
def file_complaint(body: NewComplaint, request: Request, db: Session = Depends(get_db), user: User = Depends(college)):
    rate_limit(request, f"complaint:{user.id}", limit=10)
    c = next((x for x in CATEGORIES if x["key"] == body.category_key), None)
    if c is None:
        raise HTTPException(400, {"message": "Choose what the complaint is about.", "field": "category"})
    if len(body.description.strip()) < 20:
        raise HTTPException(400, {"message": "Please write at least 20 characters so the officer understands the problem.", "field": "description"})
    if body.happened_on and body.happened_on > rules.today(db):
        raise HTTPException(400, {"message": "The date cannot be in the future.", "field": "happened_on"})
    if not user.institution_id:
        raise HTTPException(400, {"message": "Add your college to your account first.", "field": "college"})
    cat = db.execute(select(Category).where(Category.name == c["category"])).scalars().first()
    unit = db.execute(select(Unit).where(Unit.code == c["unit"])).scalars().first()
    inst = db.get(Institution, user.institution_id)
    try:
        case = workflow.create_case(db, user, unit_id=unit.id, category_id=cat.id, description=body.description,
                                    institution_id=inst.id, source="Complainant portal",
                                    complainant_name=user.name, complainant_email=user.email)
    except WorkflowError as e:
        db.rollback()
        raise HTTPException(e.status, e.message)
    case.complainant_user_id, case.happened_on, case.synthetic = user.id, body.happened_on, False
    mail.queue(db, to=user.email, kind="receipt", case_id=case.id, subject=f"We received your complaint {case.case_id}",
               body=(f"Dear {user.name},\n\nYour complaint about {inst.name} is registered as {case.case_id}.\n\n"
                     "What happens next:\n1. Received: it is in AICTE's register now.\n2. It is given to the right AICTE unit.\n"
                     "3. We will email you each time it moves."),
               action_url=f"{settings.public_web_url}/my/{case.case_id}", action_label="Track this complaint")
    db.commit()
    mail.kick()
    return {"reference": case.case_id}


@router.post("/my/complaints/{ref}/files")
async def upload(ref: str, files: list[UploadFile] = File(...), db: Session = Depends(get_db), user: User = Depends(college)):
    case = _own(db, ref, user)
    have = db.query(CaseEvent).filter(CaseEvent.case_id == case.id, CaseEvent.kind == "evidence").count()
    if have + len(files) > MAX_FILES:
        raise HTTPException(400, f"Up to {MAX_FILES} files per complaint.")
    saved = []
    for f in files:
        data = await f.read()
        ext = Path(f.filename or "").suffix.lower()
        if ext not in MAGIC:
            raise HTTPException(400, f"'{f.filename}': only PDF, JPG and PNG files can be added.")
        if len(data) > MAX_FILE_MB * 1024 * 1024:
            raise HTTPException(413, f"'{f.filename}' is larger than {MAX_FILE_MB} MB.")
        if not any(data.startswith(m) for m in MAGIC[ext]):
            raise HTTPException(400, f"'{f.filename}' is not really a {ext[1:].upper()} file.")
        name = f"{uuid.uuid4().hex}{ext}"
        Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
        (Path(settings.upload_dir) / name).write_bytes(data)
        db.add(CaseEvent(case_id=case.id, at=rules.now(db), kind="evidence", actor_id=user.id, actor=f"{user.name} (complainant)",
                         unit_id=case.unit_id, remarks="Proof added by the complainant.", attachment_name=(f.filename or name)[:200],
                         attachment_path=name))
        saved.append(f.filename)
    db.commit()
    return {"saved": saved}


def _own(db: Session, ref: str, user: User) -> Case:
    case = db.execute(select(Case).where(Case.case_id == ref.upper())).scalars().first()
    if case is None or case.complainant_user_id != user.id:
        raise HTTPException(404, "No complaint with this number in your account.")
    return case


def _label(case: Case) -> str:
    return next((c["label"] for c in CATEGORIES if c["category"] == case.category.name), case.category.name)


@router.get("/my/complaints")
def my_complaints(db: Session = Depends(get_db), user: User = Depends(college)):
    rows = db.execute(select(Case).where(Case.complainant_user_id == user.id).order_by(Case.id.desc())).scalars().unique()
    return [{"reference": c.case_id, "about": _label(c), "college": c.institution.name if c.institution else "",
             "received_on": c.received_on.isoformat(), "status": _status(c)} for c in rows]


def _status(c: Case) -> str:
    return {"RECEIVED": "Received", "UNDER_PROCESS": "Being worked on", "TRANSFERRED": "Being moved to another unit",
            "ESCALATED": "Being worked on (raised to a senior officer)", "DISPOSED": "Closed"}[c.status]


@router.get("/my/complaints/{ref}")
def track(ref: str, db: Session = Depends(get_db), user: User = Depends(college)):
    c = _own(db, ref, user)
    today = rules.today(db)
    events = db.execute(select(CaseEvent).where(CaseEvent.case_id == c.id).order_by(CaseEvent.at, CaseEvent.id)).scalars().all()
    msgs = []
    for e in events:
        text = None
        if e.kind == "received":
            text = "We received your complaint."
        elif e.kind == "assigned":
            text = f"An officer of the {e.unit.name if e.unit else c.unit.name} is handling it."
        elif e.kind == "transfer_accepted":
            text = f"It was moved to the {c.unit.name}, which handles this kind of complaint."
        elif e.kind == "action" and e.action_type in PLAIN:
            text = PLAIN[e.action_type]
        elif e.kind == "escalated":
            text = "It has been raised to a senior officer."
        elif e.kind == "evidence":
            text = f"You added a file: {e.attachment_name}"
        elif e.kind == "disposed":
            text = f"Your complaint is closed. Decision: {c.disposal_note}"
        elif e.kind == "merged" and c.merged_into_id:
            text = "It was joined with another complaint about the same problem, so one officer handles both."
        if text and (not msgs or msgs[-1]["text"] != text):
            msgs.append({"at": e.at.isoformat(), "text": text})
    held = max(0, (today - rules.to_ist_date(c.held_since)).days)
    return {"reference": c.case_id, "about": _label(c), "description": c.description,
            "college": c.institution.name if c.institution else "", "received_on": c.received_on.isoformat(),
            "status": _status(c), "unit": c.unit.name, "days_waiting": held, "age": sla.age_days(c, today),
            "steps": steps(c, {e.kind for e in events}), "messages": msgs,
            "files": [e.attachment_name for e in events if e.kind == "evidence"]}


@router.get("/public/qr/{ref}.svg")
def qr(ref: str):
    import qrcode
    import qrcode.image.svg
    img = qrcode.make(f"{settings.public_web_url}/check/{ref.upper()}", image_factory=qrcode.image.svg.SvgPathImage, box_size=8)
    buf = io.BytesIO()
    img.save(buf)
    return Response(buf.getvalue(), media_type="image/svg+xml")


# ------------------------------------------------------------ location + college lookup (sign-up, no login)

@router.get("/public/location")
def resolve_location(city: str = "", pin: str = "", request: Request = None, db: Session = Depends(get_db)):
    rate_limit(request, "loc", limit=300)
    return location.resolve(city, pin, db)


@router.get("/public/states")
def states():
    return location.states()


@router.get("/public/districts")
def districts(state: str):
    return location.districts(state)


@router.get("/public/colleges")
def colleges(q: str = "", request: Request = None, db: Session = Depends(get_db)):
    """Suggestions while typing a college name. Names and cities only."""
    rate_limit(request, "colleges", limit=300)
    if len(q.strip()) < 2:
        return []
    out = []
    for i in db.execute(select(Institution)).scalars():
        m = matching.name_score(q, [i.name, *(i.aliases or [])])
        if m.score >= 60 or q.lower() in i.name.lower():
            out.append((m.score, {"id": i.id, "name": i.name, "city": i.city, "state": i.state}))
    return [x for _, x in sorted(out, key=lambda t: -t[0])[:6]]
