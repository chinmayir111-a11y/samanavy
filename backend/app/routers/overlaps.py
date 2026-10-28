from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import INTERNAL, require
from ..models import Case, OverlapAlert, Unit, User
from ..services import mail, rules, workflow
from ..services.workflow import WorkflowError
from ..views import alert_view, case_row

router = APIRouter(prefix="/overlaps", tags=["overlaps"])
reader = require(*INTERNAL)


@router.get("")
def list_alerts(status: str = "open", db: Session = Depends(get_db), user: User = Depends(reader)):
    units = {u.id: u.code for u in db.execute(select(Unit)).scalars()}
    q = select(OverlapAlert).order_by(OverlapAlert.score.desc())
    if status != "all":
        q = q.where(OverlapAlert.status == status)
    alerts = db.execute(q).scalars().all()
    if user.role in ("desk_officer", "unit_head"):
        alerts = [a for a in alerts if user.unit_id in a.unit_ids]
    return [alert_view(a, units) for a in alerts]


@router.get("/{alert_id}")
def alert_detail(alert_id: int, db: Session = Depends(get_db), user: User = Depends(reader)):
    a = db.get(OverlapAlert, alert_id)
    if a is None:
        raise HTTPException(404, "No such alert.")
    units = {u.id: u.code for u in db.execute(select(Unit)).scalars()}
    today, pcts = rules.today(db), rules.get(db, "sla_alert_pcts")
    cases = {c.id: {**case_row(c, today, pcts, a.status == "open"), "description": c.description}
             for c in db.execute(select(Case).where(Case.id.in_(a.case_ids))).scalars().unique()}
    return {**alert_view(a, units), "cases": cases, "can_resolve": user.role == "coordinator",
            "unit_choices": [{"id": uid, "code": units[uid]} for uid in a.unit_ids]}


class Resolve(BaseModel):
    action: str
    reason: str
    lead_unit_id: int | None = None
    merge_into: int | None = None


@router.post("/{alert_id}/resolve")
def resolve(alert_id: int, body: Resolve, db: Session = Depends(get_db), user: User = Depends(require("coordinator"))):
    a = db.get(OverlapAlert, alert_id)
    if a is None:
        raise HTTPException(404, "No such alert.")
    try:
        workflow.resolve_alert(db, user, a, **body.model_dump())
    except WorkflowError as e:
        db.rollback()
        raise HTTPException(e.status, e.message)
    db.commit()
    mail.kick()
    return {"ok": True}
