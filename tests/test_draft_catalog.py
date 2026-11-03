"""Tests for the hand-built DRAFT talent catalog (catalog/forever-talents-draft-2026-11-03.json).

The draft is NOT game-client data. These tests check that it is structurally sound, that it encodes the
Nov 2 development-note changes the build script claims, and that draft data can never verify a build.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.builds import validate_build
from app.main import create_app
from app.models import Build, TalentCatalog
from app.seed import build_default_config

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "catalog" / "forever-talents-draft-2026-11-03.json"
API = "/api/v1"


@pytest.fixture(scope="module")
def raw():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def config(raw):
    cfg = build_default_config()
    cfg.talent_catalog = TalentCatalog.model_validate(raw)
    return cfg


def talents(raw):
    return {c["id"]: {t["id"]: {x["id"]: x for x in t["talents"]} for t in c["trees"]} for c in raw["classes"]}


def by_name(raw, cls, name):
    hits = [x for t in raw["classes"] if t["id"] == cls for tr in t["trees"] for x in tr["talents"] if x["name"] == name]
    return hits[0] if hits else None


def test_draft_is_marked_draft_and_unverified_in_every_field(raw):
    assert raw["data_status"] == "draft"
    assert "UNVERIFIED" in raw["client_version"]
    assert "NOT read from the game client" in raw["notes"]


def test_catalog_covers_all_nine_classes_and_27_trees_that_match_the_specializations(raw, config):
    assert len(raw["classes"]) == 9
    assert sum(len(c["trees"]) for c in raw["classes"]) == 27
    for c in raw["classes"]:
        spec_ids = {s.id for s in config.get_class(c["id"]).specializations}
        assert {t["id"] for t in c["trees"]} == spec_ids
    assert sum(len(t["talents"]) for c in raw["classes"] for t in c["trees"]) == 468


def test_every_tree_is_structurally_playable(raw):
    for c in raw["classes"]:
        for tree in c["trees"]:
            label = f"{c['id']}/{tree['id']}"
            tiers = {}
            for t in tree["talents"]:
                tiers.setdefault(t["tier"], []).append(t)
                assert t["max_rank"] >= 1, label
            assert set(tiers) == set(range(7)), f"{label} has gaps in its rows"
            # One capstone per tree; Feral Druid has two because the notes put Primal Bite and Shifting Power on row 7.
            assert 1 <= len(tiers[6]) <= (2 if label == "druid/feral_combat" else 1), f"{label} capstones: {len(tiers[6])}"
            assert all(len(v) <= 4 for v in tiers.values()), label
            # The capstone must be reachable inside 51 points: 30 points above it plus the capstone itself.
            assert sum(t["max_rank"] for tier, ts in tiers.items() if tier < 6 for t in ts) >= 30, label


def test_talent_ids_are_unique_within_each_class_and_prerequisites_resolve(raw):
    for c in raw["classes"]:
        ids = [t["id"] for tr in c["trees"] for t in tr["talents"]]
        assert len(ids) == len(set(ids)), c["id"]
        for tr in c["trees"]:
            for t in tr["talents"]:
                for r in t["requires"]:
                    assert r["talent_id"] in ids and r["rank"] >= 1


@pytest.mark.parametrize(
    "cls,name,tier,rank",
    [
        ("rogue", "Mutilate", 6, 1),               # now the 31-point talent
        ("rogue", "Death Mark", 6, 1),             # new Subtlety capstone
        ("rogue", "Lethality", 2, 2),              # 5 -> 2 points
        ("warrior", "Improved Whirlwind", 5, 2),   # new, row 6
        ("warrior", "Reckless Swings", 3, 1),      # new, row 4
        ("warrior", "Flurry", 5, 3),               # 5 -> 3 points
        ("paladin", "Unsealed Wrath", 6, 1),       # new 31st talent
        ("druid", "Lacerate", 3, 1),               # Feral talent on row 4
        ("shaman", "Improved Ghost Wolf", 3, 2),   # moved to row 4
    ],
)
def test_development_note_changes_are_reflected(raw, cls, name, tier, rank):
    t = by_name(raw, cls, name)
    assert t is not None, name
    assert (t["tier"], t["max_rank"]) == (tier, rank)


@pytest.mark.parametrize(
    "cls,name",
    [("druid", "Berserk"), ("rogue", "Murder"), ("rogue", "Thousand Cuts"), ("shaman", "Lava Burst"),
     ("paladin", "Voice of Truth"), ("mage", "Piercing Ice"), ("priest", "Binding Heal")],
)
def test_removed_talents_are_absent(raw, cls, name):
    assert by_name(raw, cls, name) is None


def test_prerequisites_stated_in_the_notes_are_recorded(raw):
    def req(cls, name):
        t = by_name(raw, cls, name)
        return {next(x["name"] for c in raw["classes"] if c["id"] == cls for tr in c["trees"] for x in tr["talents"] if x["id"] == r["talent_id"]): r["rank"] for r in t["requires"]}
    assert req("druid", "Primal Bite") == {"Leader of the Pack": 1}
    assert req("warrior", "Bloodthirst") == {"Death Wish": 1}
    assert req("paladin", "Unsealed Wrath") == {"Repentance": 1}
    assert req("warrior", "Gore Drinker") == {"Blood Craze": 3}


def test_the_build_script_is_deterministic():
    before = CATALOG_PATH.read_text(encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "catalog" / "build_forever_draft.py")], check=True, capture_output=True)
    assert CATALOG_PATH.read_text(encoding="utf-8") == before


# ---------------------------------------------------------------- draft data can never verify a build


def fury_allocation(raw):
    """51 points: whole rows from the top of Fury until the budget is spent."""
    fury = next(t for c in raw["classes"] if c["id"] == "warrior" for t in c["trees"] if t["id"] == "fury")
    alloc, left = {}, 51
    for tier in range(7):
        for t in [t for t in fury["talents"] if t["tier"] == tier]:
            take = min(t["max_rank"], left)
            if take:
                alloc[t["id"]] = take
                left -= take
    assert left == 0
    return alloc


def build_for(raw, **kw):
    base = dict(id="warrior-fury-draft", class_id="warrior", specialization_id="fury", name="Fury test", role="melee_damage",
                allocations=fury_allocation(raw), source="unit test", verified_at="2026-11-03",
                client_version=raw["client_version"], status="draft", is_default=False)
    base.update(kw)
    return Build.model_validate(base)


def test_a_legal_allocation_validates_against_the_draft_but_cannot_be_verified(raw, config):
    v = validate_build(build_for(raw), config)
    assert v.valid, v.errors
    assert v.complete and v.points_spent == 51
    assert not v.can_verify
    assert any("marked draft" in p for p in v.verification_problems)


def test_the_draft_catalog_enforces_row_gates_and_stated_prerequisites(raw, config):
    fury = next(tr for c in raw["classes"] if c["id"] == "warrior" for tr in c["trees"] if tr["id"] == "fury")
    ids = {t["name"]: t["id"] for t in fury["talents"]}
    too_deep = {ids["Booming Voice"]: 5, ids["Bloodthirst"]: 1}                     # capstone with 5 points above it
    v = validate_build(build_for(raw, allocations=too_deep, status="draft"), config)
    assert any("needs 30 points in earlier rows" in e for e in v.errors)

    rows_0_to_4 = {t["id"]: t["max_rank"] for t in fury["talents"] if t["tier"] <= 4}   # 48 points
    with_prereq = {**rows_0_to_4, ids["Bloodthirst"]: 1}
    v = validate_build(build_for(raw, allocations=with_prereq, total_points=51, status="draft"), config)
    assert not any("Death Wish" in e for e in v.errors), v.errors
    without = {k: x for k, x in with_prereq.items() if k != ids["Death Wish"]}          # Bloodthirst needs Death Wish
    v = validate_build(build_for(raw, allocations=without, status="draft"), config)
    assert any("requires 1 point(s) in Death Wish" in e for e in v.errors), v.errors


def test_importing_the_draft_through_the_api_and_refusing_to_verify(tmp_path, raw):
    client = TestClient(create_app(tmp_path / "t.db"))
    r = client.put(f"{API}/talents/catalog", json={"expected_revision": 1, "catalog": raw})
    assert r.status_code == 200, r.text
    summary = client.get(f"{API}/talents/catalog").json()
    assert summary["data_status"] == "draft" and len(summary["classes"]) == 9
    body = build_for(raw).model_dump(mode="json")
    rev = client.get(f"{API}/health").json()["config_revision"]
    verified = client.post(f"{API}/builds", json={"expected_revision": rev, "build": {**body, "status": "verified"}})
    assert verified.status_code == 400 and any("draft" in e for e in verified.json()["detail"]["errors"])
    ok = client.post(f"{API}/builds", json={"expected_revision": rev, "build": body})
    assert ok.status_code == 201
    assert ok.json()["build"]["validation"]["valid"] and not ok.json()["build"]["validation"]["can_verify"]
    assert ok.json()["build"]["tree_distribution_text"] == "0/51/0" or ok.json()["build"]["points_spent"] == 51
