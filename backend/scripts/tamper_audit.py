#!/usr/bin/env python3
"""Demo: quietly change one audit entry, as a database insider might, then
show that "Verify" catches it. Restore afterwards.

    python scripts/tamper_audit.py            # tamper the latest case action
    python scripts/tamper_audit.py --restore  # put it back"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.db import session_scope  # noqa: E402

SAVE = Path(__file__).resolve().parent.parent / "uploads" / ".tamper_backup.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()
    with session_scope() as db:
        db.execute(text("ALTER TABLE audit_log DISABLE TRIGGER audit_log_no_update"))
        try:
            if a.restore:
                if not SAVE.exists():
                    print("Nothing to restore.")
                    return 0
                b = json.loads(SAVE.read_text())
                db.execute(text("UPDATE audit_log SET summary=:s WHERE id=:i"), {"s": b["summary"], "i": b["id"]})
                SAVE.unlink()
                print(f"Restored entry #{b['id']}. Press Verify again: the chain is whole.")
            else:
                row = db.execute(text("SELECT id, summary FROM audit_log WHERE entity='case' OR entity='overlap_alert' "
                                      "ORDER BY id DESC LIMIT 1")).first()
                SAVE.parent.mkdir(parents=True, exist_ok=True)
                SAVE.write_text(json.dumps({"id": row.id, "summary": row.summary}))
                db.execute(text("UPDATE audit_log SET summary=:s WHERE id=:i"),
                           {"s": row.summary + " (quietly edited: decision reversed)", "i": row.id})
                print(f"Tampered entry #{row.id} directly in the database (trigger bypassed).")
                print("Open Audit log and press Verify: it turns red at that entry.")
        finally:
            db.execute(text("ALTER TABLE audit_log ENABLE TRIGGER audit_log_no_update"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
