// Components shared by several administrative views.
import { h, fmt, signed, pct, badge, barChart, chartLegend, tipRows } from "../ui.js";

/** A grid of non-negative number inputs. onInput(id, value) receives a number, or NaN for invalid text. */
export function weightGrid(items, values, onInput, saved = values) {
  const inputs = {};
  const grid = h("div", { class: "weights" }, items.map((it) => {
    const input = h("input", {
      type: "number", min: "0", step: "0.25", inputmode: "decimal", value: String(values[it.id] ?? 0), "aria-label": it.name,
      oninput: () => {
        const v = input.value.trim() === "" ? NaN : Number(input.value);
        const bad = !Number.isFinite(v) || v < 0;
        input.setAttribute("aria-invalid", bad ? "true" : "false");
        onInput(it.id, bad ? NaN : v);
        paint(it.id);
      },
    });
    inputs[it.id] = input;
    return h("label", { title: it.hint || null }, it.name, input);
  }));
  const paint = (id) => {
    const v = Number(inputs[id].value);
    inputs[id].classList.toggle("nonzero", v > 0);
    inputs[id].classList.toggle("dirty", Number.isFinite(v) ? v !== (saved[id] ?? 0) : true);
  };
  items.forEach((it) => paint(it.id));
  return grid;
}

export function nonzero(obj) {
  return Object.fromEntries(Object.entries(obj).filter(([, v]) => v > 0));
}

/** One selected response per question: A-D buttons, 1-10 buttons, or a pair menu, depending on the question type. */
export function answerPicker(cfg, answers, onChange) {
  const rows = cfg.questions.filter((q) => q.enabled).map((q) => {
    let control;
    if (q.type === "pick_two") {
      const ids = q.answers.map((a) => a.id);
      const pairs = ids.flatMap((x, i) => ids.slice(i + 1).map((y) => `${x}+${y}`));
      control = h("select", {
        "aria-label": `${q.id} pair`,
        onchange: (e) => { if (e.target.value) answers[q.id] = e.target.value; else delete answers[q.id]; onChange(answers); },
      }, h("option", { value: "" }, "\u2013 none \u2013"),
        pairs.map((p) => h("option", { value: p, selected: answers[q.id] === p, title: p }, p.toUpperCase().replace("+", " + "))));
    } else {
      const options = q.type === "scale"
        ? Array.from({ length: 10 }, (_, i) => ({ value: String(i + 1), label: String(i + 1), title: `${i + 1} of 10` }))
        : q.answers.map((a) => ({ value: a.id, label: a.id.toUpperCase(), title: a.text }));
      const seg = h("span", { class: "seg", role: "group", "aria-label": `${q.id} response` });
      options.forEach((o) => seg.append(h("button", {
        type: "button", "aria-pressed": answers[q.id] === o.value ? "true" : "false", title: o.title, "data-value": o.value,
        onclick: () => {
          if (answers[q.id] === o.value) delete answers[q.id]; else answers[q.id] = o.value;
          seg.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.value === answers[q.id] ? "true" : "false"));
          onChange(answers);
        },
      }, o.label)));
      control = seg;
    }
    return h("div", { class: "pick-row" },
      h("span", { class: "q" }, q.id), h("span", { class: "qtext", title: q.text }, q.text), control);
  });
  return h("div", { class: "picker" }, rows);
}

export function resultLine(primary) {
  return `${primary.class_name} – ${primary.specialization_name}`;
}

