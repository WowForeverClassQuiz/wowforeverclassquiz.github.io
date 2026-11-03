// Shared in-memory state. Participant answers live only here (session-local) and are never stored by the server.
import { get } from "./api.js";

export const state = {
  quiz: null,          // participant quiz (no weights)
  started: false,
  index: 0,
  answers: {},         // question id -> answer id
  result: null,        // last participant evaluation
  config: null,        // full admin configuration (loaded on demand)
  adminAnswers: {},    // hypothetical answer set used by the inspector and simulator
  adminEval: null,     // last administrative evaluation (with explanation)
  dirtyGuard: null,    // set by views with unsaved edits: (silent) => true when it is safe to leave
};

export function setRevision(rev) {
  const pill = document.getElementById("revision-pill");
  if (rev === null || rev === undefined) { pill.hidden = true; return; }
  pill.hidden = false;
  pill.textContent = `config r${rev}`;
}

export async function ensureConfig(force = false) {
  if (!state.config || force) state.config = await get("/config");
  setRevision(state.config.revision);
  return state.config;
}

export const classById = (cfg, id) => cfg.classes.find((c) => c.id === id);
export const className = (cfg, id) => (classById(cfg, id) || { name: id }).name;
export const traitName = (cfg, id) => (cfg.traits.find((t) => t.id === id) || { name: id }).name;
export const allSpecs = (cfg) => cfg.classes.flatMap((c) => c.specializations.map((s) => ({ ...s, class_id: c.id, class_name: c.name })));

/** Every enabled question with a response chosen uniformly at random, in the format /evaluate expects. */
export function randomAnswers(cfg, rng = Math.random) {
  const pick = (n) => Math.floor(rng() * n);
  const out = {};
  for (const q of cfg.questions.filter((q) => q.enabled)) {
    if (q.type === "scale") out[q.id] = String(1 + pick(10));
    else if (q.type === "pick_two") {
      const ids = q.answers.map((a) => a.id);
      const pairs = ids.flatMap((x, i) => ids.slice(i + 1).map((y) => `${x}+${y}`));
      out[q.id] = pairs[pick(pairs.length)];
    } else out[q.id] = q.answers[pick(q.answers.length)].id;
  }
  return out;
}
