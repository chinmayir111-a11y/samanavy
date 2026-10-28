"""JSON shapes shared by the routes."""
from __future__ import annotations

from datetime import date

from .models import Case, CaseEvent, Institution, OverlapAlert
from .services import rules, sla

STATUS_LABEL = {"RECEIVED": "Received", "UNDER_PROCESS": "Under process", "TRANSFERRED": "Transferred",
                "ESCALATED": "Escalated", "DISPOSED": "Disposed"}


def inst_brief(i: Institution | None) -> dict | None:
    return {"id": i.id, "aicte_id": i.aicte_id, "name": i.name, "city": i.city, "region": i.region} if i else None


def holder(c: Case, today: date) -> dict:
    """U3 'Who is acting now?': unit, officer, days with them."""
    days = max(0, (today - rules.to_ist_date(c.held_since)).days)
    if c.status == "DISPOSED":
        return {"unit": c.unit.code, "officer": None, "days": 0, "text": f"Disposed by {c.unit.code}"}
    if c.transfer_to_unit_id:
        return {"unit": c.transfer_to_unit.code, "officer": None, "days": days,
                "text": f"Waiting for {c.transfer_to_unit.code} head to accept, {days} days"}
    who = c.officer.name if c.officer else "not assigned"
    return {"unit": c.unit.code, "officer": c.officer.name if c.officer else None, "days": days,
            "text": f"With {c.unit.code} · {who} · {days} days"}


def sla_view(c: Case, today: date, pcts: list[int]) -> dict:
    left = sla.days_left(c, today)
    st = 0 if c.status == "DISPOSED" else sla.stage(c, today, pcts)
    return {"days_left": left, "pct_used": sla.pct_used(c, today), "stage": st, "label": sla.stage_label(st, pcts),
            "overdue": c.status != "DISPOSED" and left < 0, "age": sla.age_days(c, today),
            "bucket": sla.bucket(sla.age_days(c, today))}


def steps(c: Case, kinds: set[str]) -> list[dict]:
    """Five circles: Received, Assigned, Under process, Action taken, Disposed."""
    reached = [True, bool(c.assigned_officer_id) or "assigned" in kinds,
               c.status != "RECEIVED", bool(c.last_action) or "action" in kinds, c.status == "DISPOSED"]
    cur = next((i for i, r in enumerate(reached) if not r), 5)
    labels = ["Received", "Assigned", "Under process", "Action taken", "Disposed"]
    return [{"n": i + 1, "label": lab, "state": "done" if i < cur else "current" if i == cur else "upcoming"}
            for i, lab in enumerate(labels)]


def case_row(c: Case, today: date, pcts: list[int], open_alert: bool = False) -> dict:
    inst = c.institution or c.suggested_institution
    return {
        "id": c.id, "case_id": c.case_id, "source_ref": c.source_ref, "source": c.source,
        "institution": inst_brief(c.institution), "suggested_institution": inst_brief(c.suggested_institution)
        if c.suggestion_status == "suggested" else None, "institution_name": inst.name if inst else c.raw_institution_text,
        "raw_institution_text": c.raw_institution_text, "suggestion_status": c.suggestion_status,
        "received_on": c.received_on.isoformat(), "category": c.category.name, "status": c.status,
        "status_label": STATUS_LABEL[c.status], "unit": c.unit.code, "unit_name": c.unit.name,
        "officer": c.officer.name if c.officer else None, "last_action": c.last_action,
        "last_action_on": c.last_action_on.isoformat() if c.last_action_on else None, "next_action": c.next_action,
        "expected_disposal_on": c.expected_disposal_on.isoformat(), "sla_days": c.sla_days, "priority": c.priority,
        "escalation_level": c.escalation_level, "holder": holder(c, today), "sla": sla_view(c, today, pcts),
        "has_overlap": open_alert, "region": inst.region if inst else "",
        "transfer_to": c.transfer_to_unit.code if c.transfer_to_unit else None,
    }


def event_view(e: CaseEvent) -> dict:
    return {"id": e.id, "at": e.at.isoformat(), "kind": e.kind, "actor": e.actor, "unit": e.unit.code if e.unit else None,
            "action_type": e.action_type, "remarks": e.remarks, "attachment": e.attachment_name or None,
            "meta": e.meta}


def alert_view(a: OverlapAlert, units: dict[int, str]) -> dict:
    return {"id": a.id, "institution": inst_brief(a.institution), "case_ids": a.case_ids,
            "units": [units[u] for u in a.unit_ids], "score": a.score, "pairs": a.pairs, "status": a.status,
            "lead_unit": units.get(a.lead_unit_id) if a.lead_unit_id else None, "resolution": a.resolution,
            "created_at": a.created_at.isoformat(), "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None}
