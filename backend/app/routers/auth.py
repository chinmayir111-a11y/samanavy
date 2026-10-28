"""Sign-in (password or one-tap demo), invitations, password reset.
No self sign-up: the Admin invites officers by email link."""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import COOKIE, current_user, rate_limit
from ..models import User, UserToken
from ..security import create_token, decode_token, hash_password, sha256, verify_password
from ..services import accounts, audit, mail

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger("samanvay.auth")
ROLE_ORDER = ["desk_officer", "unit_head", "coordinator", "management", "admin", "college"]
SEES = {
    "desk_officer": "your unit's cases, overlap alerts on your institutions, the conflict warning",
    "unit_head": "your unit's workload, transfers to accept, escalations",
    "coordinator": "every unit, overlap alerts to decide, lead-unit decisions",
    "management": "dashboards, reports, ageing, audit log (read-only)",
    "admin": "accounts, rules, demo clock, email log",
    "college": "filing a complaint and tracking it, as a student would",
}
MAX_FAILS, LOCK_MINUTES, INVITE_DAYS, RESET_MINUTES = 5, 15, 7, 30


class Login(BaseModel):
    email: str = ""
    username: str = ""
    password: str = ""


class Email(BaseModel):
    email: str


class NewPassword(BaseModel):
    token: str
    password: str


def me_view(u: User) -> dict:
    return {"id": u.id, "email": u.email, "username": u.username, "name": u.name, "title": u.title, "role": u.role,
            "unit": {"id": u.unit.id, "code": u.unit.code, "name": u.unit.name} if u.unit else None, "tour_done": u.tour_done,
            "institution": {"id": u.institution.id, "name": u.institution.name, "link": u.institution_link,
                            "city": u.institution.city, "state": u.institution.state} if u.institution else None,
            "user_type": u.user_type}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _issue(db: Session, u: User, how: str, response: Response) -> dict:
    audit.record(db, actor=u, action="signed_in", entity="user", entity_id=u.id, summary=f"Signed in ({how}).")
    db.commit()
    token = create_token(u.id, u.role)
    response.set_cookie(COOKIE, token, max_age=settings.jwt_expire_minutes * 60, httponly=True,
                        secure=settings.cookie_secure, samesite=settings.cookie_samesite, path="/")
    return {"token": token, "user": me_view(u)}   # token for scripts/tests; the web app relies on the cookie


def password_problem(pw: str) -> str | None:
    if len(pw) < 8:
        return "Use at least 8 characters."
    if not any(c.isalpha() for c in pw) or not any(c.isdigit() for c in pw):
        return "Use letters and at least one number."
    return None


