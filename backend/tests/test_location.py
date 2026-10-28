import pytest

from app.services import location as L


@pytest.mark.parametrize("typed,district,state,region", [
    ("Poona", "Pune", "Maharashtra", "Western"), ("Bombay", "Mumbai", "Maharashtra", "Western"),
    ("Bangalore", "Bengaluru Urban", "Karnataka", "South-West"), ("Madras", "Chennai", "Tamil Nadu", "Southern"),
    ("Calcutta", "Kolkata", "West Bengal", "Eastern"), ("Gurgaon", "Gurugram", "Haryana", "North-West"),
    ("Puen", "Pune", "Maharashtra", "Western"), ("Jabalpr", "Jabalpur", "Madhya Pradesh", "Central"),
    ("Siliguri", "Darjeeling", "West Bengal", "Eastern"),
])
def test_city_names_old_names_and_misspellings(typed, district, state, region):
    r = L.resolve(typed)
    assert (r["status"], r["district"], r["state"], r["region"]) == ("matched", district, state, region), r


def test_pin_wins_over_city_text():
    r = L.resolve("Mumbai", "411001")
    assert r["source"] == "pin" and r["district"] == "Pune" and r["state"] == "Maharashtra"
    assert L.resolve("", "221001")["district"] == "Varanasi"


def test_ambiguous_city_returns_choices():
    r = L.resolve("Aurangabad")
    assert r["status"] == "ambiguous" and 2 <= len(r["choices"]) <= 4
    assert {c["state"] for c in r["choices"]} >= {"Maharashtra", "Bihar"}


def test_unknown_city_falls_back_to_manual():
    r = L.resolve("Xyzzyville")
    assert r["status"] == "none" and r["source"] == "manual"
    assert "Maharashtra" in L.states() and "Pune" in L.districts("Maharashtra")


def test_confirmation_line():
    assert L.resolve("Poona")["line"] == "Pune, Pune district, Maharashtra, Western region"


def test_region_mapping_is_admin_editable(client, h):
    r = client.put("/admin/regions", json={"regions": {"Telangana": {"region": "Southern"}}}, headers=h["admin"])
    assert r.status_code == 200 and r.json()["Telangana"] == {"region": "Southern", "basis": "set by Admin"}
    assert client.get("/public/location?city=Hyderabad").json()["region"] == "Southern"
    client.put("/admin/regions", json={"regions": {"Telangana": {"region": "South-Central"}}}, headers=h["admin"])
    assert client.put("/admin/regions", json={"regions": {"Goa": {"region": "Moon"}}}, headers=h["admin"]).status_code == 400
