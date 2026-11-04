"""Tiebreaker questions (q75 to q103): forced choices between the finalists, asked only when the finalists hold most of the probability."""
import shutil
from itertools import combinations
from math import exp, fsum

import pytest

from app import adaptive
from app.models import AdaptiveSettings
from app.scoring import compile_config
from app.seed import build_default_config
from app.seed_tiebreakers import TIEBREAKERS
from app.static_export import export_static_data

from .test_adaptive import close
from .test_static_parity import run_node

API = "/api/v1"
NODE = shutil.which("node")
IDS = [t[0] for t in TIEBREAKERS]


@pytest.fixture(scope="module")
def cfg():
    return build_default_config()


@pytest.fixture(scope="module")
def c(cfg):
    return compile_config(cfg)


@pytest.fixture(scope="module")
def model(c):
    return adaptive.Model(c)


def spec_index(c, key):
    return c.spec_keys.index(key)


def concentrate(c, weights):
    post = [0.0] * len(c.spec_keys)
    for key, w in weights.items():
        post[spec_index(c, key)] = w
    return post


def test_there_are_seventeen_three_way_and_twelve_two_way_tiebreakers_and_only_confidence_mode_asks_them(cfg):
    tb = [q for q in cfg.questions if q.finalists]
    assert [q.id for q in tb] == IDS == [f"q{n}" for n in range(75, 104)]
    assert [len(q.finalists) for q in tb] == [3] * 17 + [2] * 12
    assert all(q.min_length == "adaptive" and q.type == "choice" and q.rationale for q in tb)


def test_every_answer_names_exactly_one_finalist_and_every_finalist_has_an_answer(cfg):
    keys = {f"{cl.id}/{sp.id}" for cl in cfg.classes for sp in cl.specializations}
    for q in cfg.questions:
        if not q.finalists:
            continue
        assert len(q.answers) == len(q.finalists) == len(set(q.finalists)) and set(q.finalists) <= keys, q.id
        for answer, finalist in zip(q.answers, q.finalists):
            assert answer.spec_weights == {finalist: 2.0}, (q.id, answer.id)
            assert max(answer.class_weights, key=answer.class_weights.get) == finalist.split("/")[0], (q.id, answer.id)
            assert sorted(answer.class_weights.values()) == [1.0, 2.0] and len(answer.trait_weights) == 2


def test_the_examples_you_would_expect_are_there(cfg):
    by_id = {q.id: q for q in cfg.questions}
    assert set(by_id["q84"].finalists) == {"paladin/protection", "warrior/protection", "druid/feral_combat"}           # the three tanks
    assert set(by_id["q78"].finalists) == {"paladin/retribution", "paladin/protection", "paladin/holy"}              # the paladin
    assert "retribution" in by_id["q78"].text and "forgiveness" in by_id["q78"].text and "steel" in by_id["q84"].text
    assert set(by_id["q92"].finalists) == {"paladin/retribution", "warrior/protection"}                                # a two-way pair


def test_no_tiebreaker_is_asked_before_the_finalists_hold_most_of_the_probability(c, model):
    flat = [1 / 27] * 27
    assert not any(model.eligible(flat, c.q_index[qid], 0.8) for qid in IDS)
    st = adaptive.status(c, {})
    assert st.next_question_id not in IDS


def test_a_tiebreaker_becomes_eligible_when_its_finalists_hold_the_probability(c, model):
    tanks = concentrate(c, {"paladin/protection": 0.3, "warrior/protection": 0.3, "druid/feral_combat": 0.3, "mage/fire": 0.1})
    assert model.eligible(tanks, c.q_index["q84"], 0.8) and not model.eligible(tanks, c.q_index["q78"], 0.8)
    assert not model.eligible(tanks, c.q_index["q84"], 0.95)                      # the share is a setting
    assert model.eligible(tanks, c.q_index["q01"], 0.99)                          # an ordinary question is always a candidate


