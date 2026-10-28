"""Tests run against a separate database (samanvay_test), seeded once with
the full demo data. SMTP is switched off so no test sends real email."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://samanvay:samanvay@localhost:5432/samanvay_test")
os.environ["SMTP_HOST"] = ""
os.environ["BREVO_API_KEY"] = ""
os.environ["TEST_ALERT_EMAIL"] = "team@example.com"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["DEMO_MODE"] = "true"
os.environ["SIGNUP_RATE_LIMIT"] = "1000"   # many sign-ups in a row

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

BACKEND = Path(__file__).resolve().parent.parent
USERS = ("officer", "officer-pgrc", "officer-ab", "head", "head-pgrc", "coordinator", "management", "admin", "student")


@pytest.fixture(scope="session", autouse=True)
def seeded_db():
    env = {**os.environ}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env, check=True, capture_output=True)
    r = subprocess.run([sys.executable, "scripts/seed.py"], cwd=BACKEND, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    yield


@pytest.fixture(scope="session")
def client(seeded_db):
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def h(client):
    """Bearer headers per demo user: h['officer'], h['coordinator'], ..."""
    out = {}
    for u in USERS:
        r = client.post("/auth/demo-login", json={"username": u})
        assert r.status_code == 200, r.text
        out[u] = {"Authorization": f"Bearer {r.json()['token']}"}
    client.cookies.clear()
    return out


@pytest.fixture
def db():
    from app.db import SessionLocal
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


@pytest.fixture(scope="session")
def meta(client, h):
    return client.get("/meta", headers=h["officer"]).json()


def inst_id(meta, word):
    return next(i["id"] for i in meta["institutions"] if i["name"].startswith(word))


def cat_id(meta, word):
    return next(c["id"] for c in meta["categories"] if c["name"].startswith(word))
