#!/usr/bin/env python3
"""Reset the database to the synthetic demo data: 12 fictional institutions
(named after rivers; none is a real college), 4 units, 12 demo accounts and
about 120 cases with five planted stories (see docs/DEMO_SCRIPT.md).

Dates are relative to today, so ages and SLA chips look the same on any day.
No email is sent while seeding."""
from __future__ import annotations

import random
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import session_scope  # noqa: E402
from app.models import Case, CaseEvent, Category, Institution, Unit, User  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services import audit, location, mail, overlap, rules, sla  # noqa: E402

R = random.Random(26264)

UNITS = [("RB", "Regulation Bureau", "Regulatory action on approved institutions: inspections, show-cause, penalties."),
         ("PGRC", "Public Grievance Redressal Cell", "Complaints from students, parents, staff and the public."),
         ("AB", "Approval Bureau", "Approval, extension of approval and intake changes."),
         ("LC", "Legal Cell", "Court cases and legal opinions.")]

CATEGORIES = [("Faculty shortage / qualification", "faculty", 45), ("Excess fee / refund", "fees", 30),
              ("Infrastructure deficiency", "infrastructure", 60), ("Admission irregularity", "admission", 30),
              ("Approval / affiliation dispute", "approval", 60), ("Harassment / ragging", "harassment", 15),
              ("Scholarship not disbursed", "scholarship", 30), ("Certificates withheld", "certificates", 21),
              ("Salary not paid to staff", "salary", 45), ("Inspection / compliance", "inspection", 90),
              ("Other grievance", "other", 30)]

# Fictional institutions. AICTE-style ids are invented ("1-SYN-...").
INSTITUTIONS = [
    ("1-SYN-4410021", "Narmada Institute of Technology", ["NIT Jabalpur (synthetic)"], "Jabalpur", "Madhya Pradesh", "West", "482001", "Engineering"),
    ("1-SYN-5520117", "Kaveri Institute of Engineering and Technology", [], "Mysuru", "Karnataka", "South", "570001", "Engineering"),
    ("1-SYN-5520388", "Kaveri College of Pharmacy", [], "Thanjavur", "Tamil Nadu", "South", "613001", "Pharmacy"),
    ("1-SYN-4410240", "Sahyadri Institute of Technology", [], "Pune", "Maharashtra", "West", "411001", "Engineering"),
    ("1-SYN-4410377", "Sahyadri Valley College of Engineering", [], "Kolhapur", "Maharashtra", "West", "416001", "Engineering"),
    ("1-SYN-3310045", "Ganga Institute of Management Studies", [], "Varanasi", "Uttar Pradesh", "North", "221001", "Management"),
    ("1-SYN-6630012", "Brahmaputra College of Engineering", [], "Guwahati", "Assam", "East", "781001", "Engineering"),
    ("1-SYN-5520902", "Godavari Institute of Engineering", [], "Rajahmundry", "Andhra Pradesh", "South", "533101", "Engineering"),
    ("1-SYN-3310588", "Yamuna Polytechnic", [], "Karnal", "Haryana", "North", "132001", "Diploma"),
    ("1-SYN-6630271", "Mahanadi Institute of Technology", [], "Cuttack", "Odisha", "East", "753001", "Engineering"),
    ("1-SYN-3310733", "Chenab College of Architecture", [], "Jammu", "Jammu and Kashmir", "North", "180001", "Architecture"),
    ("1-SYN-6630459", "Teesta Institute of Pharmacy", [], "Siliguri", "West Bengal", "East", "734001", "Pharmacy"),
]

