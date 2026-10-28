"""Reports as plain tables, each downloadable as CSV or PDF."""
from __future__ import annotations

import csv
import io
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import INTERNAL, require
from ..models import OPEN_STATUSES, Case, OverlapAlert, Unit, User
from ..services import rules, sla

router = APIRouter(prefix="/reports", tags=["reports"])
REPORTS = {
    "unit": "Unit-wise performance", "region": "Region-wise status", "institution": "Institution-wise history",
    "ageing": "Ageing of open cases", "overlaps": "Overlapping and duplicate cases",
    "monthly": "Monthly performance", "quarterly": "Quarterly performance",
}


def _perf(groups: dict[str, list[Case]], today) -> list[list]:
    rows = []
    for k, cs in sorted(groups.items()):
        disposed = [c for c in cs if c.status == "DISPOSED"]
        open_ = [c for c in cs if c.status in OPEN_STATUSES]
        in_time = sum(1 for c in disposed if c.disposed_on and c.disposed_on <= c.expected_disposal_on)
        rows.append([k, len(cs), len(open_), len(disposed), sum(sla.days_left(c, today) < 0 for c in open_),
                     f"{100 * len(disposed) / len(cs):.0f}%" if cs else "-",
                     f"{100 * in_time / len(disposed):.0f}%" if disposed else "-",
                     f"{sum(sla.age_days(c, today) for c in disposed) / len(disposed):.0f}" if disposed else "-"])
    return rows


PERF_HEAD = ["", "Received", "Open", "Disposed", "Overdue", "Disposal rate", "Disposed in time", "Avg days to dispose"]


def build(db: Session, kind: str) -> tuple[list[str], list[list]]:
    today = rules.today(db)
    cases = db.execute(select(Case)).scalars().unique().all()
    g: dict[str, list[Case]] = defaultdict(list)
    if kind == "unit":
        for c in cases:
            g[c.unit.code].append(c)
        return ["Unit", *PERF_HEAD[1:]], _perf(g, today)
    if kind == "region":
        for c in cases:
            i = c.institution or c.suggested_institution
            g[i.region if i else "Unmatched"].append(c)
        return ["Region", *PERF_HEAD[1:]], _perf(g, today)
    if kind == "monthly":
        for c in cases:
            g[c.received_on.strftime("%Y-%m")].append(c)
        return ["Month received", *PERF_HEAD[1:]], _perf(g, today)
    if kind == "quarterly":
        for c in cases:
            g[f"{c.received_on.year}-Q{(c.received_on.month - 1) // 3 + 1}"].append(c)
        return ["Quarter received", *PERF_HEAD[1:]], _perf(g, today)
    if kind == "institution":
        rows = []
        for c in sorted(cases, key=lambda c: ((c.institution or c.suggested_institution).name if (c.institution or c.suggested_institution)
                                              else c.raw_institution_text, c.received_on)):
            i = c.institution or c.suggested_institution
            rows.append([i.name if i else c.raw_institution_text, i.aicte_id if i else "", c.case_id, c.unit.code,
                         c.category.name, c.received_on.isoformat(), c.status.replace("_", " ").title(), c.last_action,
                         c.disposed_on.isoformat() if c.disposed_on else "", c.disposal_note[:80]])
        return ["Institution", "AICTE ID", "Case", "Unit", "Category", "Received", "Status", "Last action", "Disposed", "Decision"], rows
    if kind == "ageing":
        units = [u.code for u in db.execute(select(Unit).order_by(Unit.id)).scalars()]
        rows = []
        for b, _, _ in sla.BUCKETS:
            rows.append([f"{b} days", *[sum(1 for c in cases if c.status in OPEN_STATUSES and c.unit.code == u
                                            and sla.bucket(sla.age_days(c, today)) == b) for u in units]])
        return ["Age", *units], rows
    if kind == "overlaps":
        units = {u.id: u.code for u in db.execute(select(Unit)).scalars()}
        rows = []
        for a in db.execute(select(OverlapAlert).order_by(OverlapAlert.id)).scalars():
            refs = ", ".join(sorted({p["a_ref"] for p in a.pairs} | {p["b_ref"] for p in a.pairs}))
            rows.append([a.institution.name, ", ".join(units[u] for u in a.unit_ids), refs, f"{a.score:.0f}", a.status,
                         units.get(a.lead_unit_id, "") if a.lead_unit_id else "", a.resolution[:90]])
        return ["Institution", "Units", "Cases", "Score", "Status", "Lead unit", "Decision"], rows
    raise HTTPException(404, "No such report.")


@router.get("")
def list_reports(user: User = Depends(require(*INTERNAL))):
    return [{"key": k, "title": t} for k, t in REPORTS.items()]


@router.get("/{kind}")
def report(kind: str, db: Session = Depends(get_db), user: User = Depends(require(*INTERNAL))):
    head, rows = build(db, kind)
    return {"key": kind, "title": REPORTS[kind], "head": head, "rows": rows, "as_of": rules.today(db).isoformat()}


@router.get("/{kind}/csv")
def report_csv(kind: str, db: Session = Depends(get_db), user: User = Depends(require(*INTERNAL))):
    head, rows = build(db, kind)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["SAMANVAY demo - synthetic data", REPORTS[kind], f"as of {rules.today(db).isoformat()}"])
    w.writerow(head)
    w.writerows(rows)
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="samanvay-{kind}.csv"'})


@router.get("/{kind}/pdf")
def report_pdf(kind: str, db: Session = Depends(get_db), user: User = Depends(require(*INTERNAL))):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    head, rows = build(db, kind)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=28, rightMargin=28, topMargin=28, bottomMargin=28)
    ss = getSampleStyleSheet()
    cell = ss["BodyText"].clone("cell", fontSize=7.5, leading=9)
    data = [[Paragraph(f"<b>{h}</b>", cell) for h in head]] + [[Paragraph(str(x), cell) for x in r] for r in rows]
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDF2EC")),
                           ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#2D5A43")),
                           ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#D9E0D9")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    doc.build([Paragraph(f"SAMANVAY - {REPORTS[kind]}", ss["Title"]),
               Paragraph(f"As of {rules.today(db):%d %b %Y}. Synthetic demo data, not an AICTE record.", ss["Normal"]),
               Spacer(1, 10), t])
    return Response(buf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="samanvay-{kind}.pdf"'})
