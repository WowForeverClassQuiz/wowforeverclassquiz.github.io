"""Tests for the 27 best-guess draft builds and their installer.

The builds are NOT verified and NOT authoritative; these tests check that they are legal on the DRAFT
catalog, honestly labelled, and that nothing about them can be mistaken for verified data.
"""
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.builds import validate_build
from app.main import create_app
from app.models import Build, TalentCatalog
from app.repository import Repository
from app.seed import build_default_config

from .conftest import DRUID_ANSWERS

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog" / "forever-talents-draft-2026-11-03.json"
BUILDS = ROOT / "catalog" / "forever-builds-draft-2026-11-03.json"
INSTALL = ROOT / "catalog" / "install_drafts.py"
API = "/api/v1"


@pytest.fixture(scope="module")
def builds():
    return [Build.model_validate(b) for b in json.loads(BUILDS.read_text(encoding="utf-8"))]


@pytest.fixture(scope="module")
def config():
    cfg = build_default_config()
    cfg.talent_catalog = TalentCatalog.model_validate(json.loads(CATALOG.read_text(encoding="utf-8")))
    return cfg


def test_there_is_one_build_for_every_specialization(builds, config):
    keys = Counter((b.class_id, b.specialization_id) for b in builds)
    assert len(builds) == 27
    assert set(keys) == {(c.id, s.id) for c in config.classes for s in c.specializations}
    assert set(keys.values()) == {1}
    assert len({b.id for b in builds}) == 27


def test_every_build_is_legal_on_the_draft_catalog_but_never_verifiable(builds, config):
    for b in builds:
        v = validate_build(b, config)
        assert v.valid, (b.id, v.errors)
        assert v.complete and v.points_spent == 51 and v.points_remaining == 0, b.id
        assert not v.can_verify, b.id
        assert b.status == "draft" and b.verified_at is None, b.id
        assert len(b.leveling_order) == 51, b.id
        assert sum(b.allocations.values()) == 51, b.id


def test_each_builds_primary_tree_holds_the_most_points(builds, config):
    for b in builds:
        dist = validate_build(b, config).tree_distribution
        assert dist[b.specialization_id] == max(dist.values()), (b.id, dist)


def test_roles_match_the_specializations(builds, config):
    for b in builds:
        assert b.role in config.get_spec(b.class_id, b.specialization_id).role.split("_or_"), b.id


def test_builds_are_honestly_labelled(builds):
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    for b in builds:
        assert "BEST GUESS" in b.source and "Not verified" in b.source, b.id
        assert b.client_version == catalog["client_version"], b.id
        assert b.source_url.startswith("https://rankedboost.com/world-of-warcraft/forever/build/"), b.id
        assert b.professions == [], "professions are not invented"
        assert b.is_default and b.purpose == "leveling_pve" and b.level == 60 and b.total_points == 51


def test_leveling_order_matches_the_allocation(builds):
    for b in builds:
        assert dict(Counter(b.leveling_order)) == b.allocations, b.id


def test_removed_talents_never_appear(builds, config):
    removed = {"Berserk", "Murder", "Gift of the Earthmother", "Lava Burst", "Thousand Cuts", "Piercing Ice", "Twist of Light", "Instrument of Law"}
    names = {t.id: t.name for c in config.talent_catalog.classes for tr in c.trees for t in tr.talents}
    for b in builds:
        assert not removed & {names[t] for t in b.allocations}, b.id


def test_the_build_script_is_deterministic():
    before = BUILDS.read_text(encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "catalog" / "build_forever_builds.py")], check=True, capture_output=True)
    assert BUILDS.read_text(encoding="utf-8") == before


# ------------------------------------------------------------------ installer


def run_install(db, *extra):
    return subprocess.run([sys.executable, str(INSTALL), "--db", str(db), *extra], capture_output=True, text=True)


def test_installer_loads_catalog_and_builds_and_the_participant_sees_a_draft(tmp_path):
    db = tmp_path / "oracle.db"
    r = run_install(db)
    assert r.returncode == 0, r.stderr
    assert "none is verified" in r.stdout
    repo = Repository(db)
    cfg = repo.get_config()
    assert cfg.revision == 2 and cfg.talent_catalog.data_status == "draft"
    assert len(cfg.builds) == 27 and all(b.status == "draft" for b in cfg.builds)
    per_spec = Counter((b.class_id, b.specialization_id) for b in cfg.builds if b.is_default)
    assert len(per_spec) == 27 and set(per_spec.values()) == {1}

    client = TestClient(create_app(db))
    body = client.post(f"{API}/evaluate", json={"answers": DRUID_ANSWERS}).json()
    build = body["result"]["build"]
    assert (body["result"]["primary_class"]["id"], body["result"]["primary_specialization"]["id"]) == ("druid", "feral_combat")
    assert build["id"] == "druid-feral-combat-leveling" and build["status"] == "draft"
    assert build["points_spent"] == 51 and build["tree_distribution_text"] == "0/38/13"
    assert "Provisional" in build["status_note"] and "not verified" in build["status_note"]
    assert len(build["leveling_order"]) == 51 and build["combat_priorities"]
    assert body["alternatives"]["alternative_specialization"]["build"]["status"] == "draft"


def test_installer_is_repeatable_and_keeps_other_builds(tmp_path):
    db = tmp_path / "oracle.db"
    assert run_install(db).returncode == 0
    client = TestClient(create_app(db))
    rev = client.get(f"{API}/health").json()["config_revision"]
    mine = Build.model_validate(json.loads(BUILDS.read_text(encoding="utf-8"))[0]).model_dump(mode="json")
    mine.update(id="my-own-arms", name="My own Arms", is_default=False)
    assert client.post(f"{API}/builds", json={"expected_revision": rev, "build": mine}).status_code == 201
    assert run_install(db).returncode == 0
    cfg = Repository(db).get_config()
    assert len(cfg.builds) == 28 and cfg.get_build("my-own-arms") is not None
    assert Counter((b.class_id, b.specialization_id) for b in cfg.builds if b.is_default)[("warrior", "arms")] == 1


def test_installer_will_not_overwrite_a_non_draft_catalog(tmp_path):
    db = tmp_path / "oracle.db"
    client = TestClient(create_app(db))
    real = json.loads(CATALOG.read_text(encoding="utf-8"))
    real.update(data_status="verified", client_version="CLIENT-TEST", source="unit test")
    assert client.put(f"{API}/talents/catalog", json={"expected_revision": 1, "catalog": real}).status_code == 200
    r = run_install(db)
    assert r.returncode == 2 and "Refusing" in r.stderr
    assert Repository(db).get_config().talent_catalog.client_version == "CLIENT-TEST"
    assert run_install(db, "--force").returncode == 0
    assert Repository(db).get_config().talent_catalog.data_status == "draft"