# username, demo tag, name, title, role, unit
USERS = [
    ("officer", "officer", "A. Kulkarni", "Desk Officer, Regulation Bureau", "desk_officer", "RB"),
    ("officer-pgrc", "officer-pgrc", "S. Iyer", "Desk Officer, PGRC", "desk_officer", "PGRC"),
    ("officer-ab", "officer-ab", "N. Bhat", "Desk Officer, Approval Bureau", "desk_officer", "AB"),
    ("officer-lc", "officer-lc", "F. Ansari", "Desk Officer, Legal Cell", "desk_officer", "LC"),
    ("head", "head", "R. Menon", "Head, Regulation Bureau", "unit_head", "RB"),
    ("head-pgrc", "head-pgrc", "P. Das", "Head, PGRC", "unit_head", "PGRC"),
    ("head-ab", "head-ab", "V. Singh", "Head, Approval Bureau", "unit_head", "AB"),
    ("head-lc", "head-lc", "J. Thomas", "Head, Legal Cell", "unit_head", "LC"),
    ("coordinator", "coordinator", "M. Qureshi", "Coordinator (cross-unit)", "coordinator", None),
    ("management", "management", "K. Rao", "Chairman's office (read-only)", "management", None),
    ("admin", "admin", "T. Joseph", "Technical Admin", "admin", None),
    ("student", "student", "R. Verma", "Complainant (Student)", "college", None),
]

TEXT = {
    "faculty": ["Students state that {n} posts of assistant professor in {d} are vacant and classes are taken by lab staff.",
                "Faculty listed on the mandatory disclosure page are not teaching at the institute; {d} has no qualified faculty.",
                "Lecturers in {d} left mid-semester and no replacement faculty was appointed."],
    "fees": ["Parent complains that the institute charged Rs {m} over the approved fee and refuses a refund after withdrawal.",
             "Students were asked to pay a development fee of Rs {m} that is not in the fee approved by the state committee.",
             "Refund of fee after cancellation of admission not made for {n} months."],
    "infrastructure": ["Laboratories for {d} lack equipment; the computer lab has {n} working machines for 120 students.",
                       "Hostel and library buildings shown during approval are not available to students.",
                       "Classrooms are shared with another institution on the same campus; built-up area is short of norms."],
    "admission": ["Admissions made beyond the approved intake in {d}; {n} extra seats filled without approval.",
                  "Merit list for management quota not published; admission given without counselling.",
                  "Students admitted without eligibility marks in {d}."],
    "approval": ["Institute is running {d} without extension of approval for this year.",
                 "Students fear the programme is unapproved; affiliation letter from the university not shown.",
                 "Dispute over change of name and site of the institute without approval."],
    "harassment": ["Student reports ragging in the hostel by seniors; anti-ragging committee did not act.",
                   "Complaint of harassment of a woman faculty member by a senior official.",
                   "Students threatened with expulsion after complaining about fees."],
    "scholarship": ["Post-matric scholarship for {n} students not credited although the institute received the funds.",
                    "Institute is asking students to pay fees despite scholarship sanction.",
                    "Scholarship forms not verified by the institute before the portal deadline."],
    "certificates": ["Original certificates of a student withheld for demanding payment of the full course fee.",
                     "Transfer certificate and migration certificate not issued for {n} months.",
                     "Degree certificates withheld until students pay hostel dues."],
    "salary": ["Teaching staff have not received salary for {n} months; PF not deposited.",
               "Faculty salaries paid below the scale shown to AICTE; arrears pending.",
               "Non-teaching staff unpaid wages for {n} months."],
    "inspection": ["Inspection found deficiencies in {d}: faculty ratio, library and lab equipment below norms.",
                   "Mandatory disclosure on the website does not match the inspection findings.",
                   "Compliance report after last inspection not submitted."],
}
DEPTS = ["Computer Science", "Mechanical", "Civil", "Electronics", "Pharmaceutics", "MBA", "Architecture"]
DECISIONS = ["Institution replied with documents; complaint resolved and complainant informed.",
             "Refund made to the complainant; closed.", "Deficiency rectified as seen in compliance report; closed.",
             "Complaint not substantiated after hearing; closed with advice to the institution.",
             "Warning letter issued; compliance confirmed.", "Forwarded to the affiliating university; closed at AICTE."]

PASSWORD = settings.demo_password


def fill(topic: str) -> str:
    return R.choice(TEXT[topic]).format(n=R.randint(2, 9), d=R.choice(DEPTS), m=f"{R.randint(2, 9)}0,000")


def at(d: date, hour: int = 11) -> datetime:
    return datetime.combine(d, time(hour, R.randint(0, 59)), tzinfo=rules.IST)


