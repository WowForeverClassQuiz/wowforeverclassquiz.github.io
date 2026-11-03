"""Short, medium and long quizzes: nested question sets, scoring of one length, margins, persistence and the admin edit."""
import random
from math import sqrt

import pytest

from app.models import LENGTHS
from app.public import public_lengths
from app.scoring import UnknownQuestionError, IncompleteAssessmentError, batch_simulate, evaluate
from app.seed import build_default_config

from .conftest import DRUID_ANSWERS

API = "/api/v1"


def answers_for(cfg, length):
    """The fixed druid answers, restricted to the questions of one length."""
    ids = next(l.question_ids for l in public_lengths(cfg) if l.id == length)
    return {q: a for q, a in DRUID_ANSWERS.items() if q in ids}


def test_the_seed_offers_three_nested_lengths_of_ten_twenty_and_thirty_questions():
    cfg = build_default_config()
    lengths = {l.id: l for l in public_lengths(cfg)}
    assert [l.id for l in public_lengths(cfg)] == ["short", "medium", "long"]
    assert [lengths[i].question_count for i in LENGTHS] == [10, 20, 30]
    assert set(lengths["short"].question_ids) < set(lengths["medium"].question_ids) < set(lengths["long"].question_ids)
    order = [q.id for q in cfg.enabled_questions()]
    for l in lengths.values():                                    # each length keeps the quiz order
        assert l.question_ids == [q for q in order if q in l.question_ids]
    assert [l.minutes for l in lengths.values()] == [3, 7, 10]


def test_every_length_mixes_question_types_including_the_new_ones():
    cfg = build_default_config()
    kinds = {q.id: q.type for q in cfg.questions}
    for l in public_lengths(cfg):
        types = {kinds[i] for i in l.question_ids}
        assert {"choice", "scale"} <= types and types & {"ranking", "allocation"}, (l.id, types)


def test_the_public_quiz_lists_the_lengths_and_defaults_to_medium(client):
    body = client.get(f"{API}/quiz").json()
    assert body["question_count"] == 30 and len(body["questions"]) == 30 and body["default_length"] == "medium"
    assert [l["id"] for l in body["lengths"]] == ["short", "medium", "long"]
    assert all(set(l["question_ids"]) <= {q["id"] for q in body["questions"]} for l in body["lengths"])
    assert not any("min_length" in q for q in body["questions"])   # tier assignments are configuration, not participant data


@pytest.mark.parametrize("length,count", [("short", 10), ("medium", 20), ("long", 30)])
def test_a_length_scores_exactly_its_own_questions(client, length, count):
    cfg = build_default_config()
    answers = answers_for(cfg, length)
    r = client.post(f"{API}/evaluate", json={"answers": answers, "length": length})
    assert r.status_code == 200, r.text
    meta = r.json()["metadata"]
    assert meta["quiz_length"] == length and meta["total_questions"] == count == meta["answered_questions"] and meta["complete"]
    if length != "long":                                           # leaving one out is incomplete for that length
        short_one = {k: v for k, v in list(answers.items())[1:]}
        assert client.post(f"{API}/evaluate", json={"answers": short_one, "length": length}).status_code == 400


def test_answers_outside_the_chosen_length_are_rejected_not_ignored():
    cfg = build_default_config()
    with pytest.raises(UnknownQuestionError, match="not part of the short quiz"):
        evaluate(cfg, DRUID_ANSWERS, include_explanation=False, length="short")
    with pytest.raises(IncompleteAssessmentError):
        evaluate(cfg, answers_for(cfg, "short"), include_explanation=False)        # the long quiz needs all thirty


def test_an_unknown_length_is_a_schema_error(client):
    assert client.post(f"{API}/evaluate", json={"answers": DRUID_ANSWERS, "length": "epic"}).status_code == 422


