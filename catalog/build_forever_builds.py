"""Builds 27 BEST-GUESS leveling and general-PvE talent builds on the DRAFT Forever talent catalog.

    python catalog/build_forever_builds.py     # writes forever-builds-draft-2026-11-03.json next to this file

These are NOT verified and NOT authoritative. Method, honestly stated:

  * Starting point: RankedBoost's WoW Forever build pages (build 1.60.1.70707, "updated November 2, 2026"),
    one page per class, which list named talents with ranks for 3 to 5 builds each. Where RankedBoost has a
    leveling build for a specialization it is the model; otherwise its PvE damage, healing or tank build is,
    and Rogue Subtlety (RankedBoost only has a PvP build) is my own extrapolation. Warcraft Tavern's beta
    leveling guides and Mobalytics' Fury leveling guide were read for hints only (their talent plans are images
    or stop at level 30).
  * RankedBoost's pages still use pre-patch trees in places (Murder, Berserk, Gift of the Earthmother, old rank
    caps), so each build was REMAPPED onto the draft catalog, which follows the Nov 2 development notes:
    removed talents are dropped, ranks are capped to the new maximums, talents that changed trees (Heart of the
    Wild, Furor, Divine Intellect ...) are taken from their new tree, and freed points are re-spent by judgement.
  * Reddit and other forums could not be read by the tools available (blocked), so no community consensus is
    reflected beyond what RankedBoost and the guide sites state.
  * Every allocation is checked against the draft catalog (51 points, ranks, row gates, stated prerequisites,
    primary tree holds the most points) and expanded into a LEGAL point-by-point leveling order. Passing that
    check proves the allocation is legal in the DRAFT data, nothing about whether it is good or the data is right.
  * Guidance text is limited to facts that follow from the talents taken; no rotations, stats or professions are
    invented.

Each build stays `status: draft` (never `verified`).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from app.builds import validate_build  # noqa: E402
from app.models import Build, TalentCatalog  # noqa: E402
from app.seed import build_default_config  # noqa: E402

CATALOG_JSON = HERE / "forever-talents-draft-2026-11-03.json"
OUT_JSON = HERE / "forever-builds-draft-2026-11-03.json"
RB = "https://rankedboost.com/world-of-warcraft/forever/build/{}/"

# --------------------------------------------------------------------------------------------------
# DESIGNS. Each: class, spec, role, RankedBoost model, picks, notes.
# picks = ordered (tree, "Talent:rank, Talent:rank, ...") segments; the order is the leveling priority.
# --------------------------------------------------------------------------------------------------
D: list[dict] = []


def design(cls, spec, role, model, picks, notes):
    D.append(dict(cls=cls, spec=spec, role=role, model=model, picks=picks, notes=notes))


# ----- Warrior -----------------------------------------------------------------------------------
design("warrior", "arms", "melee_damage", "RankedBoost 'Arms Warrior Leveling Build' (31/20/0)", [
    ("arms", "Improved Heroic Strike:3, Improved Rend:3, Improved Charge:2, Improved Tactical Mastery:3, Anger Management:1, "
             "Deep Wounds:3, Two-Handed Weapon Specialization:3, Impale:2, Weaponmaster:5, Bloodthrill:2, Improved Slam:2, "
             "Improved Overpower:1, Mortal Strike:1"),
    ("fury", "Cruelty:5, Unbridled Wrath:5, Blood Craze:3, Enrage:5, Lingering Rage:2"),
], "Improved Tactical Mastery (5 to 3) and Bloodthrill (5 to 2) are capped to the Nov 2 maximums; the 5 freed points went to Improved Overpower (1) and the Fury list.")
design("warrior", "fury", "melee_damage", "RankedBoost 'Fury Warrior DPS Build' (17/34/0)", [
    ("arms", "Improved Heroic Strike:3, Improved Rend:3, Improved Charge:2, Improved Tactical Mastery:3, Anger Management:1, Deep Wounds:3, Impale:2"),
    ("fury", "Cruelty:5, Unbridled Wrath:5, Furious Precision:3, Blood Craze:3, Enrage:5, Dual Wield Specialization:5, Reckless Swings:1, "
             "Death Wish:1, Improved Berserker Rage:2, Flurry:3, Bloodthirst:1"),
], "Flurry (5 to 3) and Improved Tactical Mastery (4-5 to 3) are capped to the Nov 2 maximums. Reckless Swings is new; Bloodthirst now requires Death Wish, which this build takes. "
   "Mobalytics' Fury leveling guide opens Cruelty, Lingering Rage, Furious Precision, Blood Craze (levels 10-24); this order starts in Arms instead.")
design("warrior", "protection", "tank", "RankedBoost 'Protection Warrior Tank Build' (15/0/36)", [
    ("arms", "Deflection:5, Improved Heroic Strike:3, Improved Charge:2, Improved Tactical Mastery:3, Anger Management:1, Improved Rend:1"),
    ("protection", "Shield Specialization:5, Improved Bloodrage:2, Iron Will:5, Anticipation:5, Improved Revenge:3, Last Stand:1, Master of Defense:2, "
                   "Defiance:3, Vanguard:1, Focused Rage:3, Bastion:5, Shield Slam:1"),
], "Improved Tactical Mastery (5 to 3) capped. Warcraft Tavern's Arms guide notes Anger Management is hard to fit without Deflection, which this build takes.")

# ----- Rogue -------------------------------------------------------------------------------------
design("rogue", "assassination", "melee_damage", "RankedBoost 'Assassination Rogue DPS Build' (37/12/2)", [
    ("assassination", "Remorseless Attacks:2, Malice:5, Ruthlessness:3, Improved Slice and Dice:3, Lethality:2, Vigor:2, Vile Poisons:5, "
                      "Improved Poisons:5, Cold Blood:1, Relentless Strikes:5, Venom:1, Seal Fate:3, Mutilate:1"),
    ("combat", "Coup de Grace:3, Lightning Reflexes:5, Precision:3, Puncturing Wounds:2"),
], "Murder is removed (its 2 points were re-spent in Remorseless Attacks and Vigor); Lethality (5 to 2), Seal Fate (5 to 3) and Relentless Strikes (1 to 5) follow the Nov 2 notes; "
   "Mutilate is now the 31-point capstone. Improved Eviscerate is now Coup de Grace. The two RankedBoost Subtlety points (Opportunity) went to Combat.")
design("rogue", "combat", "melee_damage", "RankedBoost 'Combat Rogue Leveling Build' (15/36/0)", [
    ("combat", "Coup de Grace:3, Efficient Strikes:2, Lightning Reflexes:5, Precision:3, Deflection:3, Endurance:2, Flawless Execution:1, "
              "Weapon Expertise:2, Aggression:3, Hack and Slash:5, Dual Wield Specialization:2, Blade Flurry:1, Flash of Steel:3, Adrenaline Rush:1"),
    ("assassination", "Remorseless Attacks:2, Malice:5, Ruthlessness:3, Improved Slice and Dice:3, Lethality:2"),
], "Murder is removed (its 2 points were re-spent in Improved Slice and Dice); Dual Wield Specialization is now a 2-point talent on row 5 (was 5 points), so 3 points moved to the new "
   "Flash of Steel (row 6). Relentless Strikes now sits at row 5 in Assassination and would need 20 points there, so it is not taken.")
design("rogue", "subtlety", "melee_damage", "no PvE source: extrapolated from RankedBoost's 'Subtlety Rogue PvP Build' (5/17/29)", [
    ("subtlety", "Master of Deception:3, Opportunity:5, Setup:3, Improved Ambush:3, Dirty Deeds:2, Initiative:3, Premeditation:1, Serrated Blades:3, "
                 "Ghostly Strike:1, Elusiveness:2, Preparation:1, Hemorrhage:1, Heightened Senses:2, Death Mark:1"),
    ("combat", "Coup de Grace:3, Efficient Strikes:2, Lightning Reflexes:5, Precision:3, Puncturing Wounds:3, Deflection:3, Endurance:1"),
], "LOWEST CONFIDENCE of the 27. RankedBoost has only a PvP Subtlety build, and Subtlety was heavily rebuilt on Nov 2 (Quietus, Cutthroat, Thousand Cuts and Improved Distract removed; "
   "Death Mark, Boot Knife and Quick Getaway added). This is my own general-PvE guess, ending in the new Death Mark capstone.")

# ----- Druid -------------------------------------------------------------------------------------
design("druid", "balance", "ranged_damage", "RankedBoost 'Balance Druid DPS Build' (41/0/10)", [
    ("balance", "Improved Wrath:5, Genesis:5, Moonglow:3, Improved Moonfire:2, Nature's Majesty:2, Nature's Reach:2, Nature's Splendor:1, Insect Swarm:1, "
                "Vengeance:5, Improved Starfire:5, Nature's Grace:1, Eclipse:3, Moonfury:5, Moonkin Form:1"),
    ("restoration", "Nature's Focus:5, Naturalist:5"),
], "Same Balance picks as the source; Heart of the Wild and Furor changed trees on Nov 2 but this build does not use them.")
design("druid", "feral_combat", "melee_damage", "RankedBoost 'Feral Combat Druid Leveling Build' (0/38/13)", [
    ("feral_combat", "Ferocity:5, Furor:5, Feral Swiftness:2, Feral Instinct:3, Brutal Impact:2, Thick Hide:3, Savage Fury:2, Sharpened Claws:2, "
                     "Feral Charge:1, Predatory Strikes:3, Blood Frenzy:2, Leader of the Pack:1, Natural Instinct:2, Natural Reaction:5"),
    ("restoration", "Heart of the Wild:5, Naturalist:5, Natural Shapeshifter:3"),
], "Furor is now a Feral talent and Heart of the Wild a Restoration one (they swapped trees on Nov 2), so the 5 + 5 points keep their effect but move trees. "
   "Berserk is removed, so the source's capstone slot is not used.")
design("druid", "restoration", "healer", "RankedBoost 'Restoration Druid Healing Build' (6/5/40)", [
    ("restoration", "Nature's Focus:5, Heart of the Wild:5, Naturalist:5, Reflection:3, Gift of Nature:5, Bloom:1, Tranquil Spirit:5, Improved Rejuvenation:3, "
                    "Swiftmend:1, Living Spirit:3, Improved Regrowth:4, Wild Growth:1"),
    ("balance", "Genesis:5, Nature's Majesty:2, Moonglow:3"),
], "Gift of the Earthmother is removed and Bloom takes its slot. Heart of the Wild is now in Restoration (its points count for this tree). "
   "Improved Tranquility (2) was dropped to afford Wild Growth; the source's Feral points are re-spent in Balance.")

# ----- Hunter ------------------------------------------------------------------------------------
design("hunter", "beast_mastery", "ranged_damage", "RankedBoost 'Beast Mastery Hunter Leveling Build' (36/15/0)", [
    ("beast_mastery", "Endurance Training:5, Deadly Aspects:2, Focused Fire:2, Improved Revive Pet:2, Pathfinding:2, Bestial Swiftness:1, Unleashed Fury:5, "
                      "Improved Mend Pet:2, Ferocity:5, Spirit Bond:2, Bestial Discipline:2, Frenzy:5, Bestial Wrath:1"),
    ("marksmanship", "Lethal Attacks:5, Improved Stings:3, Efficiency:5, Rapid Killing:2"),
], "Pathfinding moved from row 2 to row 3 on Nov 2, so it now needs 10 points in Beast Mastery; the order here already respects that.")
design("hunter", "marksmanship", "ranged_damage", "RankedBoost 'Marksmanship Hunter DPS Build' (5/41/5)", [
    ("beast_mastery", "Deadly Aspects:5"),
    ("marksmanship", "Lethal Attacks:5, Improved Stings:3, Efficiency:4, Careful Aim:5, Rapid Killing:2, Improved Arcane Shot:5, Lone Wolf:1, Mortal Shots:5, "
                     "Barrage:3, Rapid Recuperation:2, Ranged Weapon Specialization:5, Sniper Shot:1"),
    ("survival", "Improved Tracking:5"),
], "Barrage is 3 ranks (5/10/15%) after Nov 2; Efficiency 4 of 5 (the source had 3) uses the spare point.")
design("hunter", "survival", "ranged_damage", "RankedBoost 'Survival Hunter DPS Build' (5/13/33)", [
    ("survival", "Improved Tracking:5, Survivalist:4, Savage Strikes:2, Clever Traps:2, Surefooted:3, Survival Tactics:2, Predator's Edge:5, "
                 "Resourcefulness:2, Expose Prey:2, Lightning Reflexes:5, Lacerating Strikes:1"),
    ("marksmanship", "Lethal Attacks:5, Careful Aim:5, Rapid Killing:2, Lone Wolf:1"),
    ("beast_mastery", "Deadly Aspects:5"),
], "Lacerating Strikes is the capstone; Lightning Reflexes is 5 ranks (3/6/9/12/15%) after Nov 2.")

# ----- Mage --------------------------------------------------------------------------------------
design("mage", "arcane", "ranged_damage", "RankedBoost 'Arcane Mage DPS Build' (36/15/0)", [
    ("arcane", "Wand Specialization:2, Improved Channeling:5, Arcane Resilience:1, Arcane Subtlety:2, Arcane Concentration:5, Missile Barrage:2, Arcane Impact:3, "
               "Arcane Geometry:2, Arcane Blast:1, Arcane Meditation:3, Arcane Mind:5, Presence of Mind:1, Arcane Instability:3, Arcane Power:1"),
    ("fire", "Incineration:5, Accelerant:1, Ignite:5, Flame Throwing:2, Improved Fire Blast:2"),
], "Arcane Resilience now caps at 3 points on row 1 and Missile Barrage sits on row 2 (both changed Nov 2); Arcane Blast is a new 1-point talent; Incineration is 5 ranks and Accelerant is the renamed Improved Fireball.")
design("mage", "fire", "ranged_damage", "RankedBoost 'Fire Mage DPS Build' (12/36/3)", [
    ("fire", "Incineration:5, Accelerant:5, Ignite:5, Flame Throwing:1, Burning Soul:3, Improved Fire Blast:2, Pyroblast:1, Improved Scorch:3, Heating Up:1, "
             "Master of Elements:3, Critical Mass:3, Fire Power:3, Combustion:1"),
    ("arcane", "Wand Specialization:2, Improved Channeling:1, Arcane Resilience:3, Arcane Concentration:5, Arcane Subtlety:1"),
    ("frost", "Precision:3"),
], "Critical Mass is capped at 3 ranks after Nov 2 (was 5) and Improved Fire Blast moved to row 3. Elemental Precision is now Precision (Frost, 3 points).")
design("mage", "frost", "ranged_damage", "RankedBoost 'Frost Mage Leveling Build' (10/0/41)", [
    ("arcane", "Wand Specialization:2, Improved Channeling:1, Arcane Resilience:2, Arcane Concentration:5"),
    ("frost", "Improved Frostbolt:5, Precision:3, Ice Shards:5, Frostbite:3, Improved Frost Nova:2, Permafrost:3, Frost Channeling:3, Improved Blizzard:3, "
              "Arctic Reach:2, Shatter:3, Improved Cone of Cold:3, Fingers of Frost:2, Winter's Chill:3, Ice Barrier:1"),
], "Piercing Ice is removed and Elemental Precision became Precision (3 points); Winter's Chill is kept at 3 of 5 as in the source.")

# ----- Paladin -----------------------------------------------------------------------------------
design("paladin", "holy", "healer", "RankedBoost 'Holy Paladin Healing Build' (32/14/5)", [
    ("holy", "Spiritual Focus:5, Healing Light:3, Reverence:2, Purifying Power:2, Illumination:5, Divine Favor:1, Holy Conduit:2, Divine Precision:2, "
             "Infusion of Light:2, Oath of Light:1, Holy Shock:1, Boundless Light:2, Holy Power:5, Light's Vigil:1"),
    ("protection", "Divine Intellect:5, Redoubt:3, Guardian's Favor:2, Sacred Duty:2"),
    ("retribution", "Benediction:5"),
], "Divine Intellect moved from Holy to Protection on Nov 2, so it now costs Protection points; Toughness and Anticipation (in the source) moved to rows 3-4 of Protection and do not fit in the 12 Protection points "
   "left after Divine Intellect. Voice of Truth is removed; Oath of Light and Boundless Light are new.")
design("paladin", "protection", "tank", "RankedBoost 'Protection Paladin Tank Build' (8/38/5)", [
    ("protection", "Divine Intellect:5, Redoubt:5, Precision:3, Sacred Duty:2, Guardian's Favor:2, Toughness:5, Shield Specialization:2, Templar's Bulwark:1, "
                   "Anticipation:5, Improved Righteous Fury:3, Holy Shield:1, Iron Creed:3, Shieldsworn:1"),
    ("holy", "Spiritual Focus:5, Improved Seals:3"),
    ("retribution", "Deflection:5"),
], "Shield Specialization is 2 points and Iron Creed 3 (both reduced Nov 2); Holy Shield now sits on row 5; Shieldsworn is the new row 7 talent. Reckoning (5 in the source) is dropped to fit these.")
design("paladin", "retribution", "melee_damage", "RankedBoost 'Retribution Paladin Leveling Build' (18/0/33)", [
    ("holy", "Spiritual Focus:5, Divine Strength:5, Reverence:2, Improved Seals:4, Holy Conduit:2"),
    ("retribution", "Benediction:5, Improved Judgement:2, Conviction:3, Sanctified Judgement:3, Vindication:3, Pursuit of Justice:2, Unyielding Faith:2, "
                    "Seal of Command:1, Sacred Arbiter:1, Two-Handed Weapon Specialization:3, Vengeance:3, Repentance:1, Champion of the Light:3, Unsealed Wrath:1"),
], "Twist of Light and Instrument of Law are removed; Unsealed Wrath is the new 31st talent and requires Repentance; Vengeance requires Seal of Command. "
   "Divine Intellect (5 in the source) moved to Protection and is not taken.")

# ----- Priest ------------------------------------------------------------------------------------
design("priest", "discipline", "healer", "RankedBoost 'Discipline Priest Healing Build' (31/20/0)", [
    ("discipline", "Twin Disciplines:5, Silent Resolve:3, Mental Strength:3, Mental Agility:3, Improved Power Word: Shield:3, Meditation:3, Soul Warding:1, "
                   "Renewed Hope:5, Penance:1, Divine Aegis:3, Power Infusion:1"),
    ("holy", "Twilight Focus:3, Improved Renew:1, Holy Specialization:5, Divine Fury:5, Inspiration:3, Improved Healing:3"),
], "No structural Discipline changes in the Nov 2 notes; Penance and Divine Aegis are taken as the deeper picks.")
design("priest", "holy", "healer", "RankedBoost 'Holy Priest Healing Build' (17/34/0)", [
    ("holy", "Improved Renew:3, Twilight Focus:2, Holy Specialization:5, Divine Fury:5, Inspiration:3, Improved Healing:3, Holy Binding:1, Litany of Light:2, "
             "Spirit of Redemption:1, Spiritual Guidance:5, Spiritual Healing:3, Prayer of Mending:1"),
    ("discipline", "Twin Disciplines:5, Silent Resolve:3, Mental Strength:2, Mental Agility:3, Meditation:3, Inner Focus:1"),
], "Binding Heal is replaced by Holy Binding (1 point, Holy row 4), which this build takes.")
design("priest", "shadow", "ranged_damage", "RankedBoost 'Shadow Priest Leveling Build' (17/0/34)", [
    ("shadow", "Spirit Tap:5, Blackout:5, Improved Mind Blast:5, Improved Shadow Word: Pain:2, Improved Psychic Scream:2, Mind Flay:1, Improved Mind Flay:2, "
               "Shadow Weaving:3, Devouring Contagion:2, Early Demise:2, Darkness:4, Shadowform:1"),
    ("discipline", "Twin Disciplines:5, Wand Specialization:2, Mental Strength:3, Mental Agility:3, Meditation:3, Inner Focus:1"),
], "No structural Shadow changes in the Nov 2 notes (Vampiric Embrace healing can no longer crit, which this build does not take).")

# ----- Shaman ------------------------------------------------------------------------------------
design("shaman", "elemental_combat", "ranged_damage", "RankedBoost 'Elemental Shaman DPS Build' (32/5/14)", [
    ("elemental_combat", "Convection:5, Concussion:5, Reverberation:5, Call of Flame:3, Elemental Alacrity:3, Elemental Focus:1, Lightning Overload:3, "
                         "Call of Thunder:1, Elemental Fury:5, Lightning Mastery:1"),
    ("enhancement", "Thundering Strikes:5"),
    ("restoration", "Tidal Focus:5, Mindfulness:3, Totemic Focus:5, Natural Grace:1"),
], "Lava Burst is removed and replaced by Call of Thunder; Elemental Mastery is renamed Lightning Mastery; Lightning Overload is now 10/20/30%. "
   "Call of Thunder's row and rank are an assumption in the draft catalog.")
design("shaman", "enhancement", "melee_damage", "RankedBoost 'Enhancement Shaman Leveling Build' (0/43/8)", [
    ("enhancement", "Ancestral Knowledge:4, Thundering Strikes:5, Mental Dexterity:3, Elemental Weapons:3, Shamanistic Focus:1, Anticipation:3, Toughness:5, "
                    "Flurry:5, Stormstrike:1, Improved Ghost Wolf:2, Spirit Weapons:1, Mental Quickness:2, Improved Stormstrike:2, Maelstrom Weapon:5, Rage of the Farseer:1"),
    ("restoration", "Tidal Focus:5, Mindfulness:3"),
], "Improved Ghost Wolf moved from row 2 to row 4 on Nov 2, so it now unlocks later; Mental Dexterity is 50/100/150% of Intellect.")
design("shaman", "restoration", "healer", "RankedBoost 'Restoration Shaman Healing Build' (0/5/46)", [
    ("restoration", "Improved Healing Wave:5, Tidal Focus:5, Mindfulness:3, Totemic Focus:5, Ancestral Healing:3, Healing Focus:3, Water Shield:1, "
                    "Tidal Mastery:5, Restorative Totems:5, Mana Tide Totem:1, Healing Way:3, Nature's Swiftness:1, Purification:5, Riptide:1"),
    ("enhancement", "Thundering Strikes:5"),
], "Riptide is the Restoration capstone; the Nov 2 notes also change its spell values. The allocation otherwise follows the source.")

# ----- Warlock -----------------------------------------------------------------------------------
design("warlock", "affliction", "ranged_damage", "RankedBoost 'Affliction Warlock Leveling Build' (33/18/0)", [
    ("affliction", "Improved Life Tap:2, Suppression:1, Improved Corruption:5, Grim Reach:2, Soul Harvest:2, Improved Drains:3, Improved Bane of Agony:2, "
                   "Fel Concentration:3, Malevolence:2, Nightfall:2, Soul Siphon:3, Shadow Mastery:5, Wrack:1"),
    ("demonology", "Demonic Embrace:5, Improved Health Funnel:2, Fel Vitality:3, Demonic Energies:2, Improved Voidwalker:3, Master Summoner:2, Fel Domination:1"),
], "Improved Drains no longer raises Wrack damage (Nov 2) but still raises Drain Mana; Amplify Curse now affects Curse of Exhaustion and Bane of Agony and is not taken here.")
design("warlock", "demonology", "ranged_damage", "RankedBoost 'Demonology Warlock DPS Build' (5/30/16)", [
    ("demonology", "Demonic Embrace:5, Unholy Power:5, Fel Vitality:3, Demonic Energies:2, Demonic Aegis:2, Demonic Sacrifice:1, Improved Sayaad:3, Decimation:2, "
                   "Demonic Knowledge:3, Master Demonologist:5, Demonic Pact:1"),
    ("destruction", "Improved Shadow Bolt:5, Bane:5, Ruin:4"),
    ("affliction", "Suppression:5"),
], "No structural Demonology changes in the Nov 2 notes. Demonic Aegis (2) was added to keep the row 6 gate reachable; Agonizing Flames (1 in the source) is dropped.")
design("warlock", "destruction", "ranged_damage", "RankedBoost 'Destruction Warlock DPS Build' (5/11/35)", [
    ("destruction", "Improved Shadow Bolt:5, Bane:5, Aftermath:5, Ruin:5, Intensity:3, Agonizing Flames:3, Fire and Brimstone:3, Shadow and Flame:5, Incinerate:1"),
    ("demonology", "Demonic Embrace:5, Demonic Aegis:2, Fel Vitality:3, Demonic Sacrifice:1"),
    ("affliction", "Suppression:5"),
], "Shadow and Flame doubled in strength (4/8/12/16/20%) on Nov 2 and is kept at 5 ranks; Cataclysm (2 in the source) is dropped to fit Incinerate.")

# --------------------------------------------------------------------------------------------------
# Expansion, validation, output
# --------------------------------------------------------------------------------------------------
raw = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
catalog = TalentCatalog.model_validate(raw)
config = build_default_config()
config.talent_catalog = catalog


def index_for(cls_id):
    cc = next(c for c in catalog.classes if c.id == cls_id)
    return {t.name: (tree.id, t) for tree in cc.trees for t in tree.talents}, [tree.id for tree in cc.trees]


def parse(segment: str):
    for part in segment.split(", "):
        name, rank = part.rsplit(":", 1)
        yield name.strip(), int(rank)


def expand(cls_id, picks):
    idx, _ = index_for(cls_id)
    queue, alloc = [], {}
    for tree, seg in picks:
        for name, rank in parse(seg):
            if name not in idx:
                raise SystemExit(f"{cls_id}: unknown talent '{name}'")
            t_tree, t = idx[name]
            if t_tree != tree:
                raise SystemExit(f"{cls_id}: '{name}' is in {t_tree}, which differs from the expected {tree}")
            if rank > t.max_rank:
                raise SystemExit(f"{cls_id}: '{name}' rank {rank} exceeds max {t.max_rank}")
            if t.id in alloc:
                raise SystemExit(f"{cls_id}: '{name}' listed twice")
            alloc[t.id] = rank
            queue += [t.id] * rank
    by_id = {t.id: (tree.id, t) for tree in next(c for c in catalog.classes if c.id == cls_id).trees for t in tree.talents}
    have: dict[str, int] = {}
    order: list[str] = []
    remaining = list(queue)
    while remaining:
        for i, tid in enumerate(remaining):
            tree, t = by_id[tid]
            above = sum(n for k, n in have.items() if by_id[k][0] == tree and by_id[k][1].tier < t.tier)
            if above >= t.tier * catalog.points_per_tier and all(have.get(r.talent_id, 0) >= r.rank for r in t.requires):
                have[tid] = have.get(tid, 0) + 1
                order.append(tid)
                del remaining[i]
                break
        else:
            raise SystemExit(f"{cls_id}: no legal next point; stuck with {sorted(set(remaining))}")
    return alloc, order


def guidance(cls_id, alloc, order, tree_order, spec_id):
    idx, _ = index_for(cls_id)
    by_id = {t.id: (tree, t) for _, (tree, t) in idx.items()}
    names = {t.id: t.name for _, (tree, t) in idx.items()}
    dist = {}
    for tid, r in alloc.items():
        dist[by_id[tid][0]] = dist.get(by_id[tid][0], 0) + r
    dist_text = " / ".join(str(dist.get(t, 0)) for t in tree_order)
    pri = [f"Allocation {dist_text} across {', '.join(t.replace('_', ' ').title() for t in tree_order)}."]
    caps = [(tid, t) for _, (tree, t) in idx.items() for tid in [t.id] if tid in alloc and t.tier == 6 and by_id[tid][0] == spec_id]
    for tid, t in caps:
        pri.append(f"{t.name} (row 7 of this tree) comes at level {order.index(tid) + 10} in this order.")
    pri.append("First points (levels 10-15): " + ", ".join(names[t] for t in order[:6]) + ".")
    gear = []
    have = {names[t] for t in alloc}
    if "Two-Handed Weapon Specialization" in have:
        gear.append("Takes Two-Handed Weapon Specialization, so a two-handed weapon is part of the plan.")
    if "Dual Wield Specialization" in have:
        gear.append("Takes Dual Wield Specialization, so two one-handed weapons are part of the plan.")
    if "Shield Specialization" in have:
        gear.append("Takes Shield Specialization, so a shield is part of the plan.")
    if "Ranged Weapon Specialization" in have:
        gear.append("Takes Ranged Weapon Specialization, so a ranged weapon is part of the plan.")
    if "Wand Specialization" in have:
        gear.append("Takes Wand Specialization, so a wand is part of the plan.")
    return pri, gear


out = []
for d in D:
    cls, spec = d["cls"], d["spec"]
    alloc, order = expand(cls, d["picks"])
    _, tree_order = index_for(cls)
    cobj = config.get_class(cls)
    spec_obj = config.get_spec(cls, spec)
    bid = f"{cls}-{spec}-leveling".replace("_", "-")
    pri, gear = guidance(cls, alloc, order, [s.id for s in cobj.specializations], spec)
    build = Build(
        id=bid, class_id=cls, specialization_id=spec, name=f"{spec_obj.name}: leveling and general PvE (draft)",
        role=d["role"], purpose="leveling_pve", level=60, total_points=51, allocations=alloc, leveling_order=order,
        combat_priorities=pri, equipment_notes=gear, professions=[],
        source=f"BEST GUESS by Claude, 2026-11-03. Model: {d['model']}, remapped onto the draft Nov 2 talent trees. Not verified.",
        source_url=RB.format(cls), calculator_url="", verified_at=None, client_version=catalog.client_version,
        status="draft", is_default=True,
        notes=(d["notes"] + " Reddit and other forums could not be read; no community consensus is reflected beyond RankedBoost and the guide sites."),
    )
    v = validate_build(build, config)
    if not v.valid or not v.complete or v.points_spent != 51:
        raise SystemExit(f"{bid}: invalid - {v.errors} spent={v.points_spent}")
    if v.can_verify:
        raise SystemExit(f"{bid}: draft data must not allow verification")
    out.append(build.model_dump(mode="json"))
    print(f"{bid:34s} {'/'.join(str(v.tree_distribution.get(s.id, 0)) for s in cobj.specializations):10s} ok")

OUT_JSON.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"wrote {OUT_JSON.name}: {len(out)} builds")
