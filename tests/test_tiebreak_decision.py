"""A tiebreaker answered between the frontrunners settles the reading, even when the confidence is short of the threshold."""
import random
import shutil

import pytest

from app import adaptive
from app.models import AdaptiveSettings
from app.scoring import compile_config, evaluate
from app.seed import build_default_config
from app.static_export import export_static_data

from .test_static_parity import expected, run_node
from .test_tiebreakers import IDS

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


def blend_path(c, model, keys, seed=0, slip=0.0, settings=None):
    """Answer along the adaptive order as someone whose answers blend the given types (keys like 'paladin/protection'), slipping to a random answer a share of the time."""
    types = [c.spec_keys.index(k) for k in keys]
    rng = random.Random(seed)
    answers, statuses = {}, []
    for _ in range(31):
        st = adaptive.status(c, answers, settings=settings, model=model)
        statuses.append(st)
        if st.done:
            break
        qi = c.q_index[st.next_question_id]
        n = len(c.questions[qi].answer_ids)
        pick = rng.randrange(n) if rng.random() < slip else max(range(n), key=lambda r: sum(model.logp[qi][r][t] for t in types))
        answers[st.next_question_id] = c.questions[qi].answer_ids[pick]
    return statuses, answers


def decided_runs(c, model):
    """Readings that end 'decided', found over blends of two tanks and of two specializations of one class, with a few slips."""
    pairs = [("paladin/protection", "warrior/protection"), ("paladin/retribution", "paladin/protection"), ("mage/fire", "mage/frost"), ("rogue/combat", "warrior/fury"),
             ("priest/holy", "paladin/holy"), ("druid/restoration", "shaman/restoration")]
    out = []
    for pair in pairs:
        for seed in range(6):
            statuses, answers = blend_path(c, model, pair, seed=seed, slip=0.3)
            if statuses[-1].reason == "decided":
                out.append((pair, statuses, answers))
    return out


def test_the_setting_defaults_to_ten_questions_and_zero_turns_it_off(cfg, c, model):
    assert cfg.scoring.adaptive.tiebreak_min_questions == 10
    off = cfg.model_copy(deep=True)
    off.scoring.adaptive = off.scoring.adaptive.model_copy(update={"tiebreak_min_questions": 0})
    c_off = compile_config(off)
    m_off = adaptive.Model(c_off)
    for pair in (("paladin/protection", "warrior/protection"), ("mage/fire", "mage/frost")):
        for seed in range(4):
            statuses, _ = blend_path(c_off, m_off, pair, seed=seed, slip=0.3)
            assert statuses[-1].reason in ("confident", "limit"), (pair, seed)


def test_readings_end_by_a_tiebreaker_and_the_recommendation_is_the_specialization_it_names(c, model):
    runs = decided_runs(c, model)
    assert runs, "no reading ended by a tiebreaker"
    for pair, statuses, answers in runs:
        st = statuses[-1]
        picks = [(c.q_index[q], c.questions[c.q_index[q]].answer_ids.index(a)) for q, a in answers.items()]
        post = model.posterior(picks)
        g, qi = model.decision(post, picks, c.adaptive)
        assert g in c.questions[qi].finalists
        assert f"{st.recommended.class_id}/{st.recommended.specialization_id}" == c.spec_keys[g]
        assert st.answered >= c.adaptive.tiebreak_min_questions and st.current_confidence < st.threshold
        assert st.current_confidence >= st.threshold - adaptive.SOFT_BAND - 1e-9 and st.confidence >= st.current_confidence - 1e-12
        assert sum(post[x] for x in c.questions[qi].finalists) >= c.adaptive.tiebreak_mass
        answered = next(ai for q, ai in picks if q == qi)
        assert c.questions[qi].finalists[answered] == g                              # the named one is the one the person chose


def test_a_reading_is_never_decided_before_the_minimum_number_of_questions(c, model):
    for pair, statuses, _ in decided_runs(c, model):
        assert all(st.reason != "decided" or st.answered >= c.adaptive.tiebreak_min_questions for st in statuses)
        assert all(not st.done for st in statuses[:-1])


def test_a_lone_contrary_tiebreaker_answer_does_not_overrule_a_clear_leader(c, model):
    """Answer everything as Protection Paladin, then give the tank tiebreaker the Warrior answer: the Oracle does not hand the reading to the Warrior."""
    pal = c.spec_keys.index("paladin/protection")
    answers = {}
    for _ in range(30):
        st = adaptive.status(c, answers, model=model)
        if st.done:
            break
        qi = c.q_index[st.next_question_id]
        n = len(c.questions[qi].answer_ids)
        pick = max(range(n), key=lambda r: model.logp[qi][r][pal])
        if st.next_question_id == "q84":
            pick = c.questions[qi].finalists.index(c.spec_keys.index("warrior/protection"))
        answers[st.next_question_id] = c.questions[qi].answer_ids[pick]
    assert "q84" in answers or st.reason == "confident"
    assert f"{st.recommended.class_id}/{st.recommended.specialization_id}" == "paladin/protection" or st.reason == "limit"


