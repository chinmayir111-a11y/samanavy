"""Offline location resolver: city or PIN -> district, sub-region, state and AICTE region.

Data: backend/data/pincodes.csv.gz, trimmed from the India Post "All India Pincode Directory"
(data.gov.in, Government Open Data License - India). See docs/DATA_SOURCES.md.

Order: a valid PIN wins; then old city names (Poona -> Pune); then exact district, then exact
post-office locality, then fuzzy (RapidFuzz) over district and locality names. Two or more
places with the same name -> up to 4 choices for the person to pick. Nothing found -> the
person picks State then District. Location never blocks sign-up."""
from __future__ import annotations

import csv
import gzip
import re
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

from rapidfuzz import fuzz, process
from rapidfuzz.distance import OSA

DATA = Path(__file__).resolve().parents[2] / "data" / "pincodes.csv.gz"

OLD_NAMES = {
    "bombay": "mumbai", "poona": "pune", "bangalore": "bengaluru", "banglore": "bengaluru", "madras": "chennai",
    "calcutta": "kolkata", "gurgaon": "gurugram", "baroda": "vadodara", "trivandrum": "thiruvananthapuram",
    "mysore": "mysuru", "allahabad": "prayagraj", "benares": "varanasi", "banaras": "varanasi", "simla": "shimla",
    "pondicherry": "puducherry", "cawnpore": "kanpur", "calicut": "kozhikode", "cochin": "kochi",
    "mangalore": "mangaluru", "belgaum": "belagavi", "gulbarga": "kalaburagi", "vizag": "visakhapatnam",
}
# Cities whose district has another name in the India Post data.
CITY_DISTRICT = {"bengaluru": "Bengaluru Urban", "kanpur": "Kanpur Nagar", "kochi": "Ernakulam",
                 "mangaluru": "Dakshina Kannada", "belagavi": "Belgaum", "kalaburagi": "Gulbarga"}

# AICTE region by state. Source: an AICTE regional-office page (Western) and an older state-by-region table
# (indiastat, about 2010). AICTE's current site could not be reached to confirm, so every row is
# Admin-editable and rows not in either source are marked "confirm". DEMO_ASSUMPTION until confirmed.
REGIONS_DEFAULT: dict[str, dict] = {
    **{s: {"region": "Western", "basis": "AICTE page"} for s in ("Maharashtra", "Goa", "The Dadra and Nagar Haveli and Daman and Diu")},
    **{s: {"region": "Central", "basis": "dated table"} for s in ("Madhya Pradesh", "Chhattisgarh", "Gujarat")},
    **{s: {"region": "Northern", "basis": "dated table"} for s in ("Uttar Pradesh", "Bihar", "Uttarakhand")},
    **{s: {"region": "North-West", "basis": "dated table"} for s in ("Haryana", "Punjab", "Rajasthan", "Himachal Pradesh",
                                                                     "Jammu and Kashmir", "Delhi", "Chandigarh")},
    "Ladakh": {"region": "North-West", "basis": "confirm"},
    **{s: {"region": "South-Central", "basis": "dated table"} for s in ("Andhra Pradesh",)},
    "Telangana": {"region": "South-Central", "basis": "confirm"},
    **{s: {"region": "Southern", "basis": "dated table"} for s in ("Tamil Nadu", "Puducherry")},
    **{s: {"region": "South-West", "basis": "dated table"} for s in ("Karnataka", "Kerala")},
    "Lakshadweep": {"region": "South-West", "basis": "confirm"},
    **{s: {"region": "Eastern", "basis": "dated table"} for s in ("West Bengal", "Odisha", "Jharkhand",
                                                                  "Andaman and Nicobar Islands")},
    **{s: {"region": "Eastern", "basis": "confirm"} for s in ("Assam", "Arunachal Pradesh", "Manipur", "Meghalaya",
                                                              "Mizoram", "Nagaland", "Sikkim", "Tripura")},
}
REGION_NAMES = ["Central", "Eastern", "Northern", "North-West", "South-Central", "Southern", "South-West", "Western"]


