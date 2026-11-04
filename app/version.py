"""The application's version and a description of the running build (shown on the first page)."""
from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional

#: Version of the application as a whole (questions, scoring, pages). See CHANGELOG.md. The scoring rules have their own
#: ``algorithm_version`` (app/seed.py).
APP_VERSION = "1.7.0"
DEVELOPER = "Anibru"
DEVELOPER_URL = "https://github.com/Anibru"

_ROOT = Path(__file__).resolve().parent.parent


def _git(*args: str) -> Optional[str]:
    try:
        out = subprocess.run(["git", *args], cwd=_ROOT, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None if out.returncode == 0 else None


def build_info(now: Optional[datetime] = None, env: Optional[Mapping[str, str]] = None) -> dict:
    """Version, build number, commit and date of this build.

    The build number is the CI run number when there is one (GitHub Actions sets GITHUB_RUN_NUMBER), otherwise the number
    of commits in the repository; the commit is the short hash. Without git history they read "dev" and "unknown".
    """
    env = os.environ if env is None else env
    now = now or datetime.now(timezone.utc)
    sha = env.get("GITHUB_SHA") or _git("rev-parse", "HEAD") or ""
    return {
        "version": APP_VERSION,
        "build": env.get("GITHUB_RUN_NUMBER") or _git("rev-list", "--count", "HEAD") or "dev",
        "commit": sha[:7] or "unknown",
        "date": now.astimezone(timezone.utc).date().isoformat(),
        "developer": DEVELOPER,
        "developer_url": DEVELOPER_URL,
    }
