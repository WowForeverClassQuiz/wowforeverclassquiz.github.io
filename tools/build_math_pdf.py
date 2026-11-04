"""Build docs/oracle-math.pdf: the mathematics behind the Oracle's selections, with the numbers computed from the live configuration.

    python tools/build_math_pdf.py                    # writes docs/oracle-math.pdf (about two minutes)
    python tools/build_math_pdf.py --quick            # fewer simulated respondents, for a fast draft
    python tools/build_math_pdf.py --config exported.json --out my-config.pdf

Developer tool (needs numpy, reportlab and matplotlib: pip install -r requirements-dev.txt). Every table and figure in the document is
computed here from the configuration (the seed unless --config is given) and from seeded simulations, so rebuilding after changing the
weights, the questions or the confidence settings gives an up-to-date document.
"""
from __future__ import annotations

import argparse
import io
import math
import os
import random
import sys
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import letter  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import inch  # noqa: E402
from reportlab.lib.utils import ImageReader  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app import adaptive as adaptive_mod  # noqa: E402
from app.models import ALLOCATION_POINTS, LENGTHS, Config  # noqa: E402
from app.seed_classes import CLASS_ORDER  # noqa: E402
from app.scoring import active_questions, compile_config, response_coefficients  # noqa: E402
from app.seed import build_default_config  # noqa: E402
from app.version import APP_VERSION, build_info  # noqa: E402
from balance import Sim  # noqa: E402

# ------------------------------------------------------------------------------------------------ fonts and styles
FONT_DIR = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
for name, file in (("DV", "DejaVuSans.ttf"), ("DV-B", "DejaVuSans-Bold.ttf"), ("DV-I", "DejaVuSans-Oblique.ttf"), ("DV-BI", "DejaVuSans-BoldOblique.ttf"),
                   ("DVM", "DejaVuSansMono.ttf")):
    pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / file)))
pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV-I", boldItalic="DV-BI")

INK, MUTED, ACCENT, RULE = colors.HexColor("#1b1b1f"), colors.HexColor("#5b5b66"), colors.HexColor("#4a3fb5"), colors.HexColor("#c9c9d3")
BODY = ParagraphStyle("body", fontName="DV", fontSize=9.2, leading=13.2, textColor=INK, spaceAfter=6)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=7.8, leading=10.6, textColor=MUTED, spaceAfter=4)
H1 = ParagraphStyle("h1", parent=BODY, fontName="DV-B", fontSize=15, leading=19, textColor=ACCENT, spaceBefore=14, spaceAfter=7)
H2 = ParagraphStyle("h2", parent=BODY, fontName="DV-B", fontSize=10.8, leading=14, spaceBefore=9, spaceAfter=4)
TITLE = ParagraphStyle("title", parent=BODY, fontName="DV-B", fontSize=24, leading=29, textColor=ACCENT, spaceAfter=6)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=7.6, leading=9.6, spaceAfter=0)
CELLB = ParagraphStyle("cellb", parent=CELL, fontName="DV-B")
MONO = ParagraphStyle("mono", parent=BODY, fontName="DVM", fontSize=7.8, leading=10.5)

PAGE_W, PAGE_H = letter
MARGIN = 0.8 * inch
WIDTH = PAGE_W - 2 * MARGIN


def P(text, style=BODY):
    return Paragraph(text, style)


def table(rows, widths=None, header=True, align_right_from=1, font=7.6, zebra=True, repeat=1):
    """A compact table. Cells are strings (wrapped in paragraphs) or flowables."""
    cell = ParagraphStyle("c", parent=CELL, fontSize=font, leading=font * 1.26)
    cellb = ParagraphStyle("cb", parent=cell, fontName="DV-B")
    cellr = ParagraphStyle("cr", parent=cell, alignment=2)
    cellbr = ParagraphStyle("cbr", parent=cellb, alignment=2)
    data = []
    for ri, row in enumerate(rows):
        out = []
        for ci, v in enumerate(row):
            if isinstance(v, str):
                head = header and ri == 0
                right = ci >= align_right_from and align_right_from >= 0
                out.append(Paragraph(v, (cellbr if head else cellr) if right else (cellb if head else cell)))
            else:
                out.append(v)
        data.append(out)
    t = Table(data, colWidths=widths, repeatRows=repeat if header else 0, hAlign="LEFT")
    style = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, 0), 0.8, ACCENT if header else RULE),
             ("LINEBELOW", (0, 1), (-1, -1), 0.25, RULE), ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
             ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
    if zebra:
        style += [("BACKGROUND", (0, r), (-1, r), colors.HexColor("#f4f4f9")) for r in range(2, len(rows), 2)]
    t.setStyle(TableStyle(style))
    return t


# ------------------------------------------------------------------------------------------------ equations and figures
def eq(tex: str, size: float = 12.5, indent: float = 0.0):
    """A display equation, typeset with matplotlib's mathtext and placed as an image."""
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0, 0, f"${tex}$", fontsize=size, color="#1b1b1f")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=300, bbox_inches="tight", pad_inches=0.03, transparent=True)
    plt.close(fig)
    buf.seek(0)
    w, h = ImageReader(buf).getSize()
    buf.seek(0)
    scale = min(1.0, (WIDTH - indent) / (w * 72 / 300))
    img = Image(buf, width=w * 72 / 300 * scale, height=h * 72 / 300 * scale, hAlign="LEFT")
    return KeepTogether([Spacer(1, 2), Table([[img]], colWidths=[WIDTH], style=[("LEFTPADDING", (0, 0), (-1, -1), 18 + indent)]), Spacer(1, 3)])


def figure(draw, width=WIDTH, height=2.6 * inch):
    fig, ax = plt.subplots(figsize=(width / 72, height / 72), dpi=200)
    draw(ax)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200)
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=width, height=height, hAlign="LEFT")


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"


def keep_captions(story):
    """Keep each short table or figure on the same page as its caption."""
    out, i = [], 0
    while i < len(story):
        a, b = story[i], story[i + 1] if i + 1 < len(story) else None
        is_caption = isinstance(b, Paragraph) and b.style.name == "small" and b.text.startswith("<b>")
        long_table = isinstance(a, Table) and len(a._cellvalues) > 45
        if is_caption and isinstance(a, (Table, Image)) and not long_table:
            out.append(KeepTogether([a, b]))
            i += 2
        else:
            out.append(a)
            i += 1
    return out


