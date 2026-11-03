"""Shared fixtures. Tests never touch the real database in ``data/``."""
import os
import tempfile
import warnings

# ``app.main`` builds a module-level ``app`` on import; point it at a throwaway database
# before it is imported anywhere.
os.environ["ORACLE_DB"] = os.path.join(tempfile.mkdtemp(prefix="oracle-test-import-"), "import.db")
warnings.filterwarnings("ignore", message=".*httpx.*")

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.seed import build_default_config

#: A fixed, complete 30-answer set. Under the seed configuration it yields Druid / Feral Combat. It is a test
#: fixture reached by search, not a realistic persona. (Four original questions are pick-two, so their answers are pairs.)
DRUID_ANSWERS = {
    "q01": "a", "q02": "c", "q03": "c", "q04": "a", "q05": "c", "q06": "d", "q07": "b+c", "q08": "d", "q09": "a+d", "q10": "a",
    "q11": "a+c", "q12": "b", "q13": "d", "q14": "c", "q15": "a+b", "q16": "c", "q17": "6", "q18": "1", "q19": "10", "q20": "10",
    "q21": "5", "q22": "10", "q23": "1", "q24": "5", "q25": "b+c", "q26": "a+b", "q27": "b+d", "q28": "b", "q29": "b", "q30": "b",
}
ORIGINAL_ANSWERS = {k: v for k, v in DRUID_ANSWERS.items() if k <= "q16"}


def first_answers(cfg):
    """The first response to every enabled question: 'a', rating 1, or the first pair."""
    return {q.id: ("1" if q.type == "scale" else f"{q.answers[0].id}+{q.answers[1].id}" if q.type == "pick_two" else q.answers[0].id)
            for q in cfg.enabled_questions()}


@pytest.fixture
def config():
    return build_default_config()


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "oracle.db"


@pytest.fixture
def client(db_path):
    return TestClient(create_app(db_path))


@pytest.fixture
def druid_answers():
    return dict(DRUID_ANSWERS)


@pytest.fixture
def original_answers():
    return dict(ORIGINAL_ANSWERS)
