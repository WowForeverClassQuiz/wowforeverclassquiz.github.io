"""Builds the DRAFT World of Warcraft: Forever talent catalog (all 9 classes, 27 trees).

    python catalog/build_forever_draft.py        # writes the .json and RECONCILIATION.md next to this file

THIS IS NOT GAME-CLIENT DATA. It was assembled by hand on 2026-11-03 from two web sources and
has not been checked against the client:

  BASE   GuildOrder's WoW Forever talent pages (guildorder.com/games/wow_forever/tools/talents/<class>),
         which state "Last reviewed October 2026" and list every talent with its max rank and the
         points that must be spent in the tree first ("Needs N points in <tree>"). Rows are derived
         from those gates (row r needs (r-1) x 5 points). The pages show NO talent-to-talent
         prerequisites and NO grid columns.
  NOTES  Blizzard's "WoW Forever Beta Development Notes - Updated November 2" (US forums, developer
         post stamped 2026-11-03 03:20), which lists talent CHANGES only, not full trees.

Method: every structural talent claim in the notes (moved, removed, added, renamed, rank changed) is
written below as an EXPECTATION about the final tree. The script checks each against the base. Where
the base already matches, the source had already absorbed the change (Druid, Paladin, Mage, Hunter,
Priest). Where it does not (Rogue, Warrior, Shaman), the change is applied explicitly in DELTAS.
After the deltas every expectation must hold, or the script stops. RECONCILIATION.md records the result.

Known limits (also written into the catalog's `notes`): prerequisites are only those the notes state;
`column` is list order, not the real grid position; value-only changes (percentages) are not modelled;
the notes were summarised by a fetch tool, so entry-level transcription errors are possible.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from app.models import TalentCatalog  # noqa: E402

OUT_JSON = HERE / "forever-talents-draft-2026-11-03.json"
OUT_LEDGER = HERE / "RECONCILIATION.md"

# ---------------------------------------------------------------------------------------------
# BASE: "Talent|max rank|points needed in tree". Page order is kept; it is the only ordering known.
# ---------------------------------------------------------------------------------------------
BASE = {
    "druid": {
        "balance": """Improved Wrath|5|0
Genesis|5|0
Moonglow|3|5
Improved Moonfire|2|5
Nature's Majesty|2|5
Nature's Reach|2|5
Improved Entangling Roots|3|10
Nature's Splendor|1|10
Insect Swarm|1|15
Vengeance|5|15
Improved Starfire|5|15
Overgrowth|2|20
Nature's Grace|1|20
Eclipse|3|20
Moonfury|5|25
Moonkin Form|1|30""",
        "feral_combat": """Ferocity|5|0
Furor|5|0
Feral Swiftness|2|5
Feral Instinct|3|5
Brutal Impact|2|5
Thick Hide|3|5
Shredding Attacks|3|10
Savage Fury|2|10
Feral Charge|1|10
Sharpened Claws|2|10
Predatory Strikes|3|15
Lacerate|1|15
Predatory Discipline|1|15
Blood Frenzy|2|15
Leader of the Pack|1|20
Natural Instinct|2|20
Rend and Tear|5|25
Natural Reaction|5|25
Primal Bite|1|30
Shifting Power|1|30""",
        "restoration": """Nature's Focus|5|0
Heart of the Wild|5|0
Naturalist|5|5
Reflection|3|5
Natural Shapeshifter|3|5
Subtlety|3|10
Gift of Nature|5|10
Bloom|1|10
Tranquil Spirit|5|15
Improved Rejuvenation|3|15
Swiftmend|1|15
Nature's Swiftness|1|20
Living Spirit|3|20
Improved Tranquility|2|20
Improved Regrowth|5|25
Wild Growth|1|30""",
    },
    "hunter": {
        "beast_mastery": """Deadly Aspects|5|0
Endurance Training|5|0
Focused Fire|2|5
Improved Aspect of the Monkey|3|5
Improved Revive Pet|2|5
Pathfinding|2|10
Bestial Swiftness|1|10
Unleashed Fury|5|10
Improved Mend Pet|2|15
Ferocity|5|15
Summon Hawk|1|15
Spirit Bond|2|20
Intimidation|1|20
Bestial Discipline|2|20
Frenzy|5|25
Bestial Wrath|1|30""",
        "marksmanship": """Hawk Eye|3|0
Improved Concussive Shot|5|0
Lethal Attacks|5|0
Improved Stings|3|5
Efficiency|5|5
Careful Aim|5|5
Rapid Killing|2|10
Improved Arcane Shot|5|10
Lone Wolf|1|10
Trueshot Aura|1|15
Mortal Shots|5|15
Rapid Recuperation|2|20
Barrage|3|20
Scatter Shot|1|20
Ranged Weapon Specialization|5|25
Sniper Shot|1|30""",
        "survival": """Improved Tracking|5|0
Deflection|5|0
Entrapment|5|5
Savage Strikes|2|5
Survivalist|5|5
Improved Wing Clip|3|5
Clever Traps|2|10
Surefooted|3|10
Deterrence|1|10
Survival Tactics|2|15
Predator's Edge|5|15
Counterattack|1|15
Resourcefulness|2|20
Expose Prey|2|20
Survivalist's Discipline|2|20
Strider Kick|1|20
Lightning Reflexes|5|25
Lacerating Strikes|1|30""",
    },
    "mage": {
        "arcane": """Wand Specialization|2|0