def test_the_decision_does_not_depend_on_the_order_the_answers_arrive_in(c, model):
    for pair, statuses, answers in decided_runs(c, model)[:6]:
        ids = list(answers)
        a = adaptive.status(c, answers, model=model)
        for order in (ids[::-1], sorted(ids)):
            b = adaptive.status(c, {q: answers[q] for q in order}, model=model)
            assert (a.done, a.reason, a.recommended) == (b.done, b.reason, b.recommended)
            assert a.current_confidence == pytest.approx(b.current_confidence, abs=1e-12)


def test_the_result_names_the_decided_specialization_and_its_class_leads(cfg, c, model):
    for pair, statuses, answers in decided_runs(c, model):
        st = statuses[-1]
        ev = evaluate(cfg, answers, include_explanation=False, length="adaptive")
        r = ev.result
        assert (r.primary_class.id, r.primary_specialization.id) == (st.recommended.class_id, st.recommended.specialization_id)
        assert r.confidence.decided_by in IDS and r.confidence.decision_note.startswith("Your answer to a tiebreaker question settled the choice between ")
        assert ev.rankings.classes[0].id == r.primary_class.id and ev.rankings.classes[0].rank == 1
        assert all(row.gap_to_leader >= 0 for row in ev.rankings.classes)
        assert ev.rankings.specializations[0].id == r.primary_specialization.id
        assert r.confidence.overall == pytest.approx(st.confidence, abs=1e-9) and r.confidence.class_gap >= 0
        full = evaluate(cfg, answers, include_explanation=True, include_counterfactuals=True, length="adaptive")
        assert full.explanation.counterfactuals is None                       # the what-ifs describe the scores alone


def test_a_reading_that_is_not_decided_carries_no_decision_note(cfg):
    from .conftest import DRUID_ANSWERS
    ev = evaluate(cfg, DRUID_ANSWERS, include_explanation=False)
    assert ev.result.confidence.decided_by is None and ev.result.confidence.decision_note is None
    assert "decided_by" not in ev.result.confidence.model_dump(exclude_none=True)


def test_the_minimum_is_a_setting_an_administrator_can_change(client):
    rev = client.get(f"{API}/health").json()["config_revision"]
    body = {"min_questions": 1, "max_questions": 30, "confidence": 0.9, "sharpness_class": 1.0, "sharpness_spec": 0.35, "enabled": True}
    ok = client.patch(f"{API}/scoring", json={"expected_revision": rev, "adaptive": {**body, "tiebreak_min_questions": 5, "effort_ranking": 2.0, "effort_allocation": 4.0}})
    assert ok.status_code == 200
    adaptive_now = ok.json()["scoring"]["adaptive"]
    assert (adaptive_now["tiebreak_min_questions"], adaptive_now["effort_ranking"], adaptive_now["effort_allocation"]) == (5, 2.0, 4.0)
    assert client.patch(f"{API}/scoring", json={"expected_revision": rev + 1, "adaptive": {**body, "tiebreak_min_questions": -1}}).status_code == 422
    assert client.patch(f"{API}/scoring", json={"expected_revision": rev + 1, "adaptive": {**body, "effort_allocation": 0.5}}).status_code == 422


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_browser_reaches_the_same_decisions_and_results(cfg, c, model):
    runs = decided_runs(c, model)[:6]
    assert runs
    data = export_static_data(cfg)
    flat = [dict(list(answers.items())[:k]) for _, _, answers in runs for k in range(1, len(answers) + 1)]
    got = run_node({"paths": [{"data": data, "answers": flat}]})["paths"][0]
    for answers, js in zip(flat, got):
        py = adaptive.status(c, answers, model=model).model_dump(mode="json", exclude_none=True)
        assert js.get("reason") == py.get("reason") and js["done"] == py["done"] and js["recommended"]["specialization_id"] == py["recommended"]["specialization_id"]
        assert js["confidence"] == pytest.approx(py["confidence"], abs=1e-9) and js["current_confidence"] == pytest.approx(py["current_confidence"], abs=1e-9)
    finals = [answers for _, _, answers in runs]
    results = run_node({"cases": [{"data": data, "answers": finals, "length": "adaptive"}]})["cases"][0]
    for answers, js in zip(finals, results):
        assert js == expected(cfg, answers, "adaptive")
        assert js["result"]["confidence"]["decided_by"] in IDS