/** Saved vs simulated outcome for a /simulate response. */
export function comparisonView(sim) {
  const changed = sim.winning_class_changed ? ["Winning class changed", "bad"] : sim.winning_specialization_changed ? ["Winning specialization changed", "warn"] : ["Same result", "ok"];
  const rows = [...sim.simulated.rankings.classes].map((c) => {
    const o = sim.class_differences.find((d) => d.id === c.id);
    return { id: c.id, label: c.name, value: c.score, ghost: o.original, tip: [["Saved", signed(o.original)], ["Simulated", signed(o.simulated)], ["Difference", signed(o.difference)]] };
  });
  const specKeys = new Set([sim.original_primary.class_id, sim.simulated_primary.class_id]);
  const specRows = sim.specialization_differences.filter((s) => specKeys.has(s.class_id));
  const infl = sim.question_influence.slice(0, 6);
  const maxInfl = Math.max(0.01, ...infl.flatMap((i) => [Math.abs(i.original_effect), Math.abs(i.simulated_effect)]));
  return h("div", { class: "stack" },
    h("div", { class: "row" },
      h("span", {}, "Saved: ", h("b", {}, resultLine(sim.original_primary))),
      h("span", { "aria-hidden": "true" }, "→"),
      h("span", {}, "Simulated: ", h("b", {}, resultLine(sim.simulated_primary))),
      badge(changed[0], changed[1])),
    h("div", {},
      h("h4", {}, "Class scores"),
      barChart(rows, { leadId: sim.simulated_primary.class_id }),
      chartLegend([h("span", {}, h("i", { class: "ghost" }), "outline = saved configuration (fill = simulated)")])),
    h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, ["Class", "Saved", "Simulated", "Difference"].map((t, i) => h("th", { class: i ? "num" : "" }, t)))),
      h("tbody", {}, sim.class_differences.map((d) => h("tr", {}, h("td", {}, d.name), h("td", { class: "num" }, signed(d.original)), h("td", { class: "num" }, signed(d.simulated)),
        h("td", { class: `num ${d.difference > 0 ? "pos" : d.difference < 0 ? "neg" : "zero"}` }, signed(d.difference))))))),
    h("div", {},
      h("h4", {}, `Specializations (${[...specKeys].map((k) => sim.specialization_differences.find((s) => s.class_id === k)?.class_id).join(" / ")})`),
      h("div", { class: "table-wrap" }, h("table", {},
        h("thead", {}, h("tr", {}, ["Specialization", "Saved", "Simulated", "Difference"].map((t, i) => h("th", { class: i ? "num" : "" }, t)))),
        h("tbody", {}, specRows.map((s) => h("tr", {}, h("td", {}, `${s.class_id} / ${s.name}`), h("td", { class: "num" }, signed(s.original)), h("td", { class: "num" }, signed(s.simulated)),
          h("td", { class: `num ${s.difference > 0 ? "pos" : s.difference < 0 ? "neg" : "zero"}` }, signed(s.difference)))))))),
    h("div", {},
      h("h4", {}, "Questions that most influenced the result"),
      h("p", { class: "muted", style: { fontSize: "0.85rem" } }, "Each question's contribution to the gap between the winning and runner-up class (fill = simulated, outline = saved)."),
      barChart(infl.map((i) => ({ id: i.question_id, label: i.question_id, value: i.simulated_effect, ghost: i.original_effect,
        tip: [["Saved", signed(i.original_effect)], ["Simulated", signed(i.simulated_effect)]] })))),
  );
}

/** Class-selection frequencies over random answer sets, with an optional comparison column. */
export function batchView(batch) {
  const base = batch.baseline, sim = batch.simulated;
  const uni = batch.uniform_class_frequency;
  const rows = base.class_frequencies.map((c, i) => ({
    id: c.id, label: c.name, value: c.frequency, ghost: sim ? undefined : undefined, c, s: sim ? sim.class_frequencies[i] : null,
  }));
  const maxF = Math.max(uni * 1.6, ...rows.flatMap((r) => [r.c.frequency, r.s ? r.s.frequency : 0]));
  const bar = (f, cls = "") => h("span", { class: "bar-track", style: { "--zero": "0%", display: "block", minWidth: "90px" } },
    h("i", { class: `bar-fill pos ${cls}`, style: { width: `${(f / maxF) * 100}%` } }),
    h("i", { style: { position: "absolute", left: `${(uni / maxF) * 100}%`, top: "-3px", bottom: "-3px", width: "0", borderLeft: "1px dashed var(--text-3)" } }));
  return h("div", { class: "stack" },
    h("div", { class: "stats" },
      h("div", { class: "stat" }, h("b", {}, batch.count.toLocaleString()), h("span", {}, "random answer sets")),
      h("div", { class: "stat" }, h("b", {}, String(batch.seed)), h("span", {}, "seed (reproducible)")),
      h("div", { class: "stat" }, h("b", {}, fmt(base.mean_class_gap)), h("span", {}, "mean top-two gap")),
      h("div", { class: "stat" }, h("b", {}, pct(base.close_calls / batch.count, 0)), h("span", {}, "close calls (gap under moderate margin)"))),
    h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Class"), h("th", { class: "num" }, "Selected"), h("th", {}, ""), sim ? h("th", { class: "num" }, "With override") : null, sim ? h("th", {}, "") : null,
        sim ? h("th", { class: "num" }, "Change") : null, h("th", { class: "num" }, "Mean score"))),
      h("tbody", {}, rows.map((r) => {
        const d = r.s ? (r.s.frequency - r.c.frequency) * 100 : 0;
        return h("tr", {},
          h("td", {}, r.label), h("td", { class: "num" }, pct(r.c.frequency)), h("td", {}, bar(r.c.frequency)),
          sim ? h("td", { class: "num" }, pct(r.s.frequency)) : null, sim ? h("td", {}, bar(r.s.frequency)) : null,
          sim ? h("td", { class: `num ${d > 0.05 ? "pos" : d < -0.05 ? "neg" : "zero"}` }, `${d > 0 ? "+" : d < 0 ? "−" : ""}${Math.abs(d).toFixed(1)} pp`) : null,
          h("td", { class: "num" }, signed(r.c.mean_score)));
      })))),
    h("p", { class: "bar-note" }, `Dashed line = an even split (${pct(uni)}). `, batch.note,
      " Mean scores near zero are expected: the normalization makes every class's expected score zero under uniformly random answers."),
  );
}