Improved Channeling|5|0
Arcane Resilience|3|0
Arcane Subtlety|2|5
Magic Absorption|2|5
Arcane Concentration|5|5
Missile Barrage|2|5
Arcane Geometry|2|10
Arcane Impact|3|10
Arcane Blast|1|10
Arcane Shielding|2|15
Improved Counterspell|2|15
Arcane Meditation|3|15
Arcane Wrath|1|15
Presence of Mind|1|20
Arcane Mind|5|20
Arcane Instability|3|25
Arcane Power|1|30""",
        "fire": """Incineration|5|0
Accelerant|5|0
Ignite|5|5
Flame Throwing|2|5
Impact|3|5
Burning Soul|3|10
Improved Flamestrike|3|10
Pyroblast|1|10
Improved Fire Blast|2|10
Improved Scorch|3|15
Improved Fire Ward|2|15
Heating Up|1|15
Master of Elements|3|15
Critical Mass|3|20
Blast Wave|1|20
Fire Power|3|25
Combustion|1|30""",
        "frost": """Frost Warding|2|0
Improved Frostbolt|5|0
Precision|3|0
Ice Shards|5|5
Frostbite|3|5
Improved Frost Nova|2|5
Permafrost|3|5
Frost Channeling|3|10
Improved Blizzard|3|10
Ice Lance|1|10
Arctic Reach|2|15
Ice Block|1|15
Shatter|3|15
Improved Cone of Cold|3|20
Cold Snap|1|20
Fingers of Frost|2|20
Winter's Chill|5|25
Ice Barrier|1|30""",
    },
    "paladin": {
        "holy": """Spiritual Focus|5|0
