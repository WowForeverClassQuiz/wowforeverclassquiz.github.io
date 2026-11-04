"""API integration tests (FastAPI TestClient against a temporary SQLite file)."""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.seed import build_default_config

from .conftest import first_answers

API = "/api/v1"


def rev(client):
    return client.get(f"{API}/health").json()["config_revision"]


def evaluate(client, answers, **extra):
    return client.post(f"{API}/evaluate", json={"answers": answers, **extra})


def druid_score(client, answers):
    r = evaluate(client, answers, include_explanation=True)
    assert r.status_code == 200, r.text
    return next(c["score"] for c in r.json()["rankings"]["classes"] if c["id"] == "druid")


# ------------------------------------------------------------------ participant


def test_quiz_endpoint_does_not_reveal_scoring_data(client):
    r = client.get(f"{API}/quiz")
    assert r.status_code == 200
    body = r.json()
    assert body["question_count"] == 30 and len(body["questions"]) == 30
    by_type = {}
    for q in body["questions"]:
        by_type.setdefault(q["type"], []).append(q)
    assert {k: len(v) for k, v in by_type.items()} == {"choice": 14, "scale": 8, "pick_two": 2, "ranking": 3, "allocation": 3}
    assert all(len(q["answers"]) == 4 for q in by_type["pick_two"]) and all(q["pick_count"] == 2 for q in by_type["pick_two"])
    assert all(len(q["answers"]) == 4 and q["points"] is None for q in by_type["ranking"])
    assert all(len(q["answers"]) == 4 and q["points"] == 6 for q in by_type["allocation"])
    assert sum(1 for q in by_type["choice"] if len(q["answers"]) == 4) == 11 and sum(1 for q in by_type["choice"] if len(q["answers"]) == 2) == 3
    for q in by_type["scale"]:                       # the agree/disagree poles are scoring data and are never sent
        assert q["answers"] == [] and q["scale_min"] == 1 and q["scale_max"] == 10 and q["low_label"] and q["high_label"]
    blob = json.dumps(body)
    for forbidden in ("weight", "class_weights", "trait_weights", "spec_weights", "druid", "scholar", "multiplier", "rationale",
                      "Takes the lead and holds the line", "Plans first", "Lone wolf"):    # pole descriptions are administrator notes
        assert forbidden not in blob, forbidden
    assert not any(a["id"] in ("agree", "disagree") for q in body["questions"] for a in q["answers"])
    assert set(body["questions"][0]["answers"][0]) == {"id", "text"}


def test_classes_endpoint_lists_nine_classes_and_27_specs(client):
    body = client.get(f"{API}/classes").json()
    assert len(body["classes"]) == 9
    assert sum(len(c["specializations"]) for c in body["classes"]) == 27
    druid = body["classes"][0]
    assert druid["id"] == "druid"
    assert [(s["id"], s["role"]) for s in druid["specializations"]] == [
        ("balance", "ranged_damage"), ("feral_combat", "melee_damage_or_tank"), ("restoration", "healer"),
    ]
    assert "trait_multipliers" not in druid["specializations"][0]  # include_scores defaults to false
    assert druid["specializations"][0]["builds"]  # include_builds defaults to true
    scored = client.get(f"{API}/classes?include_scores=true&include_builds=false").json()["classes"][0]
    assert scored["specializations"][0]["trait_multipliers"] == {"scholar": 1.5, "wild": 1.0, "focus": 0.45}
    assert "builds" not in scored["specializations"][0]


def test_evaluate_returns_the_documented_structure(client, druid_answers):
    r = evaluate(client, druid_answers, include_explanation=True)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"result", "alternatives", "rankings", "explanation", "metadata"}
    assert body["result"]["primary_class"]["id"] == "druid"
    assert body["result"]["primary_specialization"]["id"] == "feral_combat"
    assert body["result"]["personality_interpretation"] and body["result"]["specialization_interpretation"]
    assert len(body["rankings"]["classes"]) == 9 and len(body["rankings"]["traits"]) == 12
    assert len(body["rankings"]["specializations"]) == 3
    assert len(body["explanation"]["questions"]) == 30
    assert {q["question_type"] for q in body["explanation"]["questions"]} == {"choice", "scale", "pick_two", "ranking", "allocation"}
    assert body["alternatives"]["alternative_class"]["id"]
    assert body["metadata"]["config_revision"] == 1 and body["metadata"]["spec_weight_multiplier"] == 5.0
    assert body["metadata"]["complete"] is True
    assert body["result"]["build"]["status"] == "draft" and body["result"]["build"]["trees"]
    # the "what the class does" paragraphs and their source link travel with the result
    assert body["result"]["class_overview"].startswith("Druids are") and "Feral Combat" not in body["result"]["class_overview"][:0]
    assert "cat" in body["result"]["specialization_overview"]
    assert body["result"]["overview_url"] == "https://worldofwarcraft.blizzard.com/en-us/game/classes/druid"
    # scores are plain numbers, never percentages
    assert all(isinstance(c["score"], (int, float)) for c in body["rankings"]["classes"])


