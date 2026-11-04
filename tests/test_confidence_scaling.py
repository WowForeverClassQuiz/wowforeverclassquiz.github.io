"""The confidence scales with the number of questions asked, never falls as the stated figure, starts at zero, and the quiz opens with a personality question."""
import random

import pytest

from app import adaptive
from app.models import AdaptiveSettings
from app.scoring import compile_config, evaluate
from app.seed import build_default_config
from app.seed_classes import CLASS_ORDER

API = "/api/v1"


@pytest.fixture(scope="module")
def cfg():
    return build_default_config()


@pytest.fixture(scope="module")
def c(cfg):
    return compile_config(cfg)


@pytest.fixture(scope="module")
def model(c):
    return adaptive.Model(c)


def noisy_path(c, model, tau, seed, slip=0.5, limit=30):
    """Answer along the adaptive order as a person of type tau, slipping to a random answer a share of the time. Returns every status along the way."""
    rng = random.Random(seed)
    answers, statuses = {}, []
    for _ in range(limit):
        st = adaptive.status(c, answers, model=model)
        statuses.append(st)
        if st.done:
            break
        qi = c.q_index[st.next_question_id]
        n = len(c.questions[qi].answer_ids)
        pick = rng.randrange(n) if rng.random() < slip else max(range(n), key=lambda r: model.logp[qi][r][tau])
        answers[st.next_question_id] = c.questions[qi].answer_ids[pick]
    return statuses, answers


def test_the_scaling_is_n_over_n_plus_k_and_the_default_k_is_one(cfg):
    assert cfg.scoring.adaptive.question_scaling == 1.0
    assert adaptive.question_factor(0, 1.0) == 0.0
    assert adaptive.question_factor(1, 1.0) == pytest.approx(0.5) and adaptive.question_factor(9, 1.0) == pytest.approx(0.9)
    assert adaptive.question_factor(30, 1.0) == pytest.approx(30 / 31)
    assert adaptive.question_factor(5, 0.0) == 1.0 and adaptive.question_factor(0, 0.0) == 0.0        # 0 turns the scaling off, but not before the first answer


def test_the_oracle_reads_zero_before_the_first_answer_whatever_the_scaling(cfg, c):
    st = adaptive.status(c, {})
    assert st.confidence == 0.0 and st.current_confidence == 0.0 and st.question_factor == 0.0 and st.answered == 0
    off = cfg.model_copy(deep=True)
    off.scoring.adaptive = AdaptiveSettings(question_scaling=0.0)
    assert adaptive.status(compile_config(off), {}).confidence == 0.0


def test_the_confidence_the_oracle_states_rises_with_every_question(c, model):
    for tau in (0, 4, 9, 13, 19, 25):
        for slip in (0.0, 0.5, 0.8):
            statuses, _ = noisy_path(c, model, tau, seed=tau * 7 + int(slip * 10), slip=slip)
            shown = [st.confidence for st in statuses]
            assert shown[0] == 0.0
            assert all(after > before for before, after in zip(shown, shown[1:])), (tau, slip, shown)           # strictly, every question
            assert all(s < statuses[0].threshold - adaptive.HEADROOM + 1e-12 for s, st in zip(shown, statuses) if not st.done or st.reason != "confident")


def test_the_current_confidence_can_fall_but_the_stated_one_does_not(c, model):
    """The case the stated figure exists for: a surprising answer lowers the current confidence, and the figure shown keeps rising."""
    found = False
    for tau in range(27):
        statuses, _ = noisy_path(c, model, tau, seed=100 + tau, slip=0.7)
        currents = [st.current_confidence for st in statuses]
        if any(b < a - 0.05 for a, b in zip(currents, currents[1:])):
            found = True
            shown = [st.confidence for st in statuses]
            assert all(b > a for a, b in zip(shown, shown[1:])), shown
    assert found


def test_the_stopping_rule_tests_the_current_confidence_not_the_best_so_far(c, model):
    for tau in (1, 8, 14, 22):
        statuses, _ = noisy_path(c, model, tau, seed=500 + tau, slip=0.6)
        for st in statuses:
            if st.done and st.reason == "confident":
                assert st.current_confidence >= st.threshold and st.confidence == pytest.approx(st.current_confidence)
            elif not st.done:
                assert st.current_confidence < st.threshold or st.answered < st.min_questions
                assert st.confidence < st.threshold - adaptive.HEADROOM + 1e-12


def test_the_top_of_the_stated_scale_is_compressed_smoothly_below_the_threshold():
    theta = 0.9
    assert adaptive.compress(0.5, theta) == 0.5 and adaptive.compress(0.8, theta) == pytest.approx(0.8)
    values = [adaptive.compress(x / 100, theta) for x in range(80, 101)]
    assert all(b > a for a, b in zip(values, values[1:])) and max(values) < theta - adaptive.HEADROOM
    assert adaptive.compress(0.95, theta) == pytest.approx(0.8 + 0.09 * 0.9296, abs=1e-3)


def test_with_k_equal_to_one_no_consistent_reading_stops_before_about_ten_questions(c, model):
    for tau in range(0, 27, 3):
        statuses, answers = noisy_path(c, model, tau, seed=900 + tau, slip=0.0)
        assert statuses[-1].done and statuses[-1].reason == "confident"
        assert len(answers) >= 10, (tau, len(answers))


