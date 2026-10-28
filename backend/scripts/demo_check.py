#!/usr/bin/env python3
"""Green/red readiness checklist before a demo."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select, text  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import session_scope  # noqa: E402
from app.models import Case, Institution, OverlapAlert, User  # noqa: E402
from app.services import audit, matching, rules  # noqa: E402

G, R, E = "\033[32m", "\033[31m", "\033[0m"


def line(ok: bool, name: str, detail: str) -> bool:
    print(f"  {G + 'OK  ' if ok else R + 'FAIL'}{E} {name}: {detail}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true")
    a = ap.parse_args()
    ok = True
    print("SAMANVAY demo check")
    try:
        with session_scope() as db:
            db.execute(text("SELECT 1"))
            ok &= line(True, "Database", settings.database_url.split("@")[-1])
            n, i = db.scalar(select(func.count(Case.id))), db.scalar(select(func.count(Institution.id)))
            ok &= line(n >= 100 and i == 12, "Seed", f"{n} cases, {i} institutions")
            alerts = db.execute(select(OverlapAlert).where(OverlapAlert.status == "open")).scalars().all()
            names = {x.institution.name.split()[0] for x in alerts}
            ok &= line({"Narmada", "Kaveri"} <= names, "Demo stories", f"open overlap alerts: {', '.join(sorted(names)) or 'none'} (reseed if Narmada/Kaveri missing)")
            ok &= line(rules.offset_days(db) == 0, "Demo clock", f"+{rules.offset_days(db)} days (reset before the demo)")
            m = matching.name_score("Kaveri Inst. of Engg & Tech", ["Kaveri Institute of Engineering and Technology"])
            ok &= line(m.score >= 88, "Matcher", f"'Kaveri Inst. of Engg & Tech' scores {m.score:.0f}/100")
            v = audit.verify_chain(db)
            ok &= line(v["ok"], "Audit chain", f"{v['checked']} entries" + ("" if v["ok"] else f", broken at #{v['broken_id']} (make untamper)"))
            hb = rules.get(db, "scheduler_heartbeat")
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(hb)).total_seconds() if hb else None
            ok &= line(age is not None and age < 180, "Scheduler", f"heartbeat {int(age)} s ago" if age is not None else "no heartbeat: start the API")
            ok &= line(bool(db.scalar(select(func.count(User.id)).where(User.demo_tag != ""))), "Demo accounts",
                       f"password {settings.demo_password}")
    except Exception as e:  # noqa: BLE001
        return int(not line(False, "Database", f"{type(e).__name__}: {e} (run make db migrate seed)"))
    ok &= line(settings.email_configured, "Email", f"{settings.email_provider}, sender {settings.smtp_user or '-'}, test inbox {settings.test_alert_email or '-'}")
    if a.send:
        import subprocess
        r = subprocess.run([sys.executable, "scripts/test_alert_email.py"], capture_output=True, text=True)
        ok &= line(r.returncode == 0, "Email delivery", (r.stdout.strip().splitlines() or ["no output"])[-1])
    line(True, "SMS", "planned: no gateway connected (shown in the app)")
    print(("\n" + G + "Ready." if ok else "\n" + R + "Not ready: fix the red lines.") + E)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
