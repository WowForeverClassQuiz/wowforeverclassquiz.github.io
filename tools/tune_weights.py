"""Suggest direct specialization weights that keep every specialization above a target share at every quiz length.

    python tools/tune_weights.py                    # starts from the seed, target 30%
    python tools/tune_weights.py --target 0.32 --config exported.json

Developer tool (needs numpy; see requirements-dev.txt). It is how the weights in app/seed_tuning.py were found. A greedy
search adds one point of direct weight at a time to whichever answer most reduces how far the weakest specializations of
each length fall below the target, measured on a fixed set of random answer sets shared by all lengths. It only adds weight
to an answer that already favours the specialization's class and whose trait weights fit the specialization's profile, never
beyond 3, and it never removes weight, so what it proposes stays explainable. It prints suggestions; it changes nothing.

``BANNED`` lists proposals the search found useful but a person judged not to fit the answer's meaning. Every suggestion
should still be read by a person before it goes into app/seed_tuning.py.
"""
from __future__ import annotations

import argparse
import itertools
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.models import LENGTHS, Config  # noqa: E402
from app.scoring import SCALE_MAX, SCALE_MIN, active_questions, response_coefficients  # noqa: E402
from app.seed import build_default_config  # noqa: E402
from balance import Sim  # noqa: E402

#: (question, answer, "class/spec") proposals that do not fit what the answer means.
BANNED = {
    ("q13", "c", "priest/shadow"), ("q03", "c", "druid/balance"), ("q09", "a", "warrior/arms"), ("q25", "a", "paladin/holy"),
    ("q25", "b", "druid/feral_combat"), ("q17", "agree", "warrior/fury"), ("q27", "b", "paladin/retribution"),
    ("q06", "c", "rogue/assassination"), ("q23", "agree", "warrior/arms"), ("q10", "a", "druid/balance"),
    ("q04", "a", "druid/balance"), ("q12", "d", "hunter/marksmanship"), ("q25", "b", "druid/balance"),
    ("q26", "a", "druid/balance"), ("q18", "disagree", "rogue/assassination"), ("q11", "b", "druid/feral_combat"),
    ("q06", "b", "paladin/retribution"), ("q10", "b", "hunter/marksmanship"),
}
MAX_WEIGHT = 3


def fit(cfg: Config, answer, key: str) -> float:
    """How well an answer's trait weights match a specialization's trait profile."""
    cls, spec = key.split("/")
    profile = cfg.get_spec(cls, spec).trait_multipliers
    return sum(m * answer.trait_weights.get(t, 0) for t, m in profile.items())