Divine Strength|5|0
Healing Light|3|5
Reverence|2|5
Improved Seals|5|5
Purifying Power|2|5
Divine Favor|1|10
Illumination|5|10
Holy Conduit|2|10
Divine Precision|2|15
Infusion of Light|2|15
Oath of Light|1|15
Consecrated Ground|2|20
Holy Shock|1|20
Boundless Light|2|20
Holy Power|5|25
Light's Vigil|1|30""",
        "protection": """Divine Intellect|5|0
Redoubt|5|0
Precision|3|5
Guardian's Favor|2|5
Sacred Duty|2|5
Templar's Bulwark|1|10
Improved Hammer of Justice|3|10
Shield Specialization|2|10
Toughness|5|10
Swift Judgement|1|15
Improved Righteous Fury|3|15
Anticipation|5|15
Stoicism|2|20
Holy Shield|1|20
Reckoning|5|20
Iron Creed|3|25
Shieldsworn|1|30""",
        "retribution": """Deflection|5|0
Benediction|5|0
Improved Judgement|2|5
Conviction|3|5
Sanctified Judgement|3|5
Vindication|3|10
Unyielding Faith|2|10
Seal of Command|1|10
Pursuit of Justice|2|10
Eye for an Eye|2|15
Sacred Arbiter|1|15
Two-Handed Weapon Specialization|3|15
Turn Evil|2|20
Repentance|1|20
Vengeance|3|20
Champion of the Light|5|25
Unsealed Wrath|1|30""",
    },
    "priest": {
        "discipline": """Power in Light|5|0
Wand Specialization|2|0
Twin Disciplines|5|0
Silent Resolve|3|5
Holy Precision|3|5
Mental Strength|5|5
Martyrdom|2|5
Mental Agility|3|10
Inner Focus|1|10
Improved Power Word: Shield|3|10
Meditation|3|10
Improved Inner Fire|3|15
Improved Mana Burn|2|15
Soul Warding|1|15
Penance|1|20
Renewed Hope|5|20
Divine Aegis|3|25
Power Infusion|1|30""",
        "holy": """Twilight Focus|3|0
Improved Renew|3|0
Holy Specialization|5|0
Spell Warding|5|5
Divine Fury|5|5
Holy Nova|1|10
Blessed Recovery|3|10
Inspiration|3|10
Holy Reach|2|15
Improved Healing|3|15
Searing Light|2|15
Holy Binding|1|15
Litany of Light|2|20
Spirit of Redemption|1|20
Spiritual Guidance|5|20
Spiritual Healing|3|25
Prayer of Mending|1|30""",
        "shadow": """Shadow Focus|5|0
Blackout|5|0
Spirit Tap|5|0
Improved Mind Blast|5|5
Improved Shadow Word: Pain|2|5
Shadow Reach|2|5
Improved Psychic Scream|2|10
Mind Flay|1|10
Improved Mind Flay|2|10
Dark Inspiration|5|15
Vampiric Embrace|1|15
Shadow Weaving|3|15
Silence|1|20
Devouring Contagion|2|20
Early Demise|2|25
Darkness|5|25
Shadowform|1|30""",
    },
    "rogue": {
        "assassination": """Improved Gouge|3|0
Remorseless Attacks|2|0
Malice|5|0
Ruthlessness|3|5
Murder|2|5
Improved Slice and Dice|3|5
Relentless Strikes|1|10
Improved Expose Armor|2|10
Lethality|5|10
Vile Poisons|5|15
Cold Blood|1|15
Improved Poisons|5|15
Vigor|2|20
Mutilate|1|20
Improved Kidney Shot|2|20
Seal Fate|5|25
Venom|1|30""",
        "combat": """Improved Eviscerate|3|0
Improved Sinister Strike|2|0
Lightning Reflexes|5|0
Puncturing Wounds|3|5
Deflection|3|5
Precision|3|5
Endurance|2|10
Riposte|1|10
Improved Sprint|2|10
Improved Kick|2|15
Flawless Execution|1|15
Dual Wield Specialization|5|15
Blade Flurry|1|20
Hack and Slash|5|20
Weapon Expertise|2|25
Aggression|3|25
Adrenaline Rush|1|30""",
        "subtlety": """Camouflage|5|0
Master of Deception|3|0
Opportunity|2|0
Setup|3|5
Elusiveness|2|5
Dirty Tricks|2|5
Improved Ambush|3|5
Initiative|3|10
Ghostly Strike|1|10
Improved Distract|2|10
Heightened Senses|2|15
Premeditation|1|15
Serrated Blades|3|15
Dirty Deeds|2|20
Preparation|1|20
Hemorrhage|1|20
Quietus|5|25
Cutthroat|5|25
Thousand Cuts|1|30""",
    },
    "shaman": {
        "elemental_combat": """Convection|5|0
Concussion|5|0
Elemental Devastation|3|5
Reverberation|5|5
Elemental Alacrity|3|5
Call of Flame|3|5
Elemental Focus|1|10
Elemental Warding|3|10
Trial by Fire|2|15
Eye of the Storm|3|15
Earthbound|1|15
Elemental Reach|2|20
Lava Burst|1|20
Lightning Overload|3|20
Elemental Fury|5|25
Elemental Mastery|1|30""",
        "enhancement": """Earth's Grasp|2|0
Thundering Strikes|5|0
Ancestral Knowledge|5|0
Guardian Totems|2|5
Mental Dexterity|3|5
Improved Ghost Wolf|2|5
Improved Lightning Shield|3|5
Elemental Weapons|3|10
Shamanistic Focus|1|10
Anticipation|3|10
Toughness|5|15
Flurry|5|15
Stormstrike|1|15
Spirit Weapons|1|20
Mental Quickness|2|20
Improved Stormstrike|2|20
Maelstrom Weapon|5|25
Rage of the Farseer|1|30""",
        "restoration": """Improved Healing Wave|5|0
Tidal Focus|5|0
Mindfulness|3|5
Natural Grace|3|5
Totemic Focus|5|5
Improved Reincarnation|2|5
Ancestral Healing|3|10
Healing Focus|3|10
Water Shield|1|10
Tidal Mastery|5|15
Restorative Totems|5|15
Mana Tide Totem|1|15
Healing Way|3|20
Nature's Swiftness|1|20
Purification|5|25
Riptide|1|30""",
    },
    "warlock": {
        "affliction": """Improved Life Tap|2|0
Suppression|5|0
Improved Corruption|5|0
Grim Reach|2|5
Soul Harvest|2|5
Improved Drains|3|5
Improved Bane of Agony|2|10
Fel Concentration|3|10
Amplify Curse|1|10
Pandemic|3|10
Malevolence|5|15
Nightfall|2|15
Curse of Exhaustion|1|15
Siphon Life|1|20
Soul Siphon|3|20
Shadow Mastery|5|25
Wrack|1|30""",
        "demonology": """Improved Health Funnel|2|0
Improved Imp|3|0
Demonic Embrace|5|0
Unholy Power|5|0
Demonic Aegis|2|5
Improved Voidwalker|3|5
Fel Vitality|3|5
Demonic Energies|2|5
Improved Sayaad|3|10
Demonic Sacrifice|1|10
Master Summoner|2|10
Decimation|2|15
Fel Domination|1|15
Demonic Brand|3|15
Improved Felhunter|3|20
Soul Link|1|20
Demonic Knowledge|3|20
Master Demonologist|5|25
Demonic Pact|1|30""",
        "destruction": """Destructive Reach|2|0
Improved Shadow Bolt|5|0
Bane|5|0
Molten Skin|5|5
Cataclysm|3|5
Aftermath|5|5
Ruin|5|10
Shadowburn|1|10
Intensity|3|15
Agonizing Flames|3|15
Conflagrate|1|15
Pyroclasm|2|20
Bane of Havoc|1|20
Fire and Brimstone|3|20
Shadow and Flame|5|25
Incinerate|1|30""",
    },
    "warrior": {
        "arms": """Improved Heroic Strike|3|0
Deflection|5|0
Improved Rend|3|0
Improved Charge|2|5
Improved Tactical Mastery|5|5
Improved Overpower|2|5
Anger Management|1|10
Deep Wounds|3|10
Spearing Strike|1|15
Two-Handed Weapon Specialization|3|15
Impale|2|15
Bloodthrill|5|20
Sweeping Strikes|1|20
Weaponmaster|5|20
Improved Slam|2|25
Improved Hamstring|3|25
Mortal Strike|1|30""",
        "fury": """Booming Voice|5|0
Cruelty|5|0
Lingering Rage|5|5
Unbridled Wrath|5|5
Furious Precision|3|10
Piercing Howl|1|10
Blood Craze|3|10
Dual Wield Specialization|5|15
Raging Blows|1|15
Enrage|5|15
Improved Execute|2|15
Improved Berserker Rage|2|20
Death Wish|1|20
Improved Intercept|2|20
Flurry|5|25
Gore Drinker|2|25
Bloodthirst|1|30""",
        "protection": """Improved Bloodrage|2|0
Shield Specialization|5|0
Iron Will|5|0
Anticipation|5|5
Improved Revenge|3|5
Improved Thunder Clap|3|5
Last Stand|1|10
Master of Defense|2|10
Improved Disarm|3|10
Defiance|3|10
Improved Sunder Armor|3|15
Vanguard|1|15
Improved Shield Bash|2|15
Improved Shield Wall|2|20
Concussion Blow|1|20
Focused Rage|3|20
Bastion|5|25
Shield Slam|1|30""",
    },
}

