"""The version stamp on the first page: who built it, which version, which build, and when."""
from datetime import datetime, timezone
from pathlib import Path

from app.seed import build_default_config
from app.static_export import export_static_data
from app.version import APP_VERSION, DEVELOPER, DEVELOPER_URL, build_info

API = "/api/v1"
ROOT = Path(__file__).resolve().parent.parent


def test_the_build_number_is_the_ci_run_and_the_commit_is_its_short_hash():
    when = datetime(2026, 11, 3, 23, 30, tzinfo=timezone.utc)
    info = build_info(when, {"GITHUB_RUN_NUMBER": "42", "GITHUB_SHA": "abcdef1234567890"})
    assert info == {"version": APP_VERSION, "build": "42", "commit": "abcdef1", "date": "2026-11-03",
                    "developer": "Anibru", "developer_url": "https://github.com/Anibru"}


def test_the_date_is_the_utc_date_of_the_build():
    late = datetime(2026, 11, 3, 23, 59, tzinfo=timezone.utc)
    assert build_info(late, {})["date"] == "2026-11-03"
    assert build_info(datetime(2026, 11, 4, 0, 1, tzinfo=timezone.utc), {})["date"] == "2026-11-04"


def test_without_a_ci_run_the_build_is_a_commit_count_or_dev():
    info = build_info(env={})
    assert info["build"].isdigit() or info["build"] == "dev"
    assert len(info["commit"]) in (7, 8, 9, 10) or info["commit"] == "unknown"


def test_the_version_is_served_and_matches_the_health_endpoint(client):
    body = client.get(f"{API}/version").json()
    assert body["version"] == APP_VERSION == client.get(f"{API}/health").json()["app_version"]
    assert body["developer"] == DEVELOPER == "Anibru" and body["developer_url"] == DEVELOPER_URL == "https://github.com/Anibru"
    assert body["date"] and body["build"] and body["commit"]


def test_the_static_data_carries_the_build_stamp():
    info = build_info(env={"GITHUB_RUN_NUMBER": "7", "GITHUB_SHA": "1234567890"})
    assert export_static_data(build_default_config(), info)["build"] == info
    assert export_static_data(build_default_config())["build"] is None          # tests and old callers need not pass one


def test_the_first_page_credits_the_developer_with_a_link_and_no_longer_makes_the_browser_claim():
    quiz = (ROOT / "app" / "static" / "views" / "quiz.js").read_text(encoding="utf-8")
    assert "Developed by " in quiz and "https://github.com/Anibru" in quiz and "noopener noreferrer" in quiz
    assert "scored right here in your browser" not in quiz and "Nothing is stored on the server" not in quiz


def test_the_changelog_describes_the_current_version_first():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert text.split("## ")[1].startswith(f"{APP_VERSION} ·")
