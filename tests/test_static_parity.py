"""The static edition scores in the browser; its engine (app/static/engine.js) must agree with the Python engine exactly.

Every case runs the same answers through ``scoring.evaluate`` (plus the builds the API attaches) and through the JavaScript
engine under node, then compares the complete JSON documents: scores, ranks, ties, wording, builds, metadata.
"""
import json
import math
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from app import scoring
from app.models import Config
from app.public import public_quiz, with_builds
from app.seed import build_default_config
from app.static_export import export_static_data

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")
SCRIPT = Path(__file__).with_name("static_parity.mjs")


def run_node(job: dict) -> dict:
    done = subprocess.run([NODE, str(SCRIPT)], input=json.dumps(job), capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def random_answers(cfg: Config, rng: random.Random) -> dict[str, str]:
    out = {}
    for q in cfg.enabled_questions():
        if q.type == "scale":
            out[q.id] = str(rng.randint(1, 10))
        elif q.type == "pick_two":
            a, b = rng.sample([x.id for x in q.answers], 2)
            out[q.id] = f"{a}+{b}"                                  # either order: the engine normalizes it
        else:
            out[q.id] = rng.choice(q.answers).id
    return out


def expected(cfg: Config, answers: dict) -> dict:
    try:
        ev = with_builds(cfg, scoring.evaluate(cfg, answers, include_explanation=False))
    except scoring.IncompleteAssessmentError:
        return {"error": "incomplete_assessment"}
    except scoring.UnknownQuestionError:
        return {"error": "unknown_question"}
    except scoring.UnknownAnswerError:
        return {"error": "unknown_answer"}
    return ev.model_dump(mode="json", exclude_none=True)


def edited_config() -> Config:
    """A configuration changed the way an administrator might: fractional weights, other multipliers and margins."""
    cfg = build_default_config()
    rng = random.Random(7)
    for q in cfg.questions:
        for a in q.answers:
            for k in list(a.class_weights):
                a.class_weights[k] = round(rng.choice([0.25, 0.5, 1.0, 1.5, 2.0, 3.0]), 2)
            for k in list(a.trait_weights):
                a.trait_weights[k] = round(rng.choice([0.125, 0.5, 1.0, 2.0]), 3)
    for cl in cfg.classes:
        for s in cl.specializations:
            s.trait_multipliers = {k: round(v * 1.1, 3) for k, v in s.trait_multipliers.items()}
    cfg.scoring.spec_weight_multiplier = 2.5
    cfg.scoring.confidence_margins.strong = 2.5
    cfg.scoring.confidence_margins.moderate = 0.75
    cfg.scoring.class_tie_break_order = list(reversed(cfg.scoring.class_tie_break_order))
    cfg.questions[-1].enabled = False                                   # a disabled question is not part of the quiz
    return cfg


def all_zero_config() -> Config:
    """Every answer is worth nothing: every score ties, so the tie-break rules decide everything."""
    cfg = build_default_config()
    for q in cfg.questions:
        for a in q.answers:
            a.class_weights, a.trait_weights, a.spec_weights = {}, {}, {}
    return cfg


CONFIGS = {"seed": build_default_config, "edited": edited_config, "all-tied": all_zero_config}


@pytest.mark.parametrize("name", CONFIGS)
def test_browser_engine_matches_python_engine(name):
    cfg = CONFIGS[name]()
    rng = random.Random(f"parity-{name}")
    answer_sets = [random_answers(cfg, rng) for _ in range(40)]
    answer_sets.append({k: v for k, v in answer_sets[0].items() if k != "q05"})                 # incomplete
    answer_sets.append({**answer_sets[1], "q99": "a"})                                          # unknown question
    answer_sets.append({**answer_sets[2], "q01": "zzz"})                                        # unknown answer
    answer_sets.append({**answer_sets[3], "q01": "a+a" if cfg.get_question("q01").type == "pick_two" else "nope"})
    got = run_node({"cases": [{"data": export_static_data(cfg), "answers": answer_sets}]})["cases"][0]
    for k, (answers, js) in enumerate(zip(answer_sets, got)):
        assert js == expected(cfg, answers), f"{name}: answer set {k} differs"


def test_api_and_browser_engine_agree_through_http(client):
    cfg = client.get("/api/v1/config").json()
    rng = random.Random("http")
    config = Config.model_validate(cfg)
    answer_sets = [random_answers(config, rng) for _ in range(8)]
    got = run_node({"cases": [{"data": export_static_data(config), "answers": answer_sets}]})["cases"][0]
    for answers, js in zip(answer_sets, got):
        r = client.post("/api/v1/evaluate", json={"answers": answers, "include_explanation": False})
        assert r.status_code == 200
        assert js == r.json()


def test_exported_quiz_equals_the_api_quiz(client):
    cfg = build_default_config()
    assert export_static_data(cfg)["quiz"] == client.get("/api/v1/quiz").json()
    assert public_quiz(cfg).model_dump(mode="json") == client.get("/api/v1/quiz").json()


def test_the_quiz_part_of_the_data_carries_no_weights_but_the_engine_part_does():
    """The static trade-off, stated plainly: the scoring weights are in the data file (the quiz part never shows them)."""
    data = export_static_data(build_default_config())
    assert not any(k.endswith("weights") for q in data["quiz"]["questions"] for k in q)
    assert not any(k.endswith("weights") for q in data["quiz"]["questions"] for a in q["answers"] for k in a)
    assert data["engine"]["questions"][0]["class_raw"]


# ------------------------------------------------------------------------------------ numeric helpers


def python_number_view(x: float):
    return [round(x, 9) + 0.0, round(x, 10) + 0.0, f"{x:+.2f}", f"{x:g}"]


def test_number_formatting_matches_python_including_exact_ties():
    rng = random.Random(11)
    xs = [0.0, -0.0, 0.5, -0.5, 0.125, -0.125, 0.375, 1.005, 2.675, 1e-12, -1e-12, 4.5, 13.39, 123456.0, 0.0001, 0.00001234,
          1234567.0, 1 / 3, 2 / 9, 5e-10, 1.5e-9]
    xs += [k / 2048 for k in range(1, 400, 2)] + [-k / 2048 for k in range(1, 200, 2)]    # exact ties at 10 decimals
    xs += [k / 1024 for k in range(1, 400, 2)]                                             # exact ties at 9 decimals
    xs += [k / 8 for k in range(-40, 40)]                                                  # exact ties at 2 decimals
    xs += [rng.uniform(-20, 20) for _ in range(500)] + [rng.uniform(-1, 1) * 10 ** rng.randint(-8, 5) for _ in range(500)]
    got = run_node({"numbers": xs})["numbers"]
    for x, js in zip(xs, got):
        assert js == python_number_view(x), x


def test_exact_summation_matches_math_fsum():
    rng = random.Random(5)
    lists = [[], [0.1] * 10, [1e16, 1.0, -1e16], [0.1, 0.2, 0.3], [1 / 3] * 7 + [-1 / 3] * 7]
    for _ in range(300):
        lists.append([rng.uniform(-3, 3) * rng.choice([1, 1 / 9, 1 / 6, 0.25, 4.5]) for _ in range(rng.randint(1, 40))])
    got = run_node({"sums": lists})["sums"]
    for xs, js in zip(lists, got):
        assert js == math.fsum(xs), xs