# ------------------------------------------------------------------------------------------------ simulation of the confidence mode
class Simulator:
    """The confidence-mode procedure on numpy arrays, for simulated respondents (it follows app/adaptive.py step by step)."""

    def __init__(self, cfg: Config, sharp_spec: float | None = None, sharp_class: float | None = None):
        cfg = cfg.model_copy(deep=True)
        if sharp_spec is not None:
            cfg.scoring.adaptive.sharpness_spec = sharp_spec
        if sharp_class is not None:
            cfg.scoring.adaptive.sharpness_class = sharp_class
        self.cfg, self.c = cfg, compile_config(cfg)
        model = adaptive_mod.Model(self.c)
        self.logp = [np.asarray(rows) for rows in model.logp]          # [question] -> (responses, 27)
        self.p = [np.exp(lp) for lp in self.logp]
        self.nq, self.nt = len(self.logp), model.n_types
        c = self.c
        self.cd = [np.asarray(q.class_delta) for q in c.questions]
        self.td = [np.asarray(q.trait_delta) for q in c.questions]
        self.sd = [np.asarray(q.spec_delta) for q in c.questions]
        self.tie = np.asarray(c.tie_rank)
        roles = [set(sp.role.split("_or_")) for cl in c.classes for sp in cl.specs]
        self.tcl = np.array([ci for ci, cl in enumerate(c.classes) for _ in cl.specs])
        self.same_class = self.tcl[:, None] == self.tcl[None, :]
        self.same_role = np.array([[bool(a & b) for b in roles] for a in roles])
        self.onehot = np.zeros((self.nt, c.n_classes))
        self.onehot[np.arange(self.nt), self.tcl] = 1.0

    def credit(self, rec):
        """What every type is worth toward the confidence in ``rec``: 1 for rec, the class or role credit for its class-mates and role-mates."""
        s = self.c.adaptive
        k = np.maximum(np.where(self.same_role[rec], s.role_credit, 0.0), np.where(self.same_class[rec], s.class_credit, 0.0))
        k[rec] = 1.0
        return k

    def recommend(self, ct, tt, st) -> int:
        c = self.c
        ci = sorted(range(c.n_classes), key=lambda i: (-round(float(ct[i]), 9), self.tie[i]))[0]
        scores = [sum(m * tt[t] for t, m in s.terms) + c.spec_multiplier * st[s.gidx] for s in c.classes[ci].specs]
        j = sorted(range(len(scores)), key=lambda j: (-round(float(scores[j]), 9), j))[0]
        return c.classes[ci].specs[j].gidx

    def gains(self, post, remaining):
        h0 = float(-(post[post > 0] * np.log(post[post > 0])).sum())
        out = []
        for q in remaining:
            joint = self.p[q] * post
            pr = joint.sum(axis=1)
            with np.errstate(divide="ignore", invalid="ignore"):
                t1 = np.where(joint > 0, joint * np.log(joint), 0.0).sum()
                t2 = np.where(pr > 0, pr * np.log(pr), 0.0).sum()
            out.append(h0 + t1 - t2)
        return out

    def rule_scores(self, post, remaining, rule, lead):
        """Score every remaining question by one of the alternative rules compared in section 8.7 (higher is better)."""
        h0 = float(-(post[post > 0] * np.log(post[post > 0])).sum())
        hb = lambda x: -(np.clip(x, 1e-12, 1 - 1e-12) * np.log(np.clip(x, 1e-12, 1 - 1e-12)) + (1 - np.clip(x, 1e-12, 1 - 1e-12)) * np.log(1 - np.clip(x, 1e-12, 1 - 1e-12)))
        eps = 1e-300
        out = []
        for q in remaining:
            Pq = self.p[q]
            joint = Pq * post
            pr = joint.sum(axis=1)
            pp = joint / pr[:, None]
            with np.errstate(divide="ignore", invalid="ignore"):
                ent = -np.where(pp > 0, pp * np.log(pp), 0.0).sum(axis=1)
            if rule == "leader":                     # information about "is the leader right?"
                out.append(float(hb(post[lead]) - (pr * hb(pp[:, lead])).sum()))
            elif rule == "best_guess":               # expected probability of the best guess after the answer
                out.append(float((pr * pp.max(axis=1)).sum()))
            elif rule == "spread":                   # how far the answer can move the leader's probability: confirm or reset
                m = float((pr * pp[:, lead]).sum())
                out.append(float((pr * (pp[:, lead] - m) ** 2).sum()))
            elif rule == "challenger":               # evidence between the leader and its plausible challengers, in both directions
                w = post.copy()
                w[lead] = 0
                w = w / w.sum()
                k1 = (Pq[:, [lead]] * (np.log(Pq[:, [lead]] + eps) - np.log(Pq + eps))).sum(axis=0)
                k2 = (Pq * (np.log(Pq + eps) - np.log(Pq[:, [lead]] + eps))).sum(axis=0)
                out.append(float((w * (k1 + k2)).sum()))
            elif rule == "finish":                   # chance this answer reaches the threshold, information gain as tie-break
                p_stop = float((pr * (pp.max(axis=1) >= self.c.adaptive.confidence)).sum())
                out.append(p_stop + 1e-3 * (h0 - float((pr * ent).sum())))
            else:
                raise ValueError(rule)
        return np.round(np.asarray(out), 9)

    def run(self, rng, tau=None, order="adaptive", stop=None, answer="model", full=False, truth=None):
        """One respondent. ``tau`` is the true type (None: uniformly random answers). Returns a dict of what happened."""
        s = self.c.adaptive
        mn, mx, conf = stop or (s.min_questions, s.max_questions, s.confidence)
        lp = np.zeros(self.nt)
        ct, tt, st = np.zeros(self.c.n_classes), np.zeros(self.c.n_traits), np.zeros(self.c.n_specs)
        remaining, asked, confs, ents = list(range(self.nq)), [], [], []
        stopped_at, lead = None, 0
        while remaining:
            w = np.exp(lp - lp.max())
            post = w / w.sum()
            if order == "adaptive":
                g = self.gains(post, remaining)
                q = remaining[int(np.argmax(np.round(g, 9)))]
            elif order == "fixed":
                q = remaining[0]
            else:
                q = remaining[int(np.argmax(self.rule_scores(post, remaining, order, lead)))]
            remaining.remove(q)
            answer_p = truth if truth is not None else self.p          # how respondents really answer; the Oracle still assumes self.p
            probs = answer_p[q][:, tau] if (tau is not None and answer == "model") else np.full(self.p[q].shape[0], 1 / self.p[q].shape[0])
            r = int(rng.choice(len(probs), p=probs / probs.sum()))
            lp += self.logp[q][r]
            ct += self.cd[q][r]
            tt += self.td[q][r]
            st += self.sd[q][r]
            asked.append(q)
            w = np.exp(lp - lp.max())
            post = w / w.sum()
            rec = self.recommend(ct, tt, st)
            lead = rec
            overall = float(post @ self.credit(rec))
            confs.append(overall)
            ents.append(float(-(post[post > 0] * np.log(post[post > 0])).sum()))
            if stopped_at is None and (len(asked) >= mx or (len(asked) >= mn and overall >= conf)):
                stopped_at = len(asked)
                final = (rec, overall, int(post.argmax()))
                if not full:
                    break
        if stopped_at is None:
            stopped_at = len(asked)
            final = (rec, overall, int(post.argmax()))
        earned = float(self.credit(final[0])[tau]) if tau is not None else 0.0
        return {"n": stopped_at, "conf": final[1], "right": (tau is not None and final[0] == tau), "earned": earned,
                "class_right": bool(tau is not None and self.tcl[final[0]] == self.tcl[tau]), "mode": final[2], "confs": confs, "ents": ents}


def cohort(sim: Simulator, n: int, seed: int, **kw):
    rng = np.random.default_rng(seed)
    runs = [sim.run(rng, tau=int(rng.integers(sim.nt)), **kw) for _ in range(n)]
    ns = np.array([r["n"] for r in runs])
    return {
        "runs": runs, "mean_n": float(ns.mean()), "median_n": float(np.median(ns)), "p90_n": float(np.percentile(ns, 90)),
        "mean_conf": float(np.mean([r["conf"] for r in runs])), "accuracy": float(np.mean([r["right"] for r in runs])),
        "earned": float(np.mean([r["earned"] for r in runs])), "class_accuracy": float(np.mean([r["class_right"] for r in runs])),
        "capped": float(np.mean(ns >= sim.c.adaptive.max_questions)),
    }


