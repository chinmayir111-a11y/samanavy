"""College-user accounts: sign-up, email verification (6-digit code + link), resend limits,
and attaching the user to an institution. Security timers use real time, never the demo clock.

Institution rules:
- AICTE ID typed and already on the register -> link is "pending" until a Unit Head or Admin
  approves (a stranger is never silently attached to an existing AICTE ID).
- AICTE ID typed and new -> a new institution record (unverified) is created; the user is linked.
- College picked from suggestions (or typed name matches one) -> linked; "Institution staff" stays
  pending until approved, because they speak for the college.
- "My college is not listed" and no ID -> new unverified institution with the user's location."""
from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import USER_TYPES, Institution, User, UserToken
from ..security import hash_password, sha256
from . import audit, location, mail, matching, notify, rules

log = logging.getLogger("samanvay.accounts")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
CODE_MINUTES, RESEND_WAIT_S, RESEND_PER_HOUR, MAX_CODE_TRIES = 30, 60, 5, 5


class AccountError(Exception):
    def __init__(self, message: str, code: str = "error", status: int = 400, field: str = "") -> None:
        super().__init__(message)
        self.message, self.code, self.status, self.field = message, code, status, field


def now() -> datetime:
    return datetime.now(timezone.utc)


def password_problem(pw: str) -> str | None:
    if len(pw) < 8:
        return "Use at least 8 characters."
    if not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        return "Use letters and at least one number."
    if pw.lower() in ("password1", "12345678a", "qwerty123", "samanvay1"):
        return "This password is too common. Choose another."
    return None


def send_code(db: Session, user: User) -> dict:
    """New 6-digit code + link. Enforces 60 s between sends and 5 per hour."""
    recent = db.execute(select(UserToken).where(UserToken.user_id == user.id, UserToken.purpose == "verify",
                                                UserToken.created_at > now() - timedelta(hours=1))
                        .order_by(UserToken.created_at.desc())).scalars().all()
    if recent and (now() - recent[0].created_at).total_seconds() < RESEND_WAIT_S:
        wait = RESEND_WAIT_S - int((now() - recent[0].created_at).total_seconds())
        raise AccountError(f"Please wait {wait} seconds before asking for another code.", "wait", 429)
    if len(recent) >= RESEND_PER_HOUR:
        raise AccountError("You have asked for 5 codes in the last hour. Please try again later.", "hourly", 429)
    for old in recent:
        old.used_at = old.used_at or now()
    token, code = secrets.token_urlsafe(32), f"{secrets.randbelow(1000000):06d}"
    db.add(UserToken(user_id=user.id, purpose="verify", token_hash=sha256(token), code_hash=sha256(f"{user.id}:{code}"),
                     created_at=now(), expires_at=now() + timedelta(minutes=CODE_MINUTES)))
    link = f"{settings.public_web_url}/verify?email={user.email}&token={token}"
    row = mail.queue(db, to=user.email, kind="verify", subject="Your SAMANVAY verification code",
                     body=(f"Dear {user.name},\n\nYour verification code is {code}. It works for {CODE_MINUTES} minutes.\n\n"
                           "Type it on the page, or open the link below. If you did not sign up, ignore this email."),
                     action_url=link, action_label="Verify my email")
    if settings.app_env == "development":
        log.warning("DEV ONLY (APP_ENV=development) verification code for %s: %s", user.email, code)
    db.flush()
    return {"email_status": row.status, "email_log_id": row.id}


def verify(db: Session, *, email: str = "", code: str = "", token: str = "") -> User:
    if token:
        tok = db.execute(select(UserToken).where(UserToken.token_hash == sha256(token), UserToken.purpose == "verify")).scalars().first()
        user = db.get(User, tok.user_id) if tok else None
    else:
        user = db.execute(select(User).where(func.lower(User.email) == email.strip().lower())).scalars().first()
        tok = db.execute(select(UserToken).where(UserToken.user_id == user.id, UserToken.purpose == "verify",
                                                 UserToken.used_at.is_(None)).order_by(UserToken.id.desc())).scalars().first() if user else None
    if user and user.email_verified:
        return user
    if not user or not tok or tok.used_at or tok.expires_at < now():
        raise AccountError("This code has expired or was already used. Ask for a new code.", "expired")
    if not token:
        if tok.attempts >= MAX_CODE_TRIES:
            raise AccountError("Too many wrong codes. Ask for a new code.", "tries")
        if sha256(f"{user.id}:{code.strip()}") != tok.code_hash:
            tok.attempts += 1
            db.flush()
            raise AccountError("That code is not right. Check the email and try again.", "wrong_code", field="code")
    tok.used_at = now()
    user.email_verified, user.is_active = True, True
    audit.record(db, actor=user, action="email_verified", entity="user", entity_id=user.id, summary=f"{user.email} verified.")
    db.flush()
    return user


