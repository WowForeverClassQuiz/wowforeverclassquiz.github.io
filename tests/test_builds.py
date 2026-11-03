"""Talent build validation tests.

IMPORTANT: the talent catalog below is a SYNTHETIC TEST FIXTURE. Its talent names, ranks and
prerequisites are invented to exercise the validator; they are not World of Warcraft: Forever data
and must never be shipped as game data.
"""
import copy

import pytest
from fastapi.testclient import TestClient

from app.builds import validate_build
from app.main import create_app
from app.models import Build, Config, TalentCatalog
from app.scoring import evaluate
from app.seed import build_default_config

API = "/api/v1"
FIXTURE_VERSION = "TEST-FIXTURE-0"
TREES = ["balance", "feral_combat", "restoration"]


def fixture_catalog(points_per_tier=5) -> dict:
    """Druid only. Per tree: 7 rows x 2 talents of max rank 5; row-t 'b' needs row-(t-1) 'a' at rank 5."""
    trees = []
    for tree in TREES:
        talents = []
        for tier in range(7):
            for letter in "ab":
                requires = [{"talent_id": f"{tree}-{tier - 1}a", "rank": 5}] if letter == "b" and tier > 0 else []
                talents.append({
                    "id": f"{tree}-{tier}{letter}", "name": f"Fixture {tree} {tier}{letter.upper()}",
                    "tier": tier, "column": "ab".index(letter), "max_rank": 5, "requires": requires,
                })
        trees.append({"id": tree, "name": tree.replace("_", " ").title(), "talents": talents})
    return {
        "game": "SYNTHETIC TEST FIXTURE", "client_version": FIXTURE_VERSION, "source": "unit-test fixture",
        "retrieved_at": "2026-11-03", "points_per_tier": points_per_tier,
        "classes": [{"id": "druid", "trees": trees}],
    }


def valid_allocation(tree="feral_combat") -> dict:
    """51 points: rows 0-4 fully taken (50) plus one point in row 5."""
    alloc = {}
    for tier in range(5):
        alloc[f"{tree}-{tier}a"] = 5
        alloc[f"{tree}-{tier}b"] = 5
    alloc[f"{tree}-5a"] = 1
    return alloc


def valid_order(alloc) -> list:
    order = []
    for tier in range(6):
        for letter in "ab":
            order += [f"feral_combat-{tier}{letter}"] * alloc.get(f"feral_combat-{tier}{letter}", 0)
    return order


def make_build(**overrides) -> dict:
    base = {
        "id": "druid-feral-test", "class_id": "druid", "specialization_id": "feral_combat",
        "name": "Fixture feral", "role": "melee_damage", "purpose": "leveling_pve", "level": 60, "total_points": 51,
        "allocations": valid_allocation(), "leveling_order": valid_order(valid_allocation()),
        "source": "unit-test fixture", "verified_at": "2026-11-03", "client_version": FIXTURE_VERSION,
        "status": "verified", "is_default": True,
    }
    base.update(overrides)
    return base


def config_with_catalog(**catalog_kwargs) -> Config:
    cfg = build_default_config()
    cfg.talent_catalog = TalentCatalog.model_validate(fixture_catalog(**catalog_kwargs))
    return cfg


@pytest.fixture
def cat_client(db_path):
    c = TestClient(create_app(db_path))
    r = c.put(f"{API}/talents/catalog", json={"expected_revision": 1, "catalog": fixture_catalog()})
    assert r.status_code == 200, r.text
    return c


def rev(c):
    return c.get(f"{API}/health").json()["config_revision"]


def create(c, **overrides):
    return c.post(f"{API}/builds", json={"expected_revision": rev(c), "build": make_build(**overrides)})


# ------------------------------------------------------------------ validator unit tests


def test_a_correct_level_60_build_has_exactly_51_points_and_validates():
    cfg = config_with_catalog()
    v = validate_build(Build.model_validate(make_build()), cfg)
    assert v.valid and v.can_verify and v.complete
    assert v.points_spent == 51 and v.points_remaining == 0 and v.expected_points == 51
    assert v.tree_distribution == {"balance": 0, "feral_combat": 51, "restoration": 0}


def test_talent_ranks_may_not_exceed_their_limit():
    cfg = config_with_catalog()
    alloc = valid_allocation()
    alloc["feral_combat-0a"] = 6
    alloc["feral_combat-5a"] = 0
    alloc.pop("feral_combat-5a")
    v = validate_build(Build.model_validate(make_build(allocations=alloc, leveling_order=[], status="draft")), cfg)
    assert not v.valid and any("exceeds its maximum of 5" in e for e in v.errors)


