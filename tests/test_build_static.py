"""tools/build_static.py writes a self-contained folder that any static host can serve from any path."""
import importlib.util
import json
import re
from pathlib import Path

import pytest

from app.seed import build_default_config

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location("build_static", ROOT / "tools" / "build_static.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def site(tool, tmp_path_factory):
    out = tmp_path_factory.mktemp("pages") / "site"
    tool.build(out, build_default_config())
    return out


def test_the_site_has_the_page_the_browser_code_and_the_data(site):
    for rel in ["index.html", ".nojekyll", "data/oracle.json", "static/app.js", "static/api.js", "static/engine.js",
                "static/styles.css", "static/views/quiz.js"]:
        assert (site / rel).is_file(), rel
    data = json.loads((site / "data" / "oracle.json").read_text(encoding="utf-8"))
    assert len(data["quiz"]["questions"]) == 30 and len(data["builds"]) == 27 and data["format"] == 1
    # the published builds are the draft ones with their trees, not "allocation pending" placeholders
    assert {b["status"] for b in data["builds"].values()} == {"draft"} and all(len(b["trees"]) == 3 for b in data["builds"].values())
    assert all(s["guide"] for cl in data["engine"]["classes"] for s in cl["specs"])
    assert (site / "oracle-math.pdf").is_file() == (ROOT / "docs" / "oracle-math.pdf").exists()        # the maths PDF travels with the site
    # the three quiz lengths travel with the data, and each question says which lengths ask it
    assert [(l["id"], l["question_count"]) for l in data["quiz"]["lengths"]] == [("adaptive", 30), ("short", 10), ("medium", 20), ("long", 30)]
    assert data["quiz"]["default_length"] == "adaptive" and data["engine"]["adaptive"]["confidence"] == 0.9
    assert sorted({q["length_rank"] for q in data["engine"]["questions"]}) == [0, 1, 2]


def test_the_page_is_switched_to_static_mode_and_uses_only_relative_paths(site):
    page = (site / "index.html").read_text(encoding="utf-8")
    assert '<meta name="oracle-mode" content="static">' in page and 'content="server"' not in page
    refs = re.findall(r'(?:href|src)="([^"#]+)"', page)
    local = [r for r in refs if not r.startswith(("data:", "http"))]
    assert local and not any(r.startswith("/") for r in local), local
    for r in local:
        assert (site / r).is_file(), r
    for js in (site / "static").rglob("*.js"):                       # no script reaches for a root-relative path
        assert not re.search(r'fetch\(\s*["\']/', js.read_text(encoding="utf-8")), js


def test_the_administration_views_are_not_published(site, tool):
    assert {p.name for p in (site / "static" / "views").iterdir()} == {"quiz.js", "specs.js"}
    assert not any((site / "static" / rel).exists() for rel in tool.ADMIN_ONLY)


def test_every_static_import_resolves_inside_the_published_folder(site):
    """Static imports must all resolve. Dynamic import()s may only point at the admin views left out on purpose."""
    missing_dynamic = set()
    for js in (site / "static").rglob("*.js"):
        text = js.read_text(encoding="utf-8")
        for target in re.findall(r'\bfrom\s+["\'](\.{1,2}/[^"\']+)["\']', text):
            assert (js.parent / target).resolve().is_file(), f"{js.name} imports {target}"
        for target in re.findall(r'\bimport\(\s*["\'](\.{1,2}/[^"\']+)["\']\s*\)', text):
            if not (js.parent / target).resolve().is_file():
                missing_dynamic.add((js.parent / target).resolve().relative_to((site / "static").resolve()).as_posix())
    assert missing_dynamic <= {"views/builds.js", "views/config.js", "views/editor.js", "views/inspector.js", "views/profiles.js",
                               "views/simulate.js"}, missing_dynamic          # (views/shared.js is only ever imported by those)


def test_rebuilding_replaces_the_old_output_but_never_a_foreign_folder(tool, tmp_path):
    out = tmp_path / "site"
    tool.build(out, build_default_config())
    (out / "stale.txt").write_text("old")
    tool.build(out, build_default_config())
    assert not (out / "stale.txt").exists() and (out / "index.html").is_file()

    foreign = tmp_path / "my-documents"
    foreign.mkdir()
    (foreign / "keep.txt").write_text("precious")
    with pytest.raises(SystemExit):
        tool.build(foreign, build_default_config())
    assert (foreign / "keep.txt").read_text() == "precious"


def test_the_github_workflow_publishes_the_site_folder_after_testing():
    text = (ROOT / ".github" / "workflows" / "pages.yml").read_text()
    for needle in ["pytest", "tools/build_static.py --out site", "path: site", "actions/deploy-pages", "pages: write", "id-token: write"]:
        assert needle in text, needle
    assert text.index("pytest") < text.index("build_static.py") < text.index("deploy-pages")