def _new_institution(db: Session, name: str, aicte_id: str, loc: dict) -> Institution:
    if not aicte_id:
        n = db.scalar(select(func.count(Institution.id)).where(Institution.aicte_id.like("NEW-%"))) or 0
        aicte_id = f"NEW-{n + 1:05d}"
    inst = Institution(aicte_id=aicte_id, name=name.strip(), aliases=[], address="", city=loc.get("city", ""),
                       district=loc.get("district", ""), sub_region=loc.get("sub_region", ""), state=loc.get("state", ""),
                       region=loc.get("region", ""), pin=loc.get("pin", ""), location_source=loc.get("source", ""),
                       kind="Not stated", synthetic=False, verified=False)
    db.add(inst)
    db.flush()
    audit.record(db, actor="Sign-up", action="institution_created", entity="institution", entity_id=inst.id,
                 summary=f"New unverified institution from sign-up: {inst.name} ({inst.aicte_id}), {inst.city} {inst.state}.")
    return inst


def attach(db: Session, user: User, *, institution_id: int | None, name: str, aicte_id: str, loc: dict) -> str:
    """Returns 'approved' or 'pending'. See the module docstring for the rules."""
    aicte_id = aicte_id.strip().upper()
    inst = None
    pending = False
    if aicte_id:
        inst = db.execute(select(Institution).where(func.upper(Institution.aicte_id) == aicte_id)).scalars().first()
        if inst:
            pending = True
        else:
            inst = _new_institution(db, name or aicte_id, aicte_id, loc)
    elif institution_id:
        inst = db.get(Institution, institution_id)
        if inst is None:
            raise AccountError("Choose your college again.", field="college")
        pending = user.user_type == "Institution staff"
    elif name.strip():
        all_insts = db.execute(select(Institution)).scalars().all()
        s = matching.suggest_institution(name, all_insts, float(rules.get(db, "name_match_threshold")))
        if s.institution_id and not s.ambiguous_with:
            inst = db.get(Institution, s.institution_id)
            pending = user.user_type == "Institution staff"
        else:
            inst = _new_institution(db, name, "", loc)
    else:
        raise AccountError("Type your college's name.", field="college")
    user.institution_id, user.institution_link = inst.id, "pending" if pending else "approved"
    if pending:
        people = notify.by_role(db, "admin") + notify.unit_heads(db, _pgrc_id(db))
        notify.to_users(db, people, kind="link", title=f"Please confirm: {user.name} says they belong to {inst.name}",
                        body=(f"{user.name} ({user.user_type}, {user.email}) signed up and linked themselves to {inst.name} "
                              f"({inst.aicte_id}). Approve or reject on the Admin page. Until then the link is pending."),
                        url=f"{settings.public_web_url}/admin")
    return user.institution_link


def _pgrc_id(db: Session) -> int:
    from ..models import Unit
    return db.execute(select(Unit.id).where(Unit.code == "PGRC")).scalar() or 0


def register(db: Session, *, name: str, email: str, password: str, user_type: str, mobile: str = "",
             college_id: int | None = None, college_name: str = "", aicte_id: str = "",
             city_entered: str = "", pin: str = "", picked: dict | None = None) -> User:
    email = email.strip().lower()
    if len(name.strip()) < 2:
        raise AccountError("Please write your full name.", field="name")
    if not EMAIL_RE.match(email):
        raise AccountError("This does not look like an email address.", field="email")
    if db.execute(select(User).where(func.lower(User.email) == email)).scalars().first():
        raise AccountError("An account with this email already exists. Sign in, or use Forgot password.", "duplicate", 409, "email")
    if (p := password_problem(password)):
        raise AccountError(p, field="password")
    if user_type not in USER_TYPES:
        raise AccountError("Tell us who you are.", field="user_type")
    if mobile and not re.fullmatch(r"(\+91[\s-]?)?[6-9]\d{9}", mobile.strip()):
        raise AccountError("Mobile number should be 10 digits, starting with 6, 7, 8 or 9.", field="mobile")
    loc = resolve_location(db, city_entered, pin, picked)
    u = User(email=email, username=email, name=name.strip(), title=f"Complainant ({user_type})", role="college",
             password_hash=hash_password(password), is_active=False, email_verified=False, mobile=mobile.strip(),
             user_type=user_type, created_at=now(), city_entered=city_entered.strip(), city=loc.get("city", ""),
             district=loc.get("district", ""), sub_region=loc.get("sub_region", ""), state=loc.get("state", ""),
             region=loc.get("region", ""), pin=loc.get("pin", ""), location_source=loc.get("source", ""))
    db.add(u)
    db.flush()
    attach(db, u, institution_id=college_id, name=college_name, aicte_id=aicte_id, loc=loc)
    audit.record(db, actor=u, action="signed_up", entity="user", entity_id=u.id,
                 summary=f"College user signed up: {u.user_type}, location {u.city} {u.state} ({u.location_source}).")
    return u


def resolve_location(db: Session, city: str, pin: str, picked: dict | None) -> dict:
    """picked = {district, state, city?} chosen by the person from choices or dropdowns."""
    if picked and picked.get("state"):
        p = location.place(picked.get("city") or city.strip().title() or picked.get("district", ""),
                           picked.get("district", ""), picked["state"], db)
        return {**p, "pin": re.sub(r"\D", "", pin or "")[:6], "source": picked.get("source", "picked")}
    r = location.resolve(city, pin, db)
    if r["status"] == "matched":
        return {**r, "source": r["source"]}
    return {"city": city.strip().title(), "district": "", "sub_region": "", "state": "", "region": "",
            "pin": re.sub(r"\D", "", pin or "")[:6], "source": "manual"}
