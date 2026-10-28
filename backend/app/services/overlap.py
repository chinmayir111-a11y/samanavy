"""Overlap alerts, institution suggestions and the conflict guard, on top of
the scoring in matching.py. Humans decide every outcome; the system only
raises, explains and records."""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import OPEN_STATUSES, Case, CaseEvent, Institution, OverlapAlert, Unit
from . import audit, matching, notify, rules


def view(c: Case) -> matching.CaseView:
    inst = c.institution or (c.suggested_institution if c.suggestion_status == "suggested" else None)
    return matching.CaseView(
        id=c.id, case_id=c.case_id, unit=c.unit.code, institution_id=inst.id if inst else None,
        institution_name=inst.name if inst else "", typed_name=c.raw_institution_text or (inst.name if inst else ""),
        aicte_id_confirmed=c.institution_id is not None, category=c.category.name, topic=c.category.topic,
        description=c.description, received_on=c.received_on)


def tfidf(db: Session) -> matching.TfIdf:
    return matching.TfIdf(db.execute(select(Case.description)).scalars())


def _key(a: int, b: int) -> str:
    return f"{min(a, b)}-{max(a, b)}"


def institution_cases(db: Session, inst_id: int, open_only: bool = True) -> list[Case]:
    q = select(Case).where(or_(Case.institution_id == inst_id,
                               (Case.suggested_institution_id == inst_id) & (Case.suggestion_status == "suggested")))
    if open_only:
        q = q.where(Case.status.in_(OPEN_STATUSES))
    return list(db.execute(q.order_by(Case.received_on)).scalars())


def score_pairs(db: Session, cases: list[Case], cross_unit_only: bool = True, tf: matching.TfIdf | None = None) -> list[dict]:
    tf = tf or tfidf(db)
    window = int(rules.get(db, "overlap_window_days"))
    thr = float(rules.get(db, "name_match_threshold"))
    out = []
    views = [view(c) for c in cases]
    for i, a in enumerate(views):
        for b in views[i + 1:]:
            if cross_unit_only and a.unit == b.unit:
                continue
            p = matching.pair_score(a, b, tf, window, thr)
            if p:
                out.append({"key": _key(a.id, b.id), "a": a.id, "b": b.id, "a_ref": a.case_id, "b_ref": b.case_id,
                            "a_unit": a.unit, "b_unit": b.unit, **p.as_dict()})
    return sorted(out, key=lambda x: -x["score"])


def _resolved_keys(db: Session, inst_id: int) -> set[str]:
    keys: set[str] = set()
    for al in db.execute(select(OverlapAlert).where(OverlapAlert.institution_id == inst_id,
                                                    OverlapAlert.status != "open")).scalars():
        keys.update(p["key"] for p in al.pairs)
    return keys