class Tuner:
    def __init__(self, cfg: Config, n: int = 20000, seed: int = 21):
        self.cfg = cfg
        self.sim = sim = Sim(cfg, n=n, seed=seed)
        c = sim.c
        self.mult = c.spec_multiplier
        self.pos = {q.id: k for k, q in enumerate(c.questions)}
        self.keys = [f"{cl.id}/{sp.id}" for cl in cfg.classes for sp in cl.specializations]
        self.class_index = {cl.id: i for i, cl in enumerate(cfg.classes)}
        self.lengths = {}
        for length in LENGTHS:
            try:
                self.lengths[length] = set(active_questions(c, length))
            except ValueError:
                continue
        # per-length totals over the shared random answers
        self.trait_tot, self.spec_direct, self.rows = {}, {}, {}
        for length, active in self.lengths.items():
            ct = np.zeros((n, c.n_classes))
            tt, sd = np.zeros((n, c.n_traits)), np.zeros((n, c.n_specs))
            for k in active:
                q, col = c.questions[k], sim.idx[:, k]
                ct += np.asarray(q.class_delta)[col]
                tt += np.asarray(q.trait_delta)[col]
                sd += np.asarray(q.spec_delta)[col]
            order = sim._class_order
            winner = np.asarray(order)[np.argmax(np.round(ct[:, order], 9), axis=1)]
            self.rows[length] = [np.nonzero(winner == ci)[0] for ci in range(c.n_classes)]
            self.trait_tot[length], self.spec_direct[length] = tt, sd
        self._refresh()

    def _refresh(self):
        s, c = self.sim, self.sim.c
        self.base, self.direct = {}, {}
        for length in self.lengths:
            for ci in range(c.n_classes):
                r = self.rows[length][ci]
                self.base[length, ci] = self.trait_tot[length][r] @ s.W[ci].T
                self.direct[length, ci] = self.mult * self.spec_direct[length][r][:, s.gidx[ci]]

    def shares(self, length: str, ci: int, direct=None) -> np.ndarray:
        r = self.rows[length][ci]
        if len(r) == 0:
            return np.zeros(len(self.sim.W[ci]))
        scores = self.base[length, ci] + (self.direct[length, ci] if direct is None else direct)
        return np.bincount(np.argmax(np.round(scores, 9), axis=1), minlength=scores.shape[1]) / len(r)

    def shortfall(self, length: str, ci: int, target: float, shares=None) -> float:
        s = self.shares(length, ci) if shares is None else shares
        return float(np.sum(np.maximum(0.0, target - s) ** 2))

    def table(self) -> dict[str, dict[str, float]]:
        s = self.sim
        return {length: {self.keys[g]: float(v) for ci in range(s.c.n_classes) for g, v in zip(s.gidx[ci], self.shares(length, ci))}
                for length in self.lengths}

    def column(self, q, answer_index: int, delta: int) -> np.ndarray:
        """How one more point on one answer shifts the question's baseline-subtracted weight for each possible response."""
        coef = np.array([row[2][answer_index] for row in response_coefficients(q)])
        return (delta * (coef - coef.mean()))[self.sim.idx[:, self.pos[q.id]]]

    def move(self, q, ai: int, key: str, apply: bool = False) -> float:
        """Change in total shortfall from adding one point to answer ``ai`` for specialization ``key`` (and apply it if asked)."""
        g, ci = self.keys.index(key), self.class_index[key.split("/")[0]]
        j = list(self.sim.gidx[ci]).index(g)
        diff = self.column(q, ai, 1)
        total = 0.0
        for length, active in self.lengths.items():
            if self.pos[q.id] not in active:
                continue
            r = self.rows[length][ci]
            dd = self.direct[length, ci].copy()
            dd[:, j] += self.mult * diff[r]
            total += self.shortfall(length, ci, self.target, self.shares(length, ci, dd)) - self.shortfall(length, ci, self.target)
            if apply:
                self.spec_direct[length][:, g] += diff
                self.direct[length, ci] = dd
        return total

    def run(self, target: float, max_steps: int = 300):
        self.target = target
        proposals = []
        t0 = time.time()
        for step in range(max_steps):
            table = self.table()
            low = {k for shares in table.values() for k, v in shares.items() if v < target}
            best = None
            for q in self.cfg.enabled_questions():
                for ai, a in enumerate(q.answers):
                    for key in low:
                        cls = key.split("/")[0]
                        if (q.id, a.id, key) in BANNED or not a.class_weights.get(cls, 0):
                            continue
                        if a.spec_weights.get(key, 0) >= MAX_WEIGHT or fit(self.cfg, a, key) <= 0:
                            continue
                        delta = self.move(q, ai, key) + 0.0002          # a small cost per point keeps weights modest
                        if best is None or delta < best[0]:
                            best = (delta, q, ai, key)
            if best is None or best[0] >= -1e-7:
                break
            _, q, ai, key = best
            self.move(q, ai, key, apply=True)
            a = q.answers[ai]
            a.spec_weights[key] = float(a.spec_weights.get(key, 0) + 1)
            proposals.append((q.id, a.id, key, int(a.spec_weights[key])))
            if step % 10 == 0:
                worst = {length: min(v.values()) for length, v in self.table().items()}
                print(f"step {step + 1:3d} ({time.time() - t0:3.0f}s)  worst share " + "  ".join(f"{k} {100 * v:.1f}%" for k, v in worst.items()))
        return proposals


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", help="exported configuration JSON (default: the seed)")
    ap.add_argument("--target", type=float, default=0.30, help="share every specialization should reach (default 0.30)")
    ap.add_argument("--n", type=int, default=20000, help="random answer sets used by the search")
    args = ap.parse_args(argv)
    cfg = Config.model_validate_json(Path(args.config).read_text()) if args.config else build_default_config()
    tuner = Tuner(cfg, n=args.n)
    proposals = tuner.run(args.target)
    print(f"\n{len(proposals)} proposed increases (answer: specialization -> new weight):")
    for qid, aid, key, w in proposals:
        print(f'  ("{qid}", "{aid}"): "{key}" -> {w}')
    for length, shares in tuner.table().items():
        print(f"{length}: worst {100 * min(shares.values()):.1f}%, best {100 * max(shares.values()):.1f}%")
    print("Check the result on a different sample with `python tools/balance.py report --seed 4242`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