def test_evaluate_without_explanation_omits_it(client, druid_answers):
    body = evaluate(client, druid_answers).json()
    assert "explanation" not in body


def test_final_result_requires_all_thirty_answers(client, druid_answers):
    partial = {k: v for k, v in list(druid_answers.items())[:5]}
    r = evaluate(client, partial)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "incomplete_assessment"
    assert len(r.json()["detail"]["missing_questions"]) == 25
    ok = evaluate(client, partial, allow_partial=True)
    assert ok.status_code == 200 and ok.json()["metadata"]["provisional"] is True


@pytest.mark.parametrize(
    "answers",
    [{"q99": "a"}, {"q01": "z"}, {"q17": "11"}, {"q17": "0"}, {"q17": "agree"}, {"q25": "a"}, {"q25": "a+a"}, {"q25": "a+z"}, {"q25": "a+b+c"}],
)
def test_evaluate_rejects_unknown_identifiers(client, answers):
    r = evaluate(client, answers, allow_partial=True)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "invalid_request"


# ------------------------------------------------------------------ admin config


def test_config_endpoint_returns_complete_scoring_data(client):
    cfg = client.get(f"{API}/config").json()
    assert cfg["revision"] == 1
    assert len(cfg["questions"]) == 30 and len(cfg["classes"]) == 9 and len(cfg["traits"]) == 12
    answer = cfg["questions"][0]["answers"][0]
    assert answer == {
        "id": "a",
        "text": "The conservatory, filled with plants from distant countries.",
        "class_weights": {"druid": 2.0, "hunter": 1.0},
        "trait_weights": {"wild": 2.0, "healer": 1.0},
        "spec_weights": {"druid/restoration": 2.0},
    }
    scale = next(q for q in cfg["questions"] if q["id"] == "q17")
    assert scale["type"] == "scale" and [a["id"] for a in scale["answers"]] == ["agree", "disagree"]
    assert scale["answers"][0]["spec_weights"] == {"warrior/protection": 2.0, "paladin/protection": 1.0}
    assert scale["rationale"]
    assert cfg["scoring"]["spec_weight_multiplier"] == 5.0 and cfg["scoring"]["algorithm_version"] == "1.4.0"
    assert cfg["classes"][0]["overview"] and cfg["classes"][0]["specializations"][0]["overview"]
    assert cfg["classes"][0]["specializations"][1]["trait_multipliers"] == {"wild": 1.5, "instinct": 1.0, "freedom": 0.45}
    assert cfg["scoring"]["class_tie_break_order"][0] == "druid"
    assert len(cfg["builds"]) == 27


def test_admin_can_modify_a_weight_and_scores_change_as_expected(client, druid_answers):
    before = druid_score(client, druid_answers)  # q01 answer a is selected: druid weight 2 of mean 0.5
    r = client.patch(
        f"{API}/questions/q01/answers/a",
        json={"expected_revision": 1, "class_weights": {"druid": 3.0, "hunter": 0.5}},
    )
    assert r.status_code == 200
    assert r.json()["revision"] == 2
    assert r.json()["answer"]["class_weights"] == {"druid": 3.0, "hunter": 0.5}
    after = druid_score(client, druid_answers)
    assert after - before == pytest.approx(1.0 * 3 / 4)  # +1 on the chosen answer, minus 1/4 of that on the mean
    # Restoring the original weight restores the original score and creates another revision.
    r = client.patch(
        f"{API}/questions/q01/answers/a",
        json={"expected_revision": 2, "class_weights": {"druid": 2.0, "hunter": 1.0}},
    )
    assert r.json()["revision"] == 3
    assert druid_score(client, druid_answers) == pytest.approx(before)


