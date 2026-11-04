"""The shareable blurb: a template an administrator can edit, filled in from the result."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.models import DEFAULT_SHARE_TEMPLATE, SHARE_FIELDS
from app.seed import build_default_config
from app.static_export import export_static_data

API = "/api/v1"
ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")


def run_share(snippet: str):
    """Run snippet under node with share.js imported (through a data: URL, like engine.js in the parity tests)."""
    import base64
    source = (ROOT / "app" / "static" / "share.js").read_bytes()
    script = (f'const m = await import("data:text/javascript;base64,{base64.b64encode(source).decode()}");\n'
              f'const out = await (async (m) => {{ {snippet} }})(m);\nprocess.stdout.write(JSON.stringify(out));')
    done = subprocess.run([NODE, "--input-type=module", "-e", script], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def rev(client):
    return client.get(f"{API}/health").json()["config_revision"]


# ------------------------------------------------------------------ the template and its placeholders (browser code under node)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_default_blurb_names_the_result_the_numbers_and_a_link():
    text = run_share('return m.renderShare(m.DEFAULT_SHARE_TEMPLATE, m.shareValues(m.SAMPLE_RESULT, { link: "https://example.test/oracle/", title: "T" }));')
    assert "Feral Combat Druid" in text and "Druid +13.39 · Hunter +3.08 · Shaman +2.97" in text
    assert "Mage" not in text.split("Class scores:")[1].split("\n")[0]                       # only the top three classes
    assert text.splitlines()[1] == "Class scores: Druid +13.39 · Hunter +3.08 · Shaman +2.97"           # no parenthesis after the scores
    assert "Also in the stars" not in text and "(" not in text and len(text.splitlines()) == 3
    assert text.rstrip().endswith("https://example.test/oracle/")


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_browser_and_the_server_agree_on_the_placeholders_and_the_default():
    got = run_share("return { names: m.SHARE_FIELDS.map((f) => f[0]), template: m.DEFAULT_SHARE_TEMPLATE };")
    assert got["names"] == list(SHARE_FIELDS)
    assert got["template"] == DEFAULT_SHARE_TEMPLATE


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_every_placeholder_gets_a_value_and_an_unknown_one_is_left_as_written():
    got = run_share('''const v = m.shareValues(m.SAMPLE_RESULT, { link: "L", title: "T" });
      return { values: v, text: m.renderShare("{class}/{spec}/{nope}/{link}", v) };''')
    assert set(got["values"]) == set(SHARE_FIELDS) and all(isinstance(x, str) and x for x in got["values"].values())
    assert got["text"] == "Druid/Feral Combat/{nope}/L"


def test_the_participant_page_builds_its_blurb_from_the_configured_template():
    quiz = (ROOT / "app" / "static" / "views" / "quiz.js").read_text(encoding="utf-8")
    assert "state.quiz.share_template" in quiz and "renderShare" in quiz and 'id: "share-text"' in quiz
    assert "The stars say I'm" not in quiz                                              # the wording lives in the template and never in the page


# ------------------------------------------------------------------ the admin can change it


def test_the_template_is_public_and_starts_as_the_default(client):
    assert client.get(f"{API}/quiz").json()["share_template"] == DEFAULT_SHARE_TEMPLATE
    assert client.get(f"{API}/config").json()["quiz"]["share_template"] == DEFAULT_SHARE_TEMPLATE


def test_an_admin_can_change_the_template_and_it_persists_and_reaches_participants(client, db_path):
    template = "I am a {class} ({spec}) with {class_scores}. Try it: {link}\n#{quiz_length}"
    r = client.patch(f"{API}/quiz", json={"expected_revision": rev(client), "share_template": template})
    assert r.status_code == 200 and r.json()["quiz"]["share_template"] == template
    assert client.get(f"{API}/quiz").json()["share_template"] == template
    from fastapi.testclient import TestClient
    from app.main import create_app
    assert TestClient(create_app(db_path)).get(f"{API}/quiz").json()["share_template"] == template      # survives a restart
    assert client.get(f"{API}/config/history").json()[0]["change_type"] == "quiz"


@pytest.mark.parametrize("bad,why", [
    ("Hello {nobody}", "unknown placeholder"),
    ("Broken {class", "unmatched brace"),
    ("Stray } brace", "unmatched brace"),
])
def test_a_template_with_an_unknown_placeholder_or_a_stray_brace_is_refused(client, bad, why):
    before = rev(client)
    r = client.patch(f"{API}/quiz", json={"expected_revision": before, "share_template": bad})
    assert r.status_code == 400, why
    assert any(("placeholder" in e) or ("brace" in e) for e in r.json()["detail"]["errors"])
    assert rev(client) == before                                                         # nothing was saved


def test_an_empty_or_enormous_template_is_a_schema_error(client):
    assert client.patch(f"{API}/quiz", json={"expected_revision": rev(client), "share_template": ""}).status_code == 422
    assert client.patch(f"{API}/quiz", json={"expected_revision": rev(client), "share_template": "x" * 1001}).status_code == 422


def test_a_stale_revision_does_not_overwrite_the_template(client):
    assert client.patch(f"{API}/quiz", json={"expected_revision": 99, "share_template": "{class}"}).status_code == 409


def test_editing_the_template_requires_the_admin_token_when_one_is_set(db_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    c = TestClient(create_app(db_path, admin_token="secret"))
    body = {"expected_revision": 1, "share_template": "{class}"}
    assert c.patch(f"{API}/quiz", json=body).status_code == 401
    assert c.patch(f"{API}/quiz", json=body, headers={"Authorization": "Bearer secret"}).status_code == 200
    assert c.get(f"{API}/quiz").status_code == 200                                       # participants still read it freely


def test_the_template_travels_with_an_export_import_and_into_the_static_site(client):
    template = "{class} - {spec}: {link}"
    client.patch(f"{API}/quiz", json={"expected_revision": rev(client), "share_template": template})
    exported = client.get(f"{API}/config/export").json()
    assert exported["quiz"]["share_template"] == template
    client.post(f"{API}/config/reset", json={"expected_revision": rev(client), "confirm": True})
    assert client.get(f"{API}/quiz").json()["share_template"] == DEFAULT_SHARE_TEMPLATE
    r = client.post(f"{API}/config/import", json={"expected_revision": rev(client), "config": exported})
    assert r.status_code == 200 and client.get(f"{API}/quiz").json()["share_template"] == template
    from app.models import Config
    assert export_static_data(Config.model_validate(exported))["quiz"]["share_template"] == template


def test_a_database_saved_before_the_template_existed_reads_the_default(tmp_path):
    from app.database import connect
    from app.repository import Repository
    repo = Repository(tmp_path / "old.db")
    repo.initialize()
    conn = connect(tmp_path / "old.db")
    meta = json.loads(conn.execute("SELECT value FROM meta WHERE key = 'quiz'").fetchone()[0])
    del meta["share_template"]
    conn.execute("UPDATE meta SET value = ? WHERE key = 'quiz'", (json.dumps(meta),))
    conn.commit()
    conn.close()
    repo._cache = None
    assert repo.get_config().quiz.share_template == DEFAULT_SHARE_TEMPLATE


def test_the_default_template_only_uses_known_placeholders():
    import re
    assert set(re.findall(r"\{(\w+)\}", DEFAULT_SHARE_TEMPLATE)) <= set(SHARE_FIELDS)
    assert build_default_config().quiz.share_template == DEFAULT_SHARE_TEMPLATE
