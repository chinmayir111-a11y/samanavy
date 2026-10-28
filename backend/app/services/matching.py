"""Rule-based matching. No machine learning, no external service.

Two questions are answered here:

1. Which institution does a typed name refer to?  (`name_score`, `suggest_institution`)
   Names are normalised (case, punctuation, "Inst."/"Engg"/"&" expanded, filler
   words dropped), then compared with RapidFuzz on two views: the whole name
   and only its *distinctive* words (the words left after generic ones such as
   "institute", "engineering", "college" are removed). The final score is the
   lower of the two, so "Kaveri College of Pharmacy" cannot match "Kaveri
   Institute of Engineering" just because both start with "Kaveri", and
   "Institute of Technology" cannot match every institute of technology.
   A typed city that belongs to a different institution lowers the score.

2. How likely is it that two open cases in different units concern the same
   institution and issue?  (`pair_score`)
   Score 0-100 = institution evidence (0-40) + issue evidence (0-40) + time (0-20),
   with a plain sentence for every point given and for every piece of
   evidence that is missing. It is a prioritisation signal, not a probability.

The method and its measured accuracy are in docs/MATCHING_METHOD.md
(numbers produced by scripts/evaluate_matcher.py)."""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

from rapidfuzz import fuzz

# ------------------------------------------------------------- names

ABBREV = {
    "inst": "institute", "instt": "institute", "insti": "institute", "institution": "institute",
    "engg": "engineering", "eng": "engineering", "engr": "engineering", "engineer": "engineering",
    "tech": "technology", "techn": "technology", "technol": "technology", "technological": "technology",
    "coll": "college", "clg": "college", "colg": "college", "univ": "university", "uni": "university",
    "mgmt": "management", "mgt": "management", "mngt": "management",
    "sci": "science", "sc": "science", "sciences": "science",
    "pharm": "pharmacy", "pharma": "pharmacy", "poly": "polytechnic", "govt": "government",
    "res": "research", "acad": "academy", "intl": "international", "natl": "national",
    "studs": "studies", "arch": "architecture", "comp": "computer", "it": "information technology",
}
FILLER = {"of", "the", "and", "for", "in", "at", "a", "an"}
GENERIC = {
    "institute", "college", "engineering", "technology", "technical", "management", "science",
    "studies", "research", "university", "polytechnic", "pharmacy", "school", "academy", "centre",
    "center", "group", "education", "educational", "society", "trust", "arts", "commerce",
    "professional", "advanced", "applied", "information", "computer", "architecture", "government",
    "national", "international", "women", "womens", "private", "limited", "campus", "india", "indian",
}


def normalise(text: str) -> str:
    """'Kaveri Inst. of Engg & Tech.' -> 'kaveri institute engineering technology'."""
    s = text.lower().replace("&", " and ")
    s = re.sub(r"(?<=\w)\.(?=\w)", "", s)          # "b.tech" -> "btech"
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    out: list[str] = []
    for tok in s.split():
        tok = ABBREV.get(tok, tok)
        out.extend(t for t in tok.split() if t not in FILLER)
    return " ".join(out)


def _is_generic(tok: str) -> bool:
    if tok in GENERIC:
        return True
    # misspelt generic words ("institue", "engineerng") are still generic
    return len(tok) >= 6 and any(fuzz.ratio(tok, g) >= 88 for g in GENERIC if abs(len(g) - len(tok)) <= 2)


def distinctive(norm: str, drop: Iterable[str] = ()) -> str:
    dropped = set(drop)
    return " ".join(t for t in norm.split() if not _is_generic(t) and t not in dropped)


@dataclass
class NameMatch:
    score: float
    matched_name: str          # the institution name or alias that matched best
    reasons: list[str] = field(default_factory=list)


