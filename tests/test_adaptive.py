"""Confidence mode: the choice model, the most informative next question, when to stop, and its browser twin."""
import json
import math
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from app import adaptive
from app.models import AdaptiveSettings
from app.scoring import IncompleteAssessmentError, ScoringError, compile_config, evaluate, response_coefficients
from app.seed import build_default_config
from app.static_export import export_static_data

from .conftest import DRUID_ANSWERS
from .test_static_parity import expected, random_answers, run_node

API = "/api/v1"
NODE = shutil.which("node")


@pytest.fixture(scope="module")
def cfg():
    return build_default_config()


@pytest.fixture(scope="module")
def c(cfg):
    return compile_config(cfg)


@pytest.fixture(scope="module")
def model(c):
    return adaptive.Model(c)


@pytest.fixture(scope="module")
def feral(c, model):
    """A deterministic respondent of type Druid / Feral Combat: the most likely response to every one of the fifty questions."""
    tau = next(sp.gidx for cl in c.classes if cl.id == "druid" for sp in cl.specs if sp.id == "feral_combat")
    return {q.id: q.answer_ids[max(range(len(q.answer_ids)), key=lambda r: model.logp[i][r][tau])] for i, q in enumerate(c.questions)}


def respond(model, c, qi, tau, rng):
    """Answer question qi as a person of type tau would, under the model."""
    probs = [math.exp(row[tau]) for row in model.logp[qi]]
    return c.questions[qi].answer_ids[rng.choices(range(len(probs)), probs)[0]]


def run_respondent(model, c, tau, rng, adaptive_order=True, settings=None):
    s = settings or c.adaptive
    answers, remaining = {}, list(range(len(c.questions)))
    while True:
        picks = [(c.q_index[q], c.questions[c.q_index[q]].answer_ids.index(r)) for q, r in answers.items()]
        post = model.posterior(picks)
        rec = adaptive.recommended_type(c, picks) if picks else 0
        n = len(answers)
        if n >= s.max_questions or not remaining or (n >= s.min_questions and post[rec] >= s.confidence):
            return n, post[rec], rec == tau
        qi = model.best_question(post, remaining)[0] if adaptive_order else remaining[0]
        remaining.remove(qi)
        answers[c.questions[qi].id] = respond(model, c, qi, tau, rng)


# ------------------------------------------------------------------ the model


def test_before_any_answer_the_27_types_are_equally_likely(model):
    post = model.posterior([])
    assert len(post) == 27 and all(math.isclose(p, 1 / 27) for p in post)
    assert math.isclose(model.entropy(post), math.log(27))


def test_every_response_distribution_is_a_probability_distribution(model, c):
    for qi, q in enumerate(c.questions):
        for g in range(27):
            assert math.isclose(sum(math.exp(model.logp[qi][r][g]) for r in range(len(q.answer_ids))), 1.0, rel_tol=1e-12), (q.id, g)


def test_the_posterior_adds_up_and_does_not_depend_on_the_order_of_the_answers(model, c):
    picks = [(c.q_index[q], c.questions[c.q_index[q]].answer_ids.index(r)) for q, r in list(DRUID_ANSWERS.items())[:12]]
    post = model.posterior(picks)
    assert math.isclose(sum(post), 1.0, rel_tol=1e-12)
    assert max(abs(a - b) for a, b in zip(post, model.posterior(list(reversed(picks))))) < 1e-12


