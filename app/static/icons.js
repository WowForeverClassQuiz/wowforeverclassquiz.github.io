// Class and iconic-spell icons.
//
// The images are Blizzard's artwork. They are NOT stored in this project: each one is loaded by the visitor's browser
// from Wowhead's public icon server (wow.zamimg.com). If an icon cannot load (offline, blocked, renamed), a coloured
// badge with the class or spell's initial is shown instead. To use your own copies, change ICON_BASE to a folder that
// holds files named like the ones below (for example classicon_druid.jpg).
import { h, CLASS_COLORS } from "./ui.js";

export const ICON_BASE = "https://wow.zamimg.com/images/wow/icons";

export const CLASS_ICONS = {
  druid: "classicon_druid", hunter: "classicon_hunter", mage: "classicon_mage", paladin: "classicon_paladin",
  priest: "classicon_priest", rogue: "classicon_rogue", shaman: "classicon_shaman", warlock: "classicon_warlock",
  warrior: "classicon_warrior",
};

/** class/spec -> [icon file, name of the iconic spell the icon shows] */
export const SPEC_ICONS = {
  "druid/balance": ["spell_arcane_starfire", "Starfire"],
  "druid/feral_combat": ["ability_druid_catform", "Cat Form"],
  "druid/restoration": ["spell_nature_rejuvenation", "Rejuvenation"],
  "hunter/beast_mastery": ["ability_druid_ferociousbite", "Bestial Wrath"],
  "hunter/marksmanship": ["inv_spear_07", "Aimed Shot"],
  "hunter/survival": ["spell_fire_selfdestruct", "Explosive Trap"],
  "mage/arcane": ["spell_nature_starfall", "Arcane Missiles"],
  "mage/fire": ["spell_fire_flamebolt", "Fireball"],
  "mage/frost": ["spell_frost_frostbolt02", "Frostbolt"],
  "paladin/holy": ["spell_holy_holybolt", "Holy Light"],
  "paladin/protection": ["spell_holy_blessingofprotection", "Holy Shield"],
  "paladin/retribution": ["spell_holy_crusaderstrike", "Crusader Strike"],
  "priest/discipline": ["spell_holy_powerwordshield", "Power Word: Shield"],
  "priest/holy": ["spell_holy_flashheal", "Flash Heal"],
  "priest/shadow": ["spell_shadow_shadowwordpain", "Shadow Word: Pain"],
  "rogue/assassination": ["ability_rogue_eviscerate", "Eviscerate"],
  "rogue/combat": ["spell_shadow_ritualofsacrifice", "Sinister Strike"],
  "rogue/subtlety": ["ability_stealth", "Stealth"],
  "shaman/elemental_combat": ["spell_nature_lightning", "Lightning Bolt"],
  "shaman/enhancement": ["spell_nature_windfury", "Windfury Totem"],
  "shaman/restoration": ["spell_nature_magicimmunity", "Healing Wave"],
  "warlock/affliction": ["spell_shadow_abominationexplosion", "Corruption"],
  "warlock/demonology": ["spell_shadow_summonfelguard", "Summon Felguard"],
  "warlock/destruction": ["spell_shadow_shadowbolt", "Shadow Bolt"],
  "warrior/arms": ["ability_warrior_savageblow", "Mortal Strike"],
  "warrior/fury": ["spell_nature_bloodlust", "Bloodthirst"],
  "warrior/protection": ["inv_shield_05", "Shield Slam"],
};

const sizeName = (px) => (px <= 20 ? "small" : px <= 40 ? "medium" : "large");   // the sizes the icon server offers: 18, 36, 56

function badge(text, color, px) {
  return h("span", { class: "wow-icon fallback", style: { width: `${px}px`, height: `${px}px`, background: color || "var(--accent)", fontSize: `${Math.round(px * 0.5)}px` }, "aria-hidden": "true" }, (text || "?").slice(0, 1).toUpperCase());
}

function make(file, title, fallbackText, color, px) {
  const img = h("img", {
    class: "wow-icon", src: `${ICON_BASE}/${sizeName(px)}/${file}.jpg`, alt: "", title, width: px, height: px, loading: "lazy",
    decoding: "async", referrerpolicy: "no-referrer", "aria-hidden": "true",
  });
  img.addEventListener("error", () => img.replaceWith(badge(fallbackText, color, px)), { once: true });
  return img;
}

/** The class's emblem. Returns null for a class this module has no icon for. */
export function classIcon(classId, px = 36, name = "") {
  const file = CLASS_ICONS[classId];
  return file ? make(file, name || classId, name || classId, CLASS_COLORS[classId], px) : null;
}

/** An iconic spell of the specialization. Returns null when none is known. */
export function specIcon(classId, specId, px = 36) {
  const entry = SPEC_ICONS[`${classId}/${specId}`];
  return entry ? make(entry[0], entry[1], entry[1], CLASS_COLORS[classId], px) : null;
}

export const spellName = (classId, specId) => (SPEC_ICONS[`${classId}/${specId}`] || [])[1] || "";