def main() -> None:
    with session_scope() as db:
        db.execute(text("ALTER TABLE audit_log DISABLE TRIGGER audit_log_no_update"))
        db.execute(text("TRUNCATE notification, email_log, case_link, case_event, overlap_alert, complaint_case, "
                        "user_token, app_user, category, institution, unit, setting, audit_log RESTART IDENTITY CASCADE"))
        db.execute(text("ALTER TABLE audit_log ENABLE TRIGGER audit_log_no_update"))
        units = {}
        for code, name, desc in UNITS:
            units[code] = Unit(code=code, name=name, description=desc)
            db.add(units[code])
        cats = {}
        for name, topic, days in CATEGORIES:
            cats[topic] = Category(name=name, topic=topic, sla_days=days)
            db.add(cats[topic])
        insts = {}
        for aid, name, aliases, city, state, region, pin, kind in INSTITUTIONS:
            loc = location.resolve(city, pin)
            insts[name.split()[0] + ("2" if name.split()[0] in [n.split()[0] for n in insts] else "")] = i = Institution(
                aicte_id=aid, name=name, aliases=aliases, address=f"Synthetic address, {city}", city=city, state=loc.get("state") or state,
                region=loc.get("region", ""), pin=pin, kind=kind, email="", synthetic=True, district=loc.get("district", ""),
                sub_region=loc.get("sub_region", ""), location_source=loc.get("source", ""), verified=True)
            db.add(i)
        db.flush()
        users = {}
        pw = hash_password(PASSWORD)
        for uname, tag, name, title, role, unit in USERS:
            users[uname] = User(username=uname, demo_tag=tag, email=mail.plus_address(settings.test_alert_email, tag)
                                or f"{tag}@example.invalid", name=name, title=title, role=role,
                                unit_id=units[unit].id if unit else None, password_hash=pw, created_at=rules.real_now())
            if role == "college":   # demo student of Narmada, verified, located by PIN
                n = insts["Narmada"]
                for k, v in dict(user_type="Student", institution_id=n.id, institution_link="approved", city_entered="Jabalpur",
                                 city="Jabalpur", district=n.district, sub_region=n.sub_region, state=n.state, region=n.region,
                                 pin=n.pin, location_source="pin").items():
                    setattr(users[uname], k, v)
            db.add(users[uname])
        db.flush()
        officer_of = {"RB": users["officer"], "PGRC": users["officer-pgrc"], "AB": users["officer-ab"], "LC": users["officer-lc"]}
        today = rules.today(db)
        specs: list[dict] = []

        def spec(inst, unit, topic, days_ago, desc=None, status="open", typed="", disposed_after=None, history=None, **kw):
            specs.append(dict(inst=inst, unit=unit, topic=topic, received=today - timedelta(days=days_ago),
                              desc=desc or fill(topic), status=status, typed=typed, disposed_after=disposed_after,
                              history=history, **kw))

        # ---- Story 1: Narmada, PGRC faculty complaint + RB inspection, different words, both open.
        spec("Narmada", "PGRC", "faculty", 20, desc="Third-year CSE students say most lecturers left mid-semester. Classes for "
             "Data Structures and DBMS are taken by lab assistants and no qualified faculty has joined since July.",
             history=[(2, "Letter sent to institution seeking reply")], next_action="Examine institution's reply when received")
        spec("Narmada", "RB", "inspection", 12, desc="Inspection report: faculty-student ratio in Computer Science below norms, "
             "cadre posts vacant, no PhD faculty; mandatory disclosure on the website not updated.",
             history=[(3, "Documents called for")], next_action="Decide on show-cause notice")
        # ---- Story 2: Kaveri, typed name without an id (PGRC) + RB case with the id.
        spec("Kaveri", "RB", "fees", 26, desc="Students allege a development fee of Rs 45,000 collected over the approved "
             "fee for B.Tech first year; no receipts given.", history=[(4, "Letter sent to institution seeking reply")])
        spec(None, "PGRC", "fees", 9, typed="Kaveri Inst. of Engg & Tech", desc="Parent complaint: college took Rs 45,000 "
             "extra as development fee from first-year B.Tech students and refuses to refund it.", source="Email")
        # ---- Story 3: Sahyadri Institute, three RB cases, one overdue by 20 days (escalation in progress).
        spec("Sahyadri", "RB", "salary", 45 + 20, desc="Teaching staff unpaid for four months; PF not deposited. "
             "Staff association letter enclosed.", history=[(5, "Letter sent to institution seeking reply"),
                                                            (30, "Reminder sent to institution")])
        spec("Sahyadri", "RB", "certificates", 10, history=[(2, "Letter sent to institution seeking reply")])
        spec("Sahyadri", "RB", "faculty", 120, status="disposed", disposed_after=40)
        # ---- Story 4: transferred RB -> PGRC with full history (Godavari).
        spec("Godavari", "RB", "scholarship", 40, transfer_to="PGRC", desc="Post-matric scholarship for 37 students not "
             "credited; students allege the institute is holding the funds.")
        # A transfer still waiting for the PGRC head to accept (Brahmaputra).
        spec("Brahmaputra", "AB", "harassment", 6, pending_transfer="PGRC", desc="Student reports ragging in the hostel; "
             "it was filed with the wrong unit.")
        # ---- Story 5: clean institution (Ganga): history disposed, one open case in one unit.
        for d in (300, 210, 150):
            spec("Ganga", R.choice(["PGRC", "AB"]), R.choice(["fees", "certificates", "admission"]), d, status="disposed",
                 disposed_after=R.randint(10, 28))
        spec("Ganga", "PGRC", "certificates", 5)

        # ---- Background: mostly disposed history; open cases sit in one "home" unit per institution.
        topics = [t for _, t, _ in CATEGORIES if t != "other"]
        home = {"Kaveri2": "PGRC", "Sahyadri2": "AB", "Brahmaputra": "PGRC", "Godavari": "PGRC", "Yamuna": "AB",
                "Mahanadi": "RB", "Chenab": "LC", "Teesta": "PGRC", "Narmada": None, "Kaveri": None, "Sahyadri": None, "Ganga": None}
        while len(specs) < 120:
            key = R.choice(list(insts))
            if R.random() < 0.72 or home[key] is None:
                days = R.randint(60, 420)
                spec(key, R.choice(list(units)), R.choice(topics), days, status="disposed",
                     disposed_after=R.randint(8, min(days - 5, 95)))
            else:
                spec(key, home[key], R.choice(topics), R.randint(3, 55))

        specs.sort(key=lambda s: s["received"])
        made = {}
        for s in specs:
            unit, cat = units[s["unit"]], cats[s["topic"]]
            inst = insts[s["inst"]] if s["inst"] else None
            off = officer_of[s["unit"]]
            recv = s["received"]
            c = Case(case_id=_next_id(db, unit, recv.year), source_ref=f"{unit.code}/F-{R.randint(100, 999)}/{recv.year}",
                     source=s.get("source", R.choice(["Unit register", "Email", "Post", "CPGRAMS (simulated)"])),
                     institution_id=inst.id if inst else None, raw_institution_text=s["typed"], received_on=recv,
                     category_id=cat.id, description=s["desc"], status="RECEIVED", unit_id=unit.id,
                     held_since=at(recv), sla_days=cat.sla_days, expected_disposal_on=recv + timedelta(days=cat.sla_days),
                     priority=R.choice(["Normal"] * 6 + ["High"]), complainant_name=R.choice(["Student", "Parent", "Faculty member", "Staff association"]),
                     suggestion_status="confirmed" if inst else "none", next_action=s.get("next_action", ""),
                     created_at=at(recv), updated_at=at(recv))
            db.add(c)
            db.flush()
            made[id(s)] = c
            ev = lambda kind, d, who=None, **kw: db.add(CaseEvent(case_id=c.id, at=at(d, R.randint(10, 17)), kind=kind,  # noqa: E731
                                                                  actor_id=who.id if who else None,
                                                                  actor=audit.actor_label(who) if who else "System",
                                                                  unit_id=(who.unit_id if who and who.unit_id else c.unit_id), **kw))
            ev("received", recv, remarks=f"Received by {unit.code} ({c.source}).")
            if not inst:
                overlap.suggest_for(db, c)
                continue
            assign_day = recv + timedelta(days=R.randint(0, 2))
            if assign_day <= today:
                c.assigned_officer_id, c.status, c.held_since = off.id, "UNDER_PROCESS", at(assign_day)
                ev("assigned", assign_day, users["head" if unit.code == "RB" else f"head-{unit.code.lower()}"],
                   remarks=f"Assigned to {off.name}.")
            for days_after, action in s["history"] or []:
                d = recv + timedelta(days=days_after)
                if d <= today:
                    ev("action", d, off, action_type=action, remarks="Recorded from the unit's file.")
                    c.last_action, c.last_action_on = action, d
            if s["status"] == "open" and not s["history"] and R.random() < 0.6:
                d = min(today, recv + timedelta(days=R.randint(2, 10)))
                ev("action", d, off, action_type="Letter sent to institution seeking reply", remarks="Recorded from the unit's file.")
                c.last_action, c.last_action_on = "Letter sent to institution seeking reply", d
            if s["status"] == "disposed":
                d = recv + timedelta(days=s["disposed_after"])
                ev("action", d - timedelta(days=3), off, action_type="Reply received from institution", remarks="Reply on file.")
                c.status, c.disposed_on, c.disposal_note = "DISPOSED", d, R.choice(DECISIONS)
                c.last_action, c.last_action_on = "Reply received from institution", d - timedelta(days=3)
                ev("disposed", d, off, remarks=c.disposal_note)
            if s.get("transfer_to"):
                to = units[s["transfer_to"]]
                d1, d2 = recv + timedelta(days=6), recv + timedelta(days=9)
                ev("transfer_requested", d1, off, remarks=f"Transfer to {to.code} requested: scholarship grievance from "
                   "students belongs with the Public Grievance Redressal Cell.", meta={"to": to.code})
                ev("transfer_accepted", d2, users["head-pgrc"], remarks=f"{to.code} accepted the transfer from RB.",
                   meta={"from": "RB", "to": to.code})
                ev("assigned", d2, users["head-pgrc"], remarks=f"Assigned to {officer_of[to.code].name}.")
                c.unit_id, c.assigned_officer_id, c.held_since, c.status = to.id, officer_of[to.code].id, at(d2), "UNDER_PROCESS"
                ev("action", d2 + timedelta(days=3), officer_of[to.code], action_type="Letter sent to institution seeking reply",
                   remarks="Asked for the scholarship ledger.")
                c.last_action, c.last_action_on = "Letter sent to institution seeking reply", d2 + timedelta(days=3)
            if s.get("pending_transfer"):
                to = units[s["pending_transfer"]]
                c.transfer_to_unit_id, c.status = to.id, "TRANSFERRED"
                c.transfer_reason = "Ragging complaint is a student grievance; PGRC handles it with the anti-ragging cell."
                ev("transfer_requested", recv + timedelta(days=1), off, remarks=f"Transfer to {to.code} requested: {c.transfer_reason}",
                   meta={"to": to.code})
        db.flush()
        audit.record(db, actor="System (seed)", action="seed", entity="system", entity_id=None,
                     summary=f"Synthetic demo data loaded: {len(INSTITUTIONS)} institutions, {len(specs)} cases.")
        # Bring SLA stages and the escalation ladder up to today, then raise overlap alerts.
        out = sla.run_daily(db)
        n = overlap.scan_all(db, notify_people=True)
        db.flush()
        db.execute(text("DELETE FROM email_log"))   # never mail anyone for seeded history
        print(f"Seeded {len(specs)} cases, {len(INSTITUTIONS)} institutions, {len(USERS)} accounts. "
              f"SLA alerts {out['sla_alerts']}, escalations {out['escalations']}, open overlap alerts {n}.")


def _next_id(db, unit: Unit, year: int) -> str:
    from app.services.workflow import next_case_id
    return next_case_id(db, unit, year)


if __name__ == "__main__":
    main()
