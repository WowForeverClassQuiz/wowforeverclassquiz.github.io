"""The ranking and point-allocation question types: response tables, scoring, validation and the expansion endpoint."""
from math import isclose

import pytest

from app.models import Question
from app.scoring import UnknownAnswerError, compile_config, evaluate, expand_question, response_coefficients
from app.seed import build_default_config
from app.validation import validate_config

from .conftest import DRUID_ANSWERS

API = "/api/v1"


def question(cfg, qid):
    return cfg.get_question(qid)


def test_a_ranking_has_all_24_orderings_and_weighs_the_answers_one_and_a_half_one_half_and_zero():
    q = question(build_default_config(), "q07")
    rows = response_coefficients(q)
    assert q.type == "ranking" and len(rows) == 24 and len({r[0] for r in rows}) == 24
    assert all(sorted(coefs) == [0.0, 0.5, 1.0, 1.5] for _, _, coefs in rows)
    by_id = {rid: coefs for rid, _, coefs in rows}
    assert by_id["c>a>d>b"] == [1.0, 0.0, 1.5, 0.5]            # c first, a second, d third, b last


def test_an_allocation_has_every_split_of_six_points_and_weighs_each_answer_by_points_over_three():
    q = question(build_default_config(), "q09")
    rows = response_coefficients(q)
    assert q.type == "allocation" and len(rows) == 84 and len({r[0] for r in rows}) == 84
    by_id = {rid: coefs for rid, _, coefs in rows}
    assert all(sum(int(p) for p in rid.split("-")) == 6 for rid in by_id)
    assert by_id["2-0-3-1"] == [2 / 3, 0.0, 1.0, 1 / 3]
    assert all(isclose(sum(coefs), 2.0) for coefs in by_id.values())


@pytest.mark.parametrize("qid", ["q07", "q09", "q11", "q15", "q26"])
def test_contributions_of_a_ranking_or_allocation_average_to_zero_over_all_responses(qid):
    """The baseline is the mean over every possible response, so a question cannot favour a class on average."""
    cfg = build_default_config()
    c = compile_config(cfg)
    q = c.questions[c.q_index[qid]]
    for i in range(c.n_classes):
        assert abs(sum(row[i] for row in q.class_delta) / len(q.class_delta)) < 1e-9
    for i in range(c.n_traits):
        assert abs(sum(row[i] for row in q.trait_delta) / len(q.trait_delta)) < 1e-9


def test_the_order_of_a_ranking_matters_and_first_place_counts_for_most():
    cfg = build_default_config()
    base = dict(DRUID_ANSWERS)
    forward = evaluate(cfg, {**base, "q07": "a>b>c>d"}, include_explanation=False)
    reverse = evaluate(cfg, {**base, "q07": "d>c>b>a"}, include_explanation=False)
    score = lambda ev, cid: next(c.score for c in ev.rankings.classes if c.id == cid)
    a = next(x for x in question(cfg, "q07").answers if x.id == "a")
    d = next(x for x in question(cfg, "q07").answers if x.id == "d")
    fav_a = max(a.class_weights, key=a.class_weights.get)
    fav_d = max(d.class_weights, key=d.class_weights.get)
    assert score(forward, fav_a) > score(reverse, fav_a)
    assert score(reverse, fav_d) > score(forward, fav_d)


def test_putting_all_six_points_on_one_item_counts_more_than_spreading_them():
    cfg = build_default_config()
    q = compile_config(cfg).questions
    table = {r: i for i, r in enumerate(next(x for x in q if x.id == "q09").answer_ids)}
    deltas = next(x for x in q if x.id == "q09").class_delta
    favoured = max(range(9), key=lambda i: deltas[table["6-0-0-0"]][i])
    assert deltas[table["6-0-0-0"]][favoured] > deltas[table["3-3-0-0"]][favoured] > deltas[table["2-2-1-1"]][favoured]


@pytest.mark.parametrize("qid,bad", [
    ("q07", "a>a>b>c"), ("q07", "a>b>c"), ("q07", "a+b"), ("q07", "e>b>c>d"),
    ("q09", "7-0-0-0"), ("q09", "3-3-3-3"), ("q09", "2-2-2"), ("q09", "a"),
])
def test_malformed_rankings_and_allocations_are_rejected(qid, bad):
    with pytest.raises(UnknownAnswerError):
        evaluate(build_default_config(), {**DRUID_ANSWERS, qid: bad}, include_explanation=False)


def test_questions_of_these_types_need_exactly_four_answers():
    cfg = build_default_config()
    for qid in ("q07", "q09"):
        broken = cfg.model_copy(deep=True)
        q = broken.get_question(qid)
        q.answers = q.answers[:3]
        assert any(qid in e and "exactly 4" in e for e in validate_config(broken))


def test_the_participant_view_carries_the_points_but_no_weights(client):
    qs = {q["id"]: q for q in client.get(f"{API}/quiz").json()["questions"]}
    assert qs["q09"]["type"] == "allocation" and qs["q09"]["points"] == 6 and len(qs["q09"]["answers"]) == 4
    assert qs["q07"]["type"] == "ranking" and qs["q07"]["points"] is None
    assert not any("weights" in k for q in qs.values() for k in q)


def test_the_expansion_endpoint_lists_every_ranking_and_allocation_response(client):
    cfg = client.get(f"{API}/config").json()
    for qid, count in (("q07", 24), ("q09", 84)):
        q = next(x for x in cfg["questions"] if x["id"] == qid)
        r = client.post(f"{API}/questions/expand", json={"question": q})
        assert r.status_code == 200
        body = r.json()
        assert body["type"] == q["type"] and len(body["options"]) == count


def test_every_specialization_stays_reachable_with_the_new_types():
    """A hill-climb over complete answer sets (any response, any type) reaches each of the 27 specializations."""
    import random
    from app.scoring import _lean_primary, _class_totals, _trait_totals, _spec_totals
    cfg = build_default_config()
    c = compile_config(cfg)
    rng = random.Random(3)
    sizes = [len(q.answer_ids) for q in c.questions]

    def primary(picks):
        ci, si, _ = _lean_primary(c, _class_totals(c, picks), _trait_totals(c, picks), _spec_totals(c, picks))
        return ci, si

    seen = set()
    for _ in range(4000):
        seen.add(primary([(qi, rng.randrange(n)) for qi, n in enumerate(sizes)]))
    assert len(seen) == 27
