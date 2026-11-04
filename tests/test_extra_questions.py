"""The twenty confidence-mode-only questions (q31 to q50): where they are asked, how they are built, and what they add."""
from itertools import combinations
from math import exp, fsum, log

import pytest

from app import adaptive
from app.models import LENGTHS
from app.public import public_lengths
from app.scoring import UnknownQuestionError, compile_config, evaluate
from app.seed import build_default_config
from app.validation import validate_config

from .conftest import DRUID_ANSWERS
from app.seed_classes import CLASS_ORDER

EXTRA_IDS = [f"q{n}" for n in range(31, 51)]


@pytest.fixture(scope="module")
def cfg():
    return build_default_config()


@pytest.fixture(scope="module")
def c(cfg):
    return compile_config(cfg)


@pytest.fixture(scope="module")
def model(c):
    return adaptive.Model(c)


def test_the_added_questions_are_asked_only_in_confidence_mode(cfg):
    assert [q.id for q in cfg.questions if q.min_length == "adaptive"] == EXTRA_IDS + CLASS_ORDER
    lengths = {l.id: l for l in public_lengths(cfg)}
    for length in LENGTHS:
        assert not set(EXTRA_IDS) & set(lengths[length].question_ids), length
        assert lengths[length].question_count in (10, 20, 30)
    assert set(EXTRA_IDS) <= set(lengths["adaptive"].question_ids) and len(lengths["adaptive"].question_ids) == 74
    with pytest.raises(UnknownQuestionError):                     # a fixed quiz refuses an answer to one of them
        evaluate(cfg, dict(DRUID_ANSWERS, q31="a"))
    ev = evaluate(cfg, dict(DRUID_ANSWERS, q31="a"), length="adaptive")      # confidence mode takes them
    assert ev.metadata.total_questions == 31


def test_the_added_questions_follow_the_conventions_of_the_seed(cfg):
    classes = {k.id for k in cfg.classes}
    spec_credit = {}
    for q in cfg.questions:
        if q.id not in EXTRA_IDS:
            continue
        assert q.rationale and q.text and q.type in {"choice", "scale", "ranking", "allocation"}, q.id
        assert (len(q.answers) == 3) if (q.type == "choice" and q.id != "q49") else (len(q.answers) in (2, 4)), q.id
        for a in q.answers:
            assert sorted(a.class_weights.values()) == [1.0, 2.0] and set(a.class_weights) <= classes, (q.id, a.id)
            assert sorted(a.trait_weights.values()) == [1.0, 2.0], (q.id, a.id)
            assert all(0 < w <= 2 for w in a.spec_weights.values()), (q.id, a.id)         # within the range the original questions use
            for key in a.spec_weights:
                spec_credit[key] = spec_credit.get(key, 0) + 1
    every = {f"{cl.id}/{sp.id}" for cl in cfg.classes for sp in cl.specializations}
    assert set(spec_credit) == every and min(spec_credit.values()) >= 2, spec_credit      # every specialization is credited by two or more


def _sym_kl(model, qi, a, b):
    """Symmetric Kullback-Leibler divergence (nats) between how types a and b answer question qi."""
    rows = model.logp[qi]
    return fsum(exp(r[a]) * (r[a] - r[b]) + exp(r[b]) * (r[b] - r[a]) for r in rows)


def test_the_added_questions_cover_the_pairs_the_fixed_quizzes_separate_worst(c, model):
    core = [i for i, q in enumerate(c.questions) if q.length_rank < len(LENGTHS)]
    everyone = list(range(len(c.questions)))
    pairs = [(a, b) for a, b in combinations(range(model.n_types), 2) if model.type_class[a] == model.type_class[b]]
    before = {p: fsum(_sym_kl(model, qi, *p) for qi in core) for p in pairs}
    after = {p: fsum(_sym_kl(model, qi, *p) for qi in everyone) for p in pairs}
    assert min(before.values()) < 5            # the weakness the new questions exist to fix (Arcane against Frost Mage)
    assert min(after.values()) > 12            # no pair of specializations in one class is left poorly covered
    assert all(after[p] > before[p] for p in pairs)


def test_the_added_questions_do_not_claim_more_evidence_per_question_than_the_originals(c, model):
    """Confidence mode would reach 90% sooner if the added weights were simply heavier; this guards against that."""
    pairs = list(combinations(range(model.n_types), 2))
    per_question = lambda qi: fsum(_sym_kl(model, qi, a, b) for a, b in pairs) / len(pairs)
    core = [per_question(i) for i, q in enumerate(c.questions) if q.length_rank < len(LENGTHS)]
    extra = [per_question(i) for i, q in enumerate(c.questions) if q.length_rank >= len(LENGTHS)]
    assert fsum(extra) / len(extra) <= 1.1 * fsum(core) / len(core)
    assert max(extra) <= 1.1 * max(core)           # the strongest added question (the role question) is about as strong as the strongest original


def test_there_is_no_minimum_by_default_and_a_reading_can_be_revealed_after_any_answer(c):
    assert c.adaptive.min_questions == 1
    first = adaptive.status(c, {}).next_question_id
    st = adaptive.status(c, {first: c.questions[c.q_index[first]].answer_ids[0]})
    assert st.answered == 1 and st.can_reveal and st.min_questions == 1
    assert not adaptive.status(c, {}).can_reveal              # but not before any answer: there is nothing to read


def test_the_validator_counts_only_the_questions_of_the_fixed_quizzes(cfg):
    assert validate_config(cfg) == []
    fewer = cfg.model_copy(deep=True)
    fewer.questions = [q for q in fewer.questions if q.id != "q50"]               # one confidence-mode-only question fewer: still valid
    assert validate_config(fewer) == []
    short = cfg.model_copy(deep=True)
    short.questions = [q for q in short.questions if q.id != "q05"]
    assert any("outside the confidence-mode-only tier" in e for e in validate_config(short))
    promoted = cfg.model_copy(deep=True)
    next(q for q in promoted.questions if q.id == "q31").min_length = "long"      # now a thirty-first fixed-quiz question
    assert any("found 31" in e for e in validate_config(promoted))


@pytest.mark.parametrize("class_id,spec_id", [("mage", "arcane"), ("mage", "frost"), ("paladin", "protection"), ("priest", "discipline"), ("rogue", "subtlety")])
def test_the_oracle_uses_the_added_questions_to_settle_a_specialization(c, model, class_id, spec_id):
    """A respondent who always gives the response the model finds most likely for a type is told that type, using the added questions."""
    tau = next(sp.gidx for cl in c.classes if cl.id == class_id for sp in cl.specs if sp.id == spec_id)
    answers = {}
    for _ in range(len(c.questions)):
        st = adaptive.status(c, answers)
        if st.done:
            break
        qi = c.q_index[st.next_question_id]
        answers[st.next_question_id] = c.questions[qi].answer_ids[max(range(len(c.questions[qi].answer_ids)), key=lambda r: model.logp[qi][r][tau])]
    assert st.reason == "confident" and len(answers) <= 12
    assert (st.recommended.class_id, st.recommended.specialization_id) == (class_id, spec_id)
    assert set(answers) & set(EXTRA_IDS)
