"""The page of every specialization: served by the API, and carried unchanged in the static site's data."""
import json
from pathlib import Path


from app.public import public_classes, spec_page
from app.seed import build_default_config
from app.static_export import export_static_data

API = "/api/v1"
ROOT = Path(__file__).resolve().parent.parent


def test_every_specialization_has_a_page_with_its_traits_guide_and_build(client):
    cfg = build_default_config()
    for cls in cfg.classes:
        for spec in cls.specializations:
            r = client.get(f"{API}/specializations/{cls.id}/{spec.id}")
            assert r.status_code == 200, (cls.id, spec.id)
            page = r.json()
            assert page["class_name"] == cls.name and page["name"] == spec.name and page["overview"] and page["class_overview"]
            assert page["guide"]["gear"] and page["guide"]["competes_with"]
            assert [t["id"] for t in page["traits"]] == list(spec.trait_multipliers)          # primary trait first
            assert [t["order"] for t in page["traits"]] == [1, 2, 3]
            assert all(t["name"] and t["description"] and t["multiplier"] > 0 for t in page["traits"])
            assert page["build"]["status"] == "draft" and len(page["build"]["trees"]) == 3


def test_an_unknown_specialization_is_not_found(client):
    assert client.get(f"{API}/specializations/druid/nonsense").status_code == 404
    assert client.get(f"{API}/specializations/nobody/balance").status_code == 404


def test_the_page_never_exposes_scoring_weights_other_than_the_traits_it_is_matched_on(client):
    text = json.dumps(client.get(f"{API}/specializations/druid/balance").json())
    assert "class_weights" not in text and "spec_weights" not in text and "trait_weights" not in text


def test_the_class_listing_can_leave_out_builds_for_the_navigation(client):
    body = client.get(f"{API}/classes", params={"include_builds": "false"}).json()
    assert len(body["classes"]) == 9 and all(len(c["specializations"]) == 3 for c in body["classes"])
    assert all("builds" not in s for c in body["classes"] for s in c["specializations"])


def test_the_static_data_carries_the_same_pages_and_listing_as_the_api(client):
    data = export_static_data(build_default_config())
    assert len(data["specs"]) == 27
    assert data["classes"] == client.get(f"{API}/classes", params={"include_builds": "false"}).json()
    for key, page in data["specs"].items():
        c, s = key.split("/")
        served = client.get(f"{API}/specializations/{c}/{s}").json()
        assert {**page, "build": data["builds"][key]} == served, key           # the static page has its build looked up by key


def test_a_static_page_without_a_build_is_just_the_page():
    cfg = build_default_config()
    cfg.builds = []
    page = spec_page(cfg, "druid", "balance")
    assert page.build is None and page.traits


# ---------------------------------------------------------------- the front end: guards against mistakes unit tests would miss


def test_the_build_card_no_longer_shows_how_it_was_put_together_or_its_source():
    text = (ROOT / "app" / "static" / "parts.js").read_text(encoding="utf-8")
    assert "How this was put together" not in text and "Source:" not in text and "build.notes" not in text and "build.source" not in text
    assert "dataNotice" in text and "talentTrees" in text                         # the caveat about the talent data stays


def test_the_result_cards_link_to_specialization_pages_and_the_router_knows_the_route():
    quiz = (ROOT / "app" / "static" / "views" / "quiz.js").read_text(encoding="utf-8")
    assert quiz.count("#/specs/") >= 2 and quiz.count("#/specs\"") >= 1 and 'id: "share-text"' in quiz
    app = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
    assert '"specs": () => import("./views/specs.js")' in app and "routeArgs" in app
    assert 'data-nav="specs"' in (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
