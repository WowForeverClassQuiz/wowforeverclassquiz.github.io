// Class and specialization pages: one page for each of the nine classes (what it does, its three specializations) and one for
// each specialization (the traits that define it, what it does, its role and gear guide, its build). Reached from the first
// page, the "Also in the stars" cards or the navigation bar, and paged through with Previous/Next or the arrow keys. Nothing
// here depends on having taken the quiz; when there is a result, it is shown alongside.
import { h, clear, errorList, roleLabel, signed } from "../ui.js";
import { get } from "../api.js";
import { state } from "../state.js";
import { classIcon, specIcon, spellName } from "../icons.js";
import { overviewCard, guideCard, buildCard } from "../parts.js";

const ORDER = ["Primary", "Secondary", "Tertiary", "Fourth", "Fifth", "Sixth"];
let keysInstalled = false;
let neighbours = null;      // { prev, next } hash targets of the page on screen, for the arrow keys

const href = (c, s) => `#/specs/${c}/${s}`;

export async function render(container, args = []) {
  const { classes } = await get("/classes", { include_builds: false });
  const all = classes.flatMap((c) => c.specializations.map((s) => ({ ...s, class_id: c.id, class_name: c.name, class_description: c.description })));
  installKeys();
  clear(container);
  neighbours = null;
  if (!args[0]) return container.append(indexPage(classes));
  if (!args[1]) return renderClass(container, classes, args[0]);
  const at = all.findIndex((s) => s.class_id === args[0] && s.id === args[1]);
  if (at < 0) {
    return container.append(h("div", { class: "card" }, h("h2", {}, "No such specialization"),
      h("p", {}, "That page does not exist."), h("a", { class: "btn", href: "#/specs" }, "See every class and specialization")));
  }
  const page = await get(`/specializations/${args[0]}/${args[1]}`);
  const prev = all[(at + all.length - 1) % all.length], next = all[(at + 1) % all.length];
  neighbours = { prev: href(prev.class_id, prev.id), next: href(next.class_id, next.id) };
  document.title = `${page.name} ${page.class_name} · Forever Character Oracle`;
  container.append(specPage(page, all, at, prev, next));
}

// ---------------------------------------------------------------------------- what the participant's result says about a page
function standing(page) {
  const r = state.result;
  if (!r) return { tags: [], spec: null, traitScores: null };
  const same = (c, s) => c === page.class_id && s === page.id;
  const tags = [];
  if (same(r.result.primary_class.id, r.result.primary_specialization.id)) tags.push("Your result");
  if (same(r.alternatives.alternative_class.id, r.alternatives.alternative_specialization.id)) tags.push("Also in the stars");
  if (same(r.result.primary_class.id, r.alternatives.second_specialization_in_primary_class.id)) tags.push("Your next-closest path");
  return {
    tags,
    spec: r.rankings.all_specializations.find((s) => same(s.class_id, s.id)) || null,
    traitScores: Object.fromEntries(r.rankings.traits.map((t) => [t.id, t.score])),
  };
}

// ---------------------------------------------------------------------------- the index of every specialization
function indexPage(classes) {
  const r = state.result;
  return h("div", {},
    h("div", { class: "page-head" }, h("div", {}, h("h1", {}, "Every class and specialization"),
      h("p", {}, "Nine classes, three specializations each. Open a class to see what it does, or a specialization to see the traits that define it, its role and gear, and a build."))),
    r ? h("p", {}, h("a", { class: "btn", href: "#/" }, "Back to my result")) : null,
    classes.map((c) => h("section", { class: "card spec-class" },
      h("a", { class: "spec-class-head", href: `#/specs/${c.id}`, title: `About the ${c.name}` }, classIcon(c.id, 36, c.name),
        h("div", {}, h("h3", {}, c.name, h("span", { class: "alt-go" }, "  About this class →")), h("p", { class: "muted" }, c.description))),
      h("div", { class: "spec-grid" }, c.specializations.map((s) => h("a", { class: "spec-tile", href: href(c.id, s.id) },
        specIcon(c.id, s.id, 36),
        h("span", {}, h("b", {}, s.name), h("small", {}, `${roleLabel(s.role)}${spellName(c.id, s.id) ? ` · ${spellName(c.id, s.id)}` : ""}`)),
        r && r.result.primary_class.id === c.id && r.result.primary_specialization.id === s.id ? h("em", { class: "tile-tag" }, "your result") : null))))));
}

