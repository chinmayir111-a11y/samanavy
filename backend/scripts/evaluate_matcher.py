#!/usr/bin/env python3
"""Measure the rule-based matcher on a labelled synthetic set and write
docs/MATCHING_METHOD.md.

The set is generated here with a fixed seed, separately from the demo data:
  Task A, institution matching: typed names -> which institution (or none).
    Variants: abbreviations, misspellings, dropped words, added city, upper case;
    look-alikes that share the distinctive word; names of institutions not in the list.
  Task B, case pairs: is this pair the same institution AND the same issue?
    Positives: duplicates, same issue described in different words, misspelt names.
    Negatives: same institution but a different issue, look-alike institutions, far-apart dates.

Honest limit: we wrote the generator, so the set reflects the variations we
thought of. Real AICTE records will contain others; numbers on real data will
be lower until the rules are tuned on it."""
from __future__ import annotations

import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import matching as m  # noqa: E402
from scripts.seed import TEXT  # noqa: E402

R = random.Random(2026)
WORDS = ["Narmada", "Kaveri", "Sahyadri", "Ganga", "Yamuna", "Godavari", "Krishna", "Tapti", "Sabarmati", "Mahanadi",
         "Brahmaputra", "Chenab", "Teesta", "Sutlej", "Beas", "Ravi", "Jhelum", "Indravati", "Pennar", "Tungabhadra",
         "Vindhya", "Aravali", "Satpura", "Nilgiri", "Shivalik", "Malwa", "Konkan", "Doaba", "Bundel", "Kumaon"]
TYPES = ["Institute of Technology", "College of Engineering", "Institute of Engineering and Technology",
         "College of Pharmacy", "Institute of Management Studies", "Polytechnic", "College of Architecture"]
CITIES = ["Pune", "Nagpur", "Indore", "Jabalpur", "Mysuru", "Madurai", "Patna", "Ranchi", "Kochi", "Surat", "Jaipur",
          "Bhopal", "Agra", "Rajkot", "Guntur", "Salem", "Dehradun", "Shimla", "Jammu", "Siliguri"]
ABBR = {"Institute": ["Inst.", "Instt.", "Inst"], "Engineering": ["Engg", "Engg.", "Eng."], "Technology": ["Tech", "Tech."],
        "College": ["Coll.", "Clg"], "Management": ["Mgmt", "Mgt."], "and": ["&"], "Studies": ["Studs"], "Pharmacy": ["Pharm."]}


class Inst:
    def __init__(self, i, name, city):
        self.id, self.name, self.city, self.aicte_id, self.aliases = i, name, city, f"1-EVAL-{1000 + i}", []


def build_institutions() -> list[Inst]:
    out = []
    for w in WORDS:
        # every distinctive word is used by two institutions of different types and cities (look-alikes)
        for ty in R.sample(TYPES, 2):
            out.append(Inst(len(out) + 1, f"{w} {ty}", R.choice(CITIES)))
    return out


def misspell(word: str) -> str:
    i = R.randrange(1, len(word) - 1)
    op = R.choice(["drop", "swap", "double"])
    if op == "drop":
        return word[:i] + word[i + 1:]
    if op == "swap" and i < len(word) - 1:
        return word[:i] + word[i + 1] + word[i] + word[i + 2:]
    return word[:i] + word[i] + word[i:]


def variant(inst: Inst) -> tuple[str, str]:
    words = inst.name.split()
    kind = R.choice(["abbrev", "misspell", "drop", "city", "upper", "abbrev+city", "misspell+abbrev"])
    if "abbrev" in kind:
        words = [R.choice(ABBR[w]) if w in ABBR and R.random() < 0.8 else w for w in words]
    if "misspell" in kind:
        words[0] = misspell(words[0])
    if kind == "drop" and len(words) > 3:
        words = [w for w in words if w not in ("of", "and")]
        words.pop(R.randrange(1, len(words)))
    text = " ".join(words)
    if "city" in kind:
        text += f", {inst.city}"
    if kind == "upper":
        text = text.upper()
    return text, kind


