"""SLA arithmetic and the daily job: SLA alerts at the configured percents,
due day, overdue, then the escalation ladder
(officer -> unit head -> coordinator -> management). All transparent rules."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import OPEN_STATUSES, Case, CaseEvent
from . import audit, notify, rules

BUCKETS = (("0-15", 0, 15), ("16-30", 16, 30), ("31-60", 31, 60), ("60+", 61, 10**6))
LADDER = {0: "Desk Officer", 1: "Unit Head", 2: "Coordinator", 3: "Management"}


def age_days(case: Case, today: date) -> int:
    end = case.disposed_on if case.status == "DISPOSED" and case.disposed_on else today
    return max(0, (end - case.received_on).days)


def days_left(case: Case, today: date) -> int:
    return (case.expected_disposal_on - today).days


def pct_used(case: Case, today: date) -> int:
    return round(100 * age_days(case, today) / max(case.sla_days, 1))


def bucket(age: int) -> str:
    return next(name for name, lo, hi in BUCKETS if lo <= age <= hi)


def stage(case: Case, today: date, pcts: list[int]) -> int:
    """0 none, 1..len(pcts) the percent stages (last one = due day), len(pcts)+1 overdue."""
    if days_left(case, today) < 0:
        return len(pcts) + 1
    used = pct_used(case, today)
    return sum(1 for p in pcts if used >= p)


def stage_label(st: int, pcts: list[int]) -> str:
    if st == 0:
        return ""
    if st > len(pcts):
        return "Overdue"
    p = pcts[st - 1]
    return "Due today" if p >= 100 else f"{p}% of SLA used"


def run_daily(db: Session) -> dict:
    today = rules.today(db)
    pcts = sorted(int(p) for p in rules.get(db, "sla_alert_pcts"))
    esc = {int(k): int(v) for k, v in rules.get(db, "escalation_days").items()}
    sla_digest, esc_digest = notify.Digest(), notify.Digest()
    alerts = escalations = 0
    cases = db.execute(select(Case).where(Case.status.in_(OPEN_STATUSES))).scalars().all()
    for c in cases:
        st = stage(c, today, pcts)
        if st > c.sla_stage:
            label = stage_label(st, pcts)
            left = days_left(c, today)
            body = (f"{c.case_id} ({c.institution.name if c.institution else c.raw_institution_text}): {label}. "
                    + (f"Expected disposal {c.expected_disposal_on:%d %b %Y}, {left} days left." if left >= 0
                       else f"{-left} days past the expected disposal date."))
            for u in notify.holders(db, c):
                sla_digest.add(db, u, title=label, body=body, kind="sla", case=c)
            db.add(CaseEvent(case_id=c.id, at=rules.now(db), kind="sla_alert", actor="System", unit_id=c.unit_id,
                             remarks=f"SLA alert: {label}.", meta={"stage": st}))
            c.sla_stage = st
            alerts += 1
        overdue = -days_left(c, today)
        if overdue > 0:
            target = max([lvl for lvl, d in esc.items() if overdue >= d] or [0])
            while c.escalation_level < target:
                c.escalation_level += 1
                lvl = c.escalation_level
                who = (notify.unit_heads(db, c.unit_id) if lvl == 1 else
                       notify.by_role(db, "coordinator") if lvl == 2 else notify.by_role(db, "management"))
                text = f"{c.case_id} is {overdue} days overdue and has moved up to the {LADDER[lvl]}."
                for u in who:
                    esc_digest.add(db, u, title=f"Escalated to {LADDER[lvl]}: {overdue} days overdue", body=text,
                                   kind="escalation", case=c)
                db.add(CaseEvent(case_id=c.id, at=rules.now(db), kind="escalated", actor="System (escalation ladder)",
                                 unit_id=c.unit_id, remarks=text, meta={"level": lvl, "auto": True}))
                audit.record(db, actor="System (escalation ladder)", action="escalated", entity="case", entity_id=c.id,
                             summary=text, new={"level": lvl})
                if c.status in ("RECEIVED", "UNDER_PROCESS"):
                    c.status = "ESCALATED"
                escalations += 1
    sent = sla_digest.send(db, "SLA alerts on your cases", "sla") + esc_digest.send(db, "Cases escalated to you", "escalation")
    rules.put(db, "last_daily_run", rules.now(db).isoformat())
    db.flush()
    return {"sla_alerts": alerts, "escalations": escalations, "digest_emails": sent}
