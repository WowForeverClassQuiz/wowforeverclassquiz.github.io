"""The confidence counts the recommended specialization fully and other specializations of its class or with a similar role partly."""
import math

import pytest

from app import adaptive
from app.models import AdaptiveSettings
from app.scoring import compile_config, evaluate
from app.seed import build_default_config

from .conftest import DRUID_ANSWERS

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


def gidx(c, class_id, spec_id):
    return next(sp.gidx for cl in c.classes if cl.id == class_id for sp in cl.specs if sp.id == spec_id)


def posterior(c, weights):
    post = [0.0] * 27
    for (class_id, spec_id), w in weights.items():
        post[gidx(c, class_id, spec_id)] = w
    return post


def test_protection_paladin_and_protection_warrior_count_as_similar_roles(c, model):
    rec = gidx(c, "paladin", "protection")
    post = posterior(c, {("paladin", "protection"): 0.4, ("warrior", "protection"): 0.4, ("priest", "holy"): 0.2})
    p = model.confidence_parts(post, rec, class_credit=0.5, role_credit=0.5)
    assert p.spec == pytest.approx(0.4) and p.class_ == pytest.approx(0.4) and p.role == pytest.approx(0.8)
    assert p.overall == pytest.approx(0.4 + 0.5 * 0.4)                  # the other tank counts half, the healer not at all


def test_the_three_specializations_of_one_class_all_gaining_raise_the_confidence(c, model):
    rec = gidx(c, "mage", "frost")
    post = posterior(c, {("mage", "frost"): 0.4, ("mage", "arcane"): 0.3, ("mage", "fire"): 0.25, ("rogue", "combat"): 0.05})
    p = model.confidence_parts(post, rec, class_credit=0.5, role_credit=0.0)
    assert p.spec == pytest.approx(0.4) and p.class_ == pytest.approx(0.95)
    assert p.overall == pytest.approx(0.4 + 0.5 * 0.55)                  # 0.675, against 0.4 for the specialization alone


def test_a_specialization_that_is_both_the_same_class_and_a_similar_role_earns_the_larger_credit_once(c, model):
    rec = gidx(c, "priest", "holy")                                      # a healer
    post = posterior(c, {("priest", "holy"): 0.5, ("priest", "discipline"): 0.5})             # another healer in the same class
    assert model.confidence_parts(post, rec, 0.3, 0.6).overall == pytest.approx(0.5 + 0.6 * 0.5)
    assert model.confidence_parts(post, rec, 0.6, 0.3).overall == pytest.approx(0.5 + 0.6 * 0.5)


def test_feral_combat_counts_as_both_a_tank_and_a_melee_damage_dealer(c, model):
    rec = gidx(c, "druid", "feral_combat")                               # melee_damage_or_tank
    post = posterior(c, {("druid", "feral_combat"): 0.2, ("warrior", "protection"): 0.3, ("rogue", "combat"): 0.3, ("mage", "fire"): 0.2})
    p = model.confidence_parts(post, rec, class_credit=0.0, role_credit=0.5)
    assert p.role == pytest.approx(0.8) and p.overall == pytest.approx(0.2 + 0.5 * 0.6)


def test_with_both_credits_at_zero_the_confidence_is_the_specializations_probability(c, model):
    rec = gidx(c, "warlock", "destruction")
    post = posterior(c, {("warlock", "destruction"): 0.35, ("warlock", "affliction"): 0.35, ("mage", "fire"): 0.3})
    p = model.confidence_parts(post, rec, 0.0, 0.0)
    assert p.overall == pytest.approx(p.spec) == pytest.approx(0.35)
    p = model.confidence_parts(post, rec, 1.0, 0.0)
    assert p.overall == pytest.approx(p.class_)                          # full class credit: the class's probability


def test_the_status_reports_the_parts_and_the_confidence_is_never_below_the_specializations_probability(c):
    answers = {}
    for _ in range(12):
        st = adaptive.status(c, answers)
        assert st.spec_probability == pytest.approx(st.recommended.probability)
        assert st.confidence >= st.spec_probability - 1e-12 and st.class_probability >= st.spec_probability - 1e-12
        assert st.role_probability >= st.spec_probability - 1e-12 and st.role and 0 <= st.confidence <= 1
        if st.done:
            break
        answers[st.next_question_id] = DRUID_ANSWERS.get(st.next_question_id) or c.questions[c.q_index[st.next_question_id]].answer_ids[0]