# ------------------------------------------------------------------------------------------------ the document
def build(cfg: Config, out: Path, quick: bool = False) -> dict:
    c = compile_config(cfg)
    ad = c.adaptive
    n_sim = 60 if quick else 400
    n_rand = 20000 if quick else 100000
    types = [f"{cl.name} {sp.name}" for cl in c.classes for sp in cl.specs]
    story: list = []
    info = build_info()
    print("simulating random answers ...", flush=True)

    # ---- numbers from uniformly random answers, per length
    rand = {}
    for length in LENGTHS:
        sim = Sim(cfg, n=n_rand, seed=4242, length=length)
        rep = sim.report()
        top2 = np.sort(np.round(sim.class_tot, 9), axis=1)[:, -2:]
        gap = top2[:, 1] - top2[:, 0]
        rand[length] = {"rep": rep, "gap": np.percentile(gap, [25, 50, 75, 90]), "n": len(sim.active)}

    # ================================================================ title
    story += [P("How the Forever Character Oracle chooses", TITLE),
              P(f"The mathematics behind the class, specialization and confidence figures &nbsp;·&nbsp; version {APP_VERSION} &nbsp;·&nbsp; "
                f"algorithm {c.algorithm_version} &nbsp;·&nbsp; {date.today():%B %-d, %Y}", SMALL),
              P("This document explains every calculation that turns your answers into a recommendation, and every number behind it. "
                "Each table is computed from the quiz's live configuration and from seeded simulations, so it can be regenerated whenever "
                "the weights change (<font name='DVM'>python tools/build_math_pdf.py</font>). Scores are <b>relative compatibility indicators</b> on a scale with no fixed maximum. The only "
                "probabilities in this document are the ones in the confidence model (section 8), which are exact "
                "<i>within that model</i> and rest on assumptions stated there. The quiz is playstyle lore with no personality science behind it: studies of "
                "WoW players found little or no link between personality and class choice.", BODY)]
    story += [P("Contents", H2),
              P("1 The pipeline in one page &nbsp;·&nbsp; 2 Questions and responses &nbsp;·&nbsp; 3 Baseline subtraction &nbsp;·&nbsp; 4 Class and trait scores "
                "&nbsp;·&nbsp; 5 Specialization scores &nbsp;·&nbsp; 6 Reading the gap: labels and margins &nbsp;·&nbsp; 7 Quiz lengths and balance "
                "&nbsp;·&nbsp; 8 Confidence mode &nbsp;·&nbsp; 9 A worked example &nbsp;·&nbsp; 10 Assumptions and limits &nbsp;·&nbsp; Appendices: questions, answer weights.", SMALL)]

    # ================================================================ 1 pipeline
    story += [P("1&nbsp;&nbsp;The pipeline in one page", H1),
              P("Every question has a finite set of <b>responses</b> (an answer, a pair, an ordering, a split of points, a rating). Each response carries "
                "weights for the nine classes, the twelve personality traits and, for some answers, individual specializations. The weights of the "
                "response you give are added up over the questions, after subtracting what an average response would have contributed, so that a "
                "question can never favour a class just by appearing in the quiz."),
              eq(r"\mathrm{answers}\ \rightarrow\ \mathrm{response\ weights}\ \rightarrow\ \Delta\ (\mathrm{minus\ the\ average})\ \rightarrow\ S_c,\ T_t\ \rightarrow\ P_s\ \rightarrow\ \mathrm{result}"),
              table([["Step", "What is computed", "Section"],
                     ["1", "the response you gave becomes a weight vector (classes, traits, specializations)", "2"],
                     ["2", "the average weight over all possible responses is subtracted", "3"],
                     ["3", "class scores S<sub>c</sub> and trait scores T<sub>t</sub> are the sums of those differences over the questions", "4"],
                     ["4", "the class with the largest S<sub>c</sub> wins; ties go to a fixed class order", "4"],
                     ["5", "inside the winning class, specialization scores P<sub>s</sub> combine the trait scores with the specialization's profile "
                           "and any direct weights; the largest wins", "5"],
                     ["6", "the gap between the top two classes becomes a label (Strong lean, Clear lean, Close call)", "6"],
                     ["7", "optionally, a probabilistic model reads the same numbers as evidence and gives a confidence", "8"]],
                    widths=[0.5 * inch, WIDTH - 1.1 * inch, 0.6 * inch], align_right_from=-1)]

    # ================================================================ 2 questions and responses
    story += [P("2&nbsp;&nbsp;Questions and responses", H1),
              P("A question's <i>answers</i> (up to four) carry the weights. What you submit is a <i>response</i>; its weights are a fixed linear "
                "combination of its answers' weights, with a coefficient for each answer:")]
    story += [eq(r"w_q(r,k)=\sum_{a}\ \gamma_q(r,a)\ w_{q,a}(k)\qquad k\in\{\mathrm{classes,\ traits,\ specializations}\}")]
    n_by_type = {}
    for q in cfg.enabled_questions():
        n_by_type.setdefault(q.type, []).append(q)
    resp = {t: len(response_coefficients(qs[0])) for t, qs in n_by_type.items()}
    rows = [["Type", "You do", "Responses R", "Coefficients &gamma;(r, a)", "Questions"]]
    rows += [["choice", "pick one answer", "number of answers (2 to 4)", "1 for the chosen answer, 0 for the others", str(len(n_by_type.get("choice", [])))],
             ["pick two", "choose two of four", f"{resp.get('pick_two', 6)} pairs", "1 for each of the two chosen answers", str(len(n_by_type.get("pick_two", [])))],
             ["ranking", "order the four", f"{resp.get('ranking', 24)} orderings", "(3 − place)/2: 1.5, 1, 0.5, 0 from first to last", str(len(n_by_type.get("ranking", [])))],
             ["allocation", f"spend {ALLOCATION_POINTS} points on four items", f"{resp.get('allocation', 84)} splits", f"points / {ALLOCATION_POINTS // 2} (so six points on one item counts 2)", str(len(n_by_type.get("allocation", [])))],
             ["scale", "rate 1 to 10", f"{resp.get('scale', 10)} ratings", "max(s,0) for 'agree', max(−s,0) for 'disagree', s = (rating − 5.5)/4.5", str(len(n_by_type.get("scale", [])))]]
    story += [table(rows, widths=[0.8 * inch, 1.5 * inch, 1.3 * inch, WIDTH - 5.0 * inch, 0.9 * inch], align_right_from=-1),
              P(f"<b>Table 1.</b> The five question types, with how many of the {len(cfg.enabled_questions())} questions are of each (the last {len([q for q in cfg.enabled_questions() if q.min_length == 'adaptive'])} are asked only in confidence mode). Response counts are exact; the weights a response carries follow from the coefficients.", SMALL)]

    # ================================================================ 3 baseline subtraction
    story += [P("3&nbsp;&nbsp;Baseline subtraction", H1),
              P("Some classes appear in more answers than others, and a question with many responses would otherwise add more than a short one. So each "
                "question's contribution is measured against its own average over <b>every possible response</b> (R<sub>q</sub> of them):")]
    story += [eq(r"\Delta_q(r,k)=w_q(r,k)-\frac{1}{R_q}\sum_{r'=1}^{R_q} w_q(r',k)")]
    story += [P("Two consequences hold for every question and every class, trait and specialization: the contributions average to zero over the responses "
                "(so no question favours anything on average), and, because every answer carries a class weight of 2 + 1 (or another split of 3), the class "
                "contributions of any single response add up to zero, so the nine class scores of a complete answer set sum to zero. They are comparisons "
                "with the average answer pattern and measure no absolute amount.")]
    q01 = cfg.get_question("q01")
    t01 = compile_config(cfg).questions[0]
    ci = {cid: i for i, cid in enumerate(c.class_ids)}
    rows = [["Class", "Raw weight of A", "Average over A–D", "Δ for response A"]]
    for cl in c.classes:
        i = ci[cl.id]
        if t01.class_raw[0][i] or t01.class_base[i]:
            rows.append([cl.name, f"{t01.class_raw[0][i]:.2f}", f"{t01.class_base[i]:.2f}", f"{t01.class_delta[0][i]:+.2f}"])
    story += [P(f"<b>Worked example, question 1.</b> “{q01.text}” Answer A is “{q01.answers[0].text}” Its class weights, the average over the four answers, "
                "and what choosing A contributes:"),
              table(rows, widths=[1.6 * inch, 1.5 * inch, 1.6 * inch, 1.4 * inch]),
              P("<b>Table 2.</b> Baseline subtraction for question 1, response A. The contributions of the nine classes add up to 0.00.", SMALL)]
    q09 = next(q for q in compile_config(cfg).questions if q.id == "q09")
    r09 = q09.answer_ids.index("3-0-0-3")
    rows = [["Class", "Raw", "Average over 84 splits", "Δ"]]
    for cl in c.classes:
        i = ci[cl.id]
        if q09.class_raw[r09][i] or q09.class_base[i]:
            rows.append([cl.name, f"{q09.class_raw[r09][i]:.3f}", f"{q09.class_base[i]:.3f}", f"{q09.class_delta[r09][i]:+.3f}"])
    story += [P("<b>Worked example, a point-spending question.</b> Question 9 asks how to divide six hours at a festival; the response “3-0-0-3” spends "
                "three points on the first item and three on the last. Its coefficients are 1, 0, 0, 1, so its class weights are the sums of those two answers' weights:"),
              table(rows, widths=[1.6 * inch, 1.2 * inch, 1.9 * inch, 1.4 * inch]),
              P("<b>Table 3.</b> Baseline subtraction for a response with 84 possible values.", SMALL)]

    # ================================================================ 4 class and trait scores
    story += [P("4&nbsp;&nbsp;Class and trait scores, and the winning class", H1),
              P("Over the answered questions q, the class score and the trait score are the sums of the differences. The class with the largest score is "
                "recommended; scores are compared after rounding to nine decimals, and exact ties fall to the class order below.")]
    story += [eq(r"S_c=\sum_{q}\Delta_q(r_q,c)\qquad T_t=\sum_{q}\Delta_q(r_q,t)\qquad c^{*}=\mathrm{arg\,max}_c\ S_c")]
    order = [cfg.get_class(cid).name for cid in cfg.scoring.class_tie_break_order]
    story += [P(f"Tie-break order: {', '.join(order)}. Sums are computed exactly (Shewchuk summation), so float noise never decides a result. "
                "The browser version of the engine reproduces the Python one to the last digit; a test compares them on every build.")]

    # ================================================================ 5 specialization scores
    story += [P("5&nbsp;&nbsp;Specialization scores", H1),
              P("Only the winning class's specializations compete. A specialization s has a <b>profile</b>: an ordered list of traits with multipliers "
                "(1.5, 1.0 and 0.45 for its primary, secondary and tertiary trait). Its score adds the profile-weighted trait scores to the sum of any "
                f"<b>direct specialization weights</b> that answers carry, scaled by the multiplier M = {c.spec_multiplier:g}:")]
    story += [eq(r"P_s=\sum_{t}m_{s,t}\,T_t\;+\;M\sum_{q}\Delta^{\mathrm{spec}}_q(r_q,s)\qquad s^{*}=\mathrm{arg\,max}_{s\in c^{*}}\ P_s")]
    traits = {t.id: t.name for t in cfg.traits}
    rows = [["Class", "Specialization", "Primary trait ×1.5", "Secondary ×1.0", "Tertiary ×0.45"]]
    for cl in cfg.classes:
        for sp in cl.specializations:
            names = [f"{traits[t]}" for t in sp.trait_multipliers]
            rows.append([cl.name, sp.name] + names + [""] * (3 - len(names)))
    story += [table(rows, widths=[0.95 * inch, 1.55 * inch, 1.5 * inch, 1.5 * inch, WIDTH - 5.5 * inch], align_right_from=-1),
              P("<b>Table 4.</b> The 27 specialization profiles. A trait's multiplier is its position's value; direct weights are listed in Appendix B.", SMALL)]
    direct = [(q.id, a.id) for q in cfg.enabled_questions() for a in q.answers if a.spec_weights]
    story += [P(f"{len(direct)} of the {sum(len(q.answers) for q in cfg.enabled_questions())} answers carry direct specialization weights. They exist because the "
                "trait profiles alone could not make some specializations win at all: with the original sixteen questions, a search found no answers that reached "
                f"Mage Frost or Rogue Assassination. With M = {c.spec_multiplier:g} and the direct weights every specialization can be reached, and the tuning described in "
                "section 7 keeps them all reachable, and each winning a healthy share, at every quiz length.")]

    # ================================================================ 6 labels and margins
    story += [P("6&nbsp;&nbsp;Reading the gap: labels and margins", H1),
              P("The label shown with a result is a heuristic about the gap G between the top two class scores. The confidence model in section 8 supplies the probabilities.")]
    story += [eq(r"G=S_{(1)}-S_{(2)}\qquad \mathrm{Strong\ lean}:\ G\geq \mu_{s}\sqrt{n/N}\qquad \mathrm{Clear\ lean}:\ G\geq \mu_{c}\sqrt{n/N}\qquad \mathrm{otherwise\ Close\ call}")]
    ms, mc = cfg.scoring.confidence_margins.strong, cfg.scoring.confidence_margins.moderate
    story += [P(f"Here μ<sub>s</sub> = {ms:g} and μ<sub>c</sub> = {mc:g} are the configured margins for the full {c.n_core}-question quiz (N = {c.n_core}), "
                "and n is the number of questions actually answered. The gap between the two best classes of random answers grows roughly like "
                "√n, so scaling the margins by √(n/N) keeps a short quiz from being called a “close call” merely for being short. "
                "A test checks that the share of each label under random answers stays comparable across lengths.")]
    rows = [["Questions n", "Strong lean at G ≥", "Clear lean at G ≥"]]
    for n in (10, 15, 20, 25, 30):
        f = math.sqrt(n / c.n_core)
        rows.append([str(n), f"{ms * f:.3f}", f"{mc * f:.3f}"])
    story += [table(rows, widths=[1.3 * inch, 1.8 * inch, 1.8 * inch]), P("<b>Table 5.</b> Margins by number of questions answered.", SMALL)]

    # ================================================================ 7 lengths and balance
    story += [P("7&nbsp;&nbsp;Quiz lengths and balance under random answers", H1),
              P("The quiz can be taken at three fixed lengths. The sets of questions are nested (short ⊂ medium ⊂ long), so a short result can be sharpened "
                "by answering the next ten questions. A fixed length scores only its own questions; everything else is unchanged.")]
    kinds = ["choice", "scale", "pick_two", "ranking", "allocation"]
    rows = [["Length", "Questions"] + [k.replace("_", " ") for k in kinds] + ["Top-two gap at the 25th, 50th, 75th and 90th percentiles"]]
    for length in LENGTHS:
        act = active_questions(c, length)
        counts = {k: sum(1 for i in act if c.questions[i].type == k) for k in kinds}
        g = rand[length]["gap"]
        rows.append([length, str(len(act))] + [str(counts[k]) for k in kinds] + [", ".join(f"{x:.2f}" for x in g)])
    story += [table(rows, widths=[0.7 * inch, 0.75 * inch, 0.6 * inch, 0.55 * inch, 0.7 * inch, 0.65 * inch, 0.85 * inch, WIDTH - 4.8 * inch]),
              P(f"<b>Table 6.</b> Composition of each length, and the gap G between the top two class scores for {n_rand:,} uniformly random answer sets.", SMALL)]
    story += [P("<b>What “equal” means.</b> The quiz is balanced so that, if every response to every question were equally likely, every class would be "
                "recommended equally often and every specialization would win a healthy share of its class's results. This is a property of the scoring "
                "rules, measured by simulation; it says nothing about how people really answer. With n simulated runs a share p has standard error "
                "√(p(1−p)/n):")]
    story += [eq(r"\mathrm{SE}(p)=\sqrt{p(1-p)/n}\qquad \mathrm{e.g.}\ \ p=\frac{1}{9},\ n=" + f"{n_rand:,}".replace(",", r"{,}") + r":\ \ \mathrm{SE}\approx " + f"{100 * math.sqrt((1 / 9) * (8 / 9) / n_rand):.2f}" + r"\%")]
    rows = [["Class"] + [f"{l.capitalize()} share" for l in LENGTHS]]
    for cl in cfg.classes:
        rows.append([cl.name] + [pct(rand[l]["rep"]["class"][cl.id], 2) for l in LENGTHS])
    rows.append(["<b>Even split</b>"] + [pct(1 / 9, 2)] * 3)
    story += [table(rows, widths=[1.7 * inch, 1.3 * inch, 1.3 * inch, 1.3 * inch]),
              P(f"<b>Table 7.</b> How often each class is recommended under uniformly random answers ({n_rand:,} runs per length, seed 4242).", SMALL)]
    rows = [["Class", "Specialization"] + [f"{l.capitalize()}" for l in LENGTHS]]
    for cl in cfg.classes:
        for sp in cl.specializations:
            rows.append([cl.name, sp.name] + [pct(rand[l]["rep"]["spec"][cl.id][sp.id]) for l in LENGTHS])
    low = {l: min(v for d in rand[l]["rep"]["spec"].values() for v in d.values()) for l in LENGTHS}
    story += [table(rows, widths=[1.2 * inch, 1.7 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch]),
              P("<b>Table 8.</b> The share of its class's recommendations each specialization wins under random answers. The requirement is at least 20%; the "
                f"lowest values are {pct(low['short'])} (short), {pct(low['medium'])} (medium) and {pct(low['long'])} (long).", SMALL)]

    def draw_shares(ax):
        x = np.arange(c.n_classes)
        for k, l in enumerate(LENGTHS):
            ax.bar(x + (k - 1) * 0.27, [100 * rand[l]["rep"]["class"][cid] for cid in c.class_ids], width=0.26, label=l)
        ax.axhline(100 / 9, color="#444", lw=0.8, ls="--")
        ax.set_xticks(x, [cl.name for cl in c.classes], fontsize=7)
        ax.set_ylim(10, 12.2)
        ax.set_ylabel("recommended (%)", fontsize=8)
        ax.legend(fontsize=7, frameon=False, ncol=3, loc="upper right")
        ax.tick_params(labelsize=7)
    story += [figure(draw_shares, height=2.2 * inch),
              P("<b>Figure 1.</b> Class shares under random answers; the dashed line is an even 11.11%. Differences of a few tenths of a point are within "
                "what the weights can be tuned to and the noise of the simulation.", SMALL)]

    # ================================================================ 8 confidence mode
    sim = Simulator(cfg)
    print("simulating confidence mode ...", flush=True)
    base = cohort(sim, n_sim, 101)
    fixed = cohort(sim, n_sim, 101, order="fixed")
    story += [PageBreak(), P("8&nbsp;&nbsp;Confidence mode: asking until the Oracle is sure", H1),
              P("In confidence mode (the default) the Oracle chooses each next question to learn as much as possible, and stops once it is confident in one "
                f"specialization: as soon as the model's probability for the recommended specialization reaches {pct(ad.confidence, 0)}"
                + (f", though never before {ad.min_questions} questions" if ad.min_questions > 1 else " (there is no minimum number of questions)")
                + f", and never after more than {ad.max_questions}. To say “probability” at all we need a model of how a person of each type "
                "answers. The model below is deliberately built from the quiz's own numbers.")]
    story += [P("8.1&nbsp;&nbsp;The choice model", H2),
              P("There are 27 <b>types</b> τ = (class c, specialization s). A person of type τ is assumed to answer question q by a <i>logit choice</i>: each response r "
                "has a utility equal to what it contributes to that type's scores, and responses are picked with probability proportional to exp(utility).")]
    story += [eq(r"u_q(r\,|\,\tau)=\lambda_c\,\Delta_q(r,c)+\lambda_s\left(\sum_t m_{s,t}\,\Delta_q(r,t)+M\,\Delta^{\mathrm{spec}}_q(r,s)\right)"),
              eq(r"P(r\,|\,\tau,q)=\frac{e^{\,u_q(r|\tau)}}{\sum_{r'}e^{\,u_q(r'|\tau)}}")]
    story += [P(f"The sharpness constants say how consistently people answer as their type: λ<sub>c</sub> = {ad.sharpness_class:g} and λ<sub>s</sub> = {ad.sharpness_spec:g}. "
                "Larger values mean answers reveal the type more reliably, so fewer questions are needed. They are assumptions (section 10) that can be changed in the admin settings. "
                f"With the defaults a simulated respondent needs about {base['mean_n']:.0f} questions on average, and {pct(base['capped'], 0)} of them need all {ad.max_questions}.")]
    story += [P("8.2&nbsp;&nbsp;The posterior", H2),
              P("Questions are answered independently given the type, and every type starts equally likely (1/27). Bayes' rule gives the probability of each type after "
                "the answers r<sub>1</sub>…r<sub>n</sub>:")]
    story += [eq(r"\pi(\tau\,|\,r_{1:n})=\frac{\prod_{i=1}^{n}P(r_i\,|\,\tau,q_i)}{\sum_{\tau'}\prod_{i=1}^{n}P(r_i\,|\,\tau',q_i)}"),
              eq(r"\ln\pi(\tau\,|\,r_{1:n})=\lambda_c\,S_c+\lambda_s\,P_s-\sum_{i=1}^{n}\ln Z_{q_i}(\tau)+\mathrm{const.}\qquad Z_q(\tau)=\sum_{r}e^{\,u_q(r|\tau)}")]
    story += [P("The first two terms are the quiz's own class and specialization scores: <b>the scoring is the evidence, and the model turns it into probabilities</b>. "
                "The normalizers ln Z<sub>q</sub>(τ) correct for how strongly each type prefers particular responses to a question. A test verifies this identity numerically. "
                f"Before any answer the uncertainty is the entropy H = ln 27 = {math.log(27):.3f} nats. The confidence is measured for the specialization the scoring currently "
                "recommends (class first, then specialization), even when the posterior's own maximum lies elsewhere, so the recommendation shown and the confidence stated always refer to the same specialization. "
                "One visible consequence: when a new answer changes which specialization leads, the certainty meter can fall before it rises again.")]
    story += [P("The confidence is not only the probability of that one specialization. A person torn between the three specializations of one class, or between Protection Paladin and "
                "Protection Warrior, has given the Oracle real information: it knows the class, or the role, even if it cannot yet name the specialization. So every type earns <b>credit</b> "
                f"toward the confidence in the recommendation ŝ: 1 for ŝ itself, c = {ad.class_credit:g} for another specialization of its class, r = {ad.role_credit:g} for one that shares a role with it "
                "(tank, healer, melee damage or ranged damage; Feral Combat counts as both a tank and melee damage), and the larger of the two when both apply. The confidence is the posterior's expected credit:"),
              eq(r"C=\sum_{\tau}\pi(\tau\,|\,r_{1:n})\,K(\hat\tau,\tau)\qquad K(\hat\tau,\tau)=\max\left(1_{\tau=\hat\tau},\ c\,1_{\mathrm{same\ class}},\ r\,1_{\mathrm{shared\ role}}\right)")]
    _mdl = adaptive_mod.Model(c)
    _g = lambda cid, sid: next(sp.gidx for cl in c.classes if cl.id == cid for sp in cl.specs if sp.id == sid)
    _examples = [
        ("A clear specialization", {("mage", "fire"): 0.92, ("mage", "frost"): 0.04, ("mage", "arcane"): 0.04}, ("mage", "fire")),
        ("Two tanks, two classes", {("paladin", "protection"): 0.4, ("warrior", "protection"): 0.4, ("priest", "holy"): 0.2}, ("paladin", "protection")),
        ("One class, three specializations", {("mage", "frost"): 0.4, ("mage", "arcane"): 0.3, ("mage", "fire"): 0.25, ("rogue", "combat"): 0.05}, ("mage", "frost")),
        ("Three classes, three roles", {("paladin", "holy"): 0.34, ("warlock", "destruction"): 0.33, ("rogue", "combat"): 0.33}, ("paladin", "holy")),
    ]
    _rows = [["Posterior", "Recommended", "Its probability", "Its class", "Its role", "Confidence C"]]
    for _label, _post, _rec in _examples:
        _vec = [0.0] * 27
        for (_cid, _sid), _w in _post.items():
            _vec[_g(_cid, _sid)] = _w
        _p = _mdl.confidence_parts(_vec, _g(*_rec), ad.class_credit, ad.role_credit)
        _rows.append([_label, f"{_rec[0].capitalize()} {_rec[1].replace('_', ' ').title()}", pct(_p.spec), pct(_p.class_), pct(_p.role), pct(_p.overall)])
    story += [table(_rows, widths=[1.9 * inch, 1.5 * inch, 0.9 * inch, 0.8 * inch, 0.8 * inch, WIDTH - 5.9 * inch], align_right_from=2),
              P(f"<b>Table 9.</b> The confidence for four example posteriors, with c = {ad.class_credit:g} and r = {ad.role_credit:g}. The probabilities of the specialization, its class and its role are always shown beside the "
                "confidence; with c = r = 0 the confidence is just the first of them.", SMALL)]
    story += [P("8.3&nbsp;&nbsp;Choosing the next question", H2),
              P("For each unanswered question the Oracle computes the <b>expected information gain</b>: how much, on average, the answer would reduce the uncertainty about the type. "
                "It asks the question with the largest gain (ties go to the earlier question; gains are compared after rounding to nine decimals).")]
    story += [eq(r"H(\pi)=-\sum_{\tau}\pi(\tau)\ln\pi(\tau)\qquad \mathrm{IG}(q)=H(\pi)-\sum_{r}P(r\,|\,q)\,H\left(\pi(\cdot\,|\,r)\right)\qquad P(r\,|\,q)=\sum_{\tau}\pi(\tau)\,P(r\,|\,\tau,q)")]
    post0 = np.full(27, 1 / 27)
    gains0 = sorted(zip(sim.gains(post0, list(range(sim.nq))), [q.id for q in c.questions], [q.type for q in c.questions]), reverse=True)
    rows = [["Rank", "Question", "Type", "Information gain (nats)", "Of the maximum ln 27"]]
    for k, (g, qid, ty) in enumerate(gains0[:8], start=1):
        rows.append([str(k), qid.upper(), ty.replace("_", " "), f"{g:.3f}", pct(g / math.log(27), 1)])
    story += [table(rows, widths=[0.5 * inch, 0.9 * inch, 1.1 * inch, 1.6 * inch, 1.6 * inch]),
              P("<b>Table 10.</b> The eight most informative first questions (before any answer). The Oracle always opens with the first one; what it asks next depends on your answers.", SMALL)]
    story += [P("8.4&nbsp;&nbsp;When to stop", H2)]
    story += [eq(r"\mathrm{stop\ when}\quad n\geq n_{\min}\ \ \mathrm{and}\ \ \pi\left(\hat\tau\,|\,r_{1:n}\right)\geq \theta\quad\mathrm{or}\quad n\geq n_{\max},\qquad \hat\tau=\mathrm{recommended\ specialization}")]
    story += [table([["Setting", "Symbol", "Value", "Meaning"],
                     ["Minimum questions", "n<sub>min</sub>", "none" if ad.min_questions <= 1 else str(ad.min_questions), "never reveal earlier (1 means no minimum)"],
                     ["Maximum questions", "n<sub>max</sub>", str(ad.max_questions), "reveal anyway (a “Close call” is possible)"],
                     ["Confidence threshold", "θ", pct(ad.confidence, 0), "confidence C the recommendation must reach"],
                     ["Class sharpness", "λ<sub>c</sub>", f"{ad.sharpness_class:g}", "how strongly class weights steer an answer"],
                     ["Specialization sharpness", "λ<sub>s</sub>", f"{ad.sharpness_spec:g}", "how strongly a profile steers an answer"],
                     ["Credit for the same class", "c", f"{ad.class_credit:g}", "weight of another specialization of the recommended class in the confidence"],
                     ["Credit for a similar role", "r", f"{ad.role_credit:g}", "weight of a specialization sharing a role with the recommended one"]],
                    widths=[1.7 * inch, 0.8 * inch, 0.8 * inch, WIDTH - 3.3 * inch], align_right_from=-1),
              P("<b>Table 11.</b> Confidence-mode settings (admin: Profiles & Settings).", SMALL)]

    # ---- simulations
    rows = [["Question order", "Mean questions", "Median", "90th percentile", "Reached the limit", "Mean stop confidence", "Right type at stop"]]
    for name, r in (("adaptive (information gain)", base), ("fixed (quiz order)", fixed)):
        rows.append([name, f"{r['mean_n']:.1f}", f"{r['median_n']:.0f}", f"{r['p90_n']:.0f}", pct(r["capped"], 0), pct(r["mean_conf"]), pct(r["accuracy"])])
    story += [P("8.5&nbsp;&nbsp;What to expect: simulated respondents", H2),
              P(f"To see how the procedure behaves, {n_sim} simulated people were generated for each row: a type is drawn uniformly, then they answer every question the Oracle asks "
                "as the model says that type would. The numbers follow exactly from the assumptions and measure no real people."),
              table(rows, widths=[1.9 * inch, 0.8 * inch, 0.6 * inch, 0.8 * inch, 0.8 * inch, 0.9 * inch, WIDTH - 5.8 * inch]),
              P("<b>Table 12.</b> Adaptive question choice versus asking in quiz order, under the model. Choosing questions by information gain saves several questions.", SMALL)]
    # calibration
    confs = np.array([r["conf"] for r in base["runs"]])
    right = np.array([r["earned"] for r in base["runs"]])
    bins = [(0.0, 0.8), (0.8, 0.9), (0.9, 0.95), (0.95, 0.99), (0.99, 1.01)]
    rows = [["Stop confidence", "Runs", "Mean stated confidence", "Credit earned"]]
    for lo, hi in bins:
        m = (confs >= lo) & (confs < hi)
        if m.sum():
            rows.append([f"{lo:.2f} to {min(hi, 1):.2f}", str(int(m.sum())), pct(confs[m].mean()), pct(right[m].mean())])
    story += [P("Because the posterior is exact within the model, the stated confidence should match the credit the recommendation earns among simulated people who stop with that "
                "confidence (1 when the specialization is exactly right, c or r when only the class or the role is). It does, up to sampling noise:"),
              table(rows, widths=[1.6 * inch, 0.8 * inch, 1.8 * inch, 1.5 * inch]),
              P("<b>Table 13.</b> Calibration inside the model. This checks the arithmetic. It cannot show that real people answer the way the model does.", SMALL)]

    def draw_hist(ax):
        bins_ = np.arange(0.5, 31.5, 1)
        ax.hist([r["n"] for r in base["runs"]], bins=bins_, alpha=0.75, label="adaptive", color="#4a3fb5")
        ax.hist([r["n"] for r in fixed["runs"]], bins=bins_, alpha=0.55, label="quiz order", color="#d98c2b")
        ax.set_xlabel("questions asked before the reading", fontsize=8)
        ax.set_ylabel("simulated people", fontsize=8)
        ax.legend(fontsize=7, frameon=False)
        ax.tick_params(labelsize=7)
    story += [figure(draw_hist, height=2.2 * inch), P("<b>Figure 2.</b> How many questions simulated respondents are asked.", SMALL)]

    # curves
    print("simulating full curves ...", flush=True)
    rng = np.random.default_rng(7)
    curves = {"adaptive": [], "fixed": []}
    for order in curves:
        for _ in range(max(30, n_sim // 4)):
            curves[order].append(sim.run(rng, tau=int(rng.integers(27)), order=order, stop=(31, 31, 1.0), full=True))
    ent = {k: np.mean([r["ents"] for r in v], axis=0) for k, v in curves.items()}
    cf = {k: np.mean([r["confs"] for r in v], axis=0) for k, v in curves.items()}

    def draw_curve(ax):
        xs = np.arange(1, 31)
        ax.plot(xs, cf["adaptive"][:30], label="adaptive", color="#4a3fb5", lw=1.6)
        ax.plot(xs, cf["fixed"][:30], label="quiz order", color="#d98c2b", lw=1.6)
        ax.axhline(ad.confidence, color="#444", lw=0.8, ls="--")
        if ad.min_questions > 1:
            ax.axvline(ad.min_questions, color="#999", lw=0.8, ls=":")
        ax.set_xlabel("questions answered", fontsize=8)
        ax.set_ylabel("mean confidence", fontsize=8)
        ax.set_ylim(0, 1.02)
        ax.legend(fontsize=7, frameon=False, loc="lower right")
        ax.tick_params(labelsize=7)
    story += [figure(draw_curve, height=2.2 * inch),
              P(f"<b>Figure 3.</b> Mean confidence after each question for simulated respondents (the first 30 questions asked, with no stopping). Dashed: the {pct(ad.confidence, 0)} threshold" + (f"; dotted: the minimum of {ad.min_questions}." if ad.min_questions > 1 else "."), SMALL)]
    rows = [["After n questions", "Uncertainty H, adaptive (nats)", "H, quiz order (nats)", "Confidence, adaptive", "Confidence, quiz order"]]
    for n in (0, 1, 3, 5, 8, 10, 12, 15, 20, 25, 30):
        h_a = math.log(27) if n == 0 else ent["adaptive"][n - 1]
        h_f = math.log(27) if n == 0 else ent["fixed"][n - 1]
        c_a = 1 / 27 if n == 0 else cf["adaptive"][n - 1]
        c_f = 1 / 27 if n == 0 else cf["fixed"][n - 1]
        rows.append([str(n), f"{h_a:.3f}", f"{h_f:.3f}", pct(c_a), pct(c_f)])
    story += [table(rows, widths=[1.2 * inch, 1.8 * inch, 1.5 * inch, 1.2 * inch, WIDTH - 5.7 * inch]),
              P("<b>Table 14.</b> Average uncertainty and confidence by number of questions, for simulated respondents.", SMALL)]

    # sensitivity
    print("simulating sensitivity ...", flush=True)
    rows = [["λ<sub>s</sub> (specialization sharpness)", "Mean questions", "Median", "Reached the limit", "Mean stop confidence", "Right type at stop"]]
    for ls in (0.2, 0.25, 0.3, 0.35, 0.4, 0.5):
        r = cohort(Simulator(cfg, sharp_spec=ls), n_sim, 202)
        rows.append([f"{ls:g}" + (" (default)" if abs(ls - ad.sharpness_spec) < 1e-9 else ""), f"{r['mean_n']:.1f}", f"{r['median_n']:.0f}", pct(r["capped"], 0), pct(r["mean_conf"]), pct(r["accuracy"])])
    story += [P("8.6&nbsp;&nbsp;How much the assumptions matter", H2),
              P("The sharpness constant is the one number that is a pure assumption. A larger value assumes answers reveal the type more clearly, so the Oracle needs fewer questions "
                "and reaches its threshold more easily; a smaller value assumes noisier answers and asks for more. If real people are noisier than the default assumes, the true "
                "accuracy at a stated 90% is lower than 90%."),
              table(rows, widths=[2.1 * inch, 0.9 * inch, 0.6 * inch, 1.0 * inch, 1.1 * inch, WIDTH - 5.7 * inch]),
              P("<b>Table 15.</b> Effect of the specialization sharpness (λ<sub>c</sub> held at its default), simulated respondents.", SMALL)]
    rows = [["Confidence threshold θ", "Mean questions", "Median", "Reached the limit", "Mean stop confidence", "Right type at stop"]]
    for th in (0.8, 0.9, 0.95, 0.99):
        r = cohort(sim, n_sim, 303, stop=(ad.min_questions, ad.max_questions, th))
        rows.append([pct(th, 0) + (" (default)" if abs(th - ad.confidence) < 1e-9 else ""), f"{r['mean_n']:.1f}", f"{r['median_n']:.0f}", pct(r["capped"], 0), pct(r["mean_conf"]), pct(r["accuracy"])])
    story += [table(rows, widths=[2.1 * inch, 0.9 * inch, 0.6 * inch, 1.0 * inch, 1.1 * inch, WIDTH - 5.7 * inch]),
              P("<b>Table 16.</b> The trade between certainty and length: higher thresholds ask more questions and are right more often.", SMALL)]
    rnd = cohort(sim, n_sim, 404, order="adaptive", answer="random")
    story += [P(f"<b>People who answer at random.</b> With no consistent type there is nothing to find: under uniformly random answers the mean stop is {rnd['mean_n']:.1f} questions, "
                f"{pct(rnd['capped'], 0)} of such respondents run to the limit of {ad.max_questions}, and the final reading has a typical confidence of {pct(rnd['mean_conf'], 0)}. "
                "The result is then reported with a lower confidence and a weaker label, which is the intended behaviour.")]

    # ---- robustness: respondents less consistent than the model assumes
    print("simulating less consistent respondents ...", flush=True)
    core_cfg = cfg.model_copy(deep=True)
    core_cfg.questions = [q for q in core_cfg.questions if q.min_length != "adaptive"]
    sim_core = Simulator(core_cfg)
    rows = [["Respondents are", "Questions asked", "Mean questions", "Reached the limit", "Mean stated confidence", "Credit earned", "Exact specialization right"]]
    res = {}
    for k in (1.0, 0.7, 0.5):
        truth_full = Simulator(cfg, sharp_spec=ad.sharpness_spec * k, sharp_class=ad.sharpness_class * k).p
        truth_core = Simulator(core_cfg, sharp_spec=ad.sharpness_spec * k, sharp_class=ad.sharpness_class * k).p
        for label, s_, tr in ((f"all {sim.nq} questions", sim, truth_full), (f"the {sim_core.nq} fixed-quiz questions", sim_core, truth_core)):
            r = cohort(s_, n_sim, 505, truth=tr)
            res[(k, s_.nq)] = r
            rows.append([f"{pct(k, 0)} as consistent as assumed", label, f"{r['mean_n']:.1f}", pct(r["capped"], 0), pct(r["mean_conf"]), pct(r["earned"]), pct(r["accuracy"])])
    story += [P("8.7&nbsp;&nbsp;If people are less consistent than the model assumes", H2),
              P("The stated confidence is exact only when people answer the way the model says. To see how far it can mislead, respondents were simulated who are only 70% or 50% as "
                "consistent as the Oracle assumes (their sharpness is scaled down; the Oracle's own model is unchanged). The stated confidence then overstates how often the "
                "recommendation is right, by an amount that grows as respondents get noisier. "
                f"At 70% consistency the pool of {sim.nq} questions earns {pct(res[(0.7, sim.nq)]['earned'], 0)} credit against {pct(res[(0.7, sim_core.nq)]['earned'], 0)} for the {sim_core.nq} fixed-quiz questions, "
                f"but it also stops sooner, so its stated confidence overshoots by {100 * (res[(0.7, sim.nq)]['mean_conf'] - res[(0.7, sim.nq)]['earned']):.0f} points against {100 * (res[(0.7, sim_core.nq)]['mean_conf'] - res[(0.7, sim_core.nq)]['earned']):.0f}. "
                "Raising the confidence threshold in the admin settings narrows the gap at the cost of more questions (Table 16)."),
              table(rows, widths=[1.5 * inch, 1.5 * inch, 0.7 * inch, 0.7 * inch, 0.8 * inch, 0.7 * inch, WIDTH - 5.9 * inch]),
              P("<b>Table 17.</b> Stated confidence against actual accuracy when respondents are less consistent than assumed.", SMALL)]

    # ---- other ways of choosing the next question
    print("simulating other question-choice rules ...", flush=True)
    n_rules = 150 if n_sim < 100 else 1500
    rules = [("adaptive", "Information gain over all 27 types (used)"), ("leader", "Information about whether the leader is right"),
             ("best_guess", "Expected probability of the best guess after the answer"), ("challenger", "Evidence between the leader and its challengers"),
             ("spread", "How far the answer can move the leader's probability (confirm or reset)"), ("finish", "Chance this answer reaches the threshold"),
             ("fixed", "Quiz order (for reference)")]
    results = {key: cohort(sim, n_rules, 606, order=key) for key, _ in rules}
    rows = [["Rule for the next question", "Mean questions", "Median", "90th percentile", "Reached the limit", "Right type at stop"]]
    for key, label in rules:
        r = results[key]
        rows.append([label, f"{r['mean_n']:.1f}", f"{r['median_n']:.0f}", f"{r['p90_n']:.0f}", pct(r["capped"], 0), pct(r["accuracy"])])
    others = [results[k]["mean_n"] for k, _ in rules if k not in ("adaptive", "fixed")]
    gap = min(others) - results["adaptive"]["mean_n"]
    verdict = (f"None needed fewer questions than information gain; the closest needed {gap:.1f} more." if gap >= 0
               else f"The best of the others saved {-gap:.1f} questions, which is within the noise of {n_rules:,} simulated respondents per row.")
    story += [P("8.8&nbsp;&nbsp;Aiming questions at the leader", H2),
              P("An obvious alternative is to aim each question at the current leader, so that the answer either confirms it or sends the Oracle back to look elsewhere. Several such rules "
                f"were simulated against information gain, with {n_rules:,} respondents per row. {verdict} Information gain already does this job: once one specialization leads, "
                "nearly all of the remaining uncertainty is about the leader and its closest rivals, so the most informative question is the one that separates them. Early on, "
                "when nothing leads yet, a rule that aims at the leader has nothing to aim at."),
              table(rows, widths=[3.2 * inch, 0.8 * inch, 0.6 * inch, 0.8 * inch, 0.8 * inch, WIDTH - 6.2 * inch]),
              P("<b>Table 18.</b> Ways of choosing the next question, under the model.", SMALL)]

    # ---- the pool
    core_idx = [i for i, q in enumerate(c.questions) if q.length_rank < len(LENGTHS)]
    extra_idx = [i for i in range(sim.nq) if i not in core_idx]
    if extra_idx:
        def pair_evidence(idx):
            tot = np.zeros((sim.nt, sim.nt))
            for q in idx:
                Pq = sim.p[q]
                L = np.log(Pq)
                k = np.einsum("ra,rab->ab", Pq, L[:, :, None] - L[:, None, :])
                tot += k + k.T
            return tot
        ev_core, ev_all = pair_evidence(core_idx), pair_evidence(range(sim.nq))
        type_class = [ci for ci, cls in enumerate(c.classes) for _ in cls.specs]
        type_name = [f"{cls.name} {sp.name}" for cls in c.classes for sp in cls.specs]
        within = sorted((ev_core[a, b], ev_all[a, b], a, b) for a in range(sim.nt) for b in range(a + 1, sim.nt) if type_class[a] == type_class[b])
        rows = [["Pair of specializations in one class", f"Evidence from the {len(core_idx)} fixed-quiz questions", f"Evidence from all {sim.nq} questions"]]
        rows += [[f"{type_name[a]} and {type_name[b]}", f"{e0:.1f}", f"{e1:.1f}"] for e0, e1, a, b in within[:8]]
        mean_q = lambda idx: float(np.mean([pair_evidence([q]).sum() / (sim.nt * (sim.nt - 1)) for q in idx]))
        n_class = sum(1 for q in c.questions if q.id in CLASS_ORDER)
        n_spec = len(extra_idx) - n_class
        story += [P(f"8.9&nbsp;&nbsp;Why the pool has {sim.nq} questions", H2),
                  P(f"The {len(core_idx)} questions of the fixed quizzes separate classes well and separate the specializations of one class poorly. Measured as the total evidence a pool can give about "
                    "a pair of types (the sum over questions of the symmetric Kullback-Leibler divergence between how the two types answer, in nats), the weakest pairs are all within one class, "
                    f"and the median within-class pair has {np.median([w[0] for w in within]):.0f} nats of evidence against {np.median([ev_core[a, b] for a in range(sim.nt) for b in range(a + 1, sim.nt) if type_class[a] != type_class[b]]):.0f} across classes. "
                    f"{n_spec} of the confidence-mode-only questions (two for each class, a role question and a distance question) are aimed at that gap and raise the median within-class pair to "
                    f"{np.median([w[1] for w in within]):.0f} nats. A question in the fixed quizzes carries {mean_q(core_idx):.2f} nats per pair on average and one of the added ones {mean_q([i for i in extra_idx if c.questions[i].id not in CLASS_ORDER]):.2f}, "
                    "so the gain comes from covering the weak pairs. No weight was made heavier to get there."),
                  table(rows, widths=[3.2 * inch, 1.6 * inch, WIDTH - 4.8 * inch], align_right_from=-1),
                  P("<b>Table 19.</b> The eight within-class pairs the fixed-quiz questions separate least, before and after the added questions.", SMALL)]
        if n_class:
            # class-level evidence: a class answers like an even mix of its specializations
            def class_pairs(q):
                Pc = (sim.p[q] @ sim.onehot) / 3.0
                L = np.log(Pc)
                k = np.einsum("rc,rcd->cd", Pc, L[:, :, None] - L[:, None, :])
                return k + k.T
            ev_cls = np.array([class_pairs(q) for q in range(sim.nq)])
            trios = [(a, b, d) for a in range(9) for b in range(a + 1, 9) for d in range(b + 1, 9)]
            strong = np.array([[min(ev_cls[q][a, b], ev_cls[q][a, d], ev_cls[q][b, d]) for (a, b, d) in trios] for q in range(sim.nq)]) >= 1.0
            first_fifty = [i for i, q in enumerate(c.questions) if q.id not in CLASS_ORDER and int(q.id[1:]) <= 50]
            rows = [["Questions counted", "Fewest for a trio", "Median", "Most"]]
            for label, idx in ((f"the {len(core_idx)} fixed-quiz questions", core_idx), (f"the first {len(first_fifty)} questions", first_fifty), (f"all {sim.nq} questions", list(range(sim.nq)))):
                n_sep = strong[idx].sum(axis=0)
                rows.append([label, str(int(n_sep.min())), f"{np.median(n_sep):.0f}", str(int(n_sep.max()))])
            story += [P(f"The other {n_class} confidence-mode-only questions are personality questions in which every answer belongs to a different class, so that a person torn among their three leading "
                        "classes is asked to choose among exactly those three, many times over. The table counts, for each of the 84 trios of classes, the questions that tell all three apart by at least one nat. "
                        f"They carry {np.mean([ev_cls[i].sum() / 72 for i in range(sim.nq) if c.questions[i].id in CLASS_ORDER]):.2f} nats per class pair against {np.mean([ev_cls[i].sum() / 72 for i in core_idx]):.2f} for the fixed-quiz questions: a little more, because each answer names a class no other answer does."),
                      table(rows, widths=[2.6 * inch, 1.3 * inch, 1.0 * inch, WIDTH - 4.9 * inch], align_right_from=-1),
                      P("<b>Table 20.</b> Questions that separate every class of a trio, by trio.", SMALL)]

    # ================================================================ 9 worked example
    print("worked example ...", flush=True)
    model = adaptive_mod.Model(c)
    answers, steps = {}, []
    labels = {q.id: q for q in cfg.questions}
    tau = next(sp.gidx for cl in c.classes if cl.id == "druid" for sp in cl.specs if sp.id == "feral_combat")
    PERSONA = {q.id: q.answer_ids[max(range(len(q.answer_ids)), key=lambda r: model.logp[i][r][tau])] for i, q in enumerate(c.questions)}
    for _ in range(len(c.questions)):
        st = adaptive_mod.status(c, answers, model=model)
        if steps is not None and st.answered:
            steps[-1].update({"top": st.recommended, "conf": st.confidence, "h": st.entropy})
        if st.done:
            break
        qid = st.next_question_id
        steps.append({"n": st.answered + 1, "q": qid, "type": labels[qid].type, "r": PERSONA[qid], "gain": st.expected_gain})
        answers[qid] = PERSONA[qid]
    fin = adaptive_mod.status(c, answers, model=model)
    rows = [["n", "Question", "Type", "Response", "Expected gain (nats)", "Recommended after answering", "Confidence", "H (nats)"]]
    for s in steps:
        rows.append([str(s["n"]), s["q"].upper(), s["type"].replace("_", " "), f"<font name='DVM'>{s['r']}</font>", f"{s['gain']:.3f}",
                     f"{s['top'].class_name} {s['top'].specialization_name}", pct(s["conf"]), f"{s['h']:.3f}"])
    story += [P("9&nbsp;&nbsp;A worked example", H1),
              P("A fixed example respondent taking the quiz in confidence mode: a person of type Druid Feral Combat who always gives the response the model finds most likely for that type. "
                "At each step the table shows which question the Oracle chose, the response, how much information it expected from it, and where the posterior stood after the answer."),
              table(rows, widths=[0.3 * inch, 0.7 * inch, 0.8 * inch, 0.85 * inch, 0.85 * inch, 1.65 * inch, 0.85 * inch, WIDTH - 6.0 * inch], align_right_from=-1, font=7.2),
              P(f"<b>Table 21.</b> The example run stops after {fin.answered} questions with {pct(fin.confidence)} confidence in {fin.recommended.class_name} {fin.recommended.specialization_name}. "
                "The five most probable types at the end:", SMALL)]
    rows = [["Type", "Probability"]] + [[f"{t.class_name} {t.specialization_name}", pct(t.probability, 2)] for t in fin.top]
    story += [table(rows, widths=[2.6 * inch, 1.2 * inch])]
    from app.scoring import evaluate
    ev = evaluate(cfg, answers, include_explanation=False, length="adaptive")
    story += [P(f"The deterministic result for the same {fin.answered} answers: {ev.result.primary_specialization.name} {ev.result.primary_class.name}; top-two class gap "
                f"G = {ev.result.confidence.class_gap:.2f}; label “{ev.result.confidence.label}” (margins {ev.result.confidence.strong_margin:.2f} and {ev.result.confidence.moderate_margin:.2f}).")]

    # ================================================================ 10 assumptions
    story += [P("10&nbsp;&nbsp;Assumptions and limits", H1),
              P("• <b>Scores are relative.</b> A class score is a sum of differences from the average answer pattern. “+13” does not mean 13% or 13 of anything. The nine class scores of a complete answer set sum to zero."),
              P("• <b>The weights are judgement.</b> Which answers point to which classes comes from playstyle lore and the project's own reading of Blizzard's class descriptions, and no data backs it. The twenty confidence-mode-only questions follow the same conventions. "
                "Research on WoW players has found little or no link between personality and the class they choose."),
              P("• <b>Balance is a property of the rules.</b> “Every class equally likely” holds when every response is equally likely. Real answers are not uniform, so real results will not be evenly spread, and nothing here claims they should be."),
              P("• <b>The confidence is exact inside a model, and the model is an assumption.</b> It says: people of a type answer by a logit choice with sharpness λ, independently, from a uniform start. Real answers are correlated and noisier or "
                "sharper than any one λ. A person who is a real blend of several classes is treated as noise around one of them, so the confidence overstates what can be known about them. The confidence is also an expected credit, not the probability "
                "of the exact specialization, which is always shown beside it. Read “90% sure” as “the answers are as consistent with one specialization as this model requires”; no study of real respondents backs the figure."),
              P("• <b>Talent builds are drafts.</b> The builds shown with a result come from hand-assembled talent data dated November 2, 2026 and are unverified; they play no part in the selection."),
              P("• <b>Reproducibility.</b> Everything above is deterministic given the configuration; the simulations use fixed seeds. The browser and Python engines are tested to give identical results.")]

    # ================================================================ appendix A questions
    story += [PageBreak(), P("Appendix A&nbsp;&nbsp;The questions", H1)]
    rows = [["Id", "Type", "Responses", "Shortest quiz asking it (adaptive: confidence mode only)", "Question"]]
    comp = compile_config(cfg)
    for q in cfg.enabled_questions():
        cq = comp.questions[comp.q_index[q.id]]
        text = q.text if len(q.text) < 120 else q.text[:117] + "…"
        rows.append([q.id.upper(), q.type.replace("_", " "), str(len(cq.answer_ids)), q.min_length, text.replace("&", "&amp;").replace("<", "&lt;")])
    story += [table(rows, widths=[0.45 * inch, 0.8 * inch, 0.7 * inch, 1.3 * inch, WIDTH - 3.25 * inch], align_right_from=-1)]

    # ================================================================ appendix B weights
    story += [PageBreak(), P("Appendix B&nbsp;&nbsp;Answer weights", H1),
              P("Class weights always add up to 3 for an answer (usually 2 and 1; some are adjusted by a quarter point to equalize the classes); trait weights are 2 and 1; "
                "“direct” lists specialization weights (multiplied by M in P<sub>s</sub>). For a scale question the two answers are the “agree” and “disagree” poles. "
                f"{len(cfg.traits)} traits: " + ", ".join(f"{t.name} ({t.id})" for t in cfg.traits) + ".", SMALL)]
    cn = {cl.id: cl.name for cl in cfg.classes}
    sn = {f"{cl.id}/{sp.id}": f"{cl.name} {sp.name}" for cl in cfg.classes for sp in cl.specializations}
    rows = [["Answer", "Class weights", "Trait weights", "Direct specialization weights"]]
    for q in cfg.enabled_questions():
        for a in q.answers:
            cw = ", ".join(f"{cn[k]} {v:g}" for k, v in sorted(a.class_weights.items(), key=lambda kv: -kv[1]))
            tw = ", ".join(f"{traits[k]} {v:g}" for k, v in sorted(a.trait_weights.items(), key=lambda kv: -kv[1]))
            dw = ", ".join(f"{sn[k]} {v:g}" for k, v in a.spec_weights.items())
            rows.append([f"{q.id.upper()} {a.id.upper() if len(a.id) == 1 else a.id}", cw, tw, dw or "none"])
    story += [table(rows, widths=[0.75 * inch, 1.9 * inch, 1.45 * inch, WIDTH - 4.1 * inch], align_right_from=-1, font=6.9)]

    # ------------------------------------------------------------------ build the file
    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("DV", 7.3)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN, 0.5 * inch, f"Forever Character Oracle · the mathematics · v{APP_VERSION} · algorithm {c.algorithm_version}")
        canvas.drawRightString(PAGE_W - MARGIN, 0.5 * inch, f"Page {doc.page}")
        canvas.setStrokeColor(RULE)
        canvas.line(MARGIN, 0.62 * inch, PAGE_W - MARGIN, 0.62 * inch)
        canvas.restoreState()

    out.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(out), pagesize=letter, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=0.75 * inch, bottomMargin=0.85 * inch,
                            title="How the Forever Character Oracle chooses: the mathematics", author="Anibru", subject="Scoring, balance and the confidence model")
    doc.build(keep_captions(story), onFirstPage=on_page, onLaterPages=on_page)
    return {"pages": doc.page, "path": str(out), "sim_runs": n_sim}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", help="exported configuration JSON (default: the seed)")
    ap.add_argument("--out", default=str(ROOT / "docs" / "oracle-math.pdf"))
    ap.add_argument("--quick", action="store_true", help="fewer simulated runs (a fast draft)")
    args = ap.parse_args(argv)
    cfg = Config.model_validate_json(Path(args.config).read_text()) if args.config else build_default_config()
    info = build(cfg, Path(args.out), quick=args.quick)
    print(f"Wrote {info['path']}: {info['pages']} pages ({os.path.getsize(info['path']) // 1024} KB), {info['sim_runs']} simulated respondents per row.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
