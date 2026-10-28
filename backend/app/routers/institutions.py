from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import INTERNAL, require
from ..models import OPEN_STATUSES, Case, CaseEvent, Institution, OverlapAlert, Unit, User
from ..services import rules, sla
from ..views import alert_view, case_row, event_view, inst_brief

router = APIRouter(prefix="/institutions", tags=["institutions"])
reader = require(*INTERNAL)


def _cases(db: Session, inst_id: int) -> list[Case]:
    return list(db.execute(select(Case).where(or_(Case.institution_id == inst_id, (Case.suggested_institution_id == inst_id)
                                                  & (Case.suggestion_status == "suggested"))).order_by(Case.received_on)).scalars().unique())


def summary_sentence(open_cases: list[Case], alerts: int, today) -> str:
    """U2: 'What is AICTE doing about this college right now?' in one sentence."""
    if not open_cases:
        return "No open cases. Nothing pending with any AICTE unit."
    units = sorted({c.unit.code for c in open_cases})
    oldest = max(sla.age_days(c, today) for c in open_cases)
    overdue = sum(sla.days_left(c, today) < 0 for c in open_cases)
    s = (f"{len(open_cases)} open case{'s' if len(open_cases) != 1 else ''} across "
         f"{' and '.join(units) if len(units) <= 2 else ', '.join(units[:-1]) + ' and ' + units[-1]}")
    s += f", {alerts} overlap alert{'s' if alerts != 1 else ''}" if alerts else ", no overlap alerts"
    if overdue:
        s += f", {overdue} overdue"
    return s + f", oldest {oldest} days."


@router.get("")
def list_institutions(q: str = "", db: Session = Depends(get_db), user: User = Depends(reader)):
    today = rules.today(db)
    open_alerts = Counter(i for (i,) in db.execute(select(OverlapAlert.institution_id).where(OverlapAlert.status == "open")).all())
    out = []
    for i in db.execute(select(Institution).order_by(Institution.name)).scalars():
        if q and q.lower() not in (i.name + " " + i.aicte_id + " " + i.city + " " + " ".join(i.aliases or [])).lower():
            continue
        cs = [c for c in _cases(db, i.id) if c.status in OPEN_STATUSES]
        out.append({**inst_brief(i), "state": i.state, "open": len(cs), "units": sorted({c.unit.code for c in cs}),
                    "overdue": sum(sla.days_left(c, today) < 0 for c in cs), "alerts": open_alerts.get(i.id, 0),
                    "summary": summary_sentence(cs, open_alerts.get(i.id, 0), today)})
    return out


@router.get("/{inst_id}")
def institution_360(inst_id: int, db: Session = Depends(get_db), user: User = Depends(reader)):
    i = db.get(Institution, inst_id)
    if i is None:
        raise HTTPException(404, "No such institution.")
    today, pcts = rules.today(db), rules.get(db, "sla_alert_pcts")
    units = {u.id: u.code for u in db.execute(select(Unit)).scalars()}
    alerts = db.execute(select(OverlapAlert).where(OverlapAlert.institution_id == i.id).order_by(OverlapAlert.id.desc())).scalars().all()
    open_alert_cases = {cid for a in alerts if a.status == "open" for cid in a.case_ids}
    cases = _cases(db, i.id)
    rows = [case_row(c, today, pcts, c.id in open_alert_cases) for c in cases]
    open_cases = [c for c in cases if c.status in OPEN_STATUSES]
    by_unit: dict[str, Counter] = {}
    for c in cases:
        by_unit.setdefault(c.unit.code, Counter())[c.status] += 1
    events = db.execute(select(CaseEvent, Case.case_id).join(Case, Case.id == CaseEvent.case_id)
                        .where(CaseEvent.case_id.in_([c.id for c in cases] or [-1]))
                        .order_by(CaseEvent.at.desc(), CaseEvent.id.desc()).limit(60)).all()
    conflicts = db.execute(select(CaseEvent, Case.case_id).join(Case, Case.id == CaseEvent.case_id)
                           .where(CaseEvent.case_id.in_([c.id for c in cases] or [-1]), CaseEvent.kind == "conflict_acknowledged")).all()
    open_alerts = [a for a in alerts if a.status == "open"]
    return {
        "institution": {**inst_brief(i), "address": i.address, "state": i.state, "pin": i.pin, "kind": i.kind,
                        "aliases": i.aliases or [], "synthetic": i.synthetic},
        "summary": summary_sentence(open_cases, len(open_alerts), today),
        "alerts": [alert_view(a, units) for a in alerts],
        "cases": rows,
        "by_unit": {u: dict(cn) for u, cn in sorted(by_unit.items())},
        "pending_actions": [{"case_id": r["case_id"], "unit": r["unit"], "next_action": r["next_action"],
                             "holder": r["holder"]["text"]} for r in rows if r["status"] != "DISPOSED"],
        "decisions": [{"case_id": c.case_id, "unit": c.unit.code, "on": c.disposed_on.isoformat() if c.disposed_on else None,
                       "note": c.disposal_note} for c in cases if c.status == "DISPOSED"],
        "conflicts": [{**event_view(e), "case_id": cid} for e, cid in conflicts],
        "heat": [{"case_id": r["case_id"], "unit": r["unit"], "age": r["sla"]["age"], "bucket": r["sla"]["bucket"],
                  "overdue": r["sla"]["overdue"]} for r in rows if r["status"] != "DISPOSED"],
        "timeline": [{**event_view(e), "case_id": cid} for e, cid in events],
    }
