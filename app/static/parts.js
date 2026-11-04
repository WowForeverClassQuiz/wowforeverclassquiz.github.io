// Cards shown on the result page and on every specialization page: what the class does, role and gear, and the drawn build.
import { h, titleCase, purposeLabel, badge } from "./ui.js";
import { talentTrees, dataNotice } from "./talenttree.js";

export function safeUrl(u) { return /^https?:\/\//i.test(u || "") ? u : null; }

/** "What the class does": the class paragraph, then the specialization's, with a link back to Blizzard's class page. */
export function overviewCard({ className, classOverview, specName, specOverview, url }) {
  if (!classOverview && !specOverview) return null;
  return h("div", { class: "card prose" },
    h("h3", {}, `What the ${className} does`),
    classOverview ? h("p", {}, classOverview) : null,
    specOverview ? h("p", {}, h("b", {}, `${specName}. `), specOverview) : null,
    safeUrl(url)
      ? h("p", { class: "muted", style: { fontSize: "0.85rem" } }, "In our own words, from Blizzard's published class description. ",
          h("a", { href: safeUrl(url), target: "_blank", rel: "noopener noreferrer" }, `Read Blizzard's ${className} page`))
      : null);
}

/** Roles in dungeons and raids, gear to look for, and who competes for it. */
/** `yours` is false on the pages of specializations the participant did not get. */
export function guideCard(spec, yours = true) {
  const g = spec.guide;
  if (!g) return null;
  const list = (items) => (items && items.length ? h("ul", {}, items.map((x) => h("li", {}, x))) : null);
  return h("div", { class: "card guide" },
    h("h3", {}, yours ? `Your role and gear as a ${spec.name} ${spec.class_name}` : `Role and gear for a ${spec.name} ${spec.class_name}`),
    h("div", { class: "grid two roles" },
      g.dungeon_role ? h("div", {}, h("h4", {}, "In dungeons"), h("p", {}, g.dungeon_role)) : null,
      g.raid_role ? h("div", {}, h("h4", {}, "In raids"), h("p", {}, g.raid_role)) : null),
    g.gear && g.gear.length ? h("div", {}, h("h4", {}, "Gear to look out for"), list(g.gear)) : null,
    g.competes_with && g.competes_with.length ? h("div", {}, h("h4", {}, "Who competes with you for gear"), list(g.competes_with)) : null,
    g.note ? h("p", { class: "muted guide-note" }, g.note) : null);
}

export function buildCard(build, spec, classId, yours = true) {
  if (!build) {
    return h("div", { class: "card" }, h("h3", {}, yours ? "Your build" : "Build"), h("p", { class: "muted" }, `No build has been configured for ${spec.name} yet.`));
  }
  const kind = { verified: "ok", draft: "warn", unverified: "warn", pending: "info" }[build.status] || "";
  const label = { verified: "Verified", draft: "Draft (not verified)", unverified: "Unverified", pending: "Allocation pending" }[build.status] || build.status;
  const names = Object.fromEntries(build.talents.map((t) => [t.talent_id, t.name || t.talent_id]));
  const hasAlloc = build.talents.length > 0;
  const trees = hasAlloc ? talentTrees(build, classId, spec.id) : null;
  const verified = build.status === "verified";
  return h("div", { class: "card build" },
    h("div", { class: "row between" },
      h("h3", { style: { margin: 0 } }, yours ? "Your build" : "Build"),
      h("span", { class: "row" }, badge(label, kind), build.tree_distribution_text ? badge(`${build.tree_distribution_text} points`, "") : null)),
    h("p", { style: { margin: "10px 0 4px" } }, h("b", {}, build.name), ` · ${purposeLabel(build.purpose)} · level ${build.level}`),
    h("p", { class: `note${verified ? "" : " warn"}` }, build.status_note),
    hasAlloc ? dataNotice(build) : null,
    trees,
    hasAlloc && !trees ? h("p", { class: "muted" }, "The talent trees for this class are not available, so only the allocation order is shown.") : null,
    hasAlloc && build.leveling_order.length
      ? h("details", { style: { marginTop: "14px" } }, h("summary", {}, "Order to spend points while leveling"),
          h("ol", { class: "order", start: 10 }, build.leveling_order.map((id, k) => h("li", { value: 10 + k }, `${names[id] || id}`))))
      : null,
    hasAlloc && build.combat_priorities.length ? h("div", { style: { marginTop: "12px" } }, h("h4", {}, "Notes on this build"), h("ul", {}, build.combat_priorities.map((c) => h("li", {}, c)))) : null,
    hasAlloc && build.equipment_notes.length ? h("div", { style: { marginTop: "12px" } }, h("h4", {}, "Attributes and equipment"), h("ul", {}, build.equipment_notes.map((c) => h("li", {}, c)))) : null,
    hasAlloc && build.professions.length ? h("p", {}, h("b", {}, "Professions: "), build.professions.join(", ")) : null);
}