def test_modification_persists_after_application_restart(db_path):
    first = TestClient(create_app(db_path))
    first.patch(
        f"{API}/questions/q01/answers/a",
        json={"expected_revision": 1, "class_weights": {"druid": 4.0}, "text": "Edited text."},
    )
    second = TestClient(create_app(db_path))  # a brand-new application on the same database file
    cfg = second.get(f"{API}/config").json()
    assert cfg["revision"] == 2
    answer = cfg["questions"][0]["answers"][0]
    assert answer["class_weights"] == {"druid": 4.0} and answer["text"] == "Edited text."
    assert second.get(f"{API}/quiz").json()["questions"][0]["answers"][0]["text"] == "Edited text."


def test_editing_one_answer_does_not_change_other_answers(client):
    before = client.get(f"{API}/config").json()
    client.patch(f"{API}/questions/q05/answers/c", json={"expected_revision": 1, "trait_weights": {"wild": 9.0}})
    after = client.get(f"{API}/config").json()
    for qb, qa in zip(before["questions"], after["questions"]):
        for ab, aa in zip(qb["answers"], qa["answers"]):
            if (qb["id"], ab["id"]) != ("q05", "c"):
                assert ab == aa
    def answer(cfg, qid, aid):
        return next(a for q in cfg["questions"] if q["id"] == qid for a in q["answers"] if a["id"] == aid)

    assert answer(after, "q05", "c")["trait_weights"] == {"wild": 9.0}
    assert answer(after, "q05", "c")["class_weights"] == answer(before, "q05", "c")["class_weights"]


def test_changes_are_recorded_in_history(client):
    client.patch(f"{API}/questions/q02/answers/b", json={"expected_revision": 1, "class_weights": {"mage": 3}})
    hist = client.get(f"{API}/config/history").json()
    assert [h["revision"] for h in hist] == [2, 1]
    assert hist[0]["change_type"] == "answer" and "q02/b" in hist[0]["change_description"]
    assert hist[0]["change_detail"]["before"]["class_weights"] == {"mage": 2.0, "hunter": 1.0}
    assert hist[0]["change_detail"]["after"]["class_weights"] == {"mage": 3.0}
    old = client.get(f"{API}/config/history/1").json()
    assert old["revision"] == 1 and old["questions"][1]["answers"][1]["class_weights"] == {"mage": 2.0, "hunter": 1.0}


def test_invalid_weights_are_rejected(client):
    url = f"{API}/questions/q01/answers/a"
    assert client.patch(url, json={"expected_revision": 1, "class_weights": {"druid": -1}}).status_code == 422
    assert client.patch(url, json={"expected_revision": 1, "class_weights": {"druid": "lots"}}).status_code == 422
    # Starlette's JSON parser accepts the non-standard NaN / Infinity tokens; the model must refuse them.
    for bad in ("NaN", "Infinity"):
        r = client.patch(url, content=f'{{"expected_revision":1,"class_weights":{{"druid":{bad}}}}}',
                         headers={"content-type": "application/json"})
        assert r.status_code == 422, bad
    assert rev(client) == 1


def test_invalid_identifiers_return_appropriate_errors(client):
    r = client.patch(f"{API}/questions/q01/answers/a", json={"expected_revision": 1, "class_weights": {"dragon": 1}})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "invalid_configuration"
    r = client.patch(f"{API}/questions/q01/answers/a", json={"expected_revision": 1, "trait_weights": {"charm": 1}})
    assert r.status_code == 400
    assert client.patch(f"{API}/questions/q99/answers/a", json={"expected_revision": 1}).status_code == 404
    assert client.patch(f"{API}/questions/q01/answers/z", json={"expected_revision": 1}).status_code == 404
    assert client.patch(f"{API}/classes/dragon/specs/x", json={"expected_revision": 1}).status_code == 404
    assert client.patch(f"{API}/classes/druid/specs/x", json={"expected_revision": 1}).status_code == 404
    assert client.patch(f"{API}/traits/charm", json={"expected_revision": 1}).status_code == 404
    assert client.get(f"{API}/builds/nope").status_code == 404
    assert client.get(f"{API}/config/history/99").status_code == 404
    assert client.post(f"{API}/simulate", json={"answers": {"q99": "a"}}).status_code == 400
    assert client.post(
        f"{API}/simulate",
        json={"answers": {"q01": "a"}, "overrides": [{"question_id": "q01", "answer_id": "a", "class_weights": {"dragon": 1}}]},
    ).status_code == 400
    assert rev(client) == 1


