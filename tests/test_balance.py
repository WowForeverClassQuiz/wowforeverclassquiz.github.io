"""The seed quiz must stay balanced, and every tuning edit must be documented and sensible.

"Under random answers" means every question is answered uniformly at random over its possible responses. These shares are
diagnostics of the scoring rules, not probabilities of real people's results.
"""
from collections import Counter, defaultdict

import pytest

from app import seed_tuning
from app.scoring import batch_simulate
from app.seed import QUESTIONS, build_default_config

MIN_SPEC_SHARE = 0.20          # the requirement: a specialization wins at least this share of its class's results
EVEN = 1 / 9                   # every class should be chosen equally often
CLASS_TOLERANCE = 0.010        # in this test's 12,000 random answers that is about 3.4 standard errors; tools/balance.py checks tighter


@pytest.fixture(scope="module", params=["short", "medium", "long"])
def shares(request):
    """Result shares under uniformly random answers, for each quiz length."""
    cfg = build_default_config()
    batch = batch_simulate(cfg, 12000, seed=20261104, length=request.param).baseline
    class_count = {r.id: r.count for r in batch.class_frequencies}
    spec = defaultdict(dict)
    for r in batch.specialization_frequencies:
        spec[r.class_id][r.id] = r.count / max(1, class_count[r.class_id])
    return {"class": {r.id: r.frequency for r in batch.class_frequencies}, "spec": dict(spec)}


def test_every_specialization_wins_at_least_twenty_percent_of_its_class_under_random_answers_at_every_length(shares):
    low = {f"{c}/{s}": round(v, 3) for c, specs in shares["spec"].items() for s, v in specs.items() if v < MIN_SPEC_SHARE}
    assert low == {}, low


def test_every_class_is_recommended_equally_often_at_every_length(shares):
    out = {c: round(v, 4) for c, v in shares["class"].items() if abs(v - EVEN) > CLASS_TOLERANCE}
    assert out == {}, out


def test_no_specialization_dominates_its_class(shares):
    assert max(v for specs in shares["spec"].values() for v in specs.values()) < 0.55


# ------------------------------------------------------------------ the tuning overlay is documented and sensible


def test_every_direct_spec_weight_names_a_class_the_answer_already_favours():
    cfg = build_default_config()
    for (qid, aid), weights in seed_tuning.SPEC_WEIGHTS.items():
        answer = next(a for a in cfg.get_question(qid).answers if a.id == aid)
        assert answer.spec_weights == weights
        for key, w in weights.items():
            assert key.split("/")[0] in answer.class_weights, (qid, aid, key)
            assert 0 < w <= 3, (qid, aid, key, w)


def test_every_specialization_has_direct_weights_somewhere():
    cfg = build_default_config()
    keys = {k for weights in seed_tuning.SPEC_WEIGHTS.values() for k in weights}
    assert keys == {f"{c.id}/{s.id}" for c in cfg.classes for s in c.specializations}


def test_type_changes_keep_the_original_four_answers_and_only_reword_the_question():
    cfg = build_default_config()
    original = {qid: (text, answers) for qid, text, answers in QUESTIONS}
    for qid, (qtype, text) in seed_tuning.TYPE_CHANGES.items():
        q = cfg.get_question(qid)
        assert q.type == qtype in ("ranking", "allocation") and q.text == text and q.text != original[qid][0]
        assert [a.text for a in q.answers] == [a[1] for a in original[qid][1]]       # the answers themselves are untouched


def test_class_pair_changes_only_touch_original_answers_and_keep_a_primary_and_secondary():
    for (qid, aid), pair in seed_tuning.ORIGINAL_CLASS_PAIRS.items():
        assert qid <= "q16" and len(set(pair)) == 2


def test_changes_to_the_original_questions_are_small():
    """The overlay is a rebalancing, not a rewrite: only a handful of original answers move classes."""
    assert len(seed_tuning.ORIGINAL_CLASS_PAIRS) <= 10 and len(seed_tuning.TYPE_CHANGES) <= 6


def test_class_weight_adjustments_keep_each_answers_classes_and_total():
    """The equalizing overlay only moves weight between an answer's two classes: the classes and the total of 3 never change,
    so the class scores of a complete answer set still sum to zero."""
    cfg = build_default_config()
    for (qid, aid), weights in seed_tuning.CLASS_WEIGHTS.items():
        answer = next(a for a in cfg.get_question(qid).answers if a.id == aid)
        assert answer.class_weights == weights and len(weights) == 2, (qid, aid)
        assert abs(sum(weights.values()) - 3.0) < 1e-12, (qid, aid, weights)
        assert 1.5 <= max(weights.values()) <= 2.5, (qid, aid, weights)
        assert qid != "q01", "Q01 is the documentation's worked example and stays as written"
    for q in cfg.questions:
        for a in q.answers:
            if q.type != "scale" or len(a.class_weights) == 2:
                assert abs(sum(a.class_weights.values()) - 3.0) < 1e-12, (q.id, a.id)


def test_trait_weights_of_the_original_questions_are_untouched():
    cfg = build_default_config()
    for qid, _text, answers in QUESTIONS:
        for aid, _t, _cl, (t1, t2) in answers:
            a = next(x for x in cfg.get_question(qid).answers if x.id == aid)
            assert a.trait_weights == {t1: 2.0, t2: 1.0}


# ------------------------------------------------------------------ the developer simulator agrees with the engine


def test_the_fast_balance_simulator_matches_the_scoring_engine():
    pytest.importorskip("numpy")
    import importlib.util
    import pathlib
    spec = importlib.util.spec_from_file_location("balance", pathlib.Path(__file__).resolve().parent.parent / "tools" / "balance.py")
    balance = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(balance)
    for length in ("short", "medium", "long"):
        assert balance.parity(build_default_config(), k=100, length=length) == 0
        rep = balance.Sim(build_default_config(), n=20000, seed=3, length=length).report()
        assert min(v for specs in rep["spec"].values() for v in specs.values()) >= MIN_SPEC_SHARE, length


def test_classes_are_equally_likely_to_a_tight_tolerance_on_a_large_sample():
    """100,000 random answer sets per length: every class within half a percentage point of an even 1/9."""
    pytest.importorskip("numpy")
    import importlib.util
    import pathlib
    spec = importlib.util.spec_from_file_location("balance", pathlib.Path(__file__).resolve().parent.parent / "tools" / "balance.py")
    balance = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(balance)
    for length in ("short", "medium", "long"):
        shares = balance.Sim(build_default_config(), n=100000, seed=20261105, length=length).report()["class"]
        worst = max(abs(v - EVEN) for v in shares.values())
        assert worst < 0.005, (length, {k: round(v, 4) for k, v in shares.items()})
