"""APScheduler jobs: daily SLA alerts + escalation, email retry, heartbeat."""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from .db import session_scope
from .services import mail, rules, sla

log = logging.getLogger("samanvay.scheduler")
_sched: BackgroundScheduler | None = None


def _daily() -> None:
    with session_scope() as db:
        log.info("daily job: %s", sla.run_daily(db))
    mail.kick()


def _heartbeat() -> None:
    with session_scope() as db:
        rules.put(db, "scheduler_heartbeat", rules.real_now().isoformat())


def start() -> None:
    global _sched
    if _sched is not None:
        return
    _sched = BackgroundScheduler(timezone="Asia/Kolkata")
    _sched.add_job(_daily, "cron", hour=6, minute=0, id="daily")
    _sched.add_job(_daily, "interval", hours=6, id="daily-catchup")
    _sched.add_job(lambda: mail.deliver_pending(retry_failed=True), "interval", minutes=10, id="email-retry")
    _sched.add_job(_heartbeat, "interval", minutes=1, id="heartbeat")
    _sched.start()
    _heartbeat()


def stop() -> None:
    global _sched
    if _sched is not None:
        _sched.shutdown(wait=False)
        _sched = None