def task_a(insts: list[Inst]):
    queries = []
    for inst in insts:
        for _ in range(3):
            t, k = variant(inst)
            queries.append((t, inst.id, k))
    for _ in range(60):  # institutions that are not in the list
        w = R.choice(["Saraswati", "Kosi", "Gomti", "Mahi", "Luni", "Damodar", "Subarnarekha", "Baitarani"])
        queries.append((f"{w} {R.choice(TYPES)}", None, "not in list"))
    for _ in range(40):  # only generic words
        queries.append((R.choice(["Institute of Technology", "Engg College", "College of Pharmacy, " + R.choice(CITIES)]), None, "generic only"))
    return queries


def eval_a(insts, queries, method, thr):
    tp = fp = fn = tn = 0
    for text, truth, _ in queries:
        s = m.suggest_institution(text, insts, thr, method)
        got = s.institution_id if not s.ambiguous_with else None
        if truth is None:
            fp += got is not None
            tn += got is None
        elif got == truth:
            tp += 1
        else:
            fn += 1
            fp += got is not None   # a wrong institution is also a false positive
    return tp, fp, fn, tn


def cv(i, inst, typed, unit, topic, text, d, confirmed):
    cat = {"faculty": "Faculty shortage", "fees": "Excess fee", "infrastructure": "Infrastructure",
           "inspection": "Inspection", "salary": "Salary", "certificates": "Certificates", "admission": "Admission",
           "approval": "Approval", "harassment": "Harassment", "scholarship": "Scholarship"}[topic]
    return m.CaseView(i, f"C{i}", unit, inst.id if confirmed else None, inst.name if confirmed else "", typed, confirmed,
                      cat, topic, text, d)


def task_b(insts):
    pairs, n = [], 0
    topics = list(TEXT)
    for _ in range(400):
        inst = R.choice(insts)
        base = date(2026, 6, 1) + timedelta(days=R.randint(0, 120))
        topic = R.choice(topics)
        texts = [x.format(n=4, d="Civil", m="40,000") for x in TEXT[topic]]
        kind = R.choice(["duplicate", "same issue, other words", "same issue, typed name", "other issue",
                         "look-alike institution", "far apart"])
        n += 2
        a_conf = True
        b_conf = kind not in ("same issue, typed name",)
        b_inst = inst
        b_topic, b_text = topic, R.choice(texts)
        a_text = texts[0]
        gap = R.randint(0, 60)
        label = True
        if kind == "duplicate":
            b_text = a_text.replace("Students", "Student").replace("not", "still not")
        elif kind == "same issue, other words":
            b_text = R.choice(texts[1:])
            b_topic = R.choice([topic, {"faculty": "inspection", "infrastructure": "inspection"}.get(topic, topic)])
        elif kind == "same issue, typed name":
            pass
        elif kind == "other issue":
            b_topic = R.choice([t for t in topics if t != topic and frozenset((t, topic)) not in m.RELATED_TOPICS])
            b_text, label = R.choice(TEXT[b_topic]).format(n=3, d="MBA", m="20,000"), False
        elif kind == "look-alike institution":
            b_inst = next(i for i in insts if i.name.split()[0] == inst.name.split()[0] and i.id != inst.id)
            label = False
        elif kind == "far apart":
            gap, label = R.randint(200, 400), False
        typed_b = variant(b_inst)[0] if not b_conf else b_inst.name
        a = cv(n - 1, inst, inst.name, "RB", topic, a_text, base, a_conf)
        b = cv(n, b_inst, typed_b, "PGRC", b_topic, b_text, base + timedelta(days=gap), b_conf)
        if kind == "look-alike institution":   # each has its own confirmed id: compare as typed names
            a = cv(n - 1, inst, inst.name, "RB", topic, a_text, base, False)
            b = cv(n, b_inst, b_inst.name, "PGRC", b_topic, b_text, base + timedelta(days=gap), False)
        pairs.append((a, b, label, kind))
    corpus = [p[0].description for p in pairs] + [p[1].description for p in pairs]
    return pairs, m.TfIdf(corpus)


