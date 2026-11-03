// A talent build drawn as the class's three talent trees, laid out like the in-game talent window: one panel per tree,
// one row per tier, a ranked "n/max" badge on every talent.
//
// The data source gives each talent's row (tier) exactly but not its exact column, so talents are spread evenly across
// their row in source order. Positions within a row are approximate; ranks, rows and points are not.
import { h } from "./ui.js";
import { specIcon, spellName } from "./icons.js";

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

/** '2026-11-02' -> 'November 2, 2026' (no timezone arithmetic, so the day never shifts). */
export function longDate(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
  return m ? `${MONTHS[+m[2] - 1]} ${+m[3]}, ${m[1]}` : "";
}

/** First grid column (of 8, 1-based) of each of k talents in a row, each spanning two columns. */
const STARTS = { 1: [4], 2: [2, 6], 3: [1, 4, 7], 4: [1, 3, 5, 7] };

function talentNode(t, tierPoints) {
  const state = t.rank === 0 ? "none" : t.rank >= t.max_rank ? "max" : "some";
  const needs = t.requires.length ? ` Requires ${t.requires.map((r) => `${r.rank} point${r.rank === 1 ? "" : "s"} in ${r.talent_id.replace(/-/g, " ")}`).join(" and ")}.` : "";
  const tip = `${t.name}: ${t.rank} of ${t.max_rank} point${t.max_rank === 1 ? "" : "s"}.${needs}${tierPoints ? ` Needs ${tierPoints} points spent in this tree's earlier rows.` : ""}${t.description ? ` ${t.description}` : ""}`;
  return h("div", { class: `talent ${state}`, title: tip, role: "listitem", "aria-label": tip },
    h("span", { class: "t-name" }, t.name),
    h("span", { class: "t-rank", "aria-hidden": "true" }, `${t.rank}/${t.max_rank}`));
}

function treePanel(tree, { classId, perTier, isPrimary }) {
  const rows = new Map();
  [...tree.talents].sort((a, b) => a.tier - b.tier || a.column - b.column).forEach((t) => {
    if (!rows.has(t.tier)) rows.set(t.tier, []);
    rows.get(t.tier).push(t);
  });
  const grid = h("div", { class: "tree-grid", role: "list", "aria-label": `${tree.name} talents` });
  [...rows.entries()].forEach(([tier, talents], r) => {
    grid.append(h("span", { class: "tier-label", style: { gridRow: String(r + 1) }, title: tier ? `Needs ${tier * perTier} points spent in earlier rows` : "First row" }, tier ? String(tier * perTier) : ""));
    const starts = STARTS[Math.min(talents.length, 4)];
    talents.slice(0, 4).forEach((t, i) => {
      const node = talentNode(t, tier * perTier);
      node.style.gridRow = String(r + 1);
      node.style.gridColumn = `${starts[i] + 1} / span 2`;      // column 1 is the row label
      grid.append(node);
    });
  });
  const icon = specIcon(classId, tree.id, 36);
  return h("details", { class: `talent-tree${isPrimary ? " primary" : ""}`, open: tree.points > 0 || isPrimary },
    h("summary", {},
      icon,
      h("span", { class: "tree-name" }, tree.name, icon && spellName(classId, tree.id) ? h("small", {}, ` · ${spellName(classId, tree.id)}`) : null),
      isPrimary ? h("span", { class: "tree-tag" }, "your specialization") : null,
      h("span", { class: "tree-points" }, `${tree.points} point${tree.points === 1 ? "" : "s"}`)),
    grid);
}

/** The class's trees with the build's ranks drawn in. `build.trees` comes from the API / static data. */
export function talentTrees(build, classId, primarySpecId) {
  if (!build.trees || !build.trees.length) return null;
  const perTier = (build.catalog_info && build.catalog_info.points_per_tier) || 5;
  return h("div", { class: "talent-trees" }, build.trees.map((tree) => treePanel(tree, { classId, perTier, isPrimary: tree.id === primarySpecId })));
}

/** The caution shown with every build: how current the talent data is, and that it may be out of date. */
export function dataNotice(build) {
  const info = build.catalog_info;
  const updated = info && longDate(info.source_updated);
  const compiled = info && longDate(info.retrieved_at);
  return h("div", { class: "build-notice", role: "note" },
    h("p", {}, h("b", {}, "This may not match the current World of Warcraft: Forever talent trees. "),
      "Forever is in beta and its talents change often, and this build is a best guess rather than something checked in the game."),
    info ? h("p", {}, "Talent tree data last updated ", h("b", {}, updated || "an unknown date"),
      info.source ? ` (${info.source})` : "", compiled && compiled !== updated ? `; compiled ${compiled}` : "", ".",
      info.data_status === "draft" ? " The trees were assembled by hand from published sources, not read from the game client." : "") : null,
    h("p", { class: "muted" }, "Rows and ranks are as listed in that data. The position of a talent within its row is approximate."));
}