def test_unknown_talents_are_rejected():
    cfg = config_with_catalog()
    alloc = valid_allocation()
    alloc["made-up-talent"] = 1
    v = validate_build(Build.model_validate(make_build(allocations=alloc, leveling_order=[], status="draft")), cfg)
    assert any("does not exist" in e for e in v.errors)


def test_tree_depth_prerequisites_are_enforced():
    cfg = config_with_catalog()
    # Row 3 needs 15 points in rows above; only 5 are present.
    alloc = {"feral_combat-0a": 5, "feral_combat-3a": 5}
    v = validate_build(Build.model_validate(make_build(allocations=alloc, leveling_order=[], status="draft")), cfg)
    assert any("needs 15 points in earlier rows" in e for e in v.errors)


def test_individual_talent_prerequisites_are_enforced():
    cfg = config_with_catalog()
    # 'b' of row 1 requires 5 points in row 0 'a'; give it only 4 (tier points are satisfied by 'b' of row 0).
    alloc = {"feral_combat-0a": 4, "feral_combat-0b": 5, "feral_combat-1b": 1}
    v = validate_build(Build.model_validate(make_build(allocations=alloc, leveling_order=[], status="draft")), cfg)
    assert any("requires 5 point(s)" in e for e in v.errors)


def test_points_cannot_exceed_the_budget():
    cfg = config_with_catalog()
    alloc = valid_allocation()
    alloc["feral_combat-5b"] = 2
    v = validate_build(Build.model_validate(make_build(allocations=alloc, leveling_order=[], status="draft")), cfg)
    assert any("53 points are allocated but only 51" in e for e in v.errors)


def test_total_points_must_follow_the_level_formula():
    cfg = config_with_catalog()
    v = validate_build(Build.model_validate(make_build(total_points=50, leveling_order=[], status="draft")), cfg)
    assert any("grants 51 talent points" in e for e in v.errors)
    v = validate_build(Build.model_validate(make_build(level=40, total_points=31, allocations={}, leveling_order=[],
                                                       status="draft")), cfg)
    assert v.expected_points == 31 and not v.errors


def test_role_and_primary_tree_must_agree_with_the_specialization():
    cfg = config_with_catalog()
    v = validate_build(Build.model_validate(make_build(role="healer", status="draft")), cfg)
    assert any("not consistent with specialization role" in e for e in v.errors)
    off_tree = valid_allocation("restoration")
    v = validate_build(Build.model_validate(make_build(allocations=off_tree, leveling_order=[], status="draft")), cfg)
    assert any("does not match the build's primary specialization" in e for e in v.errors)


def test_hybrid_allocations_are_allowed_when_the_primary_tree_has_the_most_points():
    cfg = config_with_catalog()
    alloc = {}
    for tier in range(4):  # 40 points feral
        alloc[f"feral_combat-{tier}a"] = 5
        alloc[f"feral_combat-{tier}b"] = 5
    alloc["restoration-0a"] = 5
    alloc["restoration-0b"] = 5
    alloc["restoration-1a"] = 1
    v = validate_build(Build.model_validate(make_build(allocations=alloc, leveling_order=[], status="draft")), cfg)
    assert v.valid and v.tree_distribution == {"balance": 0, "feral_combat": 40, "restoration": 11}


def test_leveling_order_must_be_a_legal_sequence_and_match_the_allocation():
    cfg = config_with_catalog()
    alloc = valid_allocation()
    order = valid_order(alloc)
    assert validate_build(Build.model_validate(make_build(leveling_order=order)), cfg).valid
    bad = list(reversed(order))
    v = validate_build(Build.model_validate(make_build(leveling_order=bad, status="draft")), cfg)
    assert any("not yet unlocked" in e or "prerequisite" in e for e in v.errors)
    short = order[:-1] + ["feral_combat-5b"]
    v = validate_build(Build.model_validate(make_build(leveling_order=short, status="draft")), cfg)
    assert not v.valid


def test_incomplete_or_unsourced_builds_cannot_be_verified():
    cfg = config_with_catalog()
    alloc = valid_allocation()
    alloc.pop("feral_combat-5a")
    v = validate_build(Build.model_validate(make_build(allocations=alloc, leveling_order=[], status="draft")), cfg)
    assert v.valid and not v.can_verify and any("50 of 51" in p for p in v.verification_problems)
    v = validate_build(Build.model_validate(make_build(source="", status="draft")), cfg)
    assert not v.can_verify and any("source" in p for p in v.verification_problems)
    v = validate_build(Build.model_validate(make_build(client_version="other", status="draft")), cfg)
    assert any("does not match" in p for p in v.verification_problems)
    v = validate_build(Build.model_validate(make_build(verified_at=None, status="draft")), cfg)
    assert any("verification date" in p for p in v.verification_problems)