def eval_b(pairs, tf, thr, **kw):
    tp = fp = fn = tn = 0
    for a, b, label, _ in pairs:
        p = m.pair_score(a, b, tf, 180, 80, **kw)
        hit = bool(p and p.score >= thr)
        tp += hit and label
        fp += hit and not label
        fn += (not hit) and label
        tn += (not hit) and not label
    return tp, fp, fn, tn


def rates(tp, fp, fn, tn):
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    fpr = fp / (fp + tn) if fp + tn else 0
    fnr = fn / (tp + fn) if tp + fn else 0
    return prec, rec, fpr, fnr


def row(name, c):
    p, r, fpr, fnr = rates(*c)
    return f"| {name} | {p:.2f} | {r:.2f} | {fpr:.2f} | {fnr:.2f} | {c[0]}/{c[1]}/{c[2]}/{c[3]} |"


def main() -> None:
    insts = build_institutions()
    qa = task_a(insts)
    lines_a = []
    for method, thr in (("exact", 100), ("ratio", 85), ("token_set", 85), ("hybrid", 80), ("hybrid", 85), ("hybrid", 88), ("hybrid", 92)):
        lines_a.append(row(f"{method} @ {thr}", eval_a(insts, qa, method, thr)))
    by_kind: dict[str, list[int]] = {}
    for text, truth, kind in qa:
        s = m.suggest_institution(text, insts, 80)
        got = s.institution_id if not s.ambiguous_with else None
        by_kind.setdefault(kind, [0, 0])
        by_kind[kind][0] += got == truth
        by_kind[kind][1] += 1
    pairs, tf = task_b(insts)
    lines_b = []
    for name, kw, thr in (("full scorer", {}, 55), ("full scorer", {}, 60), ("full scorer", {}, 65), ("full scorer", {}, 70),
                          ("full scorer", {}, 75), ("no text similarity", {"use_text": False}, 65),
                          ("with topic-word points", {"use_topics": True}, 65), ("institution + time only", {"use_text": False}, 65)):
        lines_b.append(row(f"{name} @ {thr}", eval_b(pairs, tf, thr, **kw)))
    kinds_b: dict[str, list[int]] = {}
    for a, b, label, kind in pairs:
        p = m.pair_score(a, b, tf, 180, 80)
        hit = bool(p and p.score >= 65)
        kinds_b.setdefault(kind, [0, 0])
        kinds_b[kind][0] += hit == label
        kinds_b[kind][1] += 1

    head = "| Method @ threshold | Precision | Recall | False-positive rate | False-negative rate | TP/FP/FN/TN |\n|---|---|---|---|---|---|"
    out = Path(__file__).resolve().parents[2] / "docs" / "MATCHING_EVAL.md"
    out.write_text(f"""# Matcher evaluation (generated by `make evaluate`)

Synthetic labelled set, fixed seed. {len(insts)} fictional institutions (every distinctive word used by two
institutions: look-alikes), {len(qa)} typed names, {len(pairs)} case pairs. Not real AICTE data.

## A. Typed name -> institution
A wrong institution counts as a false positive *and* a false negative. "Ambiguous" (two candidates within 5
points) counts as no suggestion.

{head}
{chr(10).join(lines_a)}

Correct at hybrid @ 80, by variant: {", ".join(f"{k} {v[0]}/{v[1]}" for k, v in sorted(by_kind.items()))}.

## B. Case pair -> "same institution and same issue"
{head}
{chr(10).join(lines_b)}

Correct at full scorer @ 65, by pair type: {", ".join(f"{k} {v[0]}/{v[1]}" for k, v in sorted(kinds_b.items()))}.
""")
    print(out.read_text())


if __name__ == "__main__":
    main()
