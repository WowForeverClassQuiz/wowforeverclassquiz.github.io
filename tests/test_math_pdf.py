"""The maths PDF is generated from the live configuration; check that it builds and carries the numbers it should."""
import importlib.util
import math
from pathlib import Path

import pytest

pytest.importorskip("reportlab")
pytest.importorskip("matplotlib")
pytest.importorskip("numpy")
pypdf = pytest.importorskip("pypdf")

from app.seed import build_default_config  # noqa: E402
from app.version import APP_VERSION  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def text(tmp_path_factory):
    spec = importlib.util.spec_from_file_location("build_math_pdf", ROOT / "tools" / "build_math_pdf.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = tmp_path_factory.mktemp("pdf") / "math.pdf"
    info = mod.build(build_default_config(), out, quick=True)
    reader = pypdf.PdfReader(str(out))
    assert info["pages"] == len(reader.pages) >= 12
    return "\n".join(p.extract_text() for p in reader.pages)


def test_the_pdf_has_every_section_and_the_confidence_model(text):
    for needle in ["The pipeline in one page", "Questions and responses", "Baseline subtraction", "Class and trait scores", "Specialization scores",
                   "Reading the gap", "Quiz lengths and balance", "Confidence mode", "A worked example", "Assumptions and limits",
                   "Appendix A", "Appendix B", "The choice model", "expected information gain", f"v{APP_VERSION}"]:
        assert needle in text, needle


def test_the_margin_table_matches_the_scaling_rule(text):
    for n in (10, 20, 30):
        strong = 3.0 * math.sqrt(n / 30)
        assert f"{strong:.3f}" in text, n


def test_the_worked_example_and_the_balance_tables_are_present(text):
    assert "Druid Feral Combat" in text and "Table 16" in text and "Table 8" in text
    assert text.count("Warlock") > 20 and "Destruction" in text


def test_every_answer_is_in_the_weights_appendix(text):
    cfg = build_default_config()
    for q in cfg.enabled_questions():
        for a in q.answers:
            label = a.id.upper() if len(a.id) == 1 else a.id
            assert f"{q.id.upper()} {label}" in text, (q.id, a.id)


def test_the_committed_pdf_exists_and_is_current_enough_to_describe_this_version():
    pdf = ROOT / "docs" / "oracle-math.pdf"
    assert pdf.exists() and pdf.stat().st_size > 100_000
    first = pypdf.PdfReader(str(pdf)).pages[0].extract_text()
    assert f"version {APP_VERSION}" in first.replace("\n", " ")