TREE_NAMES = {
    "balance": "Balance", "feral_combat": "Feral Combat", "restoration": "Restoration",
    "beast_mastery": "Beast Mastery", "marksmanship": "Marksmanship", "survival": "Survival",
    "arcane": "Arcane", "fire": "Fire", "frost": "Frost", "holy": "Holy", "protection": "Protection",
    "retribution": "Retribution", "discipline": "Discipline", "shadow": "Shadow",
    "assassination": "Assassination", "combat": "Combat", "subtlety": "Subtlety",
    "elemental_combat": "Elemental Combat", "enhancement": "Enhancement",
    "affliction": "Affliction", "demonology": "Demonology", "destruction": "Destruction",
    "arms": "Arms", "fury": "Fury",
}

# ---------------------------------------------------------------------------------------------
# Working model: cat[class][tree] = list of {"name", "rank", "gate", "requires": [(name, rank)], "note"}
# ---------------------------------------------------------------------------------------------
cat: dict[str, dict[str, list[dict]]] = {}
for c, trees in BASE.items():
    cat[c] = {}
    for t, block in trees.items():
        rows = []
        for line in block.strip().splitlines():
            name, rank, gate = line.split("|")
            rows.append({"name": name, "rank": int(rank), "gate": int(gate), "requires": [], "note": ""})
        cat[c][t] = rows


def find(c: str, name: str):
    hits = [(t, r) for t, rows in cat[c].items() for r in rows if r["name"] == name]
    if len(hits) > 1:
        raise SystemExit(f"ambiguous talent {c}/{name}: {[t for t, _ in hits]}")
    return hits[0] if hits else (None, None)


def row_gate(row: int) -> int:
    return (row - 1) * 5


# ---------------------------------------------------------------------------------------------
# EXPECTATIONS: structural claims from the Nov 2 notes, stated as the final state.
# (class, talent name, tree|None, gate|None, rank|None, "what the notes say")
# gate is (row-1)*5; ABSENT lists talents the notes say were removed or renamed away.
# ---------------------------------------------------------------------------------------------
EXPECT: list[tuple] = []
ABSENT: list[tuple] = []


def E(c, name, tree=None, row=None, rank=None, said=""):
    EXPECT.append((c, name, tree, None if row is None else row_gate(row), rank, said))


def X(c, name, said=""):
    ABSENT.append((c, name, said))