def test_without_the_scaling_the_same_respondents_stop_sooner(cfg):
    off = cfg.model_copy(deep=True)
    off.scoring.adaptive = AdaptiveSettings(question_scaling=0.0)
    c_off = compile_config(off)
    c_on = compile_config(cfg)
    m_off, m_on = adaptive.Model(c_off), adaptive.Model(c_on)
    sooner = []
    for tau in range(0, 27, 3):
        sooner.append(len(noisy_path(c_off, m_off, tau, seed=900 + tau, slip=0.0)[1]) < len(noisy_path(c_on, m_on, tau, seed=900 + tau, slip=0.0)[1]))
    assert all(sooner)


def test_the_current_confidence_and_the_stopping_do_not_depend_on_the_order_the_answers_arrive_in(c, model):
    statuses, answers = noisy_path(c, model, 5, seed=3, slip=0.3)
    ids = list(answers)
    for order in (ids, ids[::-1], sorted(ids)):
        reordered = {q: answers[q] for q in order}
        a, b = adaptive.status(c, answers, model=model), adaptive.status(c, reordered, model=model)
        assert a.current_confidence == pytest.approx(b.current_confidence, abs=1e-12) and a.done == b.done and a.next_question_id == b.next_question_id


def test_a_result_states_the_current_confidence_and_the_factor_it_used(cfg, c, model):
    """The meter keeps the best so far while the Oracle asks; the result of a reading states the confidence as it stands, so it never overstates."""
    for tau, slip in ((11, 0.4), (3, 0.9)):
        statuses, answers = noisy_path(c, model, tau, seed=77 + tau, slip=slip)
        st = statuses[-1]
        ev = evaluate(cfg, answers, include_explanation=False, length="adaptive")
        assert ev.result.confidence.overall == pytest.approx(st.current_confidence, abs=1e-9)
        assert ev.result.confidence.question_factor == pytest.approx(st.question_factor, abs=1e-9)
        if st.reason == "confident":
            assert ev.result.confidence.overall == pytest.approx(st.confidence, abs=1e-9) and ev.result.confidence.overall >= st.threshold


def test_the_scaling_is_a_setting_an_administrator_can_change(client):
    rev = client.get(f"{API}/health").json()["config_revision"]
    body = {"min_questions": 1, "max_questions": 30, "confidence": 0.9, "sharpness_class": 1.0, "sharpness_spec": 0.35, "enabled": True}
    ok = client.patch(f"{API}/scoring", json={"expected_revision": rev, "adaptive": {**body, "question_scaling": 0.5}})
    assert ok.status_code == 200 and ok.json()["scoring"]["adaptive"]["question_scaling"] == 0.5
    assert client.patch(f"{API}/scoring", json={"expected_revision": rev + 1, "adaptive": {**body, "question_scaling": -1}}).status_code == 422


# ---------------------------------------------------------------------------------------------------- the opening question


def test_confidence_mode_offers_a_random_opening_from_the_personality_questions(cfg, c):
    st = adaptive.status(c, {})
    expected = [q.id for q in cfg.questions if q.min_length != "adaptive"] + CLASS_ORDER
    assert sorted(st.openers) == sorted(expected) and len(st.openers) == 54
    assert not set(st.openers) & {q.id for q in cfg.questions if q.finalists}                  # no tiebreaker, no within-class specialization question
    assert not set(st.openers) & {f"q{n}" for n in range(31, 51)}
    first = c.q_index[st.openers[0]]
    after = adaptive.status(c, {st.openers[0]: c.questions[first].answer_ids[0]})
    assert after.openers == []                                                                   # only the first question is drawn at random


def test_the_random_opening_can_be_switched_off_and_the_openers_are_not_participant_data(cfg, client):
    off = cfg.model_copy(deep=True)
    off.scoring.adaptive = AdaptiveSettings(random_opening=False)
    assert adaptive.status(compile_config(off), {}).openers == []
    quiz = client.get(f"{API}/quiz").json()
    assert not any("opener" in q or "finalists" in q for q in quiz["questions"])
    first = client.post(f"{API}/adaptive/next", json={"answers": {}}).json()
    assert len(first["openers"]) == 54 and first["next_question_id"]
    rev = client.get(f"{API}/health").json()["config_revision"]
    r = client.patch(f"{API}/questions/q01", json={"expected_revision": rev, "opener": False})
    assert r.status_code == 200 and r.json()["question"]["opener"] is False
    assert len(client.post(f"{API}/adaptive/next", json={"answers": {}}).json()["openers"]) == 53


def test_the_role_and_distance_questions_are_about_personality_not_about_roles(cfg):
    by_id = {q.id: q for q in cfg.questions}
    shown = " ".join([by_id["q49"].text, by_id["q50"].text] + [a.text for a in by_id["q49"].answers] + [a.text for a in by_id["q50"].answers]).lower()
    for word in ("tank", "heal", "damage", "dps", "healer", "ranged", "melee"):
        assert word not in shown, word
    assert by_id["q49"].type == "choice" and len(by_id["q49"].answers) == 4 and by_id["q50"].type == "scale"
    assert any("warrior/protection" in a.spec_weights for a in by_id["q49"].answers)            # the evidence is the same as before


def test_no_ordinary_question_asks_which_role_or_which_class_you_want_to_play(cfg):
    """The questions are personality questions. The tiebreakers (q75 and up) are the forced choices between finalists, and are written as such on purpose."""
    import re
    blatant = re.compile(r"\b(which role|which job|your post|tanks?|tanking|healers?|dps|damage|ranged|melee|spells?)\b")
    for q in cfg.questions:
        if q.finalists:
            continue
        shown = " ".join([q.text] + [a.text for a in q.answers]).lower()
        assert not blatant.search(shown), (q.id, blatant.search(shown).group(0))