def norm(s: str) -> str:
    s = re.sub(r"[^a-z\s]", " ", s.lower())
    s = re.sub(r"\b(city|district|dist|town|nagar palika|municipal corporation)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


class Index:
    def __init__(self) -> None:
        self.pins: dict[str, list[tuple[str, str, str, str]]] = defaultdict(list)
        self.districts: dict[str, set[tuple[str, str]]] = defaultdict(set)
        self.localities: dict[str, Counter] = defaultdict(Counter)
        self.sub: dict[tuple[str, str], Counter] = defaultdict(Counter)
        self.states: dict[str, set[str]] = defaultdict(set)
        self.tokens: dict[str, Counter] = defaultdict(Counter)   # word in a post-office name -> where
        with gzip.open(DATA, "rt", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                pin, loc, dist, sub, state = r["pin"], r["locality"], r["district"], r["sub_region"], r["state"]
                self.pins[pin].append((loc, dist, sub, state))
                self.districts[norm(dist)].add((dist, state))
                self.localities[norm(loc)][(dist, state)] += 1
                for tok in set(norm(loc).split()):
                    if len(tok) >= 4:
                        self.tokens[tok][(dist, state)] += 1
                self.sub[(dist, state)][sub] += 1
                self.states[state].add(dist)
        self.district_keys = list(self.districts)
        self.locality_keys = list(self.localities)


@lru_cache(maxsize=1)
def index() -> Index:
    return Index()


def regions(db=None) -> dict[str, dict]:
    if db is not None:
        from . import rules
        stored = rules.get(db, "aicte_regions")
        if stored:
            return stored
    return REGIONS_DEFAULT


def place(city: str, dist: str, state: str, db=None) -> dict:
    ix = index()
    sub = ix.sub[(dist, state)].most_common(1)[0][0] if dist and ix.sub.get((dist, state)) else ""
    reg = regions(db).get(state, {"region": "", "basis": "confirm"})
    line = ", ".join(x for x in (city, f"{dist} district" if dist else "", state,
                                 f"{reg['region']} region" if reg.get("region") else "") if x)
    return {"city": city, "district": dist, "sub_region": sub, "state": state, "region": reg.get("region", ""),
            "region_basis": reg.get("basis", "confirm"), "line": line}


def resolve(city_text: str = "", pin: str = "", db=None) -> dict:
    """-> {status: matched|ambiguous|none, source, city_entered, pin, ..., choices}"""
    ix = index()
    base = {"city_entered": city_text.strip(), "pin": "", "choices": []}
    pin = re.sub(r"\D", "", pin or "")
    if len(pin) == 6 and pin in ix.pins:
        offices = ix.pins[pin]
        dist, state = Counter((d, s) for _, d, _, s in offices).most_common(1)[0][0]
        typed = city_text.strip()
        # The PIN wins: a typed city that does not fit the PIN is replaced by the PIN's district.
        city = OLD_NAMES.get(norm(typed), norm(typed)).title() if typed and _same_place(typed, offices) else dist
        return {**base, "pin": pin, "status": "matched", "source": "pin", **place(city, dist, state, db)}
    q = norm(city_text)
    if not q:
        return {**base, "status": "none", "source": "manual"}
    q = OLD_NAMES.get(q, q)
    if q in CITY_DISTRICT:
        d = norm(CITY_DISTRICT[q])
        hits = sorted(ix.districts.get(d, ()))
        if len(hits) == 1:
            return {**base, "status": "matched", "source": "matched", **place(q.title(), hits[0][0], hits[0][1], db)}
    if q == "delhi" or q == "new delhi":
        return {**base, "status": "matched", "source": "matched", **place("New Delhi" if "new" in q else "Delhi",
                                                                          "New Delhi" if "new" in q else "", "Delhi", db)}
    hits = _exact(ix, q)
    corrected = ""
    if not hits:
        # Spelling mistakes: one edit (incl. swapped letters) for short names, two for longer ones.
        cut = 1 if len(q) <= 6 else 2
        for keys in (ix.district_keys, list(ix.tokens), ix.locality_keys):
            best = process.extract(q, keys, scorer=OSA.distance, limit=6, score_cutoff=cut)
            if best:
                top = min(d for _, d, _ in best)
                names = [n for n, d, _ in best if d == top]
                hits = list(dict.fromkeys(h for n in names for h in _exact(ix, n)))
                if hits:
                    corrected = names[0].title()
                    break
    if not hits:
        return {**base, "status": "none", "source": "manual"}
    shown = corrected or (city_text.strip().title() if norm(city_text) == q else q.title())
    if len(hits) == 1:
        return {**base, "status": "matched", "source": "matched", **place(shown, hits[0][0], hits[0][1], db)}
    return {**base, "status": "ambiguous", "source": "matched",
            "choices": [place(shown, d, s, db) for d, s in hits[:4]]}


def _exact(ix: Index, q: str) -> list[tuple[str, str]]:
    """District of that name; else where post offices carry that name. A place that holds at least
    3x the offices of the next one wins outright (Siliguri, not a village of the same name)."""
    if q in ix.districts:
        return sorted(ix.districts[q])
    c = Counter(ix.localities.get(q, Counter()))
    if " " not in q:
        c.update(ix.tokens.get(q, Counter()))
    ranked = c.most_common(4)
    if len(ranked) > 1 and ranked[0][1] >= 3 * ranked[1][1]:
        return [ranked[0][0]]
    return [k for k, _ in ranked]


def _same_place(typed: str, offices) -> bool:
    t = OLD_NAMES.get(norm(typed), norm(typed))
    return any(fuzz.ratio(t, norm(x)) >= 85 for o in offices for x in (o[0], o[1]))


def states() -> list[str]:
    return sorted(index().states)


def districts(state: str) -> list[str]:
    return sorted(index().states.get(state, ()))
