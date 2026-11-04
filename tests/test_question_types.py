"""Scale (1-10), pick-two and binary questions, direct specialization weights, the question expansion
endpoint, reachability of all 27 specializations, and upgrading databases created by the first release."""
import random
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import scoring
from app.database import connect, init_schema
from app.main import create_app
from app.models import Answer, AnswerOverride, Question
from app.repository import Repository, _insert_revision, _write_config
from app.scoring import (
    UnknownAnswerError,
    _class_order,
    _class_totals,
    _spec_order,
    _spec_scores,
    _spec_totals,
    _trait_totals,
    compile_config,
    evaluate,
    expand_question,
)
from app.seed import build_default_config

from .conftest import DRUID_ANSWERS

API = "/api/v1"


def scale_question(agree=None, disagree=None, agree_specs=None, disagree_specs=None):
    return Question(
        id="qx", text="Statement", type="scale",
        answers=[
            Answer(id="agree", text="agree pole", class_weights=agree or {"druid": 2.0}, spec_weights=agree_specs or {}),
            Answer(id="disagree", text="disagree pole", class_weights=disagree or {"mage": 2.0}, spec_weights=disagree_specs or {}),
        ],
    )


# ------------------------------------------------------------------ scale


def test_scale_ratings_blend_the_two_poles_by_distance_from_the_middle(config):
    ex = expand_question(config, scale_question())
    by = {o.id: o for o in ex.options}
    assert [o.id for o in ex.options] == [str(r) for r in range(1, 11)]
    assert by["10"].class_raw == {"druid": 2.0} and by["1"].class_raw == {"mage": 2.0}      # the extremes are the pure poles
    assert by["6"].class_raw["druid"] == pytest.approx(2 * (0.5 / 4.5)) and "mage" not in by["6"].class_raw
    assert by["5"].class_raw["mage"] == pytest.approx(2 * (0.5 / 4.5)) and "druid" not in by["5"].class_raw
    for r in range(1, 6):                                                                   # r and 11 - r mirror each other
        assert by[str(r)].class_raw.get("mage", 0) == pytest.approx(by[str(11 - r)].class_raw.get("druid", 0))


def test_scale_baseline_is_the_mean_over_all_ten_ratings_so_the_expected_contribution_is_zero(config):
    ex = expand_question(config, scale_question())
    mean_pos = sum(max((r - 5.5) / 4.5, 0) for r in range(1, 11)) / 10
    assert ex.class_baseline["druid"] == pytest.approx(2 * mean_pos, abs=1e-8)
    assert sum(o.class_adjusted.get("druid", 0) for o in ex.options) == pytest.approx(0.0, abs=1e-8)
    assert sum(o.class_adjusted.get("mage", 0) for o in ex.options) == pytest.approx(0.0, abs=1e-8)


def test_strong_disagreement_counts_for_the_disagree_pole_not_nothing(config):
    cfg = config.model_copy(deep=True)
    cfg.questions = [scale_question()]
    cfg.quiz.expected_question_count = 1
    high = evaluate(cfg, {"qx": "10"}).rankings.classes
    low = evaluate(cfg, {"qx": "1"}).rankings.classes
    score = lambda rows, cid: next(r.score for r in rows if r.id == cid)
    assert score(high, "druid") > 0 > score(high, "mage")
    assert score(low, "mage") > 0 > score(low, "druid")
    assert score(high, "druid") == pytest.approx(score(low, "mage"))


def test_scale_answers_must_be_whole_ratings_from_one_to_ten(config, druid_answers):
    for bad in ("0", "11", "5.5", "agree", "", " 5"):
        with pytest.raises(UnknownAnswerError):
            evaluate(config, {**druid_answers, "q17": bad})
    assert evaluate(config, {**druid_answers, "q17": "10"}).metadata.complete


# ------------------------------------------------------------------ pick two