def name_score(typed: str, names: list[str], city: str = "", other_cities: Iterable[str] = (),
               method: str = "hybrid") -> NameMatch:
    """Best score of `typed` against an institution's name and aliases.

    method: "exact" (normalised equality), "ratio" (plain ratio on raw text),
    "token_set" (RapidFuzz token set on normalised text) or "hybrid" (default:
    min of whole-name and distinctive-word scores, plus city evidence).
    The alternatives exist so scripts/evaluate_matcher.py can compare them."""
    t_norm = normalise(typed)
    city_l = city.lower().strip()
    best = NameMatch(0.0, names[0] if names else "")
    for name in names:
        n_norm = normalise(name)
        if method == "exact":
            s = 100.0 if t_norm == n_norm else 0.0
            why = ["Same name after tidying"] if s else []
        elif method == "ratio":
            s = float(fuzz.ratio(typed.lower(), name.lower()))
            why = []
        elif method == "token_set":
            s = float(fuzz.token_set_ratio(t_norm, n_norm))
            why = []
        else:
            whole = float(fuzz.token_set_ratio(t_norm, n_norm))
            dt, dn = distinctive(t_norm, [city_l]), distinctive(n_norm, [city_l])
            if dt and dn:
                dist = float(fuzz.token_set_ratio(dt, dn))
                s = min(whole, dist)
                why = [f"Whole name {whole:.0f}/100", f"Distinctive words '{dt}' vs '{dn}' {dist:.0f}/100"]
            else:
                # Only generic words typed ("Institute of Technology"): never enough on its own.
                s = min(whole, 60.0)
                why = [f"Whole name {whole:.0f}/100", "No distinctive word typed"]
        if s > best.score or (s == best.score and not best.reasons):
            best = NameMatch(s, name, why)
    if method == "hybrid" and best.score > 0:
        toks = set(t_norm.split())
        if city_l and city_l in toks:
            best.score = min(100.0, best.score + 5)
            best.reasons.append(f"City '{city}' also typed (+5)")
        else:
            wrong = sorted(c for c in (x.lower() for x in other_cities) if c and c != city_l and c in toks)
            if wrong:
                best.score = max(0.0, best.score - 20)
                best.reasons.append(f"Typed city '{wrong[0].title()}' is not this institution's city (-20)")
    best.score = round(best.score, 1)
    return best


@dataclass
class Suggestion:
    institution_id: int | None
    score: float
    reasons: list[str]
    ambiguous_with: list[int] = field(default_factory=list)


def suggest_institution(typed: str, institutions: list, threshold: float, method: str = "hybrid") -> Suggestion:
    """`institutions`: objects with id, name, aliases, city, aicte_id.
    An AICTE id typed anywhere in the text wins outright. Two candidates
    within 5 points of each other above the threshold are reported as
    ambiguous: a person must choose."""
    up = typed.upper()
    for inst in institutions:
        if inst.aicte_id and inst.aicte_id.upper() in up:
            return Suggestion(inst.id, 100.0, [f"AICTE ID {inst.aicte_id} typed in the text"])
    cities = [i.city for i in institutions]
    scored = []
    for inst in institutions:
        m = name_score(typed, [inst.name, *(inst.aliases or [])], inst.city, cities, method)
        scored.append((m.score, inst, m))
    scored.sort(key=lambda x: -x[0])
    if not scored or scored[0][0] < threshold:
        top = scored[0] if scored else None
        return Suggestion(None, top[0] if top else 0.0,
                          [f"Closest is '{top[1].name}' at {top[0]:.0f}/100, below the {threshold:.0f} needed"] if top else [])
    s, inst, m = scored[0]
    close = [i.id for sc, i, _ in scored[1:] if sc >= threshold and s - sc < 5]
    reasons = [f"Typed '{typed}' matches '{m.matched_name}' ({s:.0f}/100)", *m.reasons]
    if close:
        reasons.append("Another institution scores almost the same: please choose by hand")
    return Suggestion(inst.id, s, reasons, close)


# ------------------------------------------------------------- text

STOP = set("""a an the and or of to in on for at by with from as is are was were be been being this that these those it its
he she they them his her their we our you your i me my not no but if than then so such can could would should will
shall may might must has have had do does did done also very more most other some any each every all about into
over under after before between during without within upon per via due etc institute college institution student
students complaint complaints regarding regard dated sir madam kindly please request requested matter issue issues
said same aicte case letter received""".split())