def test_without_talent_data_nothing_can_be_verified():
    cfg = build_default_config()
    v = validate_build(Build.model_validate(make_build(status="draft")), cfg)
    assert not v.catalog_available and not v.can_verify
    assert any("no imported talent data" in p for p in v.verification_problems)
    assert v.warnings


def test_seed_builds_are_honest_placeholders():
    cfg = build_default_config()
    assert len(cfg.builds) == 27
    assert {(b.class_id, b.specialization_id) for b in cfg.builds} == {
        (c.id, s.id) for c in cfg.classes for s in c.specializations
    }
    for b in cfg.builds:
        assert b.status == "pending" and b.allocations == {} and b.is_default
        assert b.level == 60 and b.total_points == 51 and b.purpose == "leveling_pve"
        assert b.verified_at is None and b.leveling_order == [] and b.combat_priorities == []


# ------------------------------------------------------------------ API behaviour


def test_verified_build_can_be_saved_when_it_validates(cat_client):
    r = create(cat_client)
    assert r.status_code == 201, r.text
    build = r.json()["build"]
    assert build["status"] == "verified" and build["points_spent"] == 51 and build["points_remaining"] == 0
    assert build["tree_distribution_text"] == "0/51/0" and build["allocation_pending"] is False
    assert build["validation"]["valid"] is True
    assert [t["name"] for t in build["talents"]][0] == "Fixture feral_combat 0A"


def test_invalid_allocations_cannot_be_marked_verified(cat_client):
    bad = valid_allocation()
    bad["feral_combat-0a"] = 6
    r = create(cat_client, id="bad-one", allocations=bad, leveling_order=[])
    assert r.status_code == 400
    assert any("exceeds its maximum" in e for e in r.json()["detail"]["errors"])
    r = create(cat_client, id="bad-two", client_version="wrong")
    assert r.status_code == 400
    # The same data is accepted as a draft, and the draft cannot be promoted without fixing it.
    assert create(cat_client, id="bad-three", allocations=bad, leveling_order=[], status="draft", is_default=False).status_code == 201
    r = cat_client.patch(f"{API}/builds/bad-three", json={"expected_revision": rev(cat_client), "status": "verified"})
    assert r.status_code == 400
    assert cat_client.get(f"{API}/builds/bad-three").json()["build"]["status"] == "draft"


def test_nothing_can_be_verified_without_talent_data(client):
    r = client.post(f"{API}/builds", json={"expected_revision": 1, "build": make_build()})
    assert r.status_code == 400
    assert any("no imported talent data" in e for e in r.json()["detail"]["errors"])
    r = client.patch(f"{API}/builds/druid-feral-combat-leveling", json={"expected_revision": 1, "status": "verified"})
    assert r.status_code == 400


def test_validate_endpoint_reports_remaining_points_without_saving(cat_client):
    r = cat_client.post(f"{API}/builds/validate", json={"build": make_build(
        allocations={"feral_combat-0a": 5, "feral_combat-0b": 5}, leveling_order=[], status="draft")})
    assert r.status_code == 200
    body = r.json()
    assert body["points_spent"] == 10 and body["points_remaining"] == 41 and body["complete"] is False
    assert cat_client.get(f"{API}/builds/druid-feral-test").status_code == 404


def test_replacing_a_catalog_downgrades_builds_that_no_longer_validate(cat_client):
    assert create(cat_client).status_code == 201
    changed = fixture_catalog()
    changed["client_version"] = "TEST-FIXTURE-1"
    r = cat_client.put(f"{API}/talents/catalog", json={"expected_revision": rev(cat_client), "catalog": changed})
    assert r.status_code == 200 and r.json()["downgraded_builds"] == ["druid-feral-test"]
    assert cat_client.get(f"{API}/builds/druid-feral-test").json()["build"]["status"] == "unverified"
    r = cat_client.put(f"{API}/talents/catalog", json={"expected_revision": rev(cat_client), "catalog": None})
    assert r.status_code == 200 and r.json()["available"] is False


def test_catalog_must_reference_known_classes_and_trees(client):
    bad = fixture_catalog()
    bad["classes"][0]["trees"][0]["id"] = "not-a-spec"
    r = client.put(f"{API}/talents/catalog", json={"expected_revision": 1, "catalog": bad})
    assert r.status_code == 400 and any("does not match a specialization" in e for e in r.json()["detail"]["errors"])
    bad = fixture_catalog()
    bad["classes"][0]["id"] = "dragon"
    assert client.put(f"{API}/talents/catalog", json={"expected_revision": 1, "catalog": bad}).status_code == 400


