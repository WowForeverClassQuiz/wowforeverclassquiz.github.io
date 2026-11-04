"""Balance diagnostics and tuning for the quiz (developer tool: needs numpy, which the application itself does not).

    python tools/balance.py report              # class and specialization shares under uniformly random answers (all three lengths)
    python tools/balance.py report --length short
    python tools/balance.py parity              # check this fast simulator against the real scoring engine
    python tools/balance.py tune                # suggest profile strengths that equalize specializations within each class
    python tools/balance.py report --config exported-config.json

"Under random answers" means every question is answered uniformly at random over its possible responses
(each rating 1-10, each answer, each pair). The shares diagnose the scoring rules and say nothing
about how real people answer. The simulator replays exactly the engine's arithmetic (baseline-subtracted deltas, 9-decimal
comparison, tie-break order), vectorized.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.models import Config  # noqa: E402
from app.scoring import active_questions, compile_config, evaluate  # noqa: E402
from app.seed import build_default_config  # noqa: E402

MIN_SHARE = 0.20      # the requirement: every specialization wins at least this share of its class's results
TARGET_SHARE = 0.27   # what the tuner aims above, so sampling noise cannot push a spec under the requirement


class Sim:
    """A fixed set of random answer sets and the totals they produce (common random numbers across tuning steps)."""

    def __init__(self, cfg: Config, n: int = 40000, seed: int = 1, length: str = "long"):
        self.cfg = cfg
        self.c = c = compile_config(cfg)
        self.n = n
        self.length = length
        self.active = active_questions(c, length)          # the questions that quiz length asks
        rng = np.random.default_rng(seed)
        self.idx = np.stack([rng.integers(0, len(q.answer_ids), size=n) for q in c.questions], axis=1)
        zeros = lambda w: np.zeros((n, w))
        self.class_tot, self.trait_tot, self.spec_direct = zeros(c.n_classes), zeros(c.n_traits), zeros(c.n_specs)
        for k, q in enumerate(c.questions):
            if k not in self.active:
                continue
            col = self.idx[:, k]
            self.class_tot += np.asarray(q.class_delta)[col]
            self.trait_tot += np.asarray(q.trait_delta)[col]
            self.spec_direct += np.asarray(q.spec_delta)[col]
        # per-class trait multiplier matrices (specs x traits)
        self.W = []
        self.gidx = []
        for cls in c.classes:
            w = np.zeros((len(cls.specs), c.n_traits))
            for j, s in enumerate(cls.specs):
                for t, m in s.terms:
                    w[j, t] = m
            self.W.append(w)
            self.gidx.append([s.gidx for s in cls.specs])
        order = sorted(range(c.n_classes), key=lambda i: c.tie_rank[i])
        self._class_order = order      # columns in tie-break order so argmax's "first maximum" matches the engine

    def class_winner(self) -> np.ndarray:
        scores = np.round(self.class_tot[:, self._class_order], 9)
        return np.asarray(self._class_order)[np.argmax(scores, axis=1)]

    def spec_scores(self, ci: int, rows: np.ndarray, W: np.ndarray | None = None) -> np.ndarray:
        W = self.W[ci] if W is None else W
        return self.trait_tot[rows] @ W.T + self.c.spec_multiplier * self.spec_direct[rows][:, self.gidx[ci]]

    def spec_shares(self, ci: int, rows: np.ndarray, W: np.ndarray | None = None) -> np.ndarray:
        if len(rows) == 0:
            return np.zeros(len(self.W[ci]))
        win = np.argmax(np.round(self.spec_scores(ci, rows, W), 9), axis=1)
        return np.bincount(win, minlength=len(self.W[ci])) / len(rows)

    def report(self) -> dict:
        cw = self.class_winner()
        class_share = np.bincount(cw, minlength=self.c.n_classes) / self.n
        specs = {}
        for ci, cls in enumerate(self.c.classes):
            rows = np.nonzero(cw == ci)[0]
            specs[cls.id] = dict(zip([s.id for s in cls.specs], self.spec_shares(ci, rows)))
        return {"class": dict(zip(self.c.class_ids, class_share)), "spec": specs}

    def answers_for_row(self, i: int) -> dict[str, str]:
        return {q.id: q.answer_ids[self.idx[i, k]] for k, q in enumerate(self.c.questions) if k in self.active}


def print_report(rep: dict, label: str = "") -> bool:
    ok = True
    print(f"== {label}")
    print("  class share  :", "  ".join(f"{k[:4]} {v * 100:4.1f}%" for k, v in rep["class"].items()))
    for cid, shares in rep["spec"].items():
        flag = "" if min(shares.values()) >= MIN_SHARE else "   <-- below 20%"
        ok &= min(shares.values()) >= MIN_SHARE
        print(f"  {cid:8s}     :", "  ".join(f"{k[:10]:10s} {v * 100:4.1f}%" for k, v in shares.items()), flag)
    cmin, cmax = min(rep["class"].values()), max(rep["class"].values())
    print(f"  classes range {cmin * 100:.1f}% - {cmax * 100:.1f}%;  worst specialization share {min(min(s.values()) for s in rep['spec'].values()) * 100:.1f}%")
    return ok


def tune(cfg: Config, n: int = 40000, seed: int = 11, rounds: int = 6) -> dict[str, float]:
    """Per-specialization strength s_k (multiplies its trait multipliers) that equalizes the specializations of each class."""
    sim = Sim(cfg, n=n, seed=seed)
    cw = sim.class_winner()
    strengths: dict[str, float] = {}
    for ci, cls in enumerate(sim.c.classes):
        rows = np.nonzero(cw == ci)[0]
        base = sim.W[ci].copy()
        s = np.ones(len(cls.specs))
        score = lambda s: float(np.sum((sim.spec_shares(ci, rows, base * s[:, None]) - 1 / 3) ** 2))
        best = score(s)
        for _ in range(rounds):
            for j in range(len(s)):
                for f in (0.7, 0.85, 0.93, 1.07, 1.15, 1.3):
                    t = s.copy()
                    t[j] = float(np.clip(t[j] * f, 0.3, 3.0))
                    v = score(t)
                    if v < best - 1e-9:
                        s, best = t, v
        s = s / s.max() if s.max() > 0 else s       # only ratios matter within a class; keep the strongest at 1.0
        for j, spec in enumerate(cls.specs):
            strengths[f"{cls.id}/{spec.id}"] = round(float(s[j]), 2)
    return strengths


def parity(cfg: Config, k: int = 300, length: str = "long") -> int:
    """Compare the vectorized winners with the real engine on k random answer sets."""
    sim = Sim(cfg, n=k, seed=99, length=length)
    cw = sim.class_winner()
    bad = 0
    for i in range(k):
        ev = evaluate(cfg, sim.answers_for_row(i), include_explanation=False, length=length)
        ci = int(cw[i])
        rows = np.array([i])
        sw = int(np.argmax(np.round(sim.spec_scores(ci, rows), 9), axis=1)[0])
        ok = ev.result.primary_class.id == sim.c.class_ids[ci] and ev.result.primary_specialization.id == sim.c.classes[ci].specs[sw].id
        bad += not ok
    print(f"parity ({length}): {k - bad}/{k} random answer sets agree with the scoring engine")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["report", "parity", "tune"])
    ap.add_argument("--config", help="exported configuration JSON (default: the seed)")
    ap.add_argument("--n", type=int, default=40000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--length", choices=["short", "medium", "long", "all"], default="all", help="quiz length to measure (default: all three)")
    args = ap.parse_args(argv)
    cfg = Config.model_validate_json(Path(args.config).read_text()) if args.config else build_default_config()
    lengths = ["short", "medium", "long"] if args.length == "all" else [args.length]
    if args.command == "parity":
        return 1 if sum(parity(cfg, length=l) for l in lengths) else 0
    if args.command == "tune":
        print(json.dumps(tune(cfg, n=args.n), indent=1))
        return 0
    ok = True
    for l in lengths:
        ok &= print_report(Sim(cfg, n=args.n, seed=args.seed, length=l).report(), f"{l}: {args.n:,} random answer sets (seed {args.seed})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