# Druid
E("druid", "Lacerate", "feral_combat", 4, said="now a Feral talent on row 4")
X("druid", "Berserk", "Berserk removed")
E("druid", "Heart of the Wild", "restoration", said="moved to Restoration, swapping with Furor")
E("druid", "Furor", "feral_combat", said="moved to Feral, swapping with Heart of the Wild")
E("druid", "Predatory Discipline", "feral_combat", 4, 1, "added: 1 point, Feral row 4")
E("druid", "Primal Bite", "feral_combat", 7, said="row 7, replaces Berserk")
E("druid", "Shifting Power", "feral_combat", 7, 1, "moved to row 7, 1 point")
E("druid", "Rend and Tear", "feral_combat", rank=5, said="5 ranks (3/6/9/12/15%)")
E("druid", "Genesis", "balance", rank=5, said="5 ranks (2/4/6/8/10%)")
E("druid", "Reflection", "restoration", 2, said="moved to row 2")
E("druid", "Subtlety", "restoration", 3, said="moved to row 3")
X("druid", "Gift of the Earthmother", "removed")
E("druid", "Bloom", "restoration", 3, 1, "added: 1 point, row 3")
# Hunter
E("hunter", "Pathfinding", "beast_mastery", 3, said="moved to row 3")
E("hunter", "Barrage", "marksmanship", rank=3, said="3 ranks (5/10/15%)")
E("hunter", "Lightning Reflexes", "survival", rank=5, said="5 ranks (3/6/9/12/15%)")
# Mage
E("mage", "Missile Barrage", "arcane", 2, said="moved to row 2")
E("mage", "Arcane Resilience", "arcane", 1, 3, "moved to row 1, up to 3 points")
X("mage", "Arcane Focus", "removed, combined into Precision (Frost)")
E("mage", "Incineration", "fire", rank=5, said="up to 5 points")
E("mage", "Accelerant", "fire", said="Improved Fireball renamed Accelerant")
X("mage", "Improved Fireball", "renamed Accelerant")
E("mage", "Critical Mass", "fire", rank=3, said="max 3 points")
E("mage", "Improved Fire Blast", "fire", 3, said="moved to row 3")
X("mage", "Piercing Ice", "removed")
E("mage", "Precision", "frost", rank=3, said="Elemental Precision renamed Precision, 3 points")
X("mage", "Elemental Precision", "renamed Precision")
# Paladin
E("paladin", "Spiritual Focus", "holy", 1, 5, "row 1, 5 points")
E("paladin", "Improved Seals", "holy", rank=5, said="5 points")
E("paladin", "Reverence", "holy", 2, 2, "row 2, 2 points")
E("paladin", "Purifying Power", "holy", 2, said="row 2")
X("paladin", "Voice of Truth", "removed")
E("paladin", "Divine Favor", "holy", 3, said="row 3")
E("paladin", "Illumination", "holy", 3, said="row 3")
E("paladin", "Holy Conduit", "holy", 3, said="Holy tree row 3")
E("paladin", "Divine Precision", "holy", 4, 2, "row 4, 2 points")
E("paladin", "Oath of Light", "holy", 4, said="added row 4")
E("paladin", "Boundless Light", "holy", 5, said="added row 5")
E("paladin", "Divine Intellect", "protection", 1, said="moved to Protection row 1")
E("paladin", "Sacred Duty", "protection", 2, said="row 2")
X("paladin", "Improved Seal of Fury", "removed")
E("paladin", "Templar's Bulwark", "protection", 3, said="row 3")
E("paladin", "Shield Specialization", "protection", rank=2, said="2 points")
E("paladin", "Toughness", "protection", 3, said="row 3")
E("paladin", "Anticipation", "protection", 4, said="row 4")
X("paladin", "One-Handed Weapon Specialization", "removed")
E("paladin", "Stoicism", "protection", 5, said="added row 5")
E("paladin", "Holy Shield", "protection", 5, said="row 5")
E("paladin", "Iron Creed", "protection", rank=3, said="3 points")
E("paladin", "Shieldsworn", "protection", 7, said="added row 7")
E("paladin", "Sanctified Judgement", "retribution", 2, said="row 2")
E("paladin", "Conviction", "retribution", 2, said="row 2")
E("paladin", "Unyielding Faith", "retribution", 3, said="Retribution row 3")
E("paladin", "Two-Handed Weapon Specialization", "retribution", 4, said="row 4")
X("paladin", "Instrument of Law", "removed")
E("paladin", "Vengeance", "retribution", said="stacks to 5, requires Seal of Command")
E("paladin", "Turn Evil", "retribution", 5, said="added row 5")
X("paladin", "Twist of Light", "removed")
E("paladin", "Unsealed Wrath", "retribution", 7, 1, "added: the 31st-point talent")
# Priest
X("priest", "Binding Heal", "removed, replaced by Holy Binding")
E("priest", "Holy Binding", "holy", said="added to Holy")
# Shaman
X("shaman", "Lava Burst", "removed, replaced by Call of Thunder")
E("shaman", "Call of Thunder", "elemental_combat", said="added, replaces Lava Burst")
E("shaman", "Lightning Mastery", "elemental_combat", said="Elemental Mastery renamed Lightning Mastery")
X("shaman", "Elemental Mastery", "renamed Lightning Mastery")
E("shaman", "Lightning Overload", "elemental_combat", rank=3, said="3 ranks (10/20/30%)")
E("shaman", "Improved Ghost Wolf", "enhancement", 4, said="moved to row 4")
# Warrior
E("warrior", "Improved Tactical Mastery", "arms", rank=3, said="now 3 points")
E("warrior", "Bloodthrill", "arms", rank=2, said="now 2 points")
E("warrior", "Gore Drinker", "fury", 5, said="moved to row 5")
E("warrior", "Enrage", "fury", 3, said="moved to row 3")
E("warrior", "Reckless Swings", "fury", 4, 1, "added: row 4, 1 point")
E("warrior", "Flurry", "fury", rank=3, said="now 3 points")
E("warrior", "Improved Whirlwind", "fury", 6, 2, "added: row 6, 2 points")
# Rogue - Assassination
X("rogue", "Murder", "removed")
E("rogue", "Lethality", "assassination", rank=2, said="now 2 points")
E("rogue", "Improved Expose Armor", "assassination", 2, said="moved to row 2")
E("rogue", "Vigor", "assassination", 3, said="moved to row 3")
E("rogue", "Blood Splatter", "assassination", 3, 1, "added: row 3, 1 point")
E("rogue", "Relentless Strikes", "assassination", 5, 5, "moved to row 5, now 5 points")
E("rogue", "Venom", "assassination", 5, said="moved to row 5")
E("rogue", "Seal Fate", "assassination", rank=3, said="now 3 points")
E("rogue", "Mutilate", "assassination", 7, said="moved to row 7 (the 31-point talent)")
# Rogue - Combat
E("rogue", "Coup de Grace", "combat", said="Improved Eviscerate renamed")
X("rogue", "Improved Eviscerate", "renamed Coup de Grace")
E("rogue", "Efficient Strikes", "combat", said="Improved Sinister Strike renamed")
X("rogue", "Improved Sinister Strike", "renamed Efficient Strikes")
E("rogue", "Improved Sprint", "combat", 2, said="moved to row 2")
E("rogue", "Composure", "combat", 3, 2, "added: row 3, 2 points")
E("rogue", "Weapon Expertise", "combat", 4, said="moved to row 4")
E("rogue", "Aggression", "combat", 4, said="moved to row 4")
E("rogue", "Dual Wield Specialization", "combat", 5, 2, "moved to row 5, now 2 points")
E("rogue", "Flash of Steel", "combat", 6, 5, "added: row 6, 5 points")
# Rogue - Subtlety
E("rogue", "Setup", "subtlety", 1, said="moved to row 1")
E("rogue", "Opportunity", "subtlety", rank=5, said="now 5 points")
E("rogue", "Dirty Deeds", "subtlety", 2, said="moved to row 2")
E("rogue", "Camouflage", "subtlety", 2, 3, "moved to row 2, now 3 points")
E("rogue", "Premeditation", "subtlety", 3, said="moved to row 3")
E("rogue", "Serrated Blades", "subtlety", 3, said="moved to row 3")
E("rogue", "Elusiveness", "subtlety", 4, said="moved to row 4")
E("rogue", "Ghostly Strike", "subtlety", 4, said="moved to row 4")
X("rogue", "Improved Distract", "removed")
E("rogue", "Quick Getaway", "subtlety", 4, 2, "added: row 4, 2 points")
E("rogue", "Heightened Senses", "subtlety", 5, said="moved to row 5")
X("rogue", "Quietus", "removed")
X("rogue", "Cutthroat", "removed")
E("rogue", "Boot Knife", "subtlety", 6, 5, "added: row 6, 5 points")
X("rogue", "Thousand Cuts", "removed")
E("rogue", "Death Mark", "subtlety", 7, 1, "added: row 7, 1 point")


