"""Suggest class-weight intensities that make every class equally likely to be chosen under random answers, at every quiz length.

    python tools/equalize_classes.py                  # starts from the seed
    python tools/equalize_classes.py --n 100000 --config exported.json

Developer tool (needs numpy; see requirements-dev.txt). It is how ``CLASS_WEIGHTS`` in app/seed_tuning.py was found.

Each answer favours two classes, a primary one (weight 2) and a secondary one (weight 1). This tool never changes *which*
classes an answer favours, and it keeps every answer's two weights adding up to 3, so the class scores of a complete answer set
still sum to zero (the scores stay a zero-sum comparison). It only moves weight between the two, a quarter point at a time:
anywhere from (2.5, 0.5) through the usual (2, 1) to an even (1.5, 1.5). A greedy search takes whichever single move brings the nine classes' shares closest to an even 1/9 across the
short, medium and long quizzes together, measured on one fixed set of random answer sets, and stops when nothing improves.
Questions named by ``--freeze`` (by default Q01, the worked example in the documentation) are left alone. It prints a
``CLASS_WEIGHTS`` table and changes nothing; read it before using it, and check the result on a different sample with
``python tools/balance.py report --seed 4242``.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.models import LENGTHS, Config  # noqa: E402
from app.scoring import active_questions, response_coefficients  # noqa: E402
from app.seed import build_default_config  # noqa: E402
from balance import Sim  # noqa: E402

STEP = 0.25
PRIMARY_RANGE = (1.5, 2.5)         # with the two weights summing to 3: (1.5, 1.5), (2, 1) or (2.5, 0.5)


class Equalizer:
    def __init__(self, cfg: Config, n: int = 60000, seed: int = 31):
        self.cfg = cfg
        self.sim = sim = Sim(cfg, n=n, seed=seed)
        self.n = n
        c = sim.c
        self.pos = {q.id: k for k, q in enumerate(c.questions)}
        self.active = {length: set(active_questions(c, length)) for length in LENGTHS}
        self.order = np.asarray(sim._class_order)
        self.class_index = {cid: i for i, cid in enumerate(c.class_ids)}
        self.totals = {}
        for length, active in self.active.items():
            t = np.zeros((n, c.n_classes))
            for k in active:
                t += np.asarray(c.questions[k].class_delta)[sim.idx[:, k]]
            self.totals[length] = t
        self._coef: dict[tuple[str, int], np.ndarray] = {}

    def shares(self, length: str) -> np.ndarray:
        t = self.totals[length]
        winner = self.order[np.argmax(np.round(t[:, self.order], 9), axis=1)]
        return np.bincount(winner, minlength=t.shape[1]) / self.n

    def objective(self) -> float:
        target = 1 / self.sim.c.n_classes
        return sum(float(np.sum((self.shares(length) - target) ** 2)) for length in LENGTHS)

    def spread(self) -> dict[str, tuple[float, float]]:
        return {length: (float(self.shares(length).min()), float(self.shares(length).max())) for length in LENGTHS}

    def _centred(self, q, ai: int) -> np.ndarray:
        key = (q.id, ai)
        if key not in self._coef:
            v = np.array([row[2][ai] for row in response_coefficients(q)])
            self._coef[key] = v - v.mean()
        return self._coef[key]

    def shift(self, q, ai: int, cls: str, delta: float) -> None:
        """Change one answer's weight for one class by ``delta`` (and update every length's totals)."""
        k = self.pos[q.id]
        diff = delta * self._centred(q, ai)[self.sim.idx[:, k]]
        for length, active in self.active.items():
            if k in active:
                self.totals[length][:, self.class_index[cls]] += diff
        q.answers[ai].class_weights[cls] += delta

    def transfer(self, q, ai: int, delta: float) -> None:
        """Move ``delta`` of weight from the secondary class to the primary one (negative: the other way)."""
        a = q.answers[ai]
        primary = max(a.class_weights, key=a.class_weights.get)
        secondary = next(k for k in a.class_weights if k != primary)
        self.shift(q, ai, primary, delta)
        self.shift(q, ai, secondary, -delta)

    def allowed(self, a, delta: float) -> bool:
        if len(a.class_weights) != 2 or abs(sum(a.class_weights.values()) - 3.0) > 1e-9:
            return False                      # only the usual two-class, total-3 answers are adjusted
        primary = max(a.class_weights.values())
        return PRIMARY_RANGE[0] - 1e-9 <= primary + delta <= PRIMARY_RANGE[1] + 1e-9

    def run(self, freeze: tuple[str, ...] = (), max_steps: int = 300):
        current, moves, t0 = self.objective(), [], time.time()
        for step in range(max_steps):
            best = None
            for q in self.cfg.enabled_questions():
                if q.id in freeze:
                    continue
                for ai, a in enumerate(q.answers):
                    for delta in (-STEP, STEP):
                        if not self.allowed(a, delta):
                            continue
                        self.transfer(q, ai, delta)
                        o = self.objective()
                        self.transfer(q, ai, -delta)
                        if best is None or o < best[0]:
                            best = (o, q, ai, delta)
            if best is None or best[0] >= current - 1e-9:
                break
            current, q, ai, delta = best
            self.transfer(q, ai, delta)
            moves.append((q.id, q.answers[ai].id, delta))
            if step % 5 == 0:
                spread = {k: f"{100 * lo:.2f}-{100 * hi:.2f}%" for k, (lo, hi) in self.spread().items()}
                print(f"step {step + 1:3d} ({time.time() - t0:3.0f}s) {spread}", flush=True)
        return moves


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", help="exported configuration JSON (default: the seed)")
    ap.add_argument("--n", type=int, default=60000, help="random answer sets used by the search (more = less chance of fitting noise)")
    ap.add_argument("--seed", type=int, default=31)
    ap.add_argument("--freeze", nargs="*", default=["q01"], help="question ids to leave alone (default: q01)")
    args = ap.parse_args(argv)
    cfg = Config.model_validate_json(Path(args.config).read_text()) if args.config else build_default_config()
    before = {(q.id, a.id): dict(a.class_weights) for q in cfg.enabled_questions() for a in q.answers}
    eq = Equalizer(cfg, n=args.n, seed=args.seed)
    eq.run(freeze=tuple(args.freeze))
    print("\nCLASS_WEIGHTS = {")
    for q in cfg.enabled_questions():
        for a in q.answers:
            if dict(a.class_weights) != before[(q.id, a.id)]:
                items = ", ".join(f'"{k}": {v:g}' for k, v in a.class_weights.items())
                print(f'    ("{q.id}", "{a.id}"): {{{items}}},')
    print("}")
    for length, (lo, hi) in eq.spread().items():
        print(f"{length}: classes {100 * lo:.2f}% to {100 * hi:.2f}% (an even split is {100 / eq.sim.c.n_classes:.2f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