def test_pick_two_adds_the_two_items_and_averages_over_all_six_pairs(config):
    q = config.get_question("q25")
    ex = expand_question(config, q)
    assert [o.id for o in ex.options] == ["a+b", "a+c", "a+d", "b+c", "b+d", "c+d"]
    item = {a.id: a for a in q.answers}
    ab = next(o for o in ex.options if o.id == "a+b")
    assert ab.class_raw["paladin"] == item["a"].class_weights["paladin"]                     # item a's paladin weight
    assert ab.class_raw["druid"] == item["b"].class_weights["druid"]                          # item b's druid weight
    # paladin appears only in item a, which is in 3 of the 6 pairs: baseline = w * 3 / 6 = w / 2
    w = item["a"].class_weights["paladin"]
    assert ex.class_baseline["paladin"] == pytest.approx(w / 2)
    assert ab.class_adjusted["paladin"] == pytest.approx(w / 2)                               # chosen with item a: +w/2
    assert next(o for o in ex.options if o.id == "b+c").class_adjusted["paladin"] == pytest.approx(-w / 2)


def test_pick_two_accepts_either_order_and_rejects_everything_else(config, druid_answers):
    forward = evaluate(config, {**druid_answers, "q25": "a+c"})
    backward = evaluate(config, {**druid_answers, "q25": "c+a"})
    assert forward.model_dump() == backward.model_dump()
    for bad in ("a", "a+a", "a+z", "a+b+c", "ab", "a,b", ""):
        with pytest.raises(UnknownAnswerError):
            evaluate(config, {**druid_answers, "q25": bad})


def test_binary_choice_questions_work_like_any_other_choice(config):
    q = config.get_question("q28")
    assert len(q.answers) == 2
    ex = expand_question(config, q)
    assert [o.id for o in ex.options] == ["a", "b"]
    assert sum(ex.options[0].class_adjusted.get(c, 0) for c in ("priest", "paladin", "rogue", "warrior")) == pytest.approx(0.0, abs=1e-8)


# ------------------------------------------------------------------ direct specialization weights


def test_direct_weights_move_the_specialization_score_by_multiplier_times_the_baseline_subtracted_weight(config):
    cfg = config.model_copy(deep=True)
    cfg.questions = [scale_question(agree={"druid": 2.0}, agree_specs={"druid/balance": 2.0})]
    cfg.quiz.expected_question_count = 1
    cfg.scoring.spec_weight_multiplier = 3.0
    row = lambda ev: next(r for r in ev.rankings.all_specializations if (r.class_id, r.id) == ("druid", "balance"))
    mean_pos = sum(max((r - 5.5) / 4.5, 0) for r in range(1, 11)) / 10
    ev = evaluate(cfg, {"qx": "10"})
    assert row(ev).direct_score == pytest.approx(3.0 * (2.0 - 2.0 * mean_pos), abs=1e-6)
    assert row(evaluate(cfg, {"qx": "1"})).direct_score == pytest.approx(3.0 * (0.0 - 2.0 * mean_pos), abs=1e-6)
    cfg.scoring.spec_weight_multiplier = 0.0
    assert row(evaluate(cfg, {"qx": "10"})).direct_score == 0.0


def test_direct_weights_can_change_the_recommended_specialization(config, druid_answers):
    base = evaluate(config, druid_answers)
    assert base.result.primary_specialization.id == "feral_combat"
    boost = AnswerOverride(question_id="q22", answer_id="agree", spec_weights={"druid/restoration": 40.0})
    sim = scoring.simulate(config, druid_answers, [boost])
    assert sim.simulated_primary.class_id == "druid" and sim.simulated_primary.specialization_id == "restoration"
    assert sim.winning_specialization_changed and not sim.winning_class_changed


# ------------------------------------------------------------------ every specialization is reachable


