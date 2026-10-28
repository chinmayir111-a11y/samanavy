#!/bin/sh
# Container entry: migrate, seed once on an empty database, then serve.
set -e
python -m alembic upgrade head
if python - <<'PY'
import sys
from sqlalchemy import text
from app.db import engine
with engine.connect() as c:
    n = c.execute(text("SELECT count(*) FROM complaint_case")).scalar()
sys.exit(0 if n == 0 else 1)
PY
then python scripts/seed.py; fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers
