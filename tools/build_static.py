"""Build the static (server-less) edition of the Oracle into a folder that any static host can serve.

    python tools/build_static.py                      # writes ./site from the built-in seed configuration
    python tools/build_static.py --out public         # another output folder
    python tools/build_static.py --config exported.json   # use a configuration exported from the admin dashboard
    python -m http.server --directory site 8080       # then open http://localhost:8080/

What it produces::

    site/index.html          the page (the same one the local app serves, switched to static mode)
    site/static/             the browser code and styles (the administration views are left out)
    site/data/oracle.json    the questions, scoring tables and builds, exported from the configuration
    site/oracle-math.pdf     the maths behind the selections (docs/oracle-math.pdf), when it exists
    site/.nojekyll           tells GitHub Pages to serve the files as they are

Every path is relative, so the folder works from a site root (https://name.github.io/) and from a project
sub-path (https://name.github.io/repo/) alike. The output folder is only ever wiped if it carries this tool's marker file.

Cache busting. Static hosts such as GitHub Pages let browsers keep each file for ten minutes, so a visitor could otherwise get
new quiz data with old code after a deploy. Every file the page loads is therefore requested with ``?v=<token>``, where the token
is a hash of everything the build publishes: the stylesheet and script tags in index.html, every module import in the browser
code, and the data file (whose address the page reads from the ``oracle-build`` meta tag). A changed build has a new token, so
its files are fetched afresh and always match each other. Only index.html itself can be up to ten minutes old.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.models import Config  # noqa: E402
from app.seed import build_default_config  # noqa: E402
from app.static_export import export_static_data  # noqa: E402
from app.version import build_info  # noqa: E402

SOURCE = ROOT / "app" / "static"
MARKER = ".oracle-static-build"
#: Browser modules only the administration dashboard uses; the static edition leaves them out.
ADMIN_ONLY = {"views/builds.js", "views/config.js", "views/editor.js", "views/inspector.js", "views/profiles.js", "views/shared.js",
              "views/simulate.js"}
MODE_TAG = '<meta name="oracle-mode" content="server">'
#: Relative module imports in the browser code: ``from "./x.js"`` and ``import("./x.js")``.
IMPORT_FROM = re.compile(r'(\bfrom\s+["\'])(\.{1,2}/[^"\']+\.js)(["\'])')
IMPORT_CALL = re.compile(r'(\bimport\(\s*["\'])(\.{1,2}/[^"\']+\.js)(["\'])')
PAGE_ASSETS = ('href="static/styles.css"', 'src="static/app.js"')


def stamp_imports(source: str, token: str) -> str:
    """Append ``?v=token`` to every relative module import, so a module is fetched afresh whenever the build changes."""
    add = lambda m: f"{m[1]}{m[2]}?v={token}{m[3]}"
    return IMPORT_CALL.sub(add, IMPORT_FROM.sub(add, source))


def content_token(parts: list[tuple[str, bytes]]) -> str:
    """A short hash of every published file's name and contents."""
    digest = hashlib.sha256()
    for name, blob in sorted(parts):
        digest.update(name.encode("utf-8") + b"\0" + blob + b"\0")
    return digest.hexdigest()[:10]


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

    page = (SOURCE / "index.html").read_text(encoding="utf-8")
    if MODE_TAG not in page:
        raise SystemExit(f"{SOURCE / 'index.html'} no longer contains {MODE_TAG}")
    for ref in PAGE_ASSETS:
        if page.count(ref) != 1:
            raise SystemExit(f"{SOURCE / 'index.html'} must contain {ref} exactly once so the build can stamp it")
    data = export_static_data(cfg, build_info())
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)

    files = [(src, src.relative_to(SOURCE).as_posix()) for src in sorted(SOURCE.rglob("*"))]
    files = [(src, rel) for src, rel in files if not (src.is_dir() or rel == "index.html" or rel in ADMIN_ONLY or src.name.startswith("."))]
    token = content_token([(f"static/{rel}", src.read_bytes()) for src, rel in files] + [("index.html", page.encode("utf-8")), ("data/oracle.json", payload.encode("utf-8"))])

    for src, rel in files:
        dest = out / "static" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix == ".js":
            dest.write_text(stamp_imports(src.read_text(encoding="utf-8"), token), encoding="utf-8")
        else:
            shutil.copyfile(src, dest)

    page = page.replace(MODE_TAG, MODE_TAG.replace("server", "static") + f'\n  <meta name="oracle-build" content="{token}">')
    for ref in PAGE_ASSETS:
        page = page.replace(ref, ref[:-1] + f'?v={token}"')
    (out / "index.html").write_text(page, encoding="utf-8")

    pdf = ROOT / "docs" / "oracle-math.pdf"            # the maths, if it has been built (python tools/build_math_pdf.py)
    if pdf.exists():
        shutil.copyfile(pdf, out / "oracle-math.pdf")
    (out / "data").mkdir()
    (out / "data" / "oracle.json").write_text(payload, encoding="utf-8")
    return {
        "token": token,
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
          f"{info['data_kb']} KB of quiz data (cache token {info['token']}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