def _reach(config, ci, si, restarts=3, seed=0):
    """Hill-climb a coherent answer set toward making (class ci, spec si) the recommendation."""
    c = compile_config(config)
    sizes = [len(q.answer_ids) for q in c.questions]
    spec_g = c.classes[ci].specs[si].gidx

    def objective(picks):
        ct, tt, st = _class_totals(c, picks), _trait_totals(c, picks), _spec_totals(c, picks)
        sc = _spec_scores(c, ci, tt, st)
        return (ct[ci] - max(ct[i] for i in range(c.n_classes) if i != ci)) + 0.5 * (sc[si] - max(x for j, x in enumerate(sc) if j != si))

    best = None
    for r in range(restarts):
        rng = random.Random(seed + r)
        picks = [(qi, rng.randrange(n)) for qi, n in enumerate(sizes)]
        for _ in range(3):
            for qi, n in enumerate(sizes):
                picks[qi] = (qi, max(range(n), key=lambda ai: objective(picks[:qi] + [(qi, ai)] + picks[qi + 1:])))
        ct, tt, st = _class_totals(c, picks), _trait_totals(c, picks), _spec_totals(c, picks)
        sc = _spec_scores(c, ci, tt, st)
        won = _class_order(c, ct)[0] == ci and _spec_order(sc)[0] == si
        if best is None or won:
            best = (won, {c.questions[qi].id: c.questions[qi].answer_ids[ai] for qi, ai in picks})
        if won:
            break
    return best


def test_every_one_of_the_27_specializations_can_be_the_recommendation(config):
    unreachable = []
    for ci, cls in enumerate(config.classes):
        for si, spec in enumerate(cls.specializations):
            won, answers = _reach(config, ci, si)
            if won:
                ev = evaluate(config, answers)      # confirm with the real engine as well as the search's own arithmetic
                won = (ev.result.primary_class.id, ev.result.primary_specialization.id) == (cls.id, spec.id)
            if not won:
                unreachable.append(f"{cls.id}/{spec.id}")
    assert unreachable == []


# ------------------------------------------------------------------ the expansion endpoint


def admin_client(db_path):
    return TestClient(create_app(db_path))


def test_expansion_endpoint_matches_the_engine_for_saved_and_unsaved_questions(client):
    cfg = client.get(f"{API}/config").json()
    q = next(x for x in cfg["questions"] if x["id"] == "q19")
    r = client.post(f"{API}/questions/expand", json={"question": q})
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "scale" and len(body["options"]) == 10
    assert body["class_baseline"]["warlock"] > 0 and body["spec_baseline"]
    # an unsaved edit is reflected immediately
    q["answers"][0]["class_weights"] = {"druid": 5.0}
    edited = client.post(f"{API}/questions/expand", json={"question": q}).json()
    assert edited["options"][-1]["class_raw"] == {"druid": 5.0}
    # the saved configuration is untouched
    assert client.get(f"{API}/config").json()["revision"] == 1


def test_expansion_rejects_malformed_questions(client):
    bad_scale = {"id": "qx", "text": "x", "type": "scale", "answers": [{"id": "a", "text": "a"}, {"id": "b", "text": "b"}]}
    assert client.post(f"{API}/questions/expand", json={"question": bad_scale}).status_code == 400
    unknown = {"id": "qx", "text": "x", "type": "choice", "answers": [
        {"id": "a", "text": "a", "spec_weights": {"druid/nonsense": 1}}, {"id": "b", "text": "b"}]}
    assert client.post(f"{API}/questions/expand", json={"question": unknown}).status_code == 400
    negative = {"id": "qx", "text": "x", "type": "choice", "answers": [
        {"id": "a", "text": "a", "class_weights": {"druid": -1}}, {"id": "b", "text": "b"}]}
    assert client.post(f"{API}/questions/expand", json={"question": negative}).status_code == 422


# ------------------------------------------------------------------ editing the new fields