def test_multiple_builds_and_default_selection(cat_client):
    assert create(cat_client).status_code == 201
    second = create(cat_client, id="druid-feral-alt", name="Alt", status="draft", is_default=False,
                    allocations={}, leveling_order=[])
    assert second.status_code == 201
    r = cat_client.post(f"{API}/builds/druid-feral-alt/default", json={"expected_revision": rev(cat_client)})
    assert r.status_code == 200 and r.json()["build"]["is_default"] is True
    builds = cat_client.get(f"{API}/builds?class_id=druid&specialization_id=feral_combat").json()["builds"]
    assert {b["id"]: b["is_default"] for b in builds} == {
        "druid-feral-combat-leveling": False, "druid-feral-test": False, "druid-feral-alt": True,
    }
    r = cat_client.delete(f"{API}/builds/druid-feral-alt?expected_revision={rev(cat_client)}")
    assert r.status_code == 200
    assert cat_client.get(f"{API}/builds/druid-feral-alt").status_code == 404


def test_duplicate_build_ids_are_rejected(cat_client):
    assert create(cat_client).status_code == 201
    assert create(cat_client).status_code == 400


def test_participant_sees_verified_build_details_and_status(cat_client, druid_answers):
    create(cat_client)
    cat_client.post(f"{API}/builds/druid-feral-test/default", json={"expected_revision": rev(cat_client)})
    body = cat_client.post(f"{API}/evaluate", json={"answers": druid_answers}).json()
    build = body["result"]["build"]
    assert build["id"] == "druid-feral-test" and build["status"] == "verified"
    assert "Verified against" in build["status_note"] and FIXTURE_VERSION in build["status_note"]
    assert build["tree_distribution_text"] == "0/51/0"
    # Other specializations still show an honest "pending" placeholder.
    alt = body["alternatives"]["alternative_specialization"]["build"]
    assert alt["status"] == "pending" and "pending" in alt["status_note"].lower()


def test_changing_a_build_does_not_alter_personality_scoring(cat_client, druid_answers):
    def scoring_only(body):
        return {k: body[k] for k in ("rankings", "alternatives")} | {
            "result": {k: v for k, v in body["result"].items() if k != "build"}
        }

    def alt_clean(body):
        s = scoring_only(copy.deepcopy(body))
        s["alternatives"]["alternative_specialization"].pop("build", None)
        s["alternatives"]["second_specialization_in_primary_class"].pop("build", None)
        s["result"]["primary_specialization"].pop("build", None)
        return s

    before = cat_client.post(f"{API}/evaluate", json={"answers": druid_answers, "include_explanation": True}).json()
    create(cat_client)
    cat_client.patch(f"{API}/builds/druid-feral-test", json={"expected_revision": rev(cat_client), "name": "Renamed"})
    cat_client.put(f"{API}/talents/catalog", json={"expected_revision": rev(cat_client), "catalog": None})
    after = cat_client.post(f"{API}/evaluate", json={"answers": druid_answers, "include_explanation": True}).json()
    assert alt_clean(before) == alt_clean(after)
    assert before["explanation"] == after["explanation"]


def test_build_edit_cannot_leave_a_verified_build_invalid(cat_client):
    create(cat_client)
    r = cat_client.patch(
        f"{API}/builds/druid-feral-test",
        json={"expected_revision": rev(cat_client), "allocations": {"feral_combat-0a": 5}},
    )
    assert r.status_code == 400
    r = cat_client.patch(
        f"{API}/builds/druid-feral-test",
        json={"expected_revision": rev(cat_client), "allocations": {"feral_combat-0a": 5}, "status": "draft", "leveling_order": []},
    )
    assert r.status_code == 200 and r.json()["build"]["points_remaining"] == 46


def test_catalog_and_builds_survive_export_import(cat_client):
    create(cat_client)
    exported = cat_client.get(f"{API}/config/export").json()
    cat_client.post(f"{API}/config/reset", json={"expected_revision": rev(cat_client), "confirm": True})
    assert cat_client.get(f"{API}/talents/catalog").json()["available"] is False
    r = cat_client.post(f"{API}/config/import", json={"expected_revision": rev(cat_client), "config": exported})
    assert r.status_code == 200, r.text
    assert cat_client.get(f"{API}/builds/druid-feral-test").json()["build"]["status"] == "verified"
    exported["builds"][-1]["allocations"]["feral_combat-0a"] = 99
    assert cat_client.post(f"{API}/config/import", json={"expected_revision": rev(cat_client), "config": exported}).status_code == 400