def holds(e) -> bool:
    c, name, tree, gate, rank, _ = e
    t, r = find(c, name)
    return bool(r) and (tree is None or t == tree) and (gate is None or r["gate"] == gate) and (rank is None or r["rank"] == rank)


def absent(a) -> bool:
    return find(a[0], a[1])[1] is None


before_e = [holds(e) for e in EXPECT]
before_a = [absent(a) for a in ABSENT]

# ---------------------------------------------------------------------------------------------
# DELTAS: changes the base source had NOT absorbed (found by the check above: Rogue, Warrior, Shaman).
# Each helper asserts the old state, so a surprise in the source fails loudly instead of silently.
# ---------------------------------------------------------------------------------------------
APPLIED: list[str] = []


def log(c, msg):
    APPLIED.append(f"{c}: {msg}")


def move(c, name, row, note, was_row=None):
    t, r = find(c, name)
    assert r, f"{c}/{name} missing"
    if was_row is not None:
        assert r["gate"] == row_gate(was_row), f"{c}/{name} expected on row {was_row}, source has gate {r['gate']}"
    r["gate"] = row_gate(row)
    r["note"] = note
    log(c, f"{name}: {note}")


def set_rank(c, name, rank, note, was=None):
    t, r = find(c, name)
    assert r, f"{c}/{name} missing"
    if was is not None:
        assert r["rank"] == was, f"{c}/{name} expected {was} ranks, source has {r['rank']}"
    r["rank"] = rank
    r["note"] = (r["note"] + "; " if r["note"] else "") + note
    log(c, f"{name}: {note}")


def remove(c, name):
    t, r = find(c, name)
    assert r, f"{c}/{name} missing"
    cat[c][t].remove(r)
    log(c, f"removed {name}")


def rename(c, old, new):
    t, r = find(c, old)
    assert r, f"{c}/{old} missing"
    r["name"] = new
    r["note"] = f"Nov 2 notes: renamed from {old}"
    log(c, f"renamed {old} -> {new}")


def add(c, tree, name, rank, row, note):
    assert find(c, name)[1] is None, f"{c}/{name} already present"
    cat[c][tree].append({"name": name, "rank": rank, "gate": row_gate(row), "requires": [], "note": note})
    log(c, f"added {name} to {tree} (row {row}, {rank} pts)")


NOV2 = "Nov 2 dev notes"
# --- Shaman -----------------------------------------------------------------------------
if not holds(("shaman", "Call of Thunder", "elemental_combat", None, None, "")):
    remove("shaman", "Lava Burst")
    add("shaman", "elemental_combat", "Call of Thunder", 1, 5,
        f"{NOV2}: replaces Lava Burst. ASSUMPTION: same slot (row 5) and 1 point; the notes give neither.")
    rename("shaman", "Elemental Mastery", "Lightning Mastery")
    move("shaman", "Improved Ghost Wolf", 4, f"{NOV2}: moved to row 4 (was row 2)", was_row=2)
# --- Warrior ----------------------------------------------------------------------------
if not holds(("warrior", "Reckless Swings", "fury", None, None, "")):
    set_rank("warrior", "Improved Tactical Mastery", 3, f"{NOV2}: now 3 points (was 5)", was=5)
    set_rank("warrior", "Bloodthrill", 2, f"{NOV2}: now 2 points (was 5)", was=5)
    move("warrior", "Enrage", 3, f"{NOV2}: moved to row 3 (was row 4)", was_row=4)
    move("warrior", "Gore Drinker", 5, f"{NOV2}: moved to row 5 (was row 6)", was_row=6)
    set_rank("warrior", "Flurry", 3, f"{NOV2}: now 3 points (was 5)", was=5)
    add("warrior", "fury", "Reckless Swings", 1, 4, f"{NOV2}: new talent, row 4, 1 point")
    add("warrior", "fury", "Improved Whirlwind", 2, 6, f"{NOV2}: new talent, row 6, 2 points")