def test_spec_weights_and_question_labels_can_be_edited_and_persist(db_path):
    client = admin_client(db_path)
    r = client.patch(f"{API}/questions/q17/answers/agree", json={"expected_revision": 1, "spec_weights": {"warrior/fury": 1.5}})
    assert r.status_code == 200 and r.json()["answer"]["spec_weights"] == {"warrior/fury": 1.5}
    bad = client.patch(f"{API}/questions/q17/answers/agree", json={"expected_revision": 2, "spec_weights": {"warrior/nope": 1}})
    assert bad.status_code == 400
    assert client.patch(f"{API}/questions/q17/answers/agree", json={"expected_revision": 2, "spec_weights": {"warrior": 1}}).status_code == 422
    r = client.patch(f"{API}/questions/q17", json={"expected_revision": 2, "low_label": "Never", "high_label": "Always", "rationale": "edited"})
    assert r.status_code == 200 and r.json()["question"]["low_label"] == "Never"
    reopened = TestClient(create_app(db_path))
    q = next(x for x in reopened.get(f"{API}/config").json()["questions"] if x["id"] == "q17")
    assert q["high_label"] == "Always" and q["rationale"] == "edited" and q["answers"][0]["spec_weights"] == {"warrior/fury": 1.5}
    pub = next(x for x in reopened.get(f"{API}/quiz").json()["questions"] if x["id"] == "q17")
    assert (pub["low_label"], pub["high_label"]) == ("Never", "Always")


def test_class_and_specialization_overviews_can_be_edited_and_reach_the_result(client, druid_answers):
    assert client.patch(f"{API}/classes/druid", json={"expected_revision": 1, "overview": "Class text."}).status_code == 200
    assert client.patch(f"{API}/classes/druid/specs/feral_combat", json={"expected_revision": 2, "overview": "Spec text."}).status_code == 200
    result = client.post(f"{API}/evaluate", json={"answers": druid_answers}).json()["result"]
    assert result["class_overview"] == "Class text." and result["specialization_overview"] == "Spec text."


def test_every_class_and_specialization_has_an_overview_and_a_source_link(config):
    for cls in config.classes:
        assert len(cls.overview) > 80 and cls.overview_url == f"https://worldofwarcraft.blizzard.com/en-us/game/classes/{cls.id}", cls.id
        for spec in cls.specializations:
            assert len(spec.overview) > 40, (cls.id, spec.id)


def test_overviews_are_summaries_not_copies_of_blizzards_wording(config):
    """Blizzard's class pages are copyrighted. The paragraphs are original; fail on any run of five words they share with
    the official descriptions that were read when writing them (as relayed, lower-cased, punctuation removed)."""
    official = [
        "wilderness adventurers who leave civilization for the wild and become skilled trackers",
        "scholars of arcane power who train with intellect and discipline",
        "holy warriors who defend the weak pursue justice and fight evil",
        "paid mercenaries with no moral code strike from hiding open with surprise melee attacks and build combo points",
        "spiritual guides who work with the elements rather than gods keep the chaotic warring elements in balance using totems",
        "dark spellcasters who gain power through forbidden magic and demonic servants",
        "heavily armored melee fighter who charges into combat and can serve as either a tank or a damage dealer build their power from rage",
        "devoted spiritual figures who leave their temples to support allies",
        "a seasoned weapon master who relies on mobility and heavy crushing blows",
        "a steadfast defender who uses a shield to guard themselves and their allies",
        "a wild berserker who fights with two weapons at once unleashing rapid strikes to overwhelm foes",
        "shields allies from harm and heals them by damaging enemies",
        "totem empowered melee fighters who imbue their weapons with fire wind or ice",
        "spellcasters who wield natures destructive forces such as lightning earthquakes and lava",
        "a poison using killer who relies on quick deadly dagger strikes",
        "a shadow stalker who ambushes unsuspecting targets",
        "freezes foes in place and then shatters them",
        "a wild tamer who befriends many kinds of beasts and fights alongside them",
        "a long distance sharpshooter who takes down enemies from afar",
    ]
    norm = lambda t: __import__("re").sub(r"[^a-z ]", "", t.lower().replace("-", " ")).split()
    grams = lambda words, n=5: {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}
    banned = set().union(*(grams(norm(o)) for o in official))
    for cls in config.classes:
        for label, text in [(cls.id, cls.overview)] + [(f"{cls.id}/{sp.id}", sp.overview) for sp in cls.specializations]:
            shared = grams(norm(text)) & banned
            assert not shared, (label, sorted(shared)[:3])


