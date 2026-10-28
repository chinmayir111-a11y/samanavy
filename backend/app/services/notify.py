"""Tell people things: an in-app inbox row (always) plus a real email.
Batch jobs (SLA, escalation) send one digest email per person per run, so
advancing the demo clock never floods the inbox."""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Case, Notification, User
from . import mail, rules, sms


def case_url(case: Case | None) -> str:
    return f"{settings.public_web_url}/cases/{case.case_id}" if case else settings.public_web_url


def inbox(db: Session, user: User, *, title: str, body: str, kind: str, case: Case | None = None,
          alert_id: int | None = None) -> None:
    db.add(Notification(user_id=user.id, kind=kind, title=title, body=body, case_id=case.id if case else None,
                        alert_id=alert_id, created_at=rules.now(db)))


def to_users(db: Session, users: list[User], *, title: str, body: str, kind: str, case: Case | None = None,
             alert_id: int | None = None, url: str = "", email: bool = True) -> None:
    seen = set()
    for u in users:
        if u.id in seen:
            continue
        seen.add(u.id)
        inbox(db, u, title=title, body=body, kind=kind, case=case, alert_id=alert_id)
        sms.provider().send("", title)   # not configured: email + in-app carry the alert
        if email:
            mail.queue(db, to=u.email, subject=title, body=f"Dear {u.name},\n\n{body}", kind=kind,
                       case_id=case.id if case else None, action_url=url or case_url(case), action_label="Open in SAMANVAY")
    db.flush()


class Digest:
    """Collect lines per person during a job; send one email each at the end."""

    def __init__(self) -> None:
        self.lines: dict[int, list[str]] = defaultdict(list)
        self.users: dict[int, User] = {}

    def add(self, db: Session, user: User, *, title: str, body: str, kind: str, case: Case) -> None:
        inbox(db, user, title=title, body=body, kind=kind, case=case)
        self.users[user.id] = user
        self.lines[user.id].append(f"- {case.case_id}: {title}")

    def send(self, db: Session, subject: str, kind: str) -> int:
        for uid, lines in self.lines.items():
            u = self.users[uid]
            mail.queue(db, to=u.email, kind=kind, subject=f"{subject} ({len(lines)})",
                       body=f"Dear {u.name},\n\n" + "\n".join(lines[:40]) +
                            (f"\n...and {len(lines) - 40} more." if len(lines) > 40 else ""),
                       action_url=f"{settings.public_web_url}/today", action_label="Open Today's register")
        db.flush()
        return len(self.lines)


def unit_officers(db: Session, unit_id: int, heads: bool = True) -> list[User]:
    roles = ("desk_officer", "unit_head") if heads else ("desk_officer",)
    return list(db.execute(select(User).where(User.unit_id == unit_id, User.role.in_(roles), User.is_active)).scalars())


def unit_heads(db: Session, unit_id: int) -> list[User]:
    return list(db.execute(select(User).where(User.unit_id == unit_id, User.role == "unit_head", User.is_active)).scalars())


def by_role(db: Session, role: str) -> list[User]:
    return list(db.execute(select(User).where(User.role == role, User.is_active)).scalars())


def holders(db: Session, case: Case) -> list[User]:
    """Whoever should hear about a case: its officer, or the unit's desk officers."""
    if case.officer and case.officer.is_active:
        return [case.officer]
    return unit_officers(db, case.unit_id, heads=False) or unit_heads(db, case.unit_id)