SYNONYMS = {
    "lecturer": "faculty", "teacher": "faculty", "professor": "faculty", "teaching": "faculty", "staff": "faculty",
    "fees": "fee", "charge": "fee", "capitation": "fee", "donation": "fee", "refund": "fee",
    "laboratory": "lab", "labs": "lab", "hostels": "hostel", "salaries": "salary", "wages": "salary",
    "certificates": "certificate", "marksheet": "certificate", "transcript": "certificate",
    "scholarships": "scholarship", "stipend": "scholarship", "ragging": "harassment", "harass": "harassment",
    "inspected": "inspection", "inspect": "inspection", "visit": "inspection", "deficiencies": "deficiency",
    "seats": "seat", "admissions": "admission", "approved": "approval", "unapproved": "approval",
}

TOPICS: dict[str, set[str]] = {
    "faculty": {"faculty", "cadre", "ratio", "qualification", "phd", "vacant", "vacancy"},
    "fees": {"fee", "excess", "payment", "money"},
    "infrastructure": {"lab", "library", "building", "hostel", "classroom", "infrastructure", "equipment", "toilet",
                       "water", "facility", "facilities", "builtup", "land"},
    "admission": {"admission", "seat", "intake", "counselling", "merit", "eligibility"},
    "approval": {"approval", "extension", "eoa", "affiliation", "permission", "recognition", "fake"},
    "harassment": {"harassment", "abuse", "threat", "discrimination", "bully"},
    "scholarship": {"scholarship", "freeship"},
    "certificates": {"certificate", "withheld", "original", "migration", "tc"},
    "salary": {"salary", "unpaid", "arrears", "pf", "provident"},
    "inspection": {"inspection", "compliance", "deficiency", "mandatory", "disclosure", "norms"},
}


# Category groups that often describe the same situation from two sides
# (a student's faculty complaint and an inspection finding about faculty).
RELATED_TOPICS = {frozenset(x) for x in (("faculty", "inspection"), ("infrastructure", "inspection"),
                                         ("fees", "admission"), ("fees", "scholarship"), ("salary", "faculty"),
                                         ("approval", "inspection"), ("approval", "admission"))}


def _stem(tok: str) -> str:
    for suf, rep in (("ies", "y"), ("ing", ""), ("ed", ""), ("s", "")):
        if len(tok) > 5 and tok.endswith(suf):
            return tok[: -len(suf)] + rep
    return tok


def tokens(text: str) -> list[str]:
    out = []
    for raw in re.findall(r"[a-z]+", text.lower()):
        if len(raw) < 3 or raw in STOP:
            continue
        tok = SYNONYMS.get(raw) or SYNONYMS.get(_stem(raw)) or _stem(raw)
        if tok not in STOP:
            out.append(tok)
    return out


def topics_of(text: str, category_topic: str = "") -> dict[str, list[str]]:
    toks = set(tokens(text))
    hits = {t: sorted(toks & words) for t, words in TOPICS.items() if toks & words}
    if category_topic and category_topic not in hits:
        hits[category_topic] = []
    return hits