def test_two_of_three_finalists_are_enough_and_so_is_a_two_way_question_for_the_top_two(c, model):
    two_tanks = concentrate(c, {"paladin/protection": 0.45, "warrior/protection": 0.45, "mage/fire": 0.1})
    assert model.eligible(two_tanks, c.q_index["q84"], 0.8)                       # the three-way tanks question serves the top two
    assert model.eligible(two_tanks, c.q_index["q92"], 0.8) is False             # q92 is Retribution against Protection Warrior: not these two
    pair = concentrate(c, {"paladin/retribution": 0.5, "warrior/protection": 0.4, "mage/fire": 0.1})
    assert model.eligible(pair, c.q_index["q92"], 0.8)


def test_the_status_never_offers_an_ineligible_tiebreaker_and_the_threshold_is_a_setting(cfg, c, model):
    seen = set()
    for tau in range(0, 27, 2):
        answers = {}
        for _ in range(12):
            st = adaptive.status(c, answers, model=model)
            if st.done:
                break
            nxt = st.next_question_id
            if nxt in IDS:
                picks = [(c.q_index[q], c.questions[c.q_index[q]].answer_ids.index(a)) for q, a in answers.items()]
                post = model.posterior(picks)
                assert fsum(post[g] for g in c.questions[c.q_index[nxt]].finalists) >= 0.8, nxt
                seen.add(nxt)
            qi = c.q_index[nxt]
            n = len(c.questions[qi].answer_ids)
            answers[nxt] = c.questions[qi].answer_ids[max(range(n), key=lambda r: model.logp[qi][r][tau])]
    assert seen, "no tiebreaker was ever asked"
    never = cfg.model_copy(deep=True)
    never.scoring.adaptive = AdaptiveSettings(tiebreak_mass=1.0)
    c2 = compile_config(never)
    assert not any(c2.questions[c2.q_index[q]].finalists and adaptive.status(c2, {}).next_question_id == q for q in IDS)


def test_a_person_torn_between_two_tanks_is_asked_the_tank_question(cfg):
    """Blend Protection Paladin and Protection Warrior; with both credits at zero the Oracle needs a decision, and asks q84 or q92."""
    strict = cfg.model_copy(deep=True)
    strict.scoring.adaptive = AdaptiveSettings(class_credit=0.0, role_credit=0.0)
    c = compile_config(strict)
    model = adaptive.Model(c)
    types = [spec_index(c, "paladin/protection"), spec_index(c, "warrior/protection")]
    answers, asked = {}, []
    for _ in range(30):
        st = adaptive.status(c, answers, model=model)
        if st.done:
            break
        asked.append(st.next_question_id)
        qi = c.q_index[st.next_question_id]
        n = len(c.questions[qi].answer_ids)
        answers[st.next_question_id] = c.questions[qi].answer_ids[max(range(n), key=lambda r: sum(model.logp[qi][r][t] for t in types))]
    assert "q84" in asked or any(c.questions[c.q_index[q]].finalists and set(c.questions[c.q_index[q]].finalists) >= set(types) for q in asked), asked


def _sym_kl(model, qi, a, b):
    """Symmetric Kullback-Leibler divergence (nats) between how types a and b answer question qi."""
    return fsum(exp(r[a]) * (r[a] - r[b]) + exp(r[b]) * (r[b] - r[a]) for r in model.logp[qi])


def test_a_forced_choice_carries_somewhat_more_evidence_but_not_a_lot_more_than_the_comparable_questions(c, model):
    """With only two or three answers each answer is sharper, so a tiebreaker separates its finalists better than a four-way question does.

    The comparable questions are the nine three-answer questions about one class (q31, q33, ... q47), measured between that class's specializations."""
    def between(qi, specs):
        pairs = list(combinations(specs, 2))
        return fsum(_sym_kl(model, qi, a, b) for a, b in pairs) / len(pairs)

    baseline = []
    for qid in ("q31", "q33", "q35", "q37", "q39", "q41", "q43", "q45", "q47"):
        qi = c.q_index[qid]
        ci = max(range(9), key=lambda i: min(r[i] for r in c.questions[qi].class_raw))      # the class every answer favours
        baseline.append(between(qi, [g for g in range(model.n_types) if model.type_class[g] == ci]))
    tiebreakers = [between(i, list(q.finalists)) for i, q in enumerate(c.questions) if q.finalists]
    assert max(tiebreakers) <= 1.5 * max(baseline) and fsum(tiebreakers) / len(tiebreakers) <= 1.5 * fsum(baseline) / len(baseline)


