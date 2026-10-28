"""Case workflow. Every change writes a case event, an audit entry and, where
someone must act, a notification. Functions raise WorkflowError with a plain
sentence; routes turn it into an HTTP error."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import OPEN_STATUSES, Case, CaseEvent, CaseLink, Category, Institution, OverlapAlert, Unit, User
from . import audit, notify, overlap, rules, sla


class WorkflowError(Exception):
    def __init__(self, message: str, status: int = 400, detail: dict | None = None) -> None:
        super().__init__(message)
        self.message, self.status, self.detail = message, status, detail or {}


def event(db: Session, case: Case, kind: str, actor: User | None, remarks: str = "", action_type: str = "",
          meta: dict | None = None, attachment: tuple[str, str] | None = None) -> CaseEvent:
    ev = CaseEvent(case_id=case.id, at=rules.now(db), kind=kind, actor_id=actor.id if actor else None,
                   actor=audit.actor_label(actor) if actor else "System", unit_id=actor.unit_id if actor and actor.unit_id else case.unit_id,
                   action_type=action_type, remarks=remarks, meta=meta or {},
                   attachment_name=attachment[0] if attachment else "", attachment_path=attachment[1] if attachment else "")
    db.add(ev)
    case.updated_at = rules.now(db)
    return ev


def _open(case: Case) -> None:
    if case.status not in OPEN_STATUSES:
        raise WorkflowError(f"{case.case_id} is already disposed.")


def next_case_id(db: Session, unit: Unit, year: int) -> str:
    prefix = f"{unit.code}-{year}-"
    last = db.execute(select(func.max(Case.case_id)).where(Case.case_id.like(prefix + "%"))).scalar()
    n = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}{n:04d}"


def create_case(db: Session, actor: User | None, *, unit_id: int, category_id: int, description: str,
                institution_id: int | None = None, raw_institution_text: str = "", received_on: date | None = None,
                source_ref: str = "", source: str = "Unit register", priority: str = "Normal",
                complainant_name: str = "", complainant_email: str = "", officer_id: int | None = None,
                confidential: bool = False, scan: bool = True) -> Case:
    unit, cat = db.get(Unit, unit_id), db.get(Category, category_id)
    if unit is None or cat is None:
        raise WorkflowError("Choose a unit and a category.")
    if not institution_id and not raw_institution_text.strip():
        raise WorkflowError("Pick the institution, or type its name as written in the complaint.")
    if len(description.strip()) < 15:
        raise WorkflowError("Describe the complaint in at least 15 characters.")
    received = received_on or rules.today(db)
    if received > rules.today(db):
        raise WorkflowError("The receipt date cannot be in the future.")
    now = rules.now(db)
    case = Case(case_id=next_case_id(db, unit, received.year), source_ref=source_ref, source=source,
                institution_id=institution_id, raw_institution_text=raw_institution_text.strip(),
                received_on=received, category_id=cat.id, description=description.strip(), status="RECEIVED",
                unit_id=unit.id, assigned_officer_id=officer_id, held_since=now, sla_days=cat.sla_days,
                expected_disposal_on=received + timedelta(days=cat.sla_days), priority=priority,
                complainant_name=complainant_name, complainant_email=complainant_email, confidential=confidential,
                suggestion_status="confirmed" if institution_id else "none", created_at=now, updated_at=now)
    db.add(case)
    db.flush()
    overlap.suggest_for(db, case)
    event(db, case, "received", actor, f"Received by {unit.code} ({source}).")
    if officer_id:
        case.status = "UNDER_PROCESS"
        event(db, case, "assigned", actor, f"Assigned to {db.get(User, officer_id).name}.")
    audit.record(db, actor=actor or "Public form", action="case_created", entity="case", entity_id=case.id,
                 summary=f"{case.case_id} created in {unit.code}: {cat.name}.",
                 new={"institution_id": institution_id, "typed": raw_institution_text, "unit": unit.code})
    db.flush()
    if scan:
        overlap.scan_case(db, case, actor)
    return case


def assign(db: Session, actor: User, case: Case, officer_id: int) -> None:
    _open(case)
    officer = db.get(User, officer_id)
    if officer is None or officer.unit_id != case.unit_id or officer.role not in ("desk_officer", "unit_head"):
        raise WorkflowError(f"Choose an officer of {case.unit.code}.")
    old = case.officer.name if case.officer else None
    case.assigned_officer_id, case.held_since = officer.id, rules.now(db)
    if case.status == "RECEIVED":
        case.status = "UNDER_PROCESS"
    event(db, case, "assigned", actor, f"Assigned to {officer.name}.")
    audit.record(db, actor=actor, action="assigned", entity="case", entity_id=case.id,
                 summary=f"{case.case_id} assigned to {officer.name}.", old={"officer": old}, new={"officer": officer.name})
    if officer.id != actor.id:
        notify.to_users(db, [officer], title=f"Case assigned to you: {case.case_id}", kind="assigned", case=case,
                        body=f"{actor.name} assigned {case.case_id} ({case.category.name}) to you.")


def record_action(db: Session, actor: User, case: Case, *, action_type: str, remarks: str, next_action: str = "",
                  ack_reason: str = "", suggested: str = "", attachment: tuple[str, str] | None = None) -> dict:
    """The conflict guard runs here: a regulatory action on an institution that
    another unit is also handling needs an acknowledgement with a reason.
    It never blocks; it asks once and records the answer."""
    _open(case)
    if not action_type:
        raise WorkflowError("Choose what was done.")
    others = overlap.conflicts(db, case) if rules.is_regulatory(action_type) else []
    if others and len(ack_reason.strip()) < 10:
        raise WorkflowError("Another unit has an open case on this institution. Read it, then continue with a reason.",
                            status=409, detail={"code": "conflict", "cases": others, "action_type": action_type})
    today = rules.today(db)
    if others:
        event(db, case, "conflict_acknowledged", actor, ack_reason.strip(), action_type,
              meta={"other_cases": [o["case_id"] for o in others]})
        audit.record(db, actor=actor, action="conflict_acknowledged", entity="case", entity_id=case.id,
                     summary=f"{actor.name} continued with '{action_type}' on {case.case_id} although "
                             f"{', '.join(o['unit'] + ' ' + o['case_id'] for o in others)} is open. Reason: {ack_reason.strip()}",
                     new={"other_cases": [o["case_id"] for o in others]})
    followed = bool(suggested) and suggested == action_type
    event(db, case, "action", actor, remarks, action_type, attachment=attachment,
          meta={"suggested": suggested, "followed": followed} if suggested else {})
    old = {"last_action": case.last_action, "status": case.status}
    case.last_action, case.last_action_on = action_type, today
    case.next_action = next_action or case.next_action
    if case.status == "RECEIVED":
        case.status = "UNDER_PROCESS"
    if not case.assigned_officer_id:
        case.assigned_officer_id, case.held_since = actor.id, rules.now(db)
    audit.record(db, actor=actor, action="action_recorded", entity="case", entity_id=case.id,
                 summary=f"{case.case_id}: {action_type}.", old=old, new={"last_action": action_type, "remarks": remarks})
    if others:
        inst = case.institution or case.suggested_institution
        people = []
        for uid in {db.execute(select(Case.unit_id).where(Case.case_id == o["case_id"])).scalar() for o in others}:
            people += notify.unit_officers(db, uid)
        notify.to_users(db, people + notify.by_role(db, "coordinator"), kind="conflict", case=case,
                        title=f"{case.unit.code} recorded '{action_type}' on {inst.name if inst else 'an institution'} you are also handling",
                        body=f"{actor.name} ({case.unit.code}) recorded '{action_type}' on {case.case_id}. "
                             f"Their reason for continuing: {ack_reason.strip()}")
    return {"conflict_acknowledged": bool(others)}


def remark(db: Session, actor: User, case: Case, text: str, attachment: tuple[str, str] | None = None) -> None:
    if len(text.strip()) < 3 and not attachment:
        raise WorkflowError("Write a remark or attach a file.")
    event(db, case, "remark", actor, text.strip(), attachment=attachment)
    audit.record(db, actor=actor, action="remark", entity="case", entity_id=case.id, summary=f"{case.case_id}: remark added.")


def request_transfer(db: Session, actor: User, case: Case, to_unit_id: int, reason: str) -> None:
    _open(case)
    to = db.get(Unit, to_unit_id)
    if to is None or to.id == case.unit_id:
        raise WorkflowError("Choose a different unit.")
    if len(reason.strip()) < 10:
        raise WorkflowError("Give a reason of at least 10 characters.")
    if case.transfer_to_unit_id:
        raise WorkflowError("A transfer is already waiting for acceptance.")
    case.transfer_to_unit_id, case.transfer_reason, case.status = to.id, reason.strip(), "TRANSFERRED"
    event(db, case, "transfer_requested", actor, f"Transfer to {to.code} requested: {reason.strip()}", meta={"to": to.code})
    audit.record(db, actor=actor, action="transfer_requested", entity="case", entity_id=case.id,
                 summary=f"{case.case_id}: transfer {case.unit.code} -> {to.code}. Reason: {reason.strip()}")
    notify.to_users(db, notify.unit_heads(db, to.id), kind="transfer", case=case,
                    title=f"Transfer waiting for you: {case.case_id} from {case.unit.code}",
                    body=f"{actor.name} asks {to.code} to take {case.case_id}. Reason: {reason.strip()}")


def decide_transfer(db: Session, actor: User, case: Case, accept: bool, note: str = "") -> None:
    if not case.transfer_to_unit_id:
        raise WorkflowError("No transfer is waiting on this case.")
    if actor.role != "unit_head" or actor.unit_id != case.transfer_to_unit_id:
        raise WorkflowError("Only the head of the receiving unit can accept or return this transfer.", status=403)
    to, frm = db.get(Unit, case.transfer_to_unit_id), case.unit
    if accept:
        case.unit_id, case.assigned_officer_id, case.held_since = to.id, None, rules.now(db)
        case.status = "RECEIVED"
        case.unit = to
        event(db, case, "transfer_accepted", actor, f"{to.code} accepted the transfer from {frm.code}. {note}".strip(),
              meta={"from": frm.code, "to": to.code})
    else:
        if len(note.strip()) < 10:
            raise WorkflowError("Say why the transfer is returned (at least 10 characters).")
        case.status = "UNDER_PROCESS" if case.assigned_officer_id else "RECEIVED"
        event(db, case, "transfer_rejected", actor, f"{to.code} returned the transfer: {note}", meta={"to": to.code})
    case.transfer_to_unit_id, case.transfer_reason = None, ""
    audit.record(db, actor=actor, action="transfer_accepted" if accept else "transfer_rejected", entity="case",
                 entity_id=case.id, summary=f"{case.case_id}: transfer {frm.code} -> {to.code} {'accepted' if accept else 'returned'}.")
    notify.to_users(db, notify.unit_officers(db, frm.id), kind="transfer", case=case,
                    title=f"{case.case_id}: transfer to {to.code} {'accepted' if accept else 'returned'}",
                    body=note or f"{to.code} {'now holds' if accept else 'returned'} the case.")
    db.flush()
    overlap.scan_case(db, case, actor)


def escalate(db: Session, actor: User, case: Case, reason: str) -> None:
    _open(case)
    if len(reason.strip()) < 10:
        raise WorkflowError("Give a reason of at least 10 characters.")
    case.escalation_level = max(case.escalation_level, 1 if actor.role == "desk_officer" else 2)
    case.status = "ESCALATED"
    lvl = sla.LADDER[case.escalation_level]
    event(db, case, "escalated", actor, f"Escalated to {lvl}: {reason.strip()}", meta={"level": case.escalation_level})
    audit.record(db, actor=actor, action="escalated", entity="case", entity_id=case.id,
                 summary=f"{case.case_id} escalated to {lvl}. Reason: {reason.strip()}")
    who = notify.unit_heads(db, case.unit_id) if case.escalation_level == 1 else notify.by_role(db, "coordinator")
    notify.to_users(db, who, kind="escalation", case=case, title=f"Escalated to you: {case.case_id}",
                    body=f"{actor.name} escalated {case.case_id}. Reason: {reason.strip()}")


def dispose(db: Session, actor: User, case: Case, note: str) -> None:
    _open(case)
    if len(note.strip()) < 10:
        raise WorkflowError("Write the decision (at least 10 characters).")
    case.status, case.disposed_on, case.disposal_note = "DISPOSED", rules.today(db), note.strip()
    case.transfer_to_unit_id = None
    event(db, case, "disposed", actor, note.strip())
    audit.record(db, actor=actor, action="disposed", entity="case", entity_id=case.id,
                 summary=f"{case.case_id} disposed: {note.strip()}")
    db.flush()
    overlap.scan_case(db, case, actor)


def confirm_institution(db: Session, actor: User, case: Case, institution_id: int | None, accept: bool = True) -> None:
    if not accept:
        case.suggestion_status = "rejected"
        event(db, case, "institution_rejected", actor, "Suggested institution rejected.")
        audit.record(db, actor=actor, action="match_rejected", entity="case", entity_id=case.id,
                     summary=f"{case.case_id}: suggested institution rejected.",
                     old={"suggested": case.suggested_institution_id})
        db.flush()
        return
    inst = db.get(Institution, institution_id or case.suggested_institution_id or 0)
    if inst is None:
        raise WorkflowError("Choose the institution.")
    was_suggestion = inst.id == case.suggested_institution_id
    case.institution_id, case.suggestion_status = inst.id, "confirmed"
    typed = case.raw_institution_text.strip()
    learned = False
    if typed and typed.lower() != inst.name.lower() and typed.lower() not in [a.lower() for a in inst.aliases or []]:
        inst.aliases = [*(inst.aliases or []), typed]   # next time this spelling matches exactly
        learned = True
    event(db, case, "institution_confirmed", actor,
          f"Institution confirmed: {inst.name} ({inst.aicte_id})" + (". Typed name saved as an alias." if learned else "."),
          meta={"suggested": was_suggestion, "score": case.suggestion_score})
    audit.record(db, actor=actor, action="match_confirmed", entity="case", entity_id=case.id,
                 summary=f"{case.case_id}: institution confirmed as {inst.name} ({inst.aicte_id}).",
                 new={"institution_id": inst.id, "was_suggestion": was_suggestion, "alias_learned": learned})
    db.flush()
    overlap.scan_case(db, case, actor)


def link_cases(db: Session, actor: User, a: Case, b: Case, kind: str, reason: str) -> CaseLink:
    if a.id == b.id:
        raise WorkflowError("Choose two different cases.")
    if kind not in ("same_institution", "same_issue", "duplicate"):
        raise WorkflowError("Unknown link type.")
    lo, hi = sorted((a.id, b.id))
    link = db.execute(select(CaseLink).where(CaseLink.a_case_id == lo, CaseLink.b_case_id == hi)).scalars().first()
    if link is None:
        link = CaseLink(a_case_id=lo, b_case_id=hi, created_at=rules.now(db), kind=kind, status="confirmed")
        db.add(link)
    link.kind, link.status, link.reason, link.created_by_id = kind, "confirmed", reason, actor.id
    for x, y in ((a, b), (b, a)):
        event(db, x, "linked", actor, f"Linked to {y.case_id} ({y.unit.code}) as {kind.replace('_', ' ')}. {reason}".strip(),
              meta={"other": y.case_id})
    audit.record(db, actor=actor, action="cases_linked", entity="case", entity_id=a.id,
                 summary=f"{a.case_id} and {b.case_id} linked as {kind}.")
    db.flush()
    return link


def merge(db: Session, actor: User, lead: Case, others: list[Case], reason: str) -> None:
    """Merge into one lead case: the others are disposed as 'merged' and point to the lead."""
    _open(lead)
    for o in others:
        if o.id == lead.id or o.status == "DISPOSED":
            continue
        link_cases(db, actor, lead, o, "duplicate", reason)
        o.status, o.disposed_on, o.merged_into_id = "DISPOSED", rules.today(db), lead.id
        o.disposal_note = f"Merged into lead case {lead.case_id} ({lead.unit.code}). {reason}".strip()
        event(db, o, "merged", actor, o.disposal_note, meta={"lead": lead.case_id})
        event(db, lead, "merged", actor, f"{o.case_id} ({o.unit.code}) merged into this case.", meta={"merged": o.case_id})
        audit.record(db, actor=actor, action="merged", entity="case", entity_id=o.id, summary=o.disposal_note)
        notify.to_users(db, notify.unit_officers(db, o.unit_id), kind="merge", case=o,
                        title=f"{o.case_id} merged into {lead.case_id}", body=o.disposal_note)


def resolve_alert(db: Session, actor: User, alert: OverlapAlert, *, action: str, lead_unit_id: int | None = None,
                  reason: str = "", merge_into: int | None = None) -> None:
    """action: lead (assign a lead unit), link, merge, dismiss."""
    if alert.status != "open":
        raise WorkflowError("This alert is already resolved.")
    if len(reason.strip()) < 10:
        raise WorkflowError("Write the decision and its reason (at least 10 characters).")
    cases = list(db.execute(select(Case).where(Case.id.in_(alert.case_ids))).scalars())
    now = rules.now(db)
    if action == "dismiss":
        alert.status = "dismissed"
        text = f"Overlap dismissed by {actor.name}: {reason}"
    elif action == "lead":
        unit = db.get(Unit, lead_unit_id or 0)
        if unit is None or unit.id not in alert.unit_ids:
            raise WorkflowError("Choose one of the units involved as the lead.")
        alert.lead_unit_id, alert.status = unit.id, "coordinated"
        text = f"Coordinator assigned {unit.code} as lead unit. {reason}"
        lead_cases = [c for c in cases if c.unit_id == unit.id]
        alert.lead_case_id = lead_cases[0].id if lead_cases else None
        for p in alert.pairs:
            a, b = db.get(Case, p["a"]), db.get(Case, p["b"])
            link_cases(db, actor, a, b, "duplicate" if p.get("duplicate_hint") else "same_institution", "Overlap alert resolved.")
        for c in cases:
            c.next_action = (f"Lead unit {unit.code}: proceed and keep other units informed" if c.unit_id == unit.id
                             else f"Coordinate with lead unit {unit.code} before any regulatory action")
    elif action == "link":
        alert.status = "coordinated"
        text = f"Cases linked for joint handling. {reason}"
        for p in alert.pairs:
            link_cases(db, actor, db.get(Case, p["a"]), db.get(Case, p["b"]), "same_institution", reason)
    elif action == "merge":
        lead = db.get(Case, merge_into or 0)
        if lead is None or lead.id not in alert.case_ids:
            raise WorkflowError("Choose the lead case to merge into.")
        merge(db, actor, lead, [c for c in cases if c.id != lead.id], reason)
        alert.status, alert.lead_case_id, alert.lead_unit_id = "coordinated", lead.id, lead.unit_id
        text = f"Cases merged into {lead.case_id}. {reason}"
    else:
        raise WorkflowError("Unknown decision.")
    alert.resolution, alert.resolved_by_id, alert.resolved_at, alert.updated_at = text.strip(), actor.id, now, now
    for c in cases:
        event(db, c, "overlap", actor, text.strip(), meta={"alert_id": alert.id, "decision": action})
    audit.record(db, actor=actor, action=f"overlap_{action}", entity="overlap_alert", entity_id=alert.id,
                 summary=f"{alert.institution.name}: {text.strip()}")
    people = []
    for uid in alert.unit_ids:
        people += notify.unit_officers(db, uid)
    notify.to_users(db, people, kind="overlap", alert_id=alert.id, title=f"Coordination decision: {alert.institution.name}",
                    body=text.strip(), url=f"{notify.settings.public_web_url}/overlaps/{alert.id}")
    db.flush()


# ------------------------------------------------------------ suggested next step

def recommend(db: Session, case: Case) -> dict | None:
    """Rule-based next step with the evidence behind it. Officers may ignore it;
    whether they followed it is recorded on the next action."""
    if case.status == "DISPOSED":
        return None
    today = rules.today(db)
    left = sla.days_left(case, today)
    since = (today - case.last_action_on).days if case.last_action_on else None

    def out(action: str, rule: str, *why: str, kind: str = "action") -> dict:
        return {"action": action, "rule": rule, "evidence": [w for w in why if w], "kind": kind}

    if case.transfer_to_unit_id:
        return out("Receiving unit head to accept or return the transfer", "R1 pending transfer",
                   f"Transfer to {case.transfer_to_unit.code} asked: {case.transfer_reason}", kind="transfer")
    alert = db.execute(select(OverlapAlert).where(OverlapAlert.status == "open",
                                                  OverlapAlert.case_ids.any(case.id))).scalars().first()
    if alert:
        return out("Wait for the coordinator's decision before any regulatory action", "R2 open overlap",
                   f"Open overlap alert, score {alert.score:.0f}: " + "; ".join(alert.pairs[0]["reasons"][:2]), kind="info")
    if not case.assigned_officer_id:
        return out("Assign an officer", "R3 unassigned", f"Received {(today - case.received_on).days} days ago, nobody assigned",
                   kind="assign")
    if left < 0 and case.escalation_level == 0:
        return out("Escalate to the Unit Head", "R4 overdue", f"{-left} days past the expected disposal date", kind="escalate")
    if case.last_action == "Reply received from institution":
        return out("Show-cause notice issued", "R5 reply in hand",
                   f"Reply received {since} days ago: examine it, then issue a show-cause notice or dispose")
    if case.last_action in ("Letter sent to institution seeking reply", "Documents called for") and since is not None and since >= 15:
        return out("Reminder sent to institution", "R6 no reply in 15 days", f"'{case.last_action}' {since} days ago, no reply recorded")
    if case.last_action == "Reminder sent to institution" and since is not None and since >= 15:
        return out("Hearing scheduled", "R7 reminder unanswered", f"Reminder sent {since} days ago, still no reply")
    if not case.last_action and (today - case.received_on).days >= 3:
        past = db.execute(select(Case).where(Case.category_id == case.category_id, Case.status == "DISPOSED",
                                             Case.id != case.id).order_by(Case.disposed_on.desc()).limit(1)).scalars().first()
        return out("Letter sent to institution seeking reply", "R8 no action yet",
                   f"No action in {(today - case.received_on).days} days",
                   f"Last similar case {past.case_id} was disposed: {past.disposal_note[:120]}" if past else "")
    if left <= 5:
        return out("Record the decision and dispose", "R9 near deadline", f"{left} days left before the expected disposal date",
                   kind="dispose")
    return None