def scan_institution(db: Session, inst_id: int, actor=None, notify_people: bool = True,
                     tf: matching.TfIdf | None = None) -> OverlapAlert | None:
    """Recompute the open alert for one institution. Pairs that a coordinator
    already resolved or dismissed are not raised again."""
    thr = float(rules.get(db, "overlap_alert_threshold"))
    done = _resolved_keys(db, inst_id)
    pairs = [p for p in score_pairs(db, institution_cases(db, inst_id), tf=tf) if p["score"] >= thr and p["key"] not in done]
    alert = db.execute(select(OverlapAlert).where(OverlapAlert.institution_id == inst_id,
                                                  OverlapAlert.status == "open")).scalars().first()
    now = rules.now(db)
    if not pairs:
        if alert:
            alert.status, alert.resolution, alert.resolved_at, alert.updated_at = (
                "closed", "Closed automatically: the overlapping cases are no longer open together.", now, now)
            audit.record(db, actor="System (matcher)", action="overlap_closed", entity="overlap_alert", entity_id=alert.id,
                         summary=alert.resolution)
        return None
    case_ids = sorted({p["a"] for p in pairs} | {p["b"] for p in pairs})
    unit_ids = sorted({c.unit_id for c in db.execute(select(Case).where(Case.id.in_(case_ids))).scalars()})
    is_new = alert is None
    old_keys = set() if is_new else {p["key"] for p in alert.pairs}
    if is_new:
        alert = OverlapAlert(institution_id=inst_id, created_at=now, status="open", score=0, pairs=[], case_ids=[], unit_ids=[])
        db.add(alert)
    alert.pairs, alert.case_ids, alert.unit_ids = pairs, case_ids, unit_ids
    alert.score, alert.updated_at = pairs[0]["score"], now
    db.flush()
    new_keys = {p["key"] for p in pairs} - old_keys
    if new_keys:
        inst = db.get(Institution, inst_id)
        units = ", ".join(u.code for u in db.execute(select(Unit).where(Unit.id.in_(unit_ids))).scalars())
        summary = f"Potential Overlapping Cases - Coordination Required: {inst.name}, units {units}, score {alert.score:.0f}."
        audit.record(db, actor=actor or "System (matcher)", action="overlap_raised" if is_new else "overlap_updated",
                     entity="overlap_alert", entity_id=alert.id, summary=summary,
                     new={"pairs": sorted(new_keys), "score": alert.score})
        units_of = dict(db.execute(select(Case.id, Case.unit_id).where(Case.id.in_(case_ids))).all())
        for cid in case_ids:
            db.add(CaseEvent(case_id=cid, at=now, kind="overlap", actor="System (matcher)", unit_id=units_of[cid],
                             remarks=f"Potential overlap with another unit's case (score {alert.score:.0f}).",
                             meta={"alert_id": alert.id}))
        if notify_people:
            people = notify.by_role(db, "coordinator")
            for uid in unit_ids:
                people += notify.unit_officers(db, uid)
            notify.to_users(db, people, title=f"Potential Overlapping Cases - Coordination Required: {inst.name}",
                            body=(f"Units {units} have open cases on {inst.name}. Top score {alert.score:.0f}/100 "
                                  f"(rule-based matching).\n\nWhy: " + "; ".join(pairs[0]["reasons"])),
                            kind="overlap", alert_id=alert.id,
                            url=f"{notify.settings.public_web_url}/overlaps/{alert.id}")
    return alert


def scan_case(db: Session, case: Case, actor=None) -> OverlapAlert | None:
    inst_id = case.institution_id or (case.suggested_institution_id if case.suggestion_status == "suggested" else None)
    return scan_institution(db, inst_id, actor) if inst_id else None


def scan_all(db: Session, notify_people: bool = False) -> int:
    tf = tfidf(db)
    n = 0
    for (iid,) in db.execute(select(Institution.id)).all():
        n += bool(scan_institution(db, iid, notify_people=notify_people, tf=tf))
    return n


# ------------------------------------------------------------ institution suggestion

def suggest_for(db: Session, case: Case) -> None:
    """Fill the suggestion fields of a case whose institution was typed, not picked."""
    if case.institution_id or not case.raw_institution_text.strip():
        return
    insts = db.execute(select(Institution)).scalars().all()
    s = matching.suggest_institution(case.raw_institution_text, insts, float(rules.get(db, "name_match_threshold")))
    case.suggested_institution_id = s.institution_id
    case.suggestion_score = s.score
    case.suggestion_reasons = s.reasons + ([f"Also possible: institution #{i}" for i in s.ambiguous_with])
    case.suggestion_status = "suggested" if s.institution_id else "none"
    if s.institution_id and not s.ambiguous_with and s.score >= 100 and s.reasons[0].startswith("AICTE ID"):
        case.institution_id, case.suggestion_status = s.institution_id, "confirmed"


# ------------------------------------------------------------ conflict guard

def conflicts(db: Session, case: Case) -> list[dict]:
    """Open cases in *other* units on the same institution. Shown before a
    regulatory action; the officer may continue after acknowledging."""
    inst_id = case.institution_id or case.suggested_institution_id
    if not inst_id:
        return []
    out = []
    for c in institution_cases(db, inst_id):
        if c.id == case.id or c.unit_id == case.unit_id:
            continue
        out.append({"case_id": c.case_id, "unit": c.unit.code, "officer": c.officer.name if c.officer else None,
                    "category": c.category.name, "status": c.status, "last_action": c.last_action,
                    "received_on": c.received_on.isoformat()})
    return out
