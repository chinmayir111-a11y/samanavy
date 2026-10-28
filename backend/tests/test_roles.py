import pytest

# (method, path, body, allowed roles)
ROUTES = [
    ("get", "/dashboard", None, {"officer", "officer-pgrc", "officer-ab", "head", "head-pgrc", "coordinator", "management", "admin"}),
    ("post", "/cases", {"category_id": 1, "description": "x" * 20, "raw_institution_text": "Some college"},
     {"officer", "officer-pgrc", "officer-ab", "head", "head-pgrc"}),
    ("post", "/overlaps/999999/resolve", {"action": "dismiss", "reason": "x" * 12}, {"coordinator"}),
    ("get", "/admin/overview", None, {"admin"}),
    ("put", "/admin/rules", {"values": {}}, {"admin"}),
    ("post", "/admin/invite", {"name": "x", "email": "bad", "role": "x"}, {"admin"}),
    ("post", "/admin/clock", {"days": 3}, {"admin"}),
    ("get", "/emails", None, {"admin", "management", "coordinator"}),
    ("post", "/emails/1/resend", None, {"admin"}),
]


@pytest.mark.parametrize("method,path,body,allowed", ROUTES)
def test_role_permissions(client, h, method, path, body, allowed):
    for user, hdr in h.items():
        r = getattr(client, method)(path, headers=hdr, **({"json": body} if body is not None else {}))
        if user in allowed:
            assert r.status_code != 403, (user, path, r.text)
        else:
            assert r.status_code == 403, (user, path, r.status_code)


def test_signed_out_is_401(client):
    assert client.get("/cases").status_code == 401


def test_other_units_case_is_read_only(client, h):
    pgrc_case = client.get("/cases?unit=PGRC&status=OPEN", headers=h["officer"]).json()[0]["case_id"]
    assert client.post(f"/cases/{pgrc_case}/action", json={"action_type": "Other"}, headers=h["officer"]).status_code == 403
    assert client.get(f"/cases/{pgrc_case}", headers=h["officer"]).json()["can_edit"] is False


def test_cookie_requests_need_csrf_header(client):
    client.post("/auth/demo-login", json={"username": "officer"})
    assert client.post("/inbox/read").status_code == 403
    assert client.post("/inbox/read", headers={"X-Requested-With": "samanvay"}).status_code == 200
    client.cookies.clear()


def test_password_login_and_lockout(client):
    from app.config import settings
    assert client.post("/auth/login", json={"username": "head", "password": settings.demo_password}).status_code == 200
    for _ in range(5):
        client.post("/auth/login", json={"username": "head-lc", "password": "wrong-pass-1"})
    assert client.post("/auth/login", json={"username": "head-lc", "password": settings.demo_password}).status_code == 423
    client.cookies.clear()