def test_the_log_posterior_is_the_scoring_evidence_less_a_normalizer(model, c):
    """For every type: sum of log P(answer | type) = lambda_c * S_class + lambda_s * P_spec - sum of per-question normalizers.

    S and P are the very class and specialization scores the quiz computes, so the confidence model is the scoring, read as evidence."""
    from app.scoring import _class_totals, _spec_totals, _trait_totals
    s = c.adaptive
    picks = [(c.q_index[q], c.questions[c.q_index[q]].answer_ids.index(r)) for q, r in DRUID_ANSWERS.items()]
    ct, tt, st = _class_totals(c, picks), _trait_totals(c, picks), _spec_totals(c, picks)
    for ci, cls in enumerate(c.classes):
        for sp in cls.specs:
            g = sp.gidx
            evidence = s.sharpness_class * ct[ci] + s.sharpness_spec * (math.fsum(m * tt[t] for t, m in sp.terms) + c.spec_multiplier * st[g])
            normalizers = 0.0
            for qi, ri in picks:
                q = c.questions[qi]
                u = [s.sharpness_class * q.class_delta[r][ci]
                     + s.sharpness_spec * (math.fsum(m * q.trait_delta[r][t] for t, m in sp.terms) + c.spec_multiplier * q.spec_delta[r][g])
                     for r in range(len(q.answer_ids))]
                normalizers += math.log(math.fsum(math.exp(x) for x in u))
            log_likelihood = math.fsum(model.logp[qi][ri][g] for qi, ri in picks)
            assert math.isclose(log_likelihood, evidence - normalizers, rel_tol=1e-9, abs_tol=1e-9), (cls.id, sp.id)


def test_asking_a_question_never_loses_information_on_average(model, c):
    post = model.posterior([])
    for qi in range(len(c.questions)):
        assert model.expected_gain(post, qi) >= -1e-12


def test_the_next_question_is_the_one_with_the_largest_expected_gain(model, c):
    post = model.posterior([])
    best, gain = model.best_question(post, list(range(len(c.questions))))
    gains = [round(model.expected_gain(post, qi), 9) for qi in range(len(c.questions))]
    assert round(gain, 9) == max(gains) and round(model.expected_gain(post, best), 9) == max(gains)


def test_the_adaptive_order_needs_fewer_questions_than_the_quiz_order():
    cfg = build_default_config()
    c = compile_config(cfg)
    model = adaptive.Model(c)
    results = {}
    for adaptive_order in (True, False):
        rng = random.Random(11)
        runs = [run_respondent(model, c, rng.randrange(27), rng, adaptive_order) for _ in range(120)]
        results[adaptive_order] = sum(r[0] for r in runs) / len(runs)
    assert results[True] < results[False] - 1.5, results


# ------------------------------------------------------------------ stopping


def test_the_status_before_any_answer_asks_the_most_informative_question(c):
    st = adaptive.status(c, {})
    assert st.answered == 0 and not st.done and st.next_question_id and not st.can_reveal
    assert math.isclose(st.confidence, 1 / 27) and st.threshold == 0.9 and (st.min_questions, st.max_questions) == (1, 30)


def test_a_clear_respondent_is_told_to_stop_as_soon_as_the_oracle_is_sure(c, feral):
    answers = {}
    for k in range(40):
        st = adaptive.status(c, answers)
        if st.done:
            break
        answers[st.next_question_id] = feral[st.next_question_id]
    assert st.done and st.reason == "confident" and st.confidence >= 0.9 and len(answers) < 15
    assert not any(adaptive.status(c, dict(list(answers.items())[:k])).done for k in range(0, len(answers)))      # not one answer sooner
    assert st.recommended.class_id == "druid" and st.recommended.specialization_id == "feral_combat"


def test_an_inconsistent_respondent_runs_to_the_limit(c, model):
    rng = random.Random(4)
    answers = {}
    for _ in range(40):
        st = adaptive.status(c, answers)
        if st.done:
            break
        qi = c.q_index[st.next_question_id]
        answers[st.next_question_id] = rng.choice(c.questions[qi].answer_ids)
    assert st.done and len(answers) <= 30
    if st.reason == "confident":
        assert st.confidence >= 0.9
    else:
        assert st.reason == "limit" and len(answers) == 30


def test_the_limit_and_the_minimum_come_from_the_settings(cfg, feral):
    cfg = cfg.model_copy(deep=True)
    cfg.scoring.adaptive = AdaptiveSettings(min_questions=3, max_questions=5, confidence=0.5)
    c = compile_config(cfg)
    answers = {}
    for _ in range(10):
        st = adaptive.status(c, answers)
        if st.done:
            break
        answers[st.next_question_id] = feral[st.next_question_id]
    assert st.done and 3 <= len(answers) <= 5


