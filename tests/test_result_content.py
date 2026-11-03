"""What the result page is given beyond the recommendation: role and gear guidance, drawn talent trees, how current the
talent data is, and the icons; plus guards for front-end mistakes that unit tests would otherwise miss."""
import re
from pathlib import Path

from app.builds import describe_build
from app.seed import build_default_config

ROOT = Path(__file__).resolve().parent.parent
API = "/api/v1"


def test_every_specialization_has_a_complete_role_and_gear_guide():
    cfg = build_default_config()
    for cls in cfg.classes:
        for spec in cls.specializations:
            g = spec.guide
            where = f"{cls.id}/{spec.id}"
            assert g.dungeon_role and g.raid_role, where
            assert len(g.gear) >= 3 and len(g.competes_with) >= 2, where
            assert g.note and "may differ" in g.note, where


def test_the_result_carries_the_guide_the_drawn_trees_and_the_date_of_the_talent_data(client, druid_answers):
    body = client.post(f"{API}/evaluate", json={"answers": druid_answers}).json()
    spec = body["result"]["primary_specialization"]
    assert spec["guide"]["dungeon_role"] and spec["guide"]["gear"] and spec["guide"]["competes_with"]
    build = body["result"]["build"]
    assert build["status"] == "draft" and not build["allocation_pending"]
    assert [t["id"] for t in build["trees"]] == ["balance", "feral_combat", "restoration"]
    assert sum(t["points"] for t in build["trees"]) == build["points_spent"] == 51
    info = build["catalog_info"]
    assert info["source_updated"] == "2026-11-02" and info["data_status"] == "draft" and info["retrieved_at"] == "2026-11-03"
    for pick in (body["alternatives"]["alternative_specialization"], body["alternatives"]["second_specialization_in_primary_class"]):
        assert pick["guide"] and pick["build"]["trees"]


def test_the_drawn_trees_hold_exactly_the_builds_allocation_for_every_specialization():
    cfg = build_default_config()
    for b in cfg.builds:
        detail = describe_build(b, cfg, with_validation=False, with_trees=True)
        assert len(detail.trees) == 3
        ranks = {t.id: t.rank for tree in detail.trees for t in tree.talents if t.rank}
        assert ranks == dict(b.allocations), b.id
        assert all(0 <= t.rank <= t.max_rank for tree in detail.trees for t in tree.talents)
        assert all(1 <= t.column + 1 and 0 <= t.tier <= 6 for tree in detail.trees for t in tree.talents)
        assert detail.allocation_pending is False


def test_builds_without_trees_are_not_inflated_for_the_admin_lists():
    cfg = build_default_config()
    assert describe_build(cfg.builds[0], cfg).trees == []


def test_the_icon_table_covers_every_class_and_specialization():
    cfg = build_default_config()
    source = (ROOT / "app" / "static" / "icons.js").read_text(encoding="utf-8")
    for cls in cfg.classes:
        assert f'{cls.id}: "classicon_{cls.id}"' in source, cls.id
        for spec in cls.specializations:
            assert f'"{cls.id}/{spec.id}":' in source, f"{cls.id}/{spec.id}"


def test_the_quiz_view_never_appends_possible_nulls_with_the_native_method():
    """Element.append(null) writes the word "null" into the page (it once showed on every multiple-choice question)."""
    text = (ROOT / "app" / "static" / "views" / "quiz.js").read_text(encoding="utf-8")
    assert not re.search(r"\broot\.append\(|clear\(root\)\.append\(", text)
    assert "put(" in text