@router.post("/login")
def login(body: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    who = (body.email or body.username).strip().lower()
    rate_limit(request, "login:" + who, limit=20)
    u = db.execute(select(User).where((func.lower(User.email) == who) | (User.username == who))).scalars().first()
    if u and u.locked_until and u.locked_until > _now():
        raise HTTPException(423, {"message": f"Account locked for {LOCK_MINUTES} minutes after 5 wrong passwords.", "code": "locked"})
    if u and not u.email_verified and u.password_hash and verify_password(body.password, u.password_hash):
        raise HTTPException(403, {"message": "Verify your email first. We sent you a 6-digit code.", "code": "unverified"})
    if not u or not u.is_active or not u.password_hash or not verify_password(body.password, u.password_hash):
        if u:
            u.failed_logins += 1
            if u.failed_logins >= MAX_FAILS:
                u.locked_until, u.failed_logins = _now() + timedelta(minutes=LOCK_MINUTES), 0
            db.commit()
        raise HTTPException(401, {"message": "Wrong email or password.", "code": "wrong"})
    u.failed_logins, u.locked_until = 0, None
    return _issue(db, u, "password", response)


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/", secure=settings.cookie_secure, samesite=settings.cookie_samesite)
    return {"ok": True}


@router.get("/demo-accounts")
def demo_accounts(db: Session = Depends(get_db)):
    if not settings.demo_mode:
        return []
    users = db.execute(select(User).where(User.demo_tag != "")).scalars().all()
    users.sort(key=lambda u: (ROLE_ORDER.index(u.role), u.unit.code if u.unit else ""))
    return [{"username": u.username, "name": u.name, "title": u.title, "role": u.role, "sees": SEES[u.role],
             "unit": u.unit.code if u.unit else None} for u in users]


@router.post("/demo-login")
def demo_login(body: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    """One-tap sign-in for the seeded demo accounts. Off when DEMO_MODE=false."""
    if not settings.demo_mode:
        raise HTTPException(404, "Not available.")
    rate_limit(request, "demo:" + body.username.lower(), limit=600)
    u = db.execute(select(User).where(User.username == body.username, User.demo_tag != "")).scalar_one_or_none()
    if u is None:
        raise HTTPException(404, "No such demo account.")
    return _issue(db, u, "demo one-tap", response)


@router.get("/session")
def session(request: Request, db: Session = Depends(get_db)):
    """Who is signed in, or null. Never 401, so a signed-out page load is quiet."""
    data = decode_token(request.cookies.get(COOKIE, "") or "")
    u = db.get(User, data["uid"]) if data else None
    return {"user": me_view(u) if u and u.is_active else None}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return me_view(user)


@router.post("/tour-done")
def tour_done(user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.tour_done = True
    db.commit()
    return {"ok": True}


def issue_link(db: Session, user: User, purpose: str) -> str:
    for old in db.execute(select(UserToken).where(UserToken.user_id == user.id, UserToken.purpose == purpose,
                                                  UserToken.used_at.is_(None))).scalars():
        old.used_at = _now()
    token = secrets.token_urlsafe(32)
    minutes = INVITE_DAYS * 1440 if purpose == "invite" else RESET_MINUTES
    db.add(UserToken(user_id=user.id, purpose=purpose, token_hash=sha256(token), created_at=_now(),
                     expires_at=_now() + timedelta(minutes=minutes)))
    link = f"{settings.public_web_url}/set-password?token={token}"
    if settings.app_env == "development":
        log.warning("DEV ONLY (APP_ENV=development) %s link for %s: %s", purpose, user.email, link)
    return link


@router.post("/forgot")
def forgot(body: Email, request: Request, db: Session = Depends(get_db)):
    rate_limit(request, "forgot", limit=10)
    u = db.execute(select(User).where(func.lower(User.email) == body.email.strip().lower())).scalars().first()
    if u and u.is_active:
        link = issue_link(db, u, "reset")
        mail.queue(db, to=u.email, kind="reset", subject="Reset your SAMANVAY password",
                   body=f"Dear {u.name},\n\nOpen the link below to choose a new password. It works for {RESET_MINUTES} minutes.",
                   action_url=link, action_label="Choose a new password")
        db.commit()
        mail.kick()
    return {"message": "If an account uses that email, a reset link is on its way."}


@router.post("/set-password")
def set_password(body: NewPassword, request: Request, response: Response, db: Session = Depends(get_db)):
    """Accept an invitation or finish a reset."""
    rate_limit(request, "reset", limit=20)
    tok = db.execute(select(UserToken).where(UserToken.token_hash == sha256(body.token))).scalars().first()
    if tok is None or tok.used_at or tok.expires_at < _now():
        raise HTTPException(400, "This link has expired or was already used. Ask the Admin for a new one.")
    if (p := password_problem(body.password)):
        raise HTTPException(400, p)
    u = db.get(User, tok.user_id)
    u.password_hash, u.is_active, tok.used_at = hash_password(body.password), True, _now()
    return _issue(db, u, "invitation accepted" if tok.purpose == "invite" else "password reset", response)


# ------------------------------------------------------------ college users: sign-up and verification

class Signup(BaseModel):
    name: str
    email: str
    password: str
    user_type: str
    mobile: str = ""
    college_id: int | None = None
    college_name: str = ""
    aicte_id: str = ""
    city_entered: str = ""
    pin: str = ""
    picked: dict | None = None


class VerifyIn(BaseModel):
    email: str = ""
    code: str = ""
    token: str = ""


def _acct(e: accounts.AccountError):
    raise HTTPException(e.status, {"message": e.message, "code": e.code, "field": e.field})


@router.post("/signup")
def signup(body: Signup, request: Request, db: Session = Depends(get_db)):
    rate_limit(request, "signup", limit=settings.signup_rate_limit)
    try:
        u = accounts.register(db, **body.model_dump())
        sent = accounts.send_code(db, u)
    except accounts.AccountError as e:
        db.rollback()
        _acct(e)
    db.commit()
    mail.kick()
    return {"email": u.email, "institution_link": u.institution_link, **sent,
            "message": f"We sent a 6-digit code to {u.email}. Type it below to finish."}


@router.post("/verify")
def verify_email(body: VerifyIn, request: Request, response: Response, db: Session = Depends(get_db)):
    rate_limit(request, "verify", limit=30)
    try:
        u = accounts.verify(db, email=body.email, code=body.code, token=body.token)
    except accounts.AccountError as e:
        db.commit()   # keep the wrong-code count
        _acct(e)
    return _issue(db, u, "email verified", response)


@router.post("/resend")
def resend(body: Email, request: Request, db: Session = Depends(get_db)):
    rate_limit(request, "resend", limit=20)
    u = db.execute(select(User).where(func.lower(User.email) == body.email.strip().lower())).scalars().first()
    if u is None or u.email_verified:
        return {"message": "If that account is waiting for verification, a new code is on its way."}
    try:
        sent = accounts.send_code(db, u)
    except accounts.AccountError as e:
        _acct(e)
    db.commit()
    mail.kick()
    return {**sent, "message": "A new code is on its way."}
