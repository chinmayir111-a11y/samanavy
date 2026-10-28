from tests.conftest import cat_id, inst_id


def new_case(client, h, meta, who="officer", word="Yamuna", cat="Excess fee", **kw):
    body = {"category_id": cat_id(meta, cat), "description": "Test complaint about excess fee collected from students.",
            "institution_id": inst_id(meta, word) if word else None, **kw}
    r = client.post("/cases", json=body, headers=h[who])
    assert r.status_code == 200, r.text
    return r.json()["case_id"]


def test_case_has_all_problem_statement_fields(client, h):
    rows = client.get("/cases?status=OPEN", headers=h["officer"]).json()
    r = rows[0]
    for f in ("case_id", "received_on", "category", "status", "unit", "officer", "last_action", "next_action",
              "last_action_on", "expected_disposal_on", "holder"):
        assert f in r


def test_create_typed_name_gets_suggestion_then_confirm_learns_alias(client, h, meta):
    ref = new_case(client, h, meta, word=None, raw_institution_text="Mahanadi Inst of Tech, Cuttack")
    d = client.get(f"/cases/{ref}", headers=h["officer"]).json()
    assert d["suggestion_status"] == "suggested" and d["suggestion"]["institution"]["name"].startswith("Mahanadi")
    r = client.post(f"/cases/{ref}/confirm-institution", json={"accept": True}, headers=h["officer"])
    assert r.status_code == 200
    inst = client.get(f"/institutions/{inst_id(meta, 'Mahanadi')}", headers=h["officer"]).json()
    assert "Mahanadi Inst of Tech, Cuttack" in inst["institution"]["aliases"]


def test_narmada_overlap_banner_and_reasons(client, h):
    alerts = client.get("/overlaps", headers=h["coordinator"]).json()
    nar = next(a for a in alerts if a["institution"]["name"].startswith("Narmada"))
    assert nar["score"] >= 65 and {"RB", "PGRC"} <= set(nar["units"])
    assert any("AICTE ID" in r for r in nar["pairs"][0]["reasons"])


def test_new_cross_unit_case_raises_alert(client, h, meta):
    new_case(client, h, meta, who="officer-ab", word="Chenab", cat="Excess fee")
    new_case(client, h, meta, who="officer-pgrc", word="Chenab", cat="Excess fee")
    alerts = client.get("/overlaps", headers=h["coordinator"]).json()
    assert any(a["institution"]["name"].startswith("Chenab") for a in alerts)


def test_conflict_guard_warns_then_records_acknowledgement(client, h, meta):
    rb = new_case(client, h, meta, who="officer", word="Teesta", cat="Infrastructure")
    new_case(client, h, meta, who="officer-pgrc", word="Teesta", cat="Harassment")
    body = {"action_type": "Show-cause notice issued", "remarks": "Deficiencies confirmed."}
    r = client.post(f"/cases/{rb}/action", json=body, headers=h["officer"])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "conflict"
    assert r.json()["detail"]["cases"][0]["unit"] == "PGRC"
    r = client.post(f"/cases/{rb}/action", json={**body, "ack_reason": "Spoke to PGRC; separate issue."}, headers=h["officer"])
    assert r.status_code == 200 and r.json()["conflict_acknowledged"]
    kinds = [e["kind"] for e in client.get(f"/cases/{rb}", headers=h["officer"]).json()["events"]]
    assert "conflict_acknowledged" in kinds
    # a non-regulatory action never asks
    r = client.post(f"/cases/{rb}/action", json={"action_type": "Reminder sent to institution"}, headers=h["officer"])
    assert r.status_code == 200


def test_transfer_needs_reason_and_the_receiving_head(client, h, meta):
    ref = new_case(client, h, meta, who="officer", word="Yamuna", cat="Scholarship")
    pgrc = next(u["id"] for u in meta["units"] if u["code"] == "PGRC")
    assert client.post(f"/cases/{ref}/transfer", json={"to_unit_id": pgrc, "reason": "x"}, headers=h["officer"]).status_code == 400
    assert client.post(f"/cases/{ref}/transfer", json={"to_unit_id": pgrc, "reason": "Student grievance belongs to PGRC."},
                       headers=h["officer"]).status_code == 200
    assert client.post(f"/cases/{ref}/transfer/decide", json={"accept": True}, headers=h["head"]).status_code == 403
    assert client.post(f"/cases/{ref}/transfer/decide", json={"accept": True}, headers=h["head-pgrc"]).status_code == 200
    d = client.get(f"/cases/{ref}", headers=h["officer"]).json()
    assert d["unit"] == "PGRC" and not d["can_edit"]
    assert [e["kind"] for e in d["events"]][-2:] == ["transfer_requested", "transfer_accepted"]


