PDF = b"%PDF-1.4\n%fake but valid header\n"


def file_one(client, h, key="fees", text="The college took Rs 30,000 extra as hostel fee and gave no receipt."):
    r = client.post("/my/complaints", json={"category_key": key, "description": text}, headers=h["student"])
    assert r.status_code == 200, r.text
    return r.json()["reference"]


def test_validation(client, h):
    assert client.post("/my/complaints", json={"category_key": "nope", "description": "x" * 30}, headers=h["student"]).status_code == 400
    r = client.post("/my/complaints", json={"category_key": "fees", "description": "too short"}, headers=h["student"])
    assert r.status_code == 400 and r.json()["detail"]["field"] == "description"
    r = client.post("/my/complaints", json={"category_key": "fees", "description": "x" * 30, "happened_on": "2999-01-01"}, headers=h["student"])
    assert r.status_code == 400


def test_system_picks_unit_and_runs_overlap(client, h):
    ref = file_one(client, h, key="approval", text="Our B.Tech course may not be approved this year; the college will not show the letter.")
    assert ref.startswith("AB-")
    officer = client.get(f"/cases/{ref}", headers=h["officer-ab"]).json()
    assert officer["source"] == "Complainant portal" and officer["institution"]["name"].startswith("Narmada")
    assert any(a["status"] == "open" for a in officer["alerts"]), "overlap detection ran against other units' open cases"


def test_files_checked_by_type_size_and_content(client, h):
    ref = file_one(client, h)
    ok = client.post(f"/my/complaints/{ref}/files", files=[("files", ("receipt.pdf", PDF, "application/pdf"))], headers=h["student"])
    assert ok.status_code == 200
    assert client.post(f"/my/complaints/{ref}/files", files=[("files", ("a.exe", b"MZ", "application/octet-stream"))], headers=h["student"]).status_code == 400
    assert client.post(f"/my/complaints/{ref}/files", files=[("files", ("fake.png", b"not a png", "image/png"))], headers=h["student"]).status_code == 400
    big = b"%PDF" + b"0" * (5 * 1024 * 1024 + 1)
    assert client.post(f"/my/complaints/{ref}/files", files=[("files", ("big.pdf", big, "application/pdf"))], headers=h["student"]).status_code == 413


def test_reference_qr_and_tracking_privacy(client, h):
    ref = file_one(client, h)
    client.post(f"/cases/{ref}/action", json={"action_type": "Letter sent to institution seeking reply",
                                               "remarks": "INTERNAL: principal is evasive, check with RB"}, headers=h["officer-pgrc"])
    qr = client.get(f"/public/qr/{ref}.svg")
    assert qr.status_code == 200 and qr.text.lstrip().startswith("<?xml")
    t = client.get(f"/my/complaints/{ref}", headers=h["student"])
    assert t.status_code == 200
    body = t.text
    for leak in ("INTERNAL", "evasive", "S. Iyer", "overlap", "Overlap", "SLA", "score"):
        assert leak not in body, leak
    j = t.json()
    assert [s["label"] for s in j["steps"]] == ["Received", "Assigned", "Under process", "Action taken", "Disposed"]
    assert j["unit"] == "Public Grievance Redressal Cell" and any("written to the college" in m["text"] for m in j["messages"])
    pub = client.get(f"/public/check/{ref}").json()
    assert set(pub) == {"case_id", "institution", "status", "last_updated", "synthetic"} and "*" in pub["institution"]


def test_complainant_sees_only_own(client, h):
    other = client.get("/cases?status=OPEN&unit=RB", headers=h["officer"]).json()[0]["case_id"]
    assert client.get(f"/my/complaints/{other}", headers=h["student"]).status_code == 404
    assert all(r["reference"] for r in client.get("/my/complaints", headers=h["student"]).json())


def test_college_role_cannot_use_officer_routes(client, h):
    for path in ("/cases", "/dashboard", "/overlaps", "/institutions", "/audit", "/today"):
        assert client.get(path, headers=h["student"]).status_code == 403, path
    assert client.get("/my/complaints", headers=h["officer"]).status_code == 403


def test_dashboard_has_state_and_city_drilldown(client, h):
    d = client.get("/dashboard", headers=h["management"]).json()
    mh = next(s for s in d["by_state"] if s["state"] == "Maharashtra")
    assert mh["region"] == "Western" and any(c["city"] == "Pune" for c in mh["cities"])
