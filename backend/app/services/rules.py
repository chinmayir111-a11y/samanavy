"""Admin-editable rules, the demo clock, and small runtime state.

Every number below is a DEMO_ASSUMPTION chosen for the prototype, not an
AICTE rule. The Admin can change them on the Rules page, and every change
is written to the audit log."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..models import Setting

IST = timezone(timedelta(hours=5, minutes=30))

# Recorded actions. `regulatory` ones go through the conflict guard.
ACTION_TYPES: list[dict[str, Any]] = [
    {"name": "Letter sent to institution seeking reply", "regulatory": False},
    {"name": "Reminder sent to institution", "regulatory": False},
    {"name": "Reply received from institution", "regulatory": False},
    {"name": "Documents called for", "regulatory": False},
    {"name": "Hearing scheduled", "regulatory": False},
    {"name": "Forwarded for legal opinion", "regulatory": False},
    {"name": "Complainant informed", "regulatory": False},
    {"name": "Inspection ordered", "regulatory": True},
    {"name": "Show-cause notice issued", "regulatory": True},
    {"name": "Penalty imposed", "regulatory": True},
    {"name": "Intake reduced / no-admission order", "regulatory": True},
    {"name": "Approval withdrawn", "regulatory": True},
    {"name": "Other", "regulatory": False},
]

DEFAULTS: dict[str, Any] = {
    # Overlap detection (see services/matching.py and docs/MATCHING_METHOD.md).
    "name_match_threshold": 80,     # typed name -> institution (measured: docs/MATCHING_EVAL.md)
    "overlap_alert_threshold": 65,  # pair score that raises "Potential Overlapping Cases"
    "overlap_window_days": 180,     # cases received further apart than this score 0 for time
    # SLA alerts: percent of the SLA used up. 100 = due day. Overdue is sent separately.
    "sla_alert_pcts": [75, 90, 100],
    # Days overdue before the case moves up the ladder:
    # officer -> unit head -> coordinator -> management.
    "escalation_days": {"1": 3, "2": 10, "3": 25},
    "transfer_accept_days": 3,
    "demo_offset_days": 0,
}

EDITABLE = ("name_match_threshold", "overlap_alert_threshold", "overlap_window_days", "sla_alert_pcts",
            "escalation_days", "transfer_accept_days")


def get(db: Session, key: str) -> Any:
    row = db.get(Setting, key)
    if row is None:
        return deepcopy(DEFAULTS.get(key))
    return row.value


def put(db: Session, key: str, value: Any) -> None:
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value
    db.flush()


def all_rules(db: Session) -> dict[str, Any]:
    return {k: get(db, k) for k in EDITABLE}


def is_regulatory(action: str) -> bool:
    return any(a["name"] == action and a["regulatory"] for a in ACTION_TYPES)


# ----------------------------------------------------------------- demo clock

def real_now() -> datetime:
    return datetime.now(timezone.utc)


def offset_days(db: Session) -> int:
    return int(get(db, "demo_offset_days") or 0)


def now(db: Session) -> datetime:
    """System time as the app sees it: real time plus the demo-clock offset."""
    return real_now() + timedelta(days=offset_days(db))


def today(db: Session) -> date:
    return now(db).astimezone(IST).date()


def to_ist_date(d: datetime) -> date:
    return d.astimezone(IST).date()