// ---------------------------------------------------------------------------- one class
function renderClass(container, classes, classId) {
  const at = classes.findIndex((c) => c.id === classId);
  if (at < 0) {
    return container.append(h("div", { class: "card" }, h("h2", {}, "No such class"),
      h("p", {}, "That page does not exist."), h("a", { class: "btn", href: "#/specs" }, "See every class and specialization")));
  }
  const c = classes[at], r = state.result;
  const prev = classes[(at + classes.length - 1) % classes.length], next = classes[(at + 1) % classes.length];
  neighbours = { prev: `#/specs/${prev.id}`, next: `#/specs/${next.id}` };
  document.title = `${c.name} · Forever Character Oracle`;
  const rank = r && r.rankings.classes.find((x) => x.id === c.id);
  const picker = h("select", { "aria-label": "Jump to a class", onchange: (e) => { location.hash = e.target.value; } },
    classes.map((x) => h("option", { value: `#/specs/${x.id}`, selected: x.id === c.id }, x.name)));
  container.append(h("div", { class: "spec-page" },
    h("div", { class: "spec-top row between" },
      h("span", { class: "row" }, h("a", { class: "btn small ghost", href: "#/specs" }, "All classes"),
        r ? h("a", { class: "btn small ghost", href: "#/" }, "Back to my result") : null),
      picker),
    h("section", { class: "result-hero" },
      h("div", { class: "eyebrow" }, "Class"),
      h("div", { class: "hero-icons" }, classIcon(c.id, 56, c.name)),
      h("h1", {}, c.name),
      h("p", { class: "sub" }, c.description),
      rank ? h("div", { class: "chips" }, h("span", { class: "chip", title: "Where this class ranks among the nine for your answers" }, h("b", {}, `Your match: ${rank.rank} of ${r.rankings.classes.length}`), h("i", {}, signed(rank.score)))) : null),
    overviewCard({ className: c.name, classOverview: c.overview || c.description, specName: "", specOverview: "", url: c.overview_url }),
    h("div", { class: "card" },
      h("h3", {}, `The ${c.name} specializations`),
      h("div", { class: "spec-list" }, c.specializations.map((s) => {
        const mine = r && r.result.primary_class.id === c.id && r.result.primary_specialization.id === s.id;
        return h("a", { class: "spec-tile wide", href: href(c.id, s.id) },
          specIcon(c.id, s.id, 36),
          h("span", {}, h("b", {}, s.name), h("small", {}, `${roleLabel(s.role)}${spellName(c.id, s.id) ? ` · ${spellName(c.id, s.id)}` : ""}`), s.description ? h("span", { class: "muted spec-blurb" }, s.description) : null),
          mine ? h("em", { class: "tile-tag" }, "your result") : null);
      }))),
    h("nav", { class: "spec-pager", "aria-label": "Other classes" },
      h("a", { class: "btn", href: `#/specs/${prev.id}`, rel: "prev" }, "← ", prev.name),
      h("span", { class: "muted" }, `${at + 1} of ${classes.length}`),
      h("a", { class: "btn", href: `#/specs/${next.id}`, rel: "next" }, next.name, " →"))));
}

// ---------------------------------------------------------------------------- one specialization
function pager(prev, next, position, total) {
  return h("nav", { class: "spec-pager", "aria-label": "Other specializations" },
    h("a", { class: "btn", href: href(prev.class_id, prev.id), rel: "prev", title: `${prev.class_name} ${prev.name}` }, "← ", prev.name),
    h("span", { class: "muted" }, `${position} of ${total}`),
    h("a", { class: "btn", href: href(next.class_id, next.id), rel: "next", title: `${next.class_name} ${next.name}` }, next.name, " →"));
}