class TfIdf:
    """Plain TF-IDF over the case descriptions, fitted on the current register."""

    def __init__(self, docs: Iterable[str]):
        docs = [tokens(d) for d in docs]
        self.n = max(len(docs), 1)
        df: Counter = Counter()
        for d in docs:
            df.update(set(d))
        self.idf = {t: math.log((1 + self.n) / (1 + c)) + 1 for t, c in df.items()}

    def vec(self, text: str) -> dict[str, float]:
        tf = Counter(tokens(text))
        v = {t: c * self.idf.get(t, math.log(1 + self.n) + 1) for t, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {t: x / norm for t, x in v.items()}

    def cosine(self, a: str, b: str) -> tuple[float, list[str]]:
        va, vb = self.vec(a), self.vec(b)
        shared = {t: va[t] * vb[t] for t in va.keys() & vb.keys()}
        top = [t for t, _ in sorted(shared.items(), key=lambda x: -x[1])[:4]]
        return sum(shared.values()), top


# ------------------------------------------------------------- pair score

@dataclass
class CaseView:
    """What the scorer needs from a case (keeps this module free of the database)."""
    id: int
    case_id: str
    unit: str
    institution_id: int | None
    institution_name: str          # confirmed or suggested institution name ("" if neither)
    typed_name: str
    aicte_id_confirmed: bool       # institution_id set by ID/confirmation (not just a suggestion)
    category: str
    topic: str
    description: str
    received_on: date


@dataclass
class PairScore:
    score: float
    institution: float
    issue: float
    time: float
    reasons: list[str]
    missing: list[str]
    duplicate_hint: bool = False

    def as_dict(self) -> dict:
        return {"score": self.score, "parts": {"institution": self.institution, "issue": self.issue, "time": self.time},
                "reasons": self.reasons, "missing": self.missing, "duplicate_hint": self.duplicate_hint}


def _d(x: date) -> str:
    return f"{x.day} {x.strftime('%b')}"


def pair_score(a: CaseView, b: CaseView, tfidf: TfIdf, window_days: int, name_threshold: float,
               inst_name_of=None, use_text: bool = True, use_topics: bool = False) -> PairScore | None:
    """None when there is no institution evidence at all (different institutions)."""
    reasons: list[str] = []
    missing: list[str] = []

    # institution (0-40)
    inst = 0.0
    if a.institution_id and a.institution_id == b.institution_id and a.aicte_id_confirmed and b.aicte_id_confirmed:
        inst = 40.0
        reasons.append("Same institution (AICTE ID matched on both cases)")
    elif a.institution_id and a.institution_id == b.institution_id:
        inst = 34.0
        typed = a if not a.aicte_id_confirmed else b
        reasons.append(f"Same institution by name match: '{typed.typed_name}' looks like '{typed.institution_name}'")
        missing.append(f"{typed.case_id} has no confirmed AICTE ID yet: confirm the institution")
    else:
        # Different or unknown institutions: compare what was typed.
        names_b = [b.institution_name or b.typed_name]
        m = name_score(a.typed_name or a.institution_name, names_b)
        if m.score < name_threshold:
            return None
        inst = round(40.0 * m.score / 100 * 0.85, 1)
        reasons.append(f"Institution names look alike ({m.score:.0f}/100): '{a.typed_name or a.institution_name}' / "
                       f"'{b.typed_name or b.institution_name}'")
        missing.append("Neither case has a confirmed AICTE ID")

    # issue (0-40)
    issue = 0.0
    if a.category == b.category:
        issue += 15
        reasons.append(f"Both filed under '{a.category}'")
    elif a.topic == b.topic or frozenset((a.topic, b.topic)) in RELATED_TOPICS:
        issue += 10
        reasons.append(f"Related categories: '{a.category}' and '{b.category}'")
    else:
        missing.append(f"Different categories: '{a.category}' and '{b.category}'")
    if use_topics:
        ta, tb = topics_of(a.description, a.topic), topics_of(b.description, b.topic)
        common = sorted(ta.keys() & tb.keys())
        # Only when the categories differ: otherwise the category already said it (measured: double counting
        # cost precision, see docs/MATCHING_EVAL.md).
        if common and a.topic != b.topic:
            issue += 10
            words = sorted(set(sum((ta[c] + tb[c] for c in common), [])))[:4]
            reasons.append(f"Both about {', '.join(common)}" + (f" ({', '.join(words)})" if words else ""))
    if use_text:
        cos, shared = tfidf.cosine(a.description, b.description)
        pts = round(15 * min(1.0, cos / 0.35), 1)
        if pts >= 3:
            issue += pts
            reasons.append(f"Descriptions share key words: {', '.join(shared)} (text similarity {cos:.2f})")
        elif not issue:
            missing.append("Descriptions use different words")
    issue = min(issue, 40.0)

    # time (0-20)
    gap = abs((a.received_on - b.received_on).days)
    t = round(20 * max(0.0, 1 - gap / window_days), 1) if window_days > 0 else 0.0
    first, second = (a, b) if a.received_on <= b.received_on else (b, a)
    if t > 0:
        reasons.append(f"{first.unit} opened {_d(first.received_on)}, {second.unit} opened {_d(second.received_on)} "
                       f"({gap} days apart)")
    else:
        missing.append(f"Received {gap} days apart (window {window_days} days)")

    total = round(min(100.0, inst + issue + t), 1)
    if t == 0 and window_days > 0:
        # Outside the window the pair is history, not a live overlap: keep it visible, below the alert line.
        total = min(total, 50.0)
    return PairScore(total, inst, round(issue, 1), t, reasons, missing, duplicate_hint=issue >= 32)
