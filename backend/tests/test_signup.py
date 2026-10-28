from sqlalchemy import select

from app.models import EmailLog, Institution, User, UserToken
from app.security import sha256

BASE = {"name": "Asha Patil", "password": "college2026", "user_type": "Student", "city_entered": "Poona"}


def code_for(db, email):
    """Tests cannot read the email, so set a known code on the newest token."""
    db.expire_all()
    u = db.execute(select(User).where(User.email == email)).scalar_one()
    t = db.execute(select(UserToken).where(UserToken.user_id == u.id).order_by(UserToken.id.desc())).scalars().first()
    t.code_hash = sha256(f"{u.id}:123456")
    db.commit()
    return "123456"


def signup(client, email, **kw):
    return client.post("/auth/signup", json={**BASE, "email": email, "college_name": "Shivneri College of Engineering", **kw})


def test_signup_validation(client):
    for body, field in [({"name": "A"}, "name"), ({"email": "not-an-email"}, "email"), ({"password": "short"}, "password"),
                        ({"user_type": "Alien"}, "user_type"), ({"mobile": "12345"}, "mobile")]:
        r = client.post("/auth/signup", json={**BASE, "email": "v@example.com", "college_name": "X College", **body})
        assert r.status_code == 400 and r.json()["detail"]["field"] == field, (body, r.text)


def test_signup_verify_and_location_and_new_college(client, db):
    r = signup(client, "asha@example.com")
    assert r.status_code == 200, r.text
    u = db.execute(select(User).where(User.email == "asha@example.com")).scalar_one()
    assert (u.role, u.email_verified, u.is_active) == ("college", False, False)
    assert (u.city, u.district, u.state, u.region, u.location_source, u.city_entered) == ("Pune", "Pune", "Maharashtra", "Western", "matched", "Poona")
    inst = db.get(Institution, u.institution_id)
    assert inst.verified is False and inst.state == "Maharashtra" and inst.aicte_id.startswith("NEW-") and u.institution_link == "approved"
    assert db.execute(select(EmailLog).where(EmailLog.to_addr == "asha@example.com", EmailLog.kind == "verify")).scalars().first()
    # sign-in refused until verified
    r = client.post("/auth/login", json={"email": "asha@example.com", "password": "college2026"})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "unverified"
    bad = client.post("/auth/verify", json={"email": "asha@example.com", "code": "000000"})
    assert bad.status_code == 400 and bad.json()["detail"]["code"] == "wrong_code"
    ok = client.post("/auth/verify", json={"email": "asha@example.com", "code": code_for(db, "asha@example.com")})
    assert ok.status_code == 200 and ok.json()["user"]["role"] == "college"
    client.cookies.clear()


def test_duplicate_email(client):
    signup(client, "dup@example.com")
    r = signup(client, "DUP@example.com")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "duplicate"


def test_resend_limits(client, db):
    signup(client, "resend@example.com")
    r = client.post("/auth/resend", json={"email": "resend@example.com"})
    assert r.status_code == 429 and "wait" in r.json()["detail"]["message"].lower()
    # pretend the codes are older than a minute: still capped at 5 per hour
    from datetime import timedelta
    u = db.execute(select(User).where(User.email == "resend@example.com")).scalar_one()
    for _ in range(4):
        for t in db.execute(select(UserToken).where(UserToken.user_id == u.id)).scalars():
            t.created_at = t.created_at - timedelta(seconds=61)
        db.commit()
        assert client.post("/auth/resend", json={"email": "resend@example.com"}).status_code == 200
    for t in db.execute(select(UserToken).where(UserToken.user_id == u.id)).scalars():
        t.created_at = t.created_at - timedelta(seconds=61)
    db.commit()
    r = client.post("/auth/resend", json={"email": "resend@example.com"})
    assert r.status_code == 429 and "5 codes" in r.json()["detail"]["message"]


def test_existing_aicte_id_is_pending_and_admin_is_told(client, db, h):
    r = signup(client, "claims@example.com", college_name="", aicte_id="1-SYN-4410021", user_type="Institution staff")
    assert r.status_code == 200 and r.json()["institution_link"] == "pending"
    links = client.get("/admin/links", headers=h["admin"]).json()
    me = next(x for x in links if x["email"] == "claims@example.com")
    assert me["institution"] == "Narmada Institute of Technology"
    assert client.post(f"/admin/links/{me['id']}", json={"approve": True}, headers=h["admin"]).json()["link"] == "approved"
    assert client.get("/admin/links", headers=h["officer"]).status_code == 403


def test_picked_college_attaches_student_directly(client, db, meta):
    nid = next(i["id"] for i in meta["institutions"] if i["name"].startswith("Kaveri Institute"))
    r = signup(client, "kav@example.com", college_name="", college_id=nid, city_entered="", pin="570001")
    assert r.status_code == 200, r.text
    assert r.json()["institution_link"] == "approved"
    u = db.execute(select(User).where(User.email == "kav@example.com")).scalar_one()
    assert u.location_source == "pin" and u.state == "Karnataka"


def test_unknown_city_is_manual_and_picked_is_kept(client, db):
    signup(client, "nowhere@example.com", city_entered="Xyzzyville")
    signup(client, "picked@example.com", city_entered="Aurangabad", picked={"district": "Aurangabad", "state": "Bihar"})
    db.expire_all()
    a = db.execute(select(User).where(User.email == "nowhere@example.com")).scalar_one()
    b = db.execute(select(User).where(User.email == "picked@example.com")).scalar_one()
    assert a.location_source == "manual" and a.state == ""
    assert (b.location_source, b.state, b.region) == ("picked", "Bihar", "Northern")


def test_lockout_message(client):
    for _ in range(5):
        client.post("/auth/login", json={"username": "head-ab", "password": "wrong-pass-1"})
    r = client.post("/auth/login", json={"username": "head-ab", "password": "anything"})
    assert r.status_code == 423 and r.json()["detail"]["message"].startswith("Account locked for 15 minutes")
    r = client.post("/auth/login", json={"username": "officer-lc", "password": "nope-nope-1"})
    assert r.json()["detail"]["message"] == "Wrong email or password."


def test_demo_login_only_in_demo_mode(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "demo_mode", False)
    assert client.post("/auth/demo-login", json={"username": "student"}).status_code == 404
    assert client.get("/auth/demo-accounts").json() == []
    monkeypatch.setattr(settings, "demo_mode", True)
    accts = client.get("/auth/demo-accounts").json()
    assert {"college", "desk_officer", "coordinator"} <= {a["role"] for a in accts} and all(a["sees"] for a in accts)