# --- Rogue ------------------------------------------------------------------------------
if not holds(("rogue", "Death Mark", "subtlety", None, None, "")):
    # Assassination
    remove("rogue", "Murder")
    set_rank("rogue", "Lethality", 2, f"{NOV2}: now 2 points (was 5)", was=5)
    move("rogue", "Improved Expose Armor", 2, f"{NOV2}: moved to row 2 (was row 3)", was_row=3)
    move("rogue", "Vigor", 3, f"{NOV2}: moved to row 3 (was row 5)", was_row=5)
    add("rogue", "assassination", "Blood Splatter", 1, 3, f"{NOV2}: new talent, row 3, 1 point")
    move("rogue", "Relentless Strikes", 5, f"{NOV2}: moved to row 5 (was row 3), now 5 points (was 1)", was_row=3)
    set_rank("rogue", "Relentless Strikes", 5, f"{NOV2}: now 5 points (was 1)", was=1)
    move("rogue", "Venom", 5, f"{NOV2}: moved to row 5 (was row 7)", was_row=7)
    set_rank("rogue", "Seal Fate", 3, f"{NOV2}: now 3 points (was 5)", was=5)
    move("rogue", "Mutilate", 7, f"{NOV2}: moved to row 7 (the 31-point talent). The notes say it was row 9; the source showed row 5.")
    # Combat
    rename("rogue", "Improved Eviscerate", "Coup de Grace")
    rename("rogue", "Improved Sinister Strike", "Efficient Strikes")
    move("rogue", "Improved Sprint", 2, f"{NOV2}: moved to row 2 (was row 3)", was_row=3)
    add("rogue", "combat", "Composure", 2, 3, f"{NOV2}: new talent, row 3, 2 points")
    move("rogue", "Weapon Expertise", 4, f"{NOV2}: moved to row 4 (was row 6)", was_row=6)
    move("rogue", "Aggression", 4, f"{NOV2}: moved to row 4 (was row 6)", was_row=6)
    move("rogue", "Dual Wield Specialization", 5, f"{NOV2}: moved to row 5 (was row 4)", was_row=4)
    set_rank("rogue", "Dual Wield Specialization", 2, f"{NOV2}: now 2 points (was 5)", was=5)
    add("rogue", "combat", "Flash of Steel", 5, 6, f"{NOV2}: new talent, row 6, 5 points")
    # Subtlety
    move("rogue", "Setup", 1, f"{NOV2}: moved to row 1 (was row 2)", was_row=2)
    set_rank("rogue", "Opportunity", 5, f"{NOV2}: now 5 points (was 2)", was=2)
    move("rogue", "Dirty Deeds", 2, f"{NOV2}: moved to row 2 (was row 5)", was_row=5)
    move("rogue", "Camouflage", 2, f"{NOV2}: moved to row 2 (was row 1)", was_row=1)
    set_rank("rogue", "Camouflage", 3, f"{NOV2}: now 3 points (was 5)", was=5)
    move("rogue", "Premeditation", 3, f"{NOV2}: moved to row 3 (was row 4)", was_row=4)
    move("rogue", "Serrated Blades", 3, f"{NOV2}: moved to row 3 (was row 4)", was_row=4)
    move("rogue", "Elusiveness", 4, f"{NOV2}: moved to row 4 (was row 2)", was_row=2)
    move("rogue", "Ghostly Strike", 4, f"{NOV2}: moved to row 4 (was row 3)", was_row=3)
    remove("rogue", "Improved Distract")
    add("rogue", "subtlety", "Quick Getaway", 2, 4, f"{NOV2}: new talent, row 4, 2 points")
    move("rogue", "Heightened Senses", 5, f"{NOV2}: moved to row 5 (was row 4)", was_row=4)
    remove("rogue", "Quietus")
    remove("rogue", "Cutthroat")
    add("rogue", "subtlety", "Boot Knife", 5, 6, f"{NOV2}: new talent, row 6, 5 points")
    remove("rogue", "Thousand Cuts")
    add("rogue", "subtlety", "Death Mark", 1, 7, f"{NOV2}: new talent, row 7, 1 point (new capstone)")

# Prerequisites stated in the notes (everything else is unknown, see module docstring).
PREREQS = [
    ("druid", "Primal Bite", "Leader of the Pack", 1, "notes: prerequisite Leader of the Pack"),
    ("druid", "Shifting Power", "Predatory Discipline", 1, "notes: prerequisite Predatory Discipline"),
    ("paladin", "Vengeance", "Seal of Command", 1, "notes: requires Seal of Command (was Sanctified Judgement)"),
    ("paladin", "Unsealed Wrath", "Repentance", 1, "notes: now requires Repentance"),
    ("warrior", "Bloodthirst", "Death Wish", 1, "notes: now requires Death Wish"),
    ("warrior", "Gore Drinker", "Blood Craze", None, "notes: connected to Blood Craze instead of Enrage. ASSUMPTION: needs Blood Craze at max rank"),
]
for c, talent, req, rank, why in PREREQS:
    t, r = find(c, talent)
    _, q = find(c, req)
    assert r and q, f"prerequisite {c}/{talent} <- {req} unresolved"
    r["requires"].append((req, rank if rank is not None else q["rank"]))
    r["note"] = (r["note"] + "; " if r["note"] else "") + why

after_e = [holds(e) for e in EXPECT]
after_a = [absent(a) for a in ABSENT]
if not (all(after_e) and all(after_a)):
    bad = [e[:2] for e, ok in zip(EXPECT, after_e) if not ok] + [a[:2] for a, ok in zip(ABSENT, after_a) if not ok]
    raise SystemExit(f"expectations from the notes do not hold after applying deltas: {bad}")

# ---------------------------------------------------------------------------------------------
# Emit the catalog
# ---------------------------------------------------------------------------------------------
def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower().replace("'", "")).strip("-")


NOTES = (
    "DRAFT assembled by hand on 2026-11-03; NOT read from the game client. Base: GuildOrder WoW Forever talent pages "
    "(reviewed October 2026). Changes: Blizzard 'WoW Forever Beta Development Notes - Updated November 2'. "
    "Limits: talent-to-talent prerequisites are only those the notes state (the source shows none); "
    "'column' is list order, not the real grid position; percentage-only changes are not modelled; "
    "tree contents were relayed through a page-summarising tool, so transcription errors are possible. "
    "Builds can be checked against this data but can never be marked verified."
)

