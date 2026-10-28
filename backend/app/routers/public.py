"""Public endpoints: the demo clock, the privacy-preserving status check
(U8) and the complainant submission form. No personal data, remarks or
internal details ever leave through here."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import rate_limit
from ..models import Category, Unit
from ..security import mask_name
from ..services import mail, rules, workflow
from ..services.workflow import WorkflowError
from ..views import STATUS_LABEL

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/clock")
def clock(db: Session = Depends(get_db)):
    return {"offset_days": rules.offset_days(db), "today": rules.today(db).isoformat(),
            "real_today": rules.to_ist_date(rules.real_now()).isoformat(), "demo_mode": settings.demo_mode}


@router.get("/check/{ref}")
def check(ref: str, request: Request, db: Session = Depends(get_db)):
    rate_limit(request, "check", limit=30)
    from ..models import Case
    c = db.execute(select(Case).where(Case.case_id == ref.strip().upper())).scalars().first()
    if c is None or c.confidential:
        raise HTTPException(404, "No public record for this number. Check the number, or contact AICTE.")
    inst = c.institution or c.suggested_institution
    last = rules.to_ist_date(c.updated_at)
    return {"case_id": c.case_id, "institution": mask_name(inst.name if inst else c.raw_institution_text),
            "status": STATUS_LABEL[c.status], "last_updated": last.isoformat(), "synthetic": c.synthetic}


@router.get("/categories")
def categories(db: Session = Depends(get_db)):
    return [{"id": c.id, "name": c.name} for c in db.execute(select(Category).order_by(Category.name)).scalars()]


class Submit(BaseModel):
    institution_text: str
    category_id: int
    description: str
    name: str = ""
    email: str = ""


@router.post("/complaints")
def submit(body: Submit, request: Request, db: Session = Depends(get_db)):
    """Complainant-side form. Lands in PGRC's register with the typed
    institution name; the matcher suggests the institution for an officer to confirm."""
    rate_limit(request, "submit", limit=5)
    pgrc = db.execute(select(Unit).where(Unit.code == "PGRC")).scalars().first()
    try:
        c = workflow.create_case(db, None, unit_id=pgrc.id, category_id=body.category_id, description=body.description,
                                 raw_institution_text=body.institution_text[:250], source="Public form",
                                 complainant_name=body.name[:120], complainant_email=body.email[:200])
        c.synthetic = False
    except WorkflowError as e:
        db.rollback()
        raise HTTPException(e.status, e.message)
    db.commit()
    mail.kick()
    return {"case_id": c.case_id, "message": f"Your complaint is registered as {c.case_id}. Use this number to check its status."}