def test_synthetic_respondents_are_recovered_about_as_often_as_the_confidence_says():
    """Within the model the posterior is exact: when the Oracle stops, it is right about as often as it says."""
    cfg = build_default_config()
    c = compile_config(cfg)
    model = adaptive.Model(c)
    rng = random.Random(2026)
    runs = [run_respondent(model, c, rng.randrange(27), rng) for _ in range(250)]
    mean_conf = sum(r[1] for r in runs) / len(runs)
    accuracy = sum(r[2] for r in runs) / len(runs)
    assert abs(mean_conf - accuracy) < 0.07, (mean_conf, accuracy)
    assert 3 <= sum(r[0] for r in runs) / len(runs) < 14 and accuracy > 0.8


# ------------------------------------------------------------------ result and API


def test_a_confidence_mode_result_scores_exactly_the_questions_answered(cfg, c, feral):
    answers = {}
    while True:
        st = adaptive.status(c, answers)
        if st.done:
            break
        answers[st.next_question_id] = feral[st.next_question_id]
    ev = evaluate(cfg, answers, include_explanation=False, length="adaptive")
    m = ev.metadata
    assert m.quiz_length == "adaptive" and m.total_questions == m.answered_questions == len(answers) and m.complete and not m.missing_questions
    assert (ev.result.primary_class.id, ev.result.primary_specialization.id) == ("druid", "feral_combat")
    assert ev.result.confidence.probability == pytest.approx(st.confidence, abs=1e-9)
    assert ev.result.confidence.strong_margin == pytest.approx(3.0 * math.sqrt(len(answers) / 30))


def test_a_confidence_mode_result_needs_the_minimum_number_of_answers(cfg):
    few = dict(list(DRUID_ANSWERS.items())[:6])
    assert evaluate(cfg, dict(list(few.items())[:1]), include_explanation=False, length="adaptive").metadata.total_questions == 1   # no minimum by default
    strict = cfg.model_copy(deep=True)
    strict.scoring.adaptive.min_questions = 10
    with pytest.raises(ScoringError, match="at least 10"):
        evaluate(strict, few, include_explanation=False, length="adaptive")
    assert evaluate(strict, few, include_explanation=False, length="adaptive", allow_partial=True).metadata.total_questions == 6
    with pytest.raises(IncompleteAssessmentError):
        evaluate(cfg, {}, include_explanation=False, length="adaptive")


def test_every_evaluation_reports_the_models_probability_for_its_recommendation(cfg):
    for length in ("short", "medium", "long"):
        ids = next(l.question_ids for l in __import__("app.public", fromlist=["public_lengths"]).public_lengths(cfg) if l.id == length)
        ev = evaluate(cfg, {q: a for q, a in DRUID_ANSWERS.items() if q in ids}, include_explanation=False, length=length)
        assert 0.0 < ev.result.confidence.probability <= 1.0
    full = evaluate(cfg, DRUID_ANSWERS, include_explanation=False)
    assert full.result.confidence.probability > 0.99


def test_the_adaptive_endpoint(client, feral):
    first = client.post(f"{API}/adaptive/next", json={"answers": {}}).json()
    assert first["next_question_id"] and first["answered"] == 0 and first["done"] is False and "reason" not in first
    answers = {}
    for _ in range(40):
        st = client.post(f"{API}/adaptive/next", json={"answers": answers}).json()
        if st["done"]:
            break
        answers[st["next_question_id"]] = feral[st["next_question_id"]]
    assert st["done"] and st["reason"] == "confident" and st["confidence"] >= 0.9 and "next_question_id" not in st
    r = client.post(f"{API}/evaluate", json={"answers": answers, "length": "adaptive"})
    assert r.status_code == 200 and r.json()["metadata"]["quiz_length"] == "adaptive"
    assert client.post(f"{API}/evaluate", json={"answers": {}, "length": "adaptive"}).status_code == 400
    assert client.post(f"{API}/adaptive/next", json={"answers": {"q99": "a"}}).status_code == 400
    assert client.post(f"{API}/adaptive/next", json={"answers": {"q09": "nonsense"}}).status_code == 400


