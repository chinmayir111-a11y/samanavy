"""Hash-chained, append-only audit log (pattern carried over from BHOOSHAKTI and JAMANAT).

Each row's hash covers its own content plus the previous row's hash, so
changing or deleting any row breaks every hash after it. A Postgres trigger
also refuses UPDATE/DELETE; verify_chain() catches someone who bypassed it."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..models import AuditLog, User
from ..security import sha256
from . import rules

GENESIS = "0" * 64


def _jsonable(v: Any) -> Any:
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    return v


def _utc(d: datetime) -> str:
    return d.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _digest(row: AuditLog) -> str:
    body = json.dumps({
        "id": row.id, "at_real": _utc(row.at_real), "at_demo": _utc(row.at_demo),
        "actor_id": row.actor_id, "actor": row.actor, "action": row.action, "entity": row.entity,
        "entity_id": row.entity_id, "summary": row.summary, "old": row.old_value,
        "new": row.new_value, "prev": row.prev_hash,
    }, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(body)


def actor_label(user: User | None) -> str:
    if user is None:
        return "System"
    return f"{user.name} ({user.title or user.role})"


def record(db: Session, *, actor: User | None | str, action: str, entity: str,
           entity_id: int | None, summary: str = "", old: Any = None, new: Any = None,
           at_demo: datetime | None = None) -> AuditLog:
    # One writer at a time so two rows never share a prev_hash.
    db.execute(text("SELECT pg_advisory_xact_lock(424242)"))
    last = db.execute(select(AuditLog.id, AuditLog.hash).order_by(AuditLog.id.desc()).limit(1)).first()
    next_id = db.execute(text("SELECT nextval('audit_log_id_seq')")).scalar_one()
    if isinstance(actor, str):
        label, actor_id = actor, None
    else:
        label, actor_id = actor_label(actor), actor.id if actor else None
    row = AuditLog(
        id=next_id, at_real=rules.real_now().replace(microsecond=0),
        at_demo=(at_demo or rules.now(db)).replace(microsecond=0),
        actor_id=actor_id, actor=label, action=action, entity=entity, entity_id=entity_id,
        summary=summary, old_value=_jsonable(old), new_value=_jsonable(new),
        prev_hash=last.hash if last else GENESIS, hash="",
    )
    row.hash = _digest(row)
    db.add(row)
    db.flush()
    return row


def verify_chain(db: Session) -> dict[str, Any]:
    prev = GENESIS
    count = 0
    for row in db.execute(select(AuditLog).order_by(AuditLog.id)).scalars():
        count += 1
        if row.prev_hash != prev:
            return {"ok": False, "checked": count, "broken_id": row.id,
                    "reason": "This entry does not point to the one before it: an entry was removed or reordered."}
        if _digest(row) != row.hash:
            return {"ok": False, "checked": count, "broken_id": row.id,
                    "reason": "This entry was changed after it was written: its content no longer matches its hash."}
        prev = row.hash
    return {"ok": True, "checked": count, "broken_id": None, "reason": "Every entry matches its hash and links to the one before it."}
