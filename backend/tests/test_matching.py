from datetime import date

import pytest

from app.services import matching as m


class I:  # minimal institution
    def __init__(self, id, name, city, aicte_id="", aliases=()):
        self.id, self.name, self.city, self.aicte_id, self.aliases = id, name, city, aicte_id, list(aliases)


INSTS = [I(1, "Kaveri Institute of Engineering and Technology", "Mysuru", "1-SYN-1"),
         I(2, "Kaveri College of Pharmacy", "Thanjavur", "1-SYN-2"),
         I(3, "Sahyadri Institute of Technology", "Pune", "1-SYN-3"),
         I(4, "Sahyadri Valley College of Engineering", "Kolhapur", "1-SYN-4"),
         I(5, "Narmada Institute of Technology", "Jabalpur", "1-SYN-5")]


def test_normalise_expands_abbreviations():
    assert m.normalise("Kaveri Inst. of Engg & Tech.") == "kaveri institute engineering technology"


@pytest.mark.parametrize("typed,expected", [
    ("Kaveri Inst. of Engg & Tech", 1),
    ("KAVERI INSTITUTE OF ENGINEERING & TECHNOLOGY, MYSURU", 1),
    ("Narmda Institue of Technology", 5),          # two misspellings
    ("Narmada Inst of Tech Jabalpur", 5),
    ("Kaveri College of Pharmacy Thanjavur", 2),
    ("Sahyadri Valley Engg College", 4),
])
def test_name_variants_match_the_right_institution(typed, expected):
    s = m.suggest_institution(typed, INSTS, 88)
    assert s.institution_id == expected, s.reasons


def test_aicte_id_typed_wins():
    s = m.suggest_institution("complaint about 1-syn-3 hostel", INSTS, 88)
    assert s.institution_id == 3 and s.score == 100


@pytest.mark.parametrize("typed", ["Kaveri Pharmacy Institute Mysuru", "Godavari Institute of Engineering",
                                   "Institute of Technology", "Ganga College"])
def test_no_false_match_across_different_colleges(typed):
    s = m.suggest_institution(typed, INSTS, 88)
    assert s.institution_id is None or s.ambiguous_with, (typed, s)


def test_shared_first_word_is_not_enough():
    assert m.name_score("Kaveri College of Pharmacy", [INSTS[0].name]).score < 70


def test_wrong_city_lowers_score():
    good = m.name_score("Sahyadri Institute of Technology Pune", [INSTS[2].name], "Pune", ["Pune", "Kolhapur"]).score
    bad = m.name_score("Sahyadri Institute of Technology Kolhapur", [INSTS[2].name], "Pune", ["Pune", "Kolhapur"]).score
    assert good > 88 > bad


def test_ambiguous_short_name_is_flagged():
    s = m.suggest_institution("Sahyadri", INSTS, 88)
    assert s.institution_id is None or s.ambiguous_with


def _cv(id, unit, inst, cat, topic, text, d, typed="", confirmed=True):
    return m.CaseView(id, f"{unit}-{id}", unit, inst, "Narmada Institute of Technology" if inst else "", typed, confirmed,
                      cat, topic, text, d)


def test_pair_score_explains_and_ranks():
    tf = m.TfIdf(["faculty left mid semester", "inspection found faculty ratio below norms", "hostel water"])
    a = _cv(1, "PGRC", 5, "Faculty shortage", "faculty", "Lecturers left mid-semester, no qualified faculty", date(2026, 9, 1))
    b = _cv(2, "RB", 5, "Inspection / compliance", "inspection", "Inspection: faculty ratio below norms", date(2026, 9, 9))
    c = _cv(3, "AB", 5, "Infrastructure deficiency", "infrastructure", "Hostel has no water", date(2026, 3, 1))
    ab, ac = m.pair_score(a, b, tf, 180, 88), m.pair_score(a, c, tf, 180, 88)
    assert ab.score > ac.score
    assert any("AICTE ID" in r for r in ab.reasons)
    assert any("8 days apart" in r for r in ab.reasons)
    assert ac.missing, "missing evidence must be listed"


def test_pair_of_different_colleges_scores_nothing():
    tf = m.TfIdf(["x"])
    a = _cv(1, "PGRC", None, "Excess fee", "fees", "fee", date(2026, 9, 1), typed="Kaveri College of Pharmacy", confirmed=False)
    b = _cv(2, "RB", None, "Excess fee", "fees", "fee", date(2026, 9, 2), typed="Kaveri Institute of Engineering", confirmed=False)
    assert m.pair_score(a, b, tf, 180, 88) is None
