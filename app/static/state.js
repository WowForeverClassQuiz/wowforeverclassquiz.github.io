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

export const ALLOCATION_POINTS = 6;

/** Every possible response id of a question, as /evaluate expects it ('a+c', 'c>a>d>b', '2-0-3-1', '7', or an answer id). */
export function responseIds(q) {
  const ids = (q.answers || []).map((a) => a.id);
  if (q.type === "scale") return Array.from({ length: 10 }, (_, i) => String(i + 1));
  if (q.type === "pick_two") return ids.flatMap((x, i) => ids.slice(i + 1).map((y) => `${x}+${y}`));
  if (q.type === "ranking") {
    const orderings = (rest) => (rest.length <= 1 ? [rest] : rest.flatMap((x) => orderings(rest.filter((y) => y !== x)).map((o) => [x, ...o])));
    return orderings(ids).map((o) => o.join(">"));
  }
  if (q.type === "allocation") {
    const out = [];
    for (let a = 0; a <= ALLOCATION_POINTS; a++) for (let b = 0; a + b <= ALLOCATION_POINTS; b++) for (let c = 0; a + b + c <= ALLOCATION_POINTS; c++) {
      out.push(`${a}-${b}-${c}-${ALLOCATION_POINTS - a - b - c}`);
    }
    return out;
  }
  return ids;
}

/** A readable form of a response id for menus: 'B › A › D › C' or 'A 2 · B 0 · C 3 · D 1'. */
export function responseLabel(q, rid) {
  if (q.type === "ranking") return rid.split(">").map((x) => x.toUpperCase()).join(" › ");
  if (q.type === "allocation") return rid.split("-").map((p, i) => `${String.fromCharCode(65 + i)} ${p}`).join(" · ");
  if (q.type === "pick_two") return rid.toUpperCase().replace("+", " + ");
  return rid.toUpperCase();
}

/** Every enabled question with a response chosen uniformly at random, in the format /evaluate expects. */
export function randomAnswers(cfg, rng = Math.random) {
  const out = {};
  for (const q of cfg.questions.filter((q) => q.enabled)) {
    const all = responseIds(q);
    out[q.id] = all[Math.floor(rng() * all.length)];
  }
  return out;
}