function specPage(page, all, at, prev, next) {
  const { tags, spec, traitScores } = standing(page);
  const r = state.result;
  const mine = tags.includes("Your result");
  const picker = h("select", { "aria-label": "Jump to a specialization", onchange: (e) => { location.hash = e.target.value; } },
    [...new Set(all.map((s) => s.class_id))].map((cid) => h("optgroup", { label: all.find((s) => s.class_id === cid).class_name },
      all.filter((s) => s.class_id === cid).map((s) => h("option", { value: href(cid, s.id), selected: s.class_id === page.class_id && s.id === page.id }, s.name)))));
  const maxMult = Math.max(...page.traits.map((t) => t.multiplier), 1e-9);

  return h("div", { class: "spec-page" },
    h("div", { class: "spec-top row between" },
      h("span", { class: "row" }, h("a", { class: "btn small ghost", href: "#/specs" }, "All specializations"),
        r ? h("a", { class: "btn small ghost", href: "#/" }, "Back to my result") : null),
      picker),
    h("section", { class: "result-hero", style: { "--cls": `var(--cls-${page.class_id}, var(--accent))` } },
      h("div", { class: "eyebrow" }, `${page.class_name} specialization`),
      h("div", { class: "hero-icons", title: `${page.class_name}: ${spellName(page.class_id, page.id) || page.name}` }, classIcon(page.class_id, 56, page.class_name), specIcon(page.class_id, page.id, 56)),
      h("h1", {}, h("a", { class: "plain", href: `#/specs/${page.class_id}`, title: `About the ${page.class_name}` }, page.class_name)),
      h("h2", {}, page.name),
      h("div", { class: "chips" },
        h("span", { class: "chip" }, h("b", {}, roleLabel(page.role))),
        tags.map((t) => h("span", { class: "chip" }, h("b", {}, t))),
        spec ? h("span", { class: "chip", title: "How closely your answers match this specialization, among the three of its class" }, h("b", {}, `Your match: ${spec.rank} of 3`), h("i", {}, signed(spec.score))) : null)),
    page.description ? h("div", { class: "card prose" }, h("p", {}, page.description)) : null,
    traitsCard(page, traitScores, maxMult),
    overviewCard({ className: page.class_name, classOverview: page.class_overview, specName: page.name, specOverview: page.overview, url: page.overview_url }),
    guideCard(page, mine),
    buildCard(page.build, page, page.class_id, mine),
    pager(prev, next, at + 1, all.length));
}

function traitsCard(page, scores, maxMult) {
  if (!page.traits.length) return null;
  return h("div", { class: "card traits" },
    h("h3", {}, `What defines the ${page.name} ${page.class_name}`),
    h("p", { class: "muted" }, "The temperament traits this specialization is matched on, strongest first. The bar shows how much each counts."
      + (scores ? " On the right is your own score in each (above zero means more than the average answer pattern)." : " Take the quiz and your own scores will appear here.")),
    h("ul", { class: "trait-list" }, page.traits.map((t) => h("li", {},
      h("div", { class: "trait-head" },
        h("b", {}, t.name),
        h("span", { class: "trait-order" }, ORDER[t.order - 1] || `#${t.order}`),
        scores && scores[t.id] !== undefined
          ? h("span", { class: `trait-score ${scores[t.id] > 0 ? "pos" : scores[t.id] < 0 ? "neg" : ""}`, title: "Your score in this trait" }, signed(scores[t.id]))
          : null),
      h("span", { class: "trait-bar", title: `Counts ×${t.multiplier}` }, h("i", { style: { width: `${(t.multiplier / maxMult) * 100}%` } })),
      t.description ? h("p", { class: "muted" }, t.description) : null))));
}

/** Left and right arrow keys page through the specializations. */
function installKeys() {
  if (keysInstalled) return;
  keysInstalled = true;
  document.addEventListener("keydown", (e) => {
    if (!neighbours || e.metaKey || e.ctrlKey || e.altKey || e.shiftKey) return;
    if (e.target instanceof Element && e.target.matches("input, textarea, select")) return;
    if (e.key === "ArrowLeft") location.hash = neighbours.prev;
    else if (e.key === "ArrowRight") location.hash = neighbours.next;
  });
}
