"""Request-level helpers: current user, role checks, rate limits."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import Case, User
from .security import decode_token

bearer = HTTPBearer(auto_error=False)
COOKIE = "smv_session"

OFFICERS = ("desk_officer", "unit_head")
COORD = ("coordinator",)
INTERNAL = ("desk_officer", "unit_head", "coordinator", "management", "admin")


def current_user(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer),
                 db: Session = Depends(get_db)) -> User:
    """Bearer token (scripts, tests) or the httpOnly session cookie (browser).
    Cookie requests that change data must carry X-Requested-With, which a
    foreign site cannot add without passing CORS: a cheap CSRF guard."""
    raw = creds.credentials if creds else request.cookies.get(COOKIE)
    if not raw:
        raise HTTPException(401, "Please sign in.")
    if not creds and request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get("x-requested-with") != "samanvay":
        raise HTTPException(403, "Request blocked: missing security header. Reload the page and try again.")
    data = decode_token(raw)
    if not data:
        raise HTTPException(401, "Your session has ended. Please sign in again.")
    user = db.get(User, data["uid"])
    if user is None or not user.is_active:
        raise HTTPException(401, "Account not found.")
    return user


def require(*roles: str) -> Callable[[User], User]:
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "Your role cannot do this.")
        return user
    return dep


def load_case(db: Session, case_ref: str) -> Case:
    """By number ("RB-2026-0042") or database id."""
    from sqlalchemy import select
    q = select(Case).where(Case.case_id == case_ref.upper()) if not case_ref.isdigit() else select(Case).where(Case.id == int(case_ref))
    case = db.execute(q).scalars().first()
    if case is None:
        raise HTTPException(404, "No case with this number.")
    return case


def can_edit(user: User, case: Case) -> bool:
    """Officers change their own unit's cases. A pending transfer belongs to
    the receiving unit's head for accept/reject only (handled in the route)."""
    return user.role in OFFICERS and user.unit_id == case.unit_id


def must_edit(user: User, case: Case) -> None:
    if not can_edit(user, case):
        raise HTTPException(403, f"Only {case.unit.code} officers can change this case.")


_attempts: dict[str, deque] = defaultdict(deque)


def rate_limit(request: Request, key: str, limit: int | None = None) -> None:
    now = time.monotonic()
    q = _attempts[f"{client_ip(request) or '?'}:{key}"]
    while q and now - q[0] > settings.login_rate_window_s:
        q.popleft()
    if len(q) >= (limit or settings.login_rate_limit):
        wait = int(settings.login_rate_window_s - (now - q[0])) + 1
        raise HTTPException(429, f"Too many attempts. Try again in {wait} seconds.")
    q.append(now)


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "")