def test_the_confidence_margins_scale_with_the_square_root_of_the_questions_asked():
    cfg = build_default_config()
    base = cfg.scoring.confidence_margins
    for length, count in (("short", 10), ("medium", 20), ("long", 30)):
        ev = evaluate(cfg, answers_for(cfg, length), include_explanation=False, length=length)
        scale = sqrt(count / 30)
        assert ev.result.confidence.strong_margin == base.strong * scale
        assert ev.result.confidence.moderate_margin == base.moderate * scale
    ev = evaluate(cfg, DRUID_ANSWERS, include_explanation=False)
    assert ev.result.confidence.strong_margin == base.strong == 3.0                # the long quiz is unchanged


def test_a_short_quiz_is_not_called_a_close_call_merely_for_being_short():
    """Under random answers the share of each confidence label is similar at every length."""
    cfg = build_default_config()
    shares = {}
    for length in LENGTHS:
        rng = random.Random(3)
        from app.scoring import compile_config, _class_totals, active_questions, margin_scale
        c = compile_config(cfg)
        act = active_questions(c, length)
        close = 0
        for _ in range(3000):
            picks = [(qi, rng.randrange(len(c.questions[qi].answer_ids))) for qi in act]
            tot = sorted(_class_totals(c, picks), reverse=True)
            close += (tot[0] - tot[1]) < c.moderate_margin * margin_scale(c, act)
        shares[length] = close / 3000
    assert max(shares.values()) - min(shares.values()) < 0.06, shares


def test_batch_simulation_can_target_a_length_and_the_long_default_is_unchanged(client):
    cfg = build_default_config()
    long_default = batch_simulate(cfg, 500, seed=9)
    assert long_default.baseline == batch_simulate(cfg, 500, seed=9, length="long").baseline
    short = batch_simulate(cfg, 500, seed=9, length="short")
    assert short.baseline != long_default.baseline and sum(r.count for r in short.baseline.class_frequencies) == 500
    r = client.post(f"{API}/simulate/batch", json={"count": 200, "seed": 1, "length": "short"})
    assert r.status_code == 200


def test_the_admin_can_move_a_question_between_lengths_and_it_persists(client):
    rev = client.get(f"{API}/health").json()["config_revision"]
    r = client.patch(f"{API}/questions/q05", json={"expected_revision": rev, "min_length": "short"})
    assert r.status_code == 200, r.text
    lengths = {l["id"]: l for l in client.get(f"{API}/quiz").json()["lengths"]}
    assert "q05" in lengths["short"]["question_ids"] and lengths["short"]["question_count"] == 11
    assert client.get(f"{API}/config").json()["questions"][6]["min_length"] in {"short", "medium", "long"}
    bad = client.patch(f"{API}/questions/q05", json={"expected_revision": rev + 1, "min_length": "epic"})
    assert bad.status_code == 422


def test_a_configuration_without_tiers_is_just_the_long_quiz():
    cfg = build_default_config()
    for q in cfg.questions:
        q.min_length = "long"
    lengths = public_lengths(cfg)
    assert [l.id for l in lengths] == ["long"] and lengths[0].question_count == 30
    ev = evaluate(cfg, DRUID_ANSWERS, include_explanation=False)
    assert ev.metadata.total_questions == 30


def test_lengths_with_identical_questions_are_listed_once_under_the_longest_name():
    cfg = build_default_config()
    for q in cfg.questions:
        q.min_length = "short"
    assert [l.id for l in public_lengths(cfg)] == ["long"]


def test_an_old_database_without_the_column_reads_every_question_as_long(tmp_path):
    from app.database import connect
    from app.repository import Repository
    repo = Repository(tmp_path / "x.db")
    repo.initialize()
    conn = connect(tmp_path / "x.db")
    conn.execute("UPDATE questions SET min_length = 'long'")
    conn.commit()
    conn.close()
    repo._cache = None
    assert {q.min_length for q in repo.get_config().questions} == {"long"}