def test_revision_conflicts_are_detected(client):
    url = f"{API}/questions/q01/answers/a"
    assert client.patch(url, json={"expected_revision": 1, "class_weights": {"druid": 3}}).status_code == 200
    stale = client.patch(url, json={"expected_revision": 1, "class_weights": {"druid": 4}})
    assert stale.status_code == 409
    detail = stale.json()["detail"]
    assert detail["code"] == "revision_conflict" and detail["current_revision"] == 2 and detail["expected_revision"] == 1
    assert client.get(f"{API}/config").json()["questions"][0]["answers"][0]["class_weights"] == {"druid": 3.0}
    assert client.patch(url, json={"class_weights": {"druid": 4}}).status_code == 422  # revision is mandatory


def test_specialization_profile_can_be_edited_with_arbitrary_trait_count(client):
    r = client.patch(
        f"{API}/classes/druid/specs/feral_combat",
        json={
            "expected_revision": 1,
            "trait_multipliers": {"wild": 1.8, "instinct": 1.2, "freedom": 0.5, "power": 0.2},
            "description": "An adaptive shapeshifting combat specialist.",
        },
    )
    assert r.status_code == 200
    spec = r.json()["specialization"]
    assert list(spec["trait_multipliers"]) == ["wild", "instinct", "freedom", "power"]
    assert spec["description"] == "An adaptive shapeshifting combat specialist."
    persisted = client.get(f"{API}/config").json()["classes"][0]["specializations"][1]
    assert persisted["trait_multipliers"] == {"wild": 1.8, "instinct": 1.2, "freedom": 0.5, "power": 0.2}


def test_trait_class_and_question_text_can_be_edited(client):
    assert client.patch(f"{API}/traits/wild", json={"expected_revision": 1, "name": "Instinctive"}).status_code == 200
    assert client.patch(f"{API}/classes/druid", json={"expected_revision": 2, "description": "Rooted."}).status_code == 200
    r = client.patch(f"{API}/questions/q01", json={"expected_revision": 3, "text": "Pick a room."})
    assert r.status_code == 200 and r.json()["question"]["text"] == "Pick a room."
    cfg = client.get(f"{API}/config").json()
    assert cfg["traits"][0]["name"] == "Instinctive" and cfg["classes"][0]["description"] == "Rooted."
    ev = evaluate(client, first_answers(build_default_config())).json()
    assert any(t["name"] == "Instinctive" for t in ev["rankings"]["traits"])


def test_disabling_a_question_is_refused_because_it_breaks_the_quiz_structure(client):
    r = client.patch(f"{API}/questions/q01", json={"expected_revision": 1, "enabled": False})
    assert r.status_code == 400 and "30 enabled questions" in json.dumps(r.json())


# ------------------------------------------------------------------ simulation


def test_simulation_does_not_modify_saved_configuration(client, druid_answers):
    before = client.get(f"{API}/config").json()
    body = {
        "answers": druid_answers,
        "overrides": [{"question_id": "q01", "answer_id": "a", "class_weights": {"druid": 0.0, "hunter": 6.0}}],
        "specialization_overrides": [{"class_id": "druid", "specialization_id": "balance", "trait_multipliers": {"wild": 9}}],
    }
    r = client.post(f"{API}/simulate", json=body)
    assert r.status_code == 200
    sim = r.json()
    assert sim["persisted"] is False and sim["overrides_applied"] == 2
    assert {"original", "simulated", "class_differences", "winning_class_changed", "winning_specialization_changed"} <= set(sim)
    assert len(sim["class_differences"]) == 9
    assert sim["original"]["metadata"]["config_revision"] == 1
    assert client.get(f"{API}/config").json() == before
    assert rev(client) == 1


def test_simulation_accepts_partial_answers(client):
    r = client.post(f"{API}/simulate", json={"answers": {"q01": "a", "q02": "c"}, "overrides": []})
    assert r.status_code == 200
    assert r.json()["original"]["metadata"]["provisional"] is True
    assert r.json()["winning_class_changed"] is False