def test_finalists_are_stored_changed_and_validated_through_the_api(client):
    cfg = client.get(f"{API}/config").json()
    assert next(q for q in cfg["questions"] if q["id"] == "q84")["finalists"] == ["paladin/protection", "warrior/protection", "druid/feral_combat"]
    quiz = client.get(f"{API}/quiz").json()
    assert not any("finalists" in q for q in quiz["questions"])               # which specializations a question settles is not participant data
    rev = cfg["revision"]
    r = client.patch(f"{API}/questions/q84", json={"expected_revision": rev, "finalists": ["paladin/protection", "warrior/protection"]})
    assert r.status_code == 200 and r.json()["question"]["finalists"] == ["paladin/protection", "warrior/protection"]
    bad = client.patch(f"{API}/questions/q84", json={"expected_revision": rev + 1, "finalists": ["paladin/protection", "mage/nonsense"]})
    assert bad.status_code in (400, 422)
    one = client.patch(f"{API}/questions/q84", json={"expected_revision": rev + 1, "finalists": ["paladin/protection"]})
    assert one.status_code == 400 and any("at least two" in e for e in one.json()["detail"]["errors"])
    cleared = client.patch(f"{API}/questions/q84", json={"expected_revision": rev + 1, "finalists": []})
    assert cleared.status_code == 200 and cleared.json()["question"]["finalists"] == []


def test_finalists_survive_a_restart_of_the_database(tmp_path):
    from app.repository import Repository
    repo = Repository(tmp_path / "t.db")
    repo.initialize()
    again = Repository(tmp_path / "t.db")
    again.initialize()
    assert next(q for q in again.get_config().questions if q.id == "q92").finalists == ["paladin/retribution", "warrior/protection"]


def tiebreak_paths(cfg):
    """Answer sets that reach tiebreakers: respondents who answer like one type, and like a blend of two, along the adaptive order."""
    c = compile_config(cfg)
    model = adaptive.Model(c)
    blends = [("paladin/protection", "warrior/protection"), ("mage/fire", "warlock/destruction"), ("priest/holy", "paladin/holy"), ("rogue/combat", "warrior/fury")]
    out = []
    for pair in blends:
        types = [spec_index(c, k) for k in pair]
        answers, steps = {}, [{}]
        for _ in range(30):
            st = adaptive.status(c, answers, model=model)
            if st.done:
                break
            qi = c.q_index[st.next_question_id]
            n = len(c.questions[qi].answer_ids)
            answers = {**answers, st.next_question_id: c.questions[qi].answer_ids[max(range(n), key=lambda r: sum(model.logp[qi][r][t] for t in types))]}
            steps.append(dict(answers))
        out.append(steps)
    return out


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("name", ["seed", "edited"])
def test_the_browser_engine_chooses_the_same_questions_including_tiebreakers(name):
    from .test_static_parity import CONFIGS
    cfg = CONFIGS[name]()
    c = compile_config(cfg)
    flat = [a for steps in tiebreak_paths(cfg) for a in steps]
    got = run_node({"paths": [{"data": export_static_data(cfg), "answers": flat}]})["paths"][0]
    asked = set()
    for answers, js in zip(flat, got):
        py = adaptive.status(c, answers).model_dump(mode="json", exclude_none=True)
        close(py, js)
        asked.add(py.get("next_question_id"))
    if name == "seed":
        assert asked & set(IDS)
