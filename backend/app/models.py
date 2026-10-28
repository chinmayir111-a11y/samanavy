"""SAMANVAY data model. Every record in the demo is synthetic.

Times are timezone-aware. `received_on` and other calendar dates are plain
dates in Indian Standard Time. Event times use the demo clock, so advancing
it ages cases exactly as real days would."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

Json = JSON().with_variant(JSONB(), "postgresql")

ROLES = ("desk_officer", "unit_head", "coordinator", "management", "admin", "college")
USER_TYPES = ("Student", "Faculty", "Parent", "Institution staff", "Other")
STATUSES = ("RECEIVED", "UNDER_PROCESS", "TRANSFERRED", "ESCALATED", "DISPOSED")
OPEN_STATUSES = ("RECEIVED", "UNDER_PROCESS", "TRANSFERRED", "ESCALATED")


class Unit(Base):
    __tablename__ = "unit"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(12), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Institution(Base):
    __tablename__ = "institution"
    id: Mapped[int] = mapped_column(primary_key=True)
    aicte_id: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    address: Mapped[str] = mapped_column(Text, default="")
    city: Mapped[str] = mapped_column(String(80), default="")
    state: Mapped[str] = mapped_column(String(80), default="")
    region: Mapped[str] = mapped_column(String(40), default="")
    pin: Mapped[str] = mapped_column(String(10), default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    kind: Mapped[str] = mapped_column(String(60), default="Engineering")
    synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    district: Mapped[str] = mapped_column(String(80), default="")
    sub_region: Mapped[str] = mapped_column(String(80), default="")
    location_source: Mapped[str] = mapped_column(String(12), default="")
    verified: Mapped[bool] = mapped_column(Boolean, default=True)   # False = created by a sign-up, not yet checked by AICTE


class User(Base):
    __tablename__ = "app_user"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    username: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(120), default="")
    role: Mapped[str] = mapped_column(String(20))
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("unit.id"), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(200), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    demo_tag: Mapped[str] = mapped_column(String(40), default="")   # plus-address tag; "" for real accounts
    tour_done: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # College users (complainants) only
    email_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    mobile: Mapped[str] = mapped_column(String(20), default="")
    user_type: Mapped[str] = mapped_column(String(30), default="")
    institution_id: Mapped[int | None] = mapped_column(ForeignKey("institution.id"), nullable=True)
    institution_link: Mapped[str] = mapped_column(String(10), default="none")   # none / approved / pending / rejected
    city_entered: Mapped[str] = mapped_column(String(120), default="")
    city: Mapped[str] = mapped_column(String(120), default="")
    district: Mapped[str] = mapped_column(String(80), default="")
    sub_region: Mapped[str] = mapped_column(String(80), default="")
    state: Mapped[str] = mapped_column(String(80), default="")
    region: Mapped[str] = mapped_column(String(40), default="")
    pin: Mapped[str] = mapped_column(String(10), default="")
    location_source: Mapped[str] = mapped_column(String(12), default="")   # pin / matched / picked / manual
    unit: Mapped[Unit | None] = relationship(lazy="joined")
    institution: Mapped["Institution | None"] = relationship(lazy="joined")


class UserToken(Base):
    """One-time invitation and password-reset links (only the hash is stored)."""
    __tablename__ = "user_token"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"))
    purpose: Mapped[str] = mapped_column(String(20))
    token_hash: Mapped[str] = mapped_column(String(64), index=True)
    code_hash: Mapped[str] = mapped_column(String(64), default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Category(Base):
    __tablename__ = "category"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    topic: Mapped[str] = mapped_column(String(40))      # group used by the matcher ("faculty", "fees", ...)
    sla_days: Mapped[int] = mapped_column(Integer, default=30)


class Case(Base):
    __tablename__ = "complaint_case"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[str] = mapped_column(String(30), unique=True)          # RB-2026-0042
    source_ref: Mapped[str] = mapped_column(String(60), default="")         # the unit's own file number
    source: Mapped[str] = mapped_column(String(30), default="Unit register")
    institution_id: Mapped[int | None] = mapped_column(ForeignKey("institution.id"), nullable=True, index=True)
    raw_institution_text: Mapped[str] = mapped_column(String(250), default="")
    # Matcher suggestion when the institution was typed, not picked.
    suggested_institution_id: Mapped[int | None] = mapped_column(ForeignKey("institution.id"), nullable=True)
    suggestion_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    suggestion_reasons: Mapped[list[Any]] = mapped_column(Json, default=list)
    suggestion_status: Mapped[str] = mapped_column(String(12), default="none")  # none/suggested/confirmed/rejected
    received_on: Mapped[date] = mapped_column(Date, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("category.id"))
    description: Mapped[str] = mapped_column(Text)
    complainant_name: Mapped[str] = mapped_column(String(120), default="")   # private: never shown publicly
    complainant_email: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(16), default="RECEIVED", index=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("unit.id"), index=True)
    assigned_officer_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), nullable=True)
    held_since: Mapped[datetime] = mapped_column(DateTime(timezone=True))    # with the current unit/officer since
    last_action: Mapped[str] = mapped_column(String(200), default="")
    last_action_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_action: Mapped[str] = mapped_column(String(200), default="")
    expected_disposal_on: Mapped[date] = mapped_column(Date)
    sla_days: Mapped[int] = mapped_column(Integer)
    priority: Mapped[str] = mapped_column(String(10), default="Normal")      # Normal / High / Urgent
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)        # 0 officer, 1 head, 2 coordinator, 3 management
    sla_stage: Mapped[int] = mapped_column(Integer, default=0)               # highest SLA alert already sent (0..4)
    transfer_to_unit_id: Mapped[int | None] = mapped_column(ForeignKey("unit.id"), nullable=True)
    transfer_reason: Mapped[str] = mapped_column(Text, default="")
    merged_into_id: Mapped[int | None] = mapped_column(ForeignKey("complaint_case.id"), nullable=True)
    disposed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    disposal_note: Mapped[str] = mapped_column(Text, default="")
    confidential: Mapped[bool] = mapped_column(Boolean, default=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    complainant_user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), nullable=True, index=True)
    happened_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    institution: Mapped[Institution | None] = relationship(foreign_keys=[institution_id], lazy="joined")
    suggested_institution: Mapped[Institution | None] = relationship(foreign_keys=[suggested_institution_id], lazy="joined")
    category: Mapped[Category] = relationship(lazy="joined")
    unit: Mapped[Unit] = relationship(foreign_keys=[unit_id], lazy="joined")
    transfer_to_unit: Mapped[Unit | None] = relationship(foreign_keys=[transfer_to_unit_id], lazy="joined")
    officer: Mapped[User | None] = relationship(foreign_keys=[assigned_officer_id], lazy="joined")


class CaseEvent(Base):
    """Chronological history. Kinds: received, assigned, action, remark, transfer_requested,
    transfer_accepted, transfer_rejected, escalated, linked, merged, overlap, conflict_acknowledged,
    institution_confirmed, sla_alert, disposed, reopened."""
    __tablename__ = "case_event"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("complaint_case.id"), index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    kind: Mapped[str] = mapped_column(String(30))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), nullable=True)
    actor: Mapped[str] = mapped_column(String(160), default="System")
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("unit.id"), nullable=True)
    action_type: Mapped[str] = mapped_column(String(120), default="")
    remarks: Mapped[str] = mapped_column(Text, default="")
    attachment_name: Mapped[str] = mapped_column(String(200), default="")
    attachment_path: Mapped[str] = mapped_column(String(300), default="")
    meta: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    unit: Mapped[Unit | None] = relationship(lazy="joined")


class CaseLink(Base):
    __tablename__ = "case_link"
    __table_args__ = (UniqueConstraint("a_case_id", "b_case_id", name="uq_case_link_pair"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    a_case_id: Mapped[int] = mapped_column(ForeignKey("complaint_case.id"))   # always the smaller id
    b_case_id: Mapped[int] = mapped_column(ForeignKey("complaint_case.id"))
    kind: Mapped[str] = mapped_column(String(20))       # same_institution / same_issue / duplicate
    status: Mapped[str] = mapped_column(String(12))     # suggested / confirmed / rejected
    reason: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OverlapAlert(Base):
    """One alert per institution while it is open. `pairs` holds every
    cross-unit pair with its score and reasons; `score` is the highest."""
    __tablename__ = "overlap_alert"
    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institution.id"), index=True)
    case_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    unit_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    score: Mapped[float] = mapped_column(Float)
    pairs: Mapped[list[Any]] = mapped_column(Json, default=list)
    status: Mapped[str] = mapped_column(String(12), default="open", index=True)   # open / coordinated / dismissed
    lead_unit_id: Mapped[int | None] = mapped_column(ForeignKey("unit.id"), nullable=True)
    lead_case_id: Mapped[int | None] = mapped_column(ForeignKey("complaint_case.id"), nullable=True)
    resolution: Mapped[str] = mapped_column(Text, default="")
    resolved_by_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    institution: Mapped[Institution] = relationship(lazy="joined")


class Notification(Base):
    __tablename__ = "notification"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(250))
    body: Mapped[str] = mapped_column(Text, default="")
    case_id: Mapped[int | None] = mapped_column(ForeignKey("complaint_case.id"), nullable=True)
    alert_id: Mapped[int | None] = mapped_column(ForeignKey("overlap_alert.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EmailLog(Base):
    __tablename__ = "email_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    to_addr: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    html: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(30))
    case_id: Mapped[int | None] = mapped_column(ForeignKey("complaint_case.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20))   # QUEUED SENT FAILED NOT_CONFIGURED NO_ADDRESS
    detail: Mapped[str] = mapped_column(Text, default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    at_real: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    at_demo: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor: Mapped[str] = mapped_column(String(160))
    action: Mapped[str] = mapped_column(String(40))
    entity: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    old_value: Mapped[Any] = mapped_column(Json, nullable=True)
    new_value: Mapped[Any] = mapped_column(Json, nullable=True)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


class Setting(Base):
    __tablename__ = "setting"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[Any] = mapped_column(Json)