def test_batch_simulation_endpoint(client):
    r = client.post(f"{API}/simulate/batch", json={"count": 1500, "seed": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1500 and body["seed"] == 5 and body["simulated"] is None
    assert len(body["baseline"]["class_frequencies"]) == 9 and len(body["baseline"]["specialization_frequencies"]) == 27
    with_override = client.post(
        f"{API}/simulate/batch",
        json={"count": 1500, "seed": 5,
              "overrides": [{"question_id": "q01", "answer_id": "a", "class_weights": {"druid": 30}}]},
    ).json()
    d0 = next(r["count"] for r in with_override["baseline"]["class_frequencies"] if r["id"] == "druid")
    d1 = next(r["count"] for r in with_override["simulated"]["class_frequencies"] if r["id"] == "druid")
    assert d1 > d0
    assert client.post(f"{API}/simulate/batch", json={"count": 10**6}).status_code == 422


# ------------------------------------------------------------------ import / export / reset


def test_export_and_import_preserve_scoring_behaviour(client, druid_answers):
    client.patch(f"{API}/questions/q01/answers/a", json={"expected_revision": 1, "class_weights": {"hunter": 5.0}})
    expected = evaluate(client, druid_answers, include_explanation=True).json()
    exported = client.get(f"{API}/config/export")
    assert exported.status_code == 200 and "attachment" in exported.headers["content-disposition"]
    cfg = exported.json()

    client.patch(f"{API}/questions/q01/answers/a", json={"expected_revision": 2, "class_weights": {"mage": 9.0}})
    assert evaluate(client, druid_answers, include_explanation=True).json() != expected

    r = client.post(f"{API}/config/import", json={"expected_revision": 3, "config": cfg, "description": "Roundtrip"})
    assert r.status_code == 200, r.text
    assert r.json()["revision"] == 4 and r.json()["backup_path"]
    again = evaluate(client, druid_answers, include_explanation=True).json()
    again["metadata"]["config_revision"] = expected["metadata"]["config_revision"]
    assert again == expected


def test_invalid_imports_are_rejected_without_changing_anything(client):
    cfg = client.get(f"{API}/config").json()
    before = client.get(f"{API}/config").json()

    bad = json.loads(json.dumps(cfg))
    bad["questions"][0]["answers"][0]["class_weights"]["dragon"] = 1
    r = client.post(f"{API}/config/import", json={"expected_revision": 1, "config": bad})
    assert r.status_code == 400 and any("dragon" in e for e in r.json()["detail"]["errors"])

    bad = json.loads(json.dumps(cfg))
    bad["questions"].pop()
    assert client.post(f"{API}/config/import", json={"expected_revision": 1, "config": bad}).status_code == 400

    bad = json.loads(json.dumps(cfg))
    bad["questions"][0]["answers"] = bad["questions"][0]["answers"][:1]      # a choice needs at least two answers
    assert client.post(f"{API}/config/import", json={"expected_revision": 1, "config": bad}).status_code == 400

    bad = json.loads(json.dumps(cfg))
    scale = next(q for q in bad["questions"] if q["type"] == "scale")
    scale["answers"][0]["id"] = "yes"                                         # scale poles must be agree/disagree
    assert client.post(f"{API}/config/import", json={"expected_revision": 1, "config": bad}).status_code == 400

    bad = json.loads(json.dumps(cfg))
    next(q for q in bad["questions"] if q["type"] == "pick_two")["answers"].pop()   # pick_two needs exactly four
    assert client.post(f"{API}/config/import", json={"expected_revision": 1, "config": bad}).status_code == 400

    bad = json.loads(json.dumps(cfg))
    bad["questions"][2]["answers"][0]["spec_weights"] = {"warrior/nonsense": 1}
    r = client.post(f"{API}/config/import", json={"expected_revision": 1, "config": bad})
    assert r.status_code == 400 and any("nonsense" in e for e in r.json()["detail"]["errors"])

    bad = json.loads(json.dumps(cfg))
    bad["questions"][1]["id"] = "q01"
    r = client.post(f"{API}/config/import", json={"expected_revision": 1, "config": bad})
    assert r.status_code == 400 and any("Duplicate question" in e for e in r.json()["detail"]["errors"])

    bad = json.loads(json.dumps(cfg))
    bad["questions"][0]["answers"][0]["class_weights"]["druid"] = -2
    assert client.post(f"{API}/config/import", json={"expected_revision": 1, "config": bad}).status_code == 422

    bad = json.loads(json.dumps(cfg))
    bad["classes"][0]["specializations"][0]["trait_multipliers"] = {"charm": 1}
    assert client.post(f"{API}/config/import", json={"expected_revision": 1, "config": bad}).status_code == 400

    assert client.get(f"{API}/config").json() == before


def test_reset_requires_confirmation_and_restores_seed_data(client, druid_answers):
    original = client.get(f"{API}/config/default").json()
    client.patch(f"{API}/questions/q01/answers/a", json={"expected_revision": 1, "class_weights": {"mage": 8.0}})
    r = client.post(f"{API}/config/reset", json={"expected_revision": 2})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "confirmation_required"
    assert rev(client) == 2
    r = client.post(f"{API}/config/reset", json={"expected_revision": 2, "confirm": True})
    assert r.status_code == 200 and r.json()["revision"] == 3 and r.json()["backup_path"]
    restored = client.get(f"{API}/config").json()
    assert restored["revision"] == 3
    original["revision"] = 3
    assert restored == original
    assert client.post(f"{API}/config/reset", json={"expected_revision": 1, "confirm": True}).status_code == 409


def test_default_config_is_immutable_and_always_original(client):
    client.patch(f"{API}/questions/q01/answers/a", json={"expected_revision": 1, "class_weights": {"mage": 8.0}})
    default = client.get(f"{API}/config/default").json()
    assert default["questions"][0]["answers"][0]["class_weights"] == {"druid": 2.0, "hunter": 1.0}


def test_history_snapshot_can_be_restored(client):
    client.patch(f"{API}/questions/q01/answers/a", json={"expected_revision": 1, "class_weights": {"mage": 8.0}})
    r = client.post(f"{API}/config/history/1/restore", json={"expected_revision": 2})
    assert r.status_code == 200 and r.json()["revision"] == 3
    assert client.get(f"{API}/config").json()["questions"][0]["answers"][0]["class_weights"] == {"druid": 2.0, "hunter": 1.0}


# ------------------------------------------------------------------ misc


def test_health_endpoint(client):
    body = client.get(f"{API}/health").json()
    assert body["status"] == "ok" and body["class_count"] == 9 and body["specialization_count"] == 27
    assert body["algorithm_version"] == "1.4.0" and body["question_count"] == 30


def test_openapi_documentation_is_available_and_complete(client):
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    for path in (
        "/api/v1/quiz", "/api/v1/classes", "/api/v1/config", "/api/v1/evaluate", "/api/v1/simulate",
        "/api/v1/config/default", "/api/v1/config/export", "/api/v1/config/import", "/api/v1/config/reset",
        "/api/v1/config/history", "/api/v1/health",
        "/api/v1/questions/{question_id}/answers/{answer_id}", "/api/v1/classes/{class_id}/specs/{spec_id}",
    ):
        assert path in paths, path
    assert client.get("/docs").status_code == 200


def test_admin_token_protects_administrative_endpoints(db_path, druid_answers):
    client = TestClient(create_app(db_path, admin_token="s3cret"))
    assert client.get(f"{API}/health").json()["admin_auth_required"] is True
    assert client.get(f"{API}/quiz").status_code == 200
    assert evaluate(client, druid_answers).status_code == 200  # participant result needs no token
    assert evaluate(client, druid_answers, include_explanation=True).status_code == 401
    assert client.get(f"{API}/config").status_code == 401
    assert client.patch(f"{API}/questions/q01/answers/a", json={"expected_revision": 1}).status_code == 401
    assert client.get(f"{API}/classes?include_scores=true").status_code == 401
    headers = {"Authorization": "Bearer s3cret"}
    assert client.get(f"{API}/config", headers=headers).status_code == 200
    assert evaluate(client, druid_answers, include_explanation=True).status_code == 401
    r = client.post(f"{API}/evaluate", json={"answers": druid_answers, "include_explanation": True}, headers=headers)
    assert r.status_code == 200


def test_static_interface_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    for asset in ("/static/styles.css", "/static/app.js"):
        assert client.get(asset).status_code == 200, asset