def test_the_credits_decide_when_confidence_mode_stops(cfg):
    """A Mage who answers like Frost, Arcane and Fire in turn is surely a Mage but not surely any one of the three: credits let the Oracle stop."""
    def questions_needed(class_credit, role_credit):
        settings = cfg.model_copy(deep=True)
        settings.scoring.adaptive = AdaptiveSettings(class_credit=class_credit, role_credit=role_credit)
        c = compile_config(settings)
        model = adaptive.Model(c)
        types = [gidx(c, "mage", s) for s in ("frost", "arcane", "fire")]
        answers = {}
        for _ in range(30):
            st = adaptive.status(c, answers, model=model)
            if st.done:
                return len(answers), st
            qi = c.q_index[st.next_question_id]
            t = types[len(answers) % 3]
            answers[st.next_question_id] = c.questions[qi].answer_ids[max(range(len(c.questions[qi].answer_ids)), key=lambda r: model.logp[qi][r][t])]
        return 30, st

    with_credit, st = questions_needed(0.5, 0.5)
    without, st_plain = questions_needed(0.0, 0.0)
    assert st.recommended.class_id == "mage"
    assert with_credit <= without and with_credit < 30


def test_a_person_torn_between_two_tanks_gets_a_confident_reading_sooner(cfg):
    """Protection Paladin and Protection Warrior are different classes with the same role: with role credit the Oracle can be sure of the role."""
    def run(class_credit, role_credit):
        settings = cfg.model_copy(deep=True)
        settings.scoring.adaptive = AdaptiveSettings(class_credit=class_credit, role_credit=role_credit)
        c = compile_config(settings)
        model = adaptive.Model(c)
        types = [gidx(c, "paladin", "protection"), gidx(c, "warrior", "protection")]
        answers = {}
        for _ in range(30):
            st = adaptive.status(c, answers, model=model)
            if st.done:
                return len(answers), st
            qi = c.q_index[st.next_question_id]
            n = len(c.questions[qi].answer_ids)
            answers[st.next_question_id] = c.questions[qi].answer_ids[max(range(n), key=lambda r: sum(model.logp[qi][r][t] for t in types))]
        return 30, st

    sooner, st = run(0.5, 0.5)
    plain, _ = run(0.0, 0.0)
    assert sooner <= plain and st.role_probability > 0.9 and "tank" in st.role


def test_evaluate_reports_the_same_parts_and_they_agree_with_the_status(cfg, c):
    ev = evaluate(cfg, DRUID_ANSWERS, include_explanation=False)
    conf = ev.result.confidence
    assert conf.role == "melee_damage_or_tank"
    assert conf.probability <= conf.overall <= 1 and conf.probability <= conf.class_probability <= 1 and conf.probability <= conf.role_probability <= 1
    strict = cfg.model_copy(deep=True)
    strict.scoring.adaptive.class_credit = strict.scoring.adaptive.role_credit = 0.0
    assert evaluate(strict, DRUID_ANSWERS, include_explanation=False).result.confidence.overall == pytest.approx(conf.probability, abs=1e-9)
    assert math.isclose(conf.probability, adaptive.model_probability(c, [(c.q_index[q], c.questions[c.q_index[q]].answer_ids.index(a)) for q, a in DRUID_ANSWERS.items()]), abs_tol=1e-9)


def test_an_administrator_can_set_the_credits_and_they_must_lie_between_zero_and_one(client):
    rev = client.get(f"{API}/health").json()["config_revision"]
    body = {"min_questions": 1, "max_questions": 30, "confidence": 0.9, "sharpness_class": 1.0, "sharpness_spec": 0.35, "enabled": True}
    ok = client.patch(f"{API}/scoring", json={"expected_revision": rev, "adaptive": {**body, "class_credit": 0.25, "role_credit": 0.75}})
    assert ok.status_code == 200 and ok.json()["scoring"]["adaptive"]["class_credit"] == 0.25 and ok.json()["scoring"]["adaptive"]["role_credit"] == 0.75
    first = client.post(f"{API}/adaptive/next", json={"answers": {}}).json()
    assert {"spec_probability", "class_probability", "role_probability", "role"} <= set(first)
    for bad in (-0.1, 1.5):
        assert client.patch(f"{API}/scoring", json={"expected_revision": rev + 1, "adaptive": {**body, "class_credit": bad}}).status_code == 422