def test_escalate_and_dispose(client, h, meta):
    ref = new_case(client, h, meta, who="officer", word="Mahanadi", cat="Certificates")
    assert client.post(f"/cases/{ref}/escalate", json={"reason": "Institution not responding at all."}, headers=h["officer"]).status_code == 200
    assert client.get(f"/cases/{ref}", headers=h["officer"]).json()["status"] == "ESCALATED"
    assert client.post(f"/cases/{ref}/dispose", json={"reason": "short"}, headers=h["officer"]).status_code == 400
    assert client.post(f"/cases/{ref}/dispose", json={"reason": "Certificates returned to the student."}, headers=h["officer"]).status_code == 200
    assert client.post(f"/cases/{ref}/action", json={"action_type": "Other"}, headers=h["officer"]).status_code == 400


def test_coordinator_assigns_lead_unit(client, h, meta):
    a = next(x for x in client.get("/overlaps", headers=h["coordinator"]).json() if x["institution"]["name"].startswith("Narmada"))
    rb = next(u["id"] for u in meta["units"] if u["code"] == "RB")
    assert client.post(f"/overlaps/{a['id']}/resolve", json={"action": "lead", "lead_unit_id": rb, "reason": "ok"},
                       headers=h["coordinator"]).status_code == 400
    assert client.post(f"/overlaps/{a['id']}/resolve", json={"action": "lead", "lead_unit_id": rb, "reason": "RB leads; PGRC informs complainant."},
                       headers=h["officer"]).status_code == 403
    r = client.post(f"/overlaps/{a['id']}/resolve", json={"action": "lead", "lead_unit_id": rb,
                    "reason": "RB leads; PGRC informs complainant."}, headers=h["coordinator"])
    assert r.status_code == 200
    d = client.get(f"/overlaps/{a['id']}", headers=h["coordinator"]).json()
    assert d["status"] == "coordinated" and d["lead_unit"] == "RB"
    # resolved pairs are not raised again on the next scan
    from app.db import SessionLocal
    from app.services import overlap
    with SessionLocal() as s:
        assert overlap.scan_institution(s, a["institution"]["id"]) is None
        s.rollback()


def test_merge_into_lead_case(client, h, meta):
    a = new_case(client, h, meta, who="officer-ab", word="Godavari", cat="Admission")
    b = new_case(client, h, meta, who="officer", word="Godavari", cat="Admission")
    al = next(x for x in client.get("/overlaps", headers=h["coordinator"]).json() if x["institution"]["name"].startswith("Godavari"))
    det = client.get(f"/overlaps/{al['id']}", headers=h["coordinator"]).json()
    lead = next(int(k) for k, v in det["cases"].items() if v["case_id"] == a)
    assert client.post(f"/overlaps/{al['id']}/resolve", json={"action": "merge", "merge_into": lead,
                       "reason": "Same admission complaint in two units."}, headers=h["coordinator"]).status_code == 200
    d = client.get(f"/cases/{b}", headers=h["officer"]).json()
    assert d["status"] == "DISPOSED" and a in d["disposal_note"]


def test_institution_360_sentence(client, h, meta):
    d = client.get(f"/institutions/{inst_id(meta, 'Narmada')}", headers=h["management"]).json()
    assert "open case" in d["summary"] and "RB" in d["summary"] and "PGRC" in d["summary"]
    clean = client.get(f"/institutions/{inst_id(meta, 'Ganga')}", headers=h["management"]).json()
    assert "no overlap" in clean["summary"]


def test_public_check_is_masked_and_minimal(client, h):
    ref = client.get("/cases?status=OPEN", headers=h["officer"]).json()[0]["case_id"]
    r = client.get(f"/public/check/{ref}")
    assert r.status_code == 200
    assert set(r.json()) == {"case_id", "institution", "status", "last_updated", "synthetic"}
    assert "*" in r.json()["institution"]
    assert client.get("/public/check/RB-2026-9999").status_code == 404


def test_public_submission_lands_in_pgrc_with_suggestion(client, meta):
    r = client.post("/public/complaints", json={"institution_text": "Yamuna Polytechnic Karnal", "category_id": cat_id(meta, "Excess"),
                                                "description": "College charged extra fee for the hostel this year.", "name": "A parent"})
    assert r.status_code == 200 and r.json()["case_id"].startswith("PGRC-")


def test_reports_and_exports(client, h):
    for k in ("unit", "region", "institution", "ageing", "overlaps", "monthly", "quarterly"):
        assert client.get(f"/reports/{k}", headers=h["management"]).json()["rows"], k
    assert client.get("/reports/unit/csv", headers=h["management"]).text.startswith("SAMANVAY demo")
    assert client.get("/reports/ageing/pdf", headers=h["management"]).content[:4] == b"%PDF"


def test_dashboard_numbers_add_up(client, h):
    d = client.get("/dashboard", headers=h["management"]).json()
    t = d["totals"]
    assert t["received"] == t["pending"] + t["disposed"]
    assert t["pending"] == t["received_status"] + t["under_process"] + t["transferred"] + t["escalated"]
    assert sum(b["count"] for b in d["ageing"]) == t["pending"]
