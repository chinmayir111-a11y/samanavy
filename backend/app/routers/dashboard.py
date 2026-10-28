from __future__ import annotations

from collections import Counter, defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import INTERNAL, require
from ..models import OPEN_STATUSES, Case, OverlapAlert, Unit, User
from ..services import rules, sla

router = APIRouter(tags=["dashboard"])


def stats(db: Session) -> dict:
    today = rules.today(db)
    cases = db.execute(select(Case)).scalars().unique().all()
    units = [u.code for u in db.execute(select(Unit).order_by(Unit.id)).scalars()]
    status = Counter(c.status for c in cases)
    open_cases = [c for c in cases if c.status in OPEN_STATUSES]
    overdue = [c for c in open_cases if sla.days_left(c, today) < 0]
    ageing = Counter(sla.bucket(sla.age_days(c, today)) for c in open_cases)
    workload: dict[str, Counter] = defaultdict(Counter)
    for c in open_cases:
        workload[c.unit.code]["open"] += 1
        workload[c.unit.code]["overdue"] += sla.days_left(c, today) < 0
    for c in cases:
        if c.status == "DISPOSED":
            workload[c.unit.code]["disposed"] += 1
    inst: dict[str, dict] = {}
    for c in open_cases:
        i = c.institution or c.suggested_institution
        key = i.name if i else c.raw_institution_text
        row = inst.setdefault(key, {"id": i.id if i else None, "name": key, "region": i.region if i else "", "open": 0,
                                    "overdue": 0, "units": set()})
        row["open"] += 1
        row["overdue"] += sla.days_left(c, today) < 0
        row["units"].add(c.unit.code)
    alerts = db.execute(select(OverlapAlert)).scalars().all()
    # State -> city drill-down over every institution, including ones created by sign-ups.
    from ..models import Institution
    open_by_inst: dict[int, int] = defaultdict(int)
    for c in open_cases:
        if c.institution_id:
            open_by_inst[c.institution_id] += 1
    geo: dict[str, dict] = {}
    for i in db.execute(select(Institution)).scalars():
        st = geo.setdefault(i.state or "Not known", {"state": i.state or "Not known", "region": i.region, "institutions": 0,
                                                     "open": 0, "cities": {}})
        st["institutions"] += 1
        st["open"] += open_by_inst[i.id]
        ct = st["cities"].setdefault(i.city or "Not known", {"city": i.city or "Not known", "district": i.district,
                                                             "institutions": [], "open": 0})
        ct["institutions"].append({"id": i.id, "name": i.name, "open": open_by_inst[i.id], "verified": i.verified})
        ct["open"] += open_by_inst[i.id]
    by_state = [{**v, "cities": sorted(v["cities"].values(), key=lambda x: -x["open"])}
                for v in sorted(geo.values(), key=lambda x: (-x["open"], x["state"]))]
    disposed = [c for c in cases if c.status == "DISPOSED"]
    in_time = sum(1 for c in disposed if c.disposed_on and c.disposed_on <= c.expected_disposal_on)
    return {
        "today": today.isoformat(),
        "totals": {"received": len(cases), "pending": len(open_cases), "received_status": status["RECEIVED"],
                   "under_process": status["UNDER_PROCESS"], "disposed": status["DISPOSED"],
                   "transferred": status["TRANSFERRED"], "escalated": status["ESCALATED"], "overdue": len(overdue),
                   "open_alerts": sum(a.status == "open" for a in alerts)},
        "disposal_rate": round(100 * len(disposed) / len(cases), 1) if cases else 0,
        "disposed_in_time_pct": round(100 * in_time / len(disposed), 1) if disposed else 0,
        "avg_open_age": round(sum(sla.age_days(c, today) for c in open_cases) / len(open_cases), 1) if open_cases else 0,
        "ageing": [{"bucket": b, "count": ageing.get(b, 0)} for b, _, _ in sla.BUCKETS],
        "workload": [{"unit": u, **{k: workload[u][k] for k in ("open", "overdue", "disposed")}} for u in units],
        "institutions": sorted(({**r, "units": sorted(r["units"])} for r in inst.values()),
                               key=lambda r: (-r["overdue"], -len(r["units"]), -r["open"])),
        "by_state": by_state,
        "alerts": {"open": sum(a.status == "open" for a in alerts), "coordinated": sum(a.status == "coordinated" for a in alerts),
                   "dismissed": sum(a.status == "dismissed" for a in alerts)},
    }


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(require(*INTERNAL))):
    return stats(db)