classes_out = []
for c, trees in cat.items():
    used_ids: set[str] = set()
    trees_out = []
    for tree, rows in trees.items():
        by_tier: dict[int, int] = {}
        talents = []
        for r in rows:
            assert r["gate"] % 5 == 0, (c, tree, r)
            tid = slug(r["name"])
            if tid in used_ids:
                tid = f"{tree.replace('_', '-')}-{tid}"
            assert tid not in used_ids, (c, tid)
            used_ids.add(tid)
            r["id"] = tid
            tier = r["gate"] // 5
            col = by_tier.get(tier, 0)
            by_tier[tier] = col + 1
            r["tier"], r["column"] = tier, col
        for r in sorted(rows, key=lambda x: (x["tier"], x["column"])):
            talents.append(r)
        trees_out.append((tree, talents))
    classes_out.append((c, trees_out))

# resolve prerequisite names -> ids
ids_by_class = {c: {r["name"]: r["id"] for _, ts in trees_out for r in ts} for c, trees_out in classes_out}
catalog_dict = {
    "game": "World of Warcraft: Forever",
    "client_version": "UNVERIFIED-DRAFT (beta 1.60.1 + dev notes of 2026-11-02)",
    "source": "GuildOrder WoW Forever talent pages (reviewed Oct 2026) reconciled with Blizzard beta development notes updated Nov 2, 2026",
    "retrieved_at": "2026-11-03",
    "data_status": "draft",
    "notes": NOTES,
    "points_per_tier": 5,
    "classes": [
        {
            "id": c,
            "trees": [
                {
                    "id": tree,
                    "name": TREE_NAMES[tree],
                    "talents": [
                        {
                            "id": r["id"], "name": r["name"], "tier": r["tier"], "column": r["column"], "max_rank": r["rank"],
                            "requires": [{"talent_id": ids_by_class[c][n], "rank": k} for n, k in r["requires"]],
                            "description": r["note"],
                        }
                        for r in talents
                    ],
                }
                for tree, talents in trees_out
            ],
        }
        for c, trees_out in classes_out
    ],
}
TalentCatalog.model_validate(catalog_dict)   # schema check
OUT_JSON.write_text(json.dumps(catalog_dict, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def counts(c):
    return {t: len(rs) for t, rs in cat[c].items()}


lines = [
    "# Reconciliation ledger: Forever talent trees, draft of 2026-11-03",
    "",
    "Generated by `catalog/build_forever_draft.py`. **Draft data, not read from the game client.**",
    "",
    "For every structural talent claim in Blizzard's *Updated November 2* beta development notes the script checked "
    "whether the base source (GuildOrder, 'reviewed October 2026') already showed the post-change state. "
    "Where it did not, the change was applied by hand and re-checked.",
    "",
    "| Class | Notes checked | Already in source | Applied by us | Tree sizes (talents) |",
    "|---|---:|---:|---:|---|",
]
for c in cat:
    idx = [i for i, e in enumerate(EXPECT) if e[0] == c]
    idxa = [i for i, a in enumerate(ABSENT) if a[0] == c]
    n = len(idx) + len(idxa)
    already = sum(before_e[i] for i in idx) + sum(before_a[i] for i in idxa)
    sizes = " / ".join(f"{TREE_NAMES[t]} {k}" for t, k in counts(c).items())
    lines.append(f"| {c.title()} | {n} | {already} | {n - already} | {sizes} |")
total_checked = len(EXPECT) + len(ABSENT)
total_already = sum(before_e) + sum(before_a)
lines += [
    f"| **All** | **{total_checked}** | **{total_already}** | **{total_checked - total_already}** | {sum(len(rs) for t in cat.values() for rs in t.values())} talents |",
    "",
    "After the changes, all checked claims hold.",
    "",
    "## Changes applied by hand (source had not absorbed them)",
    "",
    *[f"- {a}" for a in APPLIED],
    "",
    "## Prerequisites recorded (only those stated in the notes)",
    "",
    *[f"- {c.title()}: {t} requires {r} ({why})" for c, t, r, _, why in PREREQS],
    "",
    "## Known gaps and judgement calls",
    "",
    "- The source lists **no** talent-to-talent prerequisites. Many exist in the real trees (the notes mention several). "
    "Until a client export is imported, the validator only enforces the row gates and the prerequisites above.",
    "- `column` is the order the source lists talents within a row; it is not the real grid column.",
    "- Shaman **Call of Thunder** replaces Lava Burst; the notes give no row or points, so the same slot (row 5) and 1 point are assumed.",
    "- Warrior **Gore Drinker** is 'connected to Blood Craze'; the rank needed is not stated, so Blood Craze at max rank is assumed.",
    "- Rogue **Mutilate**: the notes say it moved from row 9; the source showed row 5. The final row 7 matches the notes.",
    "- Druid **Primal Bite** (notes: 'ranks reduced to 3') and **Lacerate** ('two new ranks') are described ambiguously. "
    "The source's 1-point entries were kept; these may be spell ranks rather than talent ranks.",
    "- Notes entries that may be spells rather than talents (Mage Ice Barrier / Frost Blast, Rogue Hemorrhage and Mutilate damage, "
    "Shaman Stormstrike / Riptide / Totemic Projection) were not used to change trees.",
    "- Value-only changes (percentages, durations, costs) are not modelled. Trees were summarised by a web-fetch tool, so "
    "single-entry transcription mistakes are possible; counts match SeeMeta for Warrior (52) and Warlock (17 / 19) before the notes.",
    "- A newer developer post than the notes used here may exist; none was visible when this was built.",
    "",
]
OUT_LEDGER.write_text("\n".join(lines), encoding="utf-8")
print(f"wrote {OUT_JSON.name}: {sum(len(rs) for t in cat.values() for rs in t.values())} talents, "
      f"{total_checked} checks ({total_already} already in source, {total_checked - total_already} applied)")
