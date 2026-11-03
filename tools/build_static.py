"""Build the static (server-less) edition of the Oracle into a folder that any static host can serve.

    python tools/build_static.py                      # writes ./site from the built-in seed configuration
    python tools/build_static.py --out public         # another output folder
    python tools/build_static.py --config exported.json   # use a configuration exported from the admin dashboard
    python -m http.server --directory site 8080       # then open http://localhost:8080/

What it produces::

    site/index.html          the page (the same one the local app serves, switched to static mode)
    site/static/             the browser code and styles (the administration views are left out)
    site/data/oracle.json    the questions, scoring tables and builds, exported from the configuration
    site/.nojekyll           tells GitHub Pages to serve the files as they are

Every path is relative, so the folder works from a site root (https://name.github.io/) and from a project
sub-path (https://name.github.io/repo/) alike. The output folder is only ever wiped if it carries this tool's marker file.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.models import Config  # noqa: E402
from app.seed import build_default_config  # noqa: E402
from app.static_export import export_static_data  # noqa: E402

SOURCE = ROOT / "app" / "static"
MARKER = ".oracle-static-build"
#: Browser modules only the administration dashboard uses; the static edition leaves them out.
ADMIN_ONLY = {"views/builds.js", "views/config.js", "views/editor.js", "views/inspector.js", "views/profiles.js", "views/shared.js",
              "views/simulate.js"}
MODE_TAG = '<meta name="oracle-mode" content="server">'


def clean(out: Path) -> None:
    if out.exists():
        if not (out / MARKER).exists():
            if any(out.iterdir()):
                raise SystemExit(f"Refusing to overwrite '{out}': it is not empty and was not created by this tool.")
        else:
            shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)


def build(out: Path, cfg: Config) -> dict:
    clean(out)
    (out / MARKER).write_text("Created by tools/build_static.py. Safe to delete or rebuild.\n")
    (out / ".nojekyll").write_text("")

    for src in sorted(SOURCE.rglob("*")):
        rel = src.relative_to(SOURCE).as_posix()
        if src.is_dir() or rel == "index.html" or rel in ADMIN_ONLY or src.name.startswith("."):
            continue
        dest = out / "static" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)

    page = (SOURCE / "index.html").read_text(encoding="utf-8")
    if MODE_TAG not in page:
        raise SystemExit(f"{SOURCE / 'index.html'} no longer contains {MODE_TAG}")
    (out / "index.html").write_text(page.replace(MODE_TAG, MODE_TAG.replace("server", "static")), encoding="utf-8")

    data = export_static_data(cfg)
    (out / "data").mkdir()
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    (out / "data" / "oracle.json").write_text(payload, encoding="utf-8")
    return {
        "out": str(out),
        "questions": len(data["quiz"]["questions"]),
        "builds": len(data["builds"]),
        "data_kb": round(len(payload.encode("utf-8")) / 1024, 1),
        "files": sum(1 for p in out.rglob("*") if p.is_file()),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="site", help="output folder (default: ./site)")
    ap.add_argument("--config", help="configuration JSON exported from the admin dashboard (default: the built-in seed)")
    args = ap.parse_args(argv)
    cfg = Config.model_validate_json(Path(args.config).read_text(encoding="utf-8")) if args.config else build_default_config()
    info = build(Path(args.out).resolve(), cfg)
    print(f"Built {info['files']} files into {info['out']}: {info['questions']} questions, {info['builds']} builds, "
          f"{info['data_kb']} KB of quiz data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
