"""SAMANVAY API. Synthetic demo data; not connected to any AICTE system."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from .config import settings
from .db import session_scope
from .models import User
from .routers import admin, auth, cases, complainant, dashboard, institutions, overlaps, public, reports
from .services import mail

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def sync_demo_emails() -> None:
    """Demo users' addresses are plus-addresses of TEST_ALERT_EMAIL, built
    here at start-up so no address is ever stored in code or seed data."""
    with session_scope() as db:
        for u in db.execute(select(User).where(User.demo_tag != "")).scalars():
            addr = mail.plus_address(settings.test_alert_email, u.demo_tag)
            u.email = addr or f"{u.demo_tag}@example.invalid"


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        sync_demo_emails()
    except Exception as e:  # noqa: BLE001 - DB may not be migrated yet
        logging.getLogger("samanvay").warning("could not sync demo emails: %s", e)
    if settings.scheduler_enabled:
        from . import scheduler
        scheduler.start()
    yield
    if settings.scheduler_enabled:
        from . import scheduler
        scheduler.stop()


app = FastAPI(title="SAMANVAY API", version="1.0", lifespan=lifespan,
              description="Integrated institution complaint monitoring prototype for AICTE (SIH26264). Synthetic data only.")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(RequestValidationError)
async def plain_validation(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(x) for x in first.get("loc", [])[1:]) or "input"
    return JSONResponse(status_code=422, content={"detail": f"Please check '{field}': {first.get('msg', 'invalid value')}."})


for r in (auth.router, complainant.router, cases.router, institutions.router, overlaps.router, dashboard.router, reports.router,
          admin.router, public.router):
    app.include_router(r)


@app.get("/")
def root():
    return {"name": "SAMANVAY API", "docs": "/docs", "note": "Synthetic demo data. Not connected to any AICTE system."}


@app.get("/health")
def health():
    return {"ok": True}
