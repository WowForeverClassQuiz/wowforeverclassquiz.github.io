"""The twenty-four class-separating personality questions (q51 to q74): how they are built and what they add to the pool."""
from collections import Counter
from itertools import combinations
from math import exp, fsum, log

import pytest

from app import adaptive
from app.models import LENGTHS
from app.scoring import compile_config
from app.seed import build_default_config
from app.seed_classes import CLASS_ORDER, CLASS_TRAITS

CLASS_IDS = ["druid", "hunter", "mage", "paladin", "priest", "rogue", "shaman", "warlock", "warrior"]


@pytest.fixture(scope="module")
def cfg():
    return build_default_config()


@pytest.fixture(scope="module")
def c(cfg):
    return compile_config(cfg)


@pytest.fixture(scope="module")
def model(c):
    return adaptive.Model(c)


def test_there_are_twenty_four_of_them_in_three_forms_and_only_confidence_mode_asks_them(cfg):
    qs = [q for q in cfg.questions if q.id in CLASS_ORDER]
    assert [q.id for q in qs] == [f"q{n}" for n in range(51, 75)] and all(q.min_length == "adaptive" for q in qs)
    assert Counter(q.type for q in qs) == {"choice": 10, "ranking": 7, "allocation": 7}
    assert all(len(q.answers) == 4 and q.rationale for q in qs)


def test_every_answer_names_its_own_class_and_the_traits_follow_that_class(cfg):
    for q in cfg.questions:
        if q.id not in CLASS_ORDER:
            continue
        primaries, secondaries = [], []
        for a in q.answers:
            (primary,) = [k for k, v in a.class_weights.items() if v == 2.0]
            (secondary,) = [k for k, v in a.class_weights.items() if v == 1.0]
            primaries.append(primary)
            secondaries.append(secondary)
            assert primary != secondary and not a.spec_weights, (q.id, a.id)
            assert a.trait_weights == {CLASS_TRAITS[primary][0]: 2.0, CLASS_TRAITS[primary][1]: 1.0}, (q.id, a.id)
        assert len(set(primaries)) == 4 and len(set(secondaries)) == 4, q.id          # no two answers share a primary or a secondary class
        assert not set(primaries) & set(secondaries), q.id                              # and no class is both


def test_each_class_is_a_primary_answer_about_equally_often(cfg):
    uses = Counter(next(k for k, v in a.class_weights.items() if v == 2.0) for q in cfg.questions if q.id in CLASS_ORDER for a in q.answers)
    assert set(uses) == set(CLASS_IDS) and max(uses.values()) - min(uses.values()) <= 2, uses


def _class_evidence(model, qi):
    """Symmetric Kullback-Leibler divergence (nats) between how two classes answer question qi (a class answers like an even mix of its specializations)."""
    rows = [[exp(model.logp[qi][r][g]) for g in range(model.n_types)] for r in range(len(model.logp[qi]))]
    by_class = {ci: [fsum(row[g] for g in range(model.n_types) if model.type_class[g] == ci) / 3 for row in rows] for ci in range(9)}
    return {(a, b): fsum(x * log(x / y) + y * log(y / x) for x, y in zip(by_class[a], by_class[b])) for a, b in combinations(range(9), 2)}


def test_every_class_trio_has_several_questions_that_tell_all_three_apart(c, model):
    evidence = [_class_evidence(model, qi) for qi in range(len(c.questions))]
    first_fifty = range(50)
    everyone = range(len(c.questions))

    def separators(idx, trio):
        return sum(1 for qi in idx if min(evidence[qi][pair] for pair in combinations(trio, 2)) >= 1.0)

    trios = list(combinations(range(9), 3))
    before = min(separators(first_fifty, t) for t in trios)
    after = min(separators(everyone, t) for t in trios)
    assert after >= 4 and after >= 2 * before - 1, (before, after)


def test_they_carry_a_little_more_class_evidence_than_the_originals_but_not_a_lot_more(c, model):
    """Each answer names a class no other answer does, which makes a question separate classes well. That must not make confidence cheap."""
    evidence = [_class_evidence(model, qi) for qi in range(len(c.questions))]
    per_question = [fsum(e.values()) / len(e) for e in evidence]
    originals = [per_question[i] for i, q in enumerate(c.questions) if q.length_rank < len(LENGTHS)]
    added = [per_question[i] for i, q in enumerate(c.questions) if q.id in CLASS_ORDER]
    assert fsum(added) / len(added) <= 1.3 * fsum(originals) / len(originals)
    assert max(added) <= 1.15 * max(originals)


TRIOS = [
    [("mage", "frost"), ("rogue", "subtlety"), ("warlock", "affliction")],
    [("paladin", "retribution"), ("warlock", "demonology"), ("hunter", "marksmanship")],
    [("druid", "restoration"), ("shaman", "restoration"), ("hunter", "beast_mastery")],
]


@pytest.mark.parametrize("trio", TRIOS)
def test_the_oracle_asks_them_when_a_person_is_torn_among_three_classes(cfg, trio):
    """A respondent whose answers blend three types (most likely response to 40% / 35% / 25% of each type's utility) needs the class questions.

    The tiebreakers are left out here: they would settle the finalists first, which tests/test_tiebreakers.py covers."""
    plain = cfg.model_copy(deep=True)
    plain.questions = [q for q in plain.questions if not q.finalists]
    c = compile_config(plain)
    model = adaptive.Model(c)
    types = [next(sp.gidx for cl in c.classes if cl.id == cid for sp in cl.specs if sp.id == sid) for cid, sid in trio]
    weights = (0.4, 0.35, 0.25)
    answers, asked = {}, []
    for _ in range(len(c.questions)):
        st = adaptive.status(c, answers)
        if st.done:
            break
        qi = c.q_index[st.next_question_id]
        asked.append(st.next_question_id)
        n = len(c.questions[qi].answer_ids)
        answers[st.next_question_id] = c.questions[qi].answer_ids[max(range(n), key=lambda r: sum(w * model.logp[qi][r][t] for w, t in zip(weights, types)))]
    assert st.done and st.recommended.class_id in {cid for cid, _ in trio}
    assert set(asked) & set(CLASS_ORDER)