# ------------------------------------------------------------------ databases from the first release


def make_old_database(path, edited=False):
    """Recreate what a first-release database looked like: sixteen questions, no new tables or columns."""
    from app.seed import QUESTIONS, _weights
    old = build_default_config()
    old.questions = [   # the first release's sixteen questions exactly as originally written: all choice, no direct spec weights
        Question(id=qid, text=text, answers=[Answer(id=aid, text=atext, class_weights=_weights(cl), trait_weights=_weights(tr))
                                             for aid, atext, cl, tr in answers])
        for qid, text, answers in QUESTIONS
    ]
    old.quiz.expected_question_count = 16
    old.scoring.algorithm_version = "1.0.0"
    old.scoring.spec_weight_multiplier = 1.0
    for cls in old.classes:
        cls.overview, cls.overview_url = "", ""
        for spec in cls.specializations:
            spec.overview = ""
    conn = connect(path)
    try:
        init_schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        _write_config(conn, old)
        _insert_revision(conn, old, "seed", "Initial seed configuration", None)
        if edited:
            old.revision = 2
            _write_config(conn, old)
            _insert_revision(conn, old, "answer", "Edited answer q01/a", None)
        conn.execute("COMMIT")
        for table, column in (("questions", "type"), ("questions", "low_label"), ("questions", "high_label"), ("questions", "rationale"),
                              ("classes", "overview"), ("classes", "overview_url"), ("specializations", "overview")):
            conn.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
        conn.execute("DROP TABLE answer_spec_weights")
    finally:
        conn.close()


def columns(path, table):
    conn = sqlite3.connect(path)
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def test_an_untouched_first_release_database_is_upgraded_to_the_new_seed(tmp_path):
    db = tmp_path / "old.db"
    make_old_database(db)
    assert "type" not in columns(db, "questions")
    repo = Repository(db)
    repo.initialize()
    assert {"type", "low_label", "high_label", "rationale"} <= columns(db, "questions")
    cfg = repo.get_config()
    assert cfg.revision == 1 and len(cfg.questions) == 30 and cfg.quiz.expected_question_count == 30
    assert cfg.scoring.algorithm_version == "1.4.0" and cfg.classes[0].overview
    assert repo.history()[0]["change_description"].startswith("Initial seed configuration (upgraded")
    client = TestClient(create_app(db))
    assert client.post(f"{API}/evaluate", json={"answers": DRUID_ANSWERS}).status_code == 200


def test_an_edited_first_release_database_keeps_its_content_and_still_works(tmp_path):
    db = tmp_path / "old.db"
    make_old_database(db, edited=True)
    repo = Repository(db)
    repo.initialize()
    cfg = repo.get_config()
    assert cfg.revision == 2 and len(cfg.questions) == 16 and cfg.quiz.expected_question_count == 16   # never rewritten silently
    assert all(q.type == "choice" for q in cfg.questions)
    client = TestClient(create_app(db))
    sixteen = dict(zip([f"q{i:02d}" for i in range(1, 17)], "acbadabcaabdacac"))   # the first release's answer letters
    ev = client.post(f"{API}/evaluate", json={"answers": sixteen}).json()
    assert ev["result"]["primary_class"]["id"] == "druid" and ev["metadata"]["total_questions"] == 16
    # Reset adopts the new seed (a backup is written first) and the history keeps the old revisions
    r = client.post(f"{API}/config/reset", json={"expected_revision": 2, "confirm": True})
    assert r.status_code == 200 and len(client.get(f"{API}/quiz").json()["questions"]) == 30