def test_confidence_mode_is_the_default_and_the_first_option(client):
    quiz = client.get(f"{API}/quiz").json()
    assert quiz["default_length"] == "adaptive" and [l["id"] for l in quiz["lengths"]] == ["adaptive", "short", "medium", "long"]
    ad = quiz["lengths"][0]
    assert ad["adaptive"] is True and (ad["min_questions"], ad["max_questions"], ad["confidence"]) == (1, 30, 0.9) and len(ad["question_ids"]) == 50


def test_an_administrator_can_change_or_switch_off_confidence_mode(client):
    rev = client.get(f"{API}/health").json()["config_revision"]
    r = client.patch(f"{API}/scoring", json={"expected_revision": rev, "adaptive": {"min_questions": 12, "max_questions": 25, "confidence": 0.95,
                                                                                 "sharpness_class": 1.0, "sharpness_spec": 0.35, "enabled": True}})
    assert r.status_code == 200 and r.json()["scoring"]["adaptive"]["confidence"] == 0.95
    assert client.post(f"{API}/adaptive/next", json={"answers": {}}).json()["threshold"] == 0.95
    bad = client.patch(f"{API}/scoring", json={"expected_revision": rev + 1, "adaptive": {"min_questions": 20, "max_questions": 10}})
    assert bad.status_code == 400 and any("min_questions" in e for e in bad.json()["detail"]["errors"])
    off = client.patch(f"{API}/scoring", json={"expected_revision": rev + 1, "adaptive": {"enabled": False}})
    assert off.status_code == 200
    assert [l["id"] for l in client.get(f"{API}/quiz").json()["lengths"]] == ["short", "medium", "long"]
    assert client.get(f"{API}/quiz").json()["default_length"] == "medium"
    assert client.post(f"{API}/adaptive/next", json={"answers": {}}).status_code == 400


# ------------------------------------------------------------------ the browser twin


def paths(cfg, seeds=8):
    """Answer sets growing along the adaptive order, for a few respondents."""
    c = compile_config(cfg)
    model = adaptive.Model(c)
    rng = random.Random(77)
    out = []
    for k in range(seeds):
        tau = rng.randrange(27)
        answers, steps = {}, [{}]
        for _ in range(30):
            st = adaptive.status(c, answers, model=model)
            if st.done:
                break
            qi = c.q_index[st.next_question_id]
            answers = {**answers, st.next_question_id: respond(model, c, qi, tau, rng) if k % 2 == 0 else rng.choice(c.questions[qi].answer_ids)}
            steps.append(dict(answers))
        out.append(steps)
    return out


def close(a, b, path=""):
    if isinstance(a, dict):
        assert a.keys() == b.keys(), (path, a.keys() ^ b.keys())
        for k in a:
            close(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list):
        assert len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            close(x, y, f"{path}[{i}]")
    elif isinstance(a, float) or isinstance(b, float):
        assert abs(a - b) < 1e-9, (path, a, b)
    else:
        assert a == b, (path, a, b)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("name", ["seed", "edited"])
def test_the_browser_confidence_model_matches_python_along_whole_question_paths(name):
    from .test_static_parity import CONFIGS
    cfg = CONFIGS[name]()
    c = compile_config(cfg)
    flat = [a for steps in paths(cfg) for a in steps]
    got = run_node({"paths": [{"data": export_static_data(cfg), "answers": flat}]})["paths"][0]
    for answers, js in zip(flat, got):
        py = adaptive.status(c, answers).model_dump(mode="json", exclude_none=True)
        close(py, js)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_browser_scores_confidence_mode_results_exactly_like_python():
    cfg = build_default_config()
    sets = [steps[-1] for steps in paths(cfg)]
    sets = [s for s in sets if len(s) >= 10]
    got = run_node({"cases": [{"data": export_static_data(cfg), "answers": sets, "length": "adaptive"}]})["cases"][0]
    assert sets
    for answers, js in zip(sets, got):
        assert js == expected(cfg, answers, "adaptive")
