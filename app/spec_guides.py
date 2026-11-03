"""Role and gear guidance for every specialization, written for this project.

This is general guidance about how these roles and gear types work in Classic-style World of Warcraft. It was not read
from World of Warcraft: Forever's item list, which may differ, so the interface labels it as general guidance. Each entry has:

  dungeon_role / raid_role  what the player is usually asked to do in five-player dungeons and in raids
  gear                      what to look for on items
  competes_with             which specializations tend to want the same items, and so compete for the same drops

Edit them in the administrative interface (Profiles) or here; they are plain data.
"""
from __future__ import annotations

GUIDES: dict[tuple[str, str], dict] = {
    # ---------------------------------------------------------------- Druid
    ("druid", "balance"): dict(
        dungeon_role="Ranged spell damage. You can also slow or put extra enemies to sleep, give the healer mana back with Innervate, and bring a fallen ally back in the middle of a fight.",
        raid_role="Ranged spell damage with group utility (mana for healers, a combat resurrection). Guilds usually bring a few for that utility rather than as their top damage dealers.",
        gear=[
            "Spell damage and Intellect above everything else; spell critical strike chance next.",
            "Spell hit, so your spells are not resisted by tougher enemies.",
            "Mana regeneration, because long fights drain you.",
            "Staves and held-in-off-hand items that carry spell damage; you cannot use wands.",
        ],
        competes_with=[
            "Mages, Warlocks and Shadow Priests for spell damage and spell hit gear.",
            "Elemental Shamans for Nature-damage items.",
            "Restoration Druids for Intellect and mana gear.",
        ],
    ),
    ("druid", "feral_combat"): dict(
        dungeon_role="Tank (in bear form) or melee damage (in cat form), depending on how you spend your points and which form you fight in.",
        raid_role="Off-tank in bear form, or melee damage in cat form. Cat form is strong but wants a lot of good gear to keep up with other melee.",
        gear=[
            "Leather armor with Agility and Strength; Stamina and armor for bear form.",
            "Weapons that add bonus attack power for feral forms, usually two-handed staves, maces or polearms, since your own weapon's damage is not used in forms.",
            "Critical strike and hit for cat form; mitigation and Stamina for bear form.",
            "Items that help in both forms are scarce, so expect to keep a second set.",
        ],
        competes_with=[
            "Rogues for Agility leather.",
            "Protection Warriors and Paladins for Stamina and armor items when you tank.",
            "Enhancement Shamans and Hunters for Agility items with attack power.",
        ],
    ),
    ("druid", "restoration"): dict(
        dungeon_role="Healer who keeps people up with healing over time, so you are strong when the damage is steady. You can also revive a fallen ally in combat and give the group's casters mana.",
        raid_role="Raid healer, best at spreading healing over time across many targets and as a back-up on tanks. You also bring a combat resurrection.",
        gear=[
            "Bonus healing, then Intellect.",
            "Mana regeneration, so you can keep healing through long fights.",
            "Spirit, which also improves your mana regeneration.",
            "Leather or cloth pieces with healing stats; armor matters little.",
        ],
        competes_with=[
            "Holy Paladins, Holy and Discipline Priests, and Restoration Shamans for healing gear.",
            "Balance Druids for Intellect and mana gear.",
        ],
    ),
    # ---------------------------------------------------------------- Hunter
    ("hunter", "beast_mastery"): dict(
        dungeon_role="Ranged damage with a pet that can pick up and hold stray enemies. Traps can keep one enemy out of the fight.",
        raid_role="Steady ranged damage. Your pet adds damage and threat, so you must watch that it does not pull attention off the tank.",
        gear=[
            "A strong ranged weapon (bow, gun or crossbow) is the most important item you own.",
            "Agility, attack power and critical strike.",
            "Stamina and Intellect, which also help your pet and your mana.",
            "Plenty of good ammunition, and a quiver or ammo pouch.",
        ],
        competes_with=[
            "Marksmanship and Survival Hunters for ranged weapons.",
            "Rogues, Feral Druids and Enhancement Shamans for Agility armor and jewelry.",
            "Warriors for bows, guns and crossbows.",
        ],
    ),
    ("hunter", "marksmanship"): dict(
        dungeon_role="Ranged damage from strong single-target shots. You can also put one enemy under a trap.",
        raid_role="Ranged damage that can also strengthen melee players' attacks with an aura, if your talents include it.",
        gear=[
            "A high-damage ranged weapon, since most of your shots scale from it.",
            "Agility, attack power and critical strike.",
            "Hit, so your shots land on tougher enemies.",
            "Plenty of good ammunition.",
        ],
        competes_with=[
            "Beast Mastery and Survival Hunters for ranged weapons.",
            "Rogues, Feral Druids and Enhancement Shamans for Agility armor.",
            "Warriors for ranged weapons.",
        ],
    ),
    ("hunter", "survival"): dict(
        dungeon_role="Damage with a lot of control: traps, slows and escapes keep fights manageable, and you are hard to kill.",
        raid_role="Utility-minded damage dealer. Traps and survivability help on harder encounters, though the damage is usually not the group's highest.",
        gear=[
            "Agility, which raises your damage and your chance to dodge.",
            "Stamina, since you aim to be tougher than other hunters.",
            "A solid ranged weapon, plus a melee weapon with good stats, because you fight in close as well.",
            "Attack power and critical strike once those are covered.",
        ],
        competes_with=[
            "Beast Mastery and Marksmanship Hunters for ranged weapons.",
            "Rogues, Feral Druids and Enhancement Shamans for Agility gear.",
        ],
    ),
    # ---------------------------------------------------------------- Mage
    ("mage", "arcane"): dict(
        dungeon_role="Ranged spell damage, plus excellent crowd control: you can turn an enemy into a harmless animal for the whole fight. You also conjure food and water for the group.",
        raid_role="Ranged spell damage in bursts, and buffs that raise the whole group's Intellect.",
        gear=[
            "Spell damage and Intellect.",
            "Spell critical strike chance, then spell hit.",
            "Mana regeneration for fights that run long.",
            "Cloth only; wands, staves and off-hand items with spell stats.",
        ],
        competes_with=[
            "Fire and Frost Mages (they want the same cloth and spell damage items).",
            "Warlocks and Shadow Priests for spell hit and general spell damage.",
            "Balance Druids and Elemental Shamans for spell damage items.",
        ],
    ),
    ("mage", "fire"): dict(
        dungeon_role="Burst ranged spell damage, and you can still control an enemy. Fire-immune enemies are a problem for you.",
        raid_role="Ranged spell damage, and your repeated fire hits can make enemies take more fire damage, which helps other fire casters.",
        gear=[
            "Fire spell damage, or general spell damage, with Intellect.",
            "Spell critical strike chance matters a great deal for you.",
            "Spell hit, so your spells land on higher-level enemies.",
            "Cloth items with spell stats, plus wands, staves and off-hand items.",
        ],
        competes_with=[
            "Arcane and Frost Mages for cloth and spell damage items.",
            "Destruction Warlocks for fire damage items.",
            "Warlocks, Shadow Priests and Elemental Shamans for spell hit and spell damage.",
        ],
    ),
    ("mage", "frost"): dict(
        dungeon_role="Control and area damage: slowing and freezing enemies keeps a group safe, and you can burn down large packs.",
        raid_role="Ranged spell damage that is often less than a fire or arcane mage's, with utility for slowing enemies and buffing the group.",
        gear=[
            "Frost spell damage, or general spell damage, with Intellect.",
            "Spell hit, since resists hurt you most against bosses.",
            "Mana regeneration and a bigger mana pool for sustained area damage.",
            "Cloth with spell stats, plus wands, staves and off-hand items.",
        ],
        competes_with=[
            "Arcane and Fire Mages for cloth and spell damage items.",
            "Warlocks and Shadow Priests for spell hit gear.",
            "Balance Druids and Elemental Shamans for spell damage items.",
        ],
    ),
    # ---------------------------------------------------------------- Paladin
    ("paladin", "holy"): dict(
        dungeon_role="Healer with large direct heals, strong when someone needs rescuing quickly. You also bring blessings and auras for the whole group.",
        raid_role="Raid healer, usually assigned to the tanks; your blessings and auras are valued by the whole group.",
        gear=[
            "Bonus healing and Intellect.",
            "Mana regeneration, since your big heals are expensive.",
            "Critical strike for healing spells.",
            "Plate is possible later, but healing stats on any armor type beat armor value.",
        ],
        competes_with=[
            "Holy and Discipline Priests, Restoration Druids and Restoration Shamans for healing gear.",
            "Protection and Retribution Paladins for Intellect-heavy plate pieces.",
        ],
    ),
    ("paladin", "protection"): dict(
        dungeon_role="Tank who is especially good against many enemies at once, since your area attacks keep them all on you.",
        raid_role="Off-tank, or the tank for groups of weaker enemies, plus blessings and auras for the raid. A Warrior is usually the main tank.",
        gear=[
            "A shield, Stamina and armor.",
            "Defense, dodge, parry and block, to avoid hits you cannot soak.",
            "Spell damage and holy damage, which raise the threat you generate.",
            "Plate armor once you can wear it; a one-handed weapon with good stats.",
        ],
        competes_with=[
            "Protection Warriors for shields and Stamina plate.",
            "Feral (bear) Druids for Stamina and armor items.",
            "Retribution and Holy Paladins for plate with Strength or Intellect.",
        ],
    ),
    ("paladin", "retribution"): dict(
        dungeon_role="Melee damage with useful extras: blessings and auras strengthen the group, and you can heal in a pinch.",
        raid_role="Melee damage that is mostly valued for the blessings and auras you bring; guilds usually bring only a few.",
        gear=[
            "A slow, hard-hitting two-handed weapon, since your strikes scale from it.",
            "Strength, critical strike and hit.",
            "Plate armor with Strength.",
            "Stamina and Intellect in moderation, so you do not run out of mana.",
        ],
        competes_with=[
            "Arms and Fury Warriors for two-handed weapons and Strength plate.",
            "Enhancement Shamans for slow two-handed weapons.",
            "Protection and Holy Paladins for plate.",
        ],
    ),
    # ---------------------------------------------------------------- Priest
    ("priest", "discipline"): dict(
        dungeon_role="Healer and protector: shields and strong buffs let the group take more damage, and you can control an enemy briefly.",
        raid_role="Raid healer and buffer, with buffs that raise Stamina and Spirit for the whole raid.",
        gear=[
            "Bonus healing and Intellect.",
            "Spirit, which raises your mana regeneration.",
            "Mana regeneration while casting.",
            "Cloth only; wands for finishing enemies cheaply.",
        ],
        competes_with=[
            "Holy Priests, whose healing gear is the same.",
            "Holy Paladins, Restoration Druids and Restoration Shamans for healing items.",
            "Shadow Priests, Mages and Warlocks for Intellect cloth.",
        ],
    ),
    ("priest", "holy"): dict(
        dungeon_role="Healer who can respond to almost any damage, with heals for single targets and for groups.",
        raid_role="Raid healer, strong on both tanks and the rest of the raid; guilds value having several.",
        gear=[
            "Bonus healing, then Intellect.",
            "Spirit and mana regeneration.",
            "Critical strike for healing spells.",
            "Cloth only; wands for finishing enemies cheaply.",
        ],
        competes_with=[
            "Discipline Priests, whose healing gear is the same.",
            "Holy Paladins, Restoration Druids and Restoration Shamans for healing items.",
            "Casters for Intellect cloth.",
        ],
    ),
    ("priest", "shadow"): dict(
        dungeon_role="Ranged shadow damage; if your talents include Vampiric Embrace, your attacks also heal you and your group. You can still heal in an emergency.",
        raid_role="Ranged damage whose attacks make enemies take more shadow damage, which Warlocks and other shadow casters benefit from, plus healing for the group through Vampiric Embrace.",
        gear=[
            "Shadow spell damage, then Intellect and Stamina.",
            "Spell hit, so your damage-over-time spells are not resisted.",
            "Spirit, which also helps your mana.",
            "Cloth only; wands, staves and off-hand items with shadow damage.",
        ],
        competes_with=[
            "Warlocks for shadow damage items.",
            "Mages and Balance Druids for spell hit and spell damage gear.",
            "Holy and Discipline Priests for Spirit and Intellect cloth.",
        ],
    ),
    # ---------------------------------------------------------------- Rogue
    ("rogue", "assassination"): dict(
        dungeon_role="Melee damage with excellent control: you can put one enemy to sleep before the fight and interrupt a dangerous cast.",
        raid_role="Single-target melee damage, with poisons and finishing strikes that scale with preparation. You also interrupt casters.",
        gear=[
            "Daggers in both hands; their speed and damage suit your attacks.",
            "Agility, attack power and critical strike.",
            "Hit, so your attacks do not miss on higher-level enemies.",
            "Leather armor with Agility and Stamina.",
        ],
        competes_with=[
            "Combat and Subtlety Rogues for daggers and leather.",
            "Fury Warriors for one-handed weapons.",
            "Hunters, Feral Druids and Enhancement Shamans for Agility gear.",
        ],
    ),
    ("rogue", "combat"): dict(
        dungeon_role="Steady melee damage in close fights, with an interrupt and the ability to put one enemy to sleep.",
        raid_role="Reliable melee damage against a single enemy, usually at or near the top of the melee damage charts when well geared.",
        gear=[
            "Fast one-handed swords, maces or fist weapons; speed and good hits suit you.",
            "Agility, Strength and attack power.",
            "Hit, which matters more for you than for any other rogue.",
            "Leather armor with Agility and Stamina.",
        ],
        competes_with=[
            "Fury Warriors for one-handed weapons.",
            "Assassination and Subtlety Rogues for leather and weapons.",
            "Enhancement Shamans, Feral Druids and Hunters for Agility gear.",
        ],
    ),
    ("rogue", "subtlety"): dict(
        dungeon_role="Scout and controller: you can slip ahead unseen, open fights with burst damage and keep one enemy out of the fight.",
        raid_role="A specialist more than a top damage dealer: stealthy openers and utility suit particular encounters and player-versus-player.",
        gear=[
            "Daggers for your opening and burst attacks.",
            "Agility, attack power and critical strike.",
            "Stamina, since you rely on surviving the first few seconds.",
            "Leather armor with Agility.",
        ],
        competes_with=[
            "Assassination and Combat Rogues for daggers and leather.",
            "Fury Warriors for one-handed weapons.",
            "Hunters, Feral Druids and Enhancement Shamans for Agility gear.",
        ],
    ),
    # ---------------------------------------------------------------- Shaman
    ("shaman", "elemental_combat"): dict(
        dungeon_role="Ranged nature and fire damage, with totems that help the group, and the ability to purge or shock a dangerous enemy.",
        raid_role="Ranged spell damage with totems that strengthen the whole group; often less damage than a mage or warlock, valued for the totems.",
        gear=[
            "Spell damage (especially Nature and Fire) with Intellect.",
            "Spell critical strike chance, then spell hit.",
            "Mana regeneration, since your spells and totems both cost mana.",
            "Mail armor once you can wear it, with spell stats; shields and one-handed weapons with spell stats.",
        ],
        competes_with=[
            "Mages, Warlocks and Balance Druids for spell damage and spell hit items.",
            "Restoration Shamans for Intellect and mana gear.",
        ],
    ),
    ("shaman", "enhancement"): dict(
        dungeon_role="Melee damage who can also heal or buff the group with totems, and use shocks to interrupt casters.",
        raid_role="Melee damage whose totems and weapon enchants give the melee players around you extra attacks and Strength.",
        gear=[
            "A slow two-handed weapon or a pair of one-handed weapons, depending on how your talents work.",
            "Strength or Agility, attack power and critical strike.",
            "Hit, so your attacks land.",
            "Mail armor with attack power and Stamina once you can wear it.",
        ],
        competes_with=[
            "Arms and Fury Warriors and Retribution Paladins for Strength weapons and plate or mail.",
            "Rogues, Hunters and Feral Druids for Agility gear.",
        ],
    ),
    ("shaman", "restoration"): dict(
        dungeon_role="Healer who heals several allies at once with a chain heal and brings totems that protect and restore mana.",
        raid_role="Raid healer, especially good for healing groups of players together, plus totems that help the whole party.",
        gear=[
            "Bonus healing and Intellect.",
            "Mana regeneration, since chain heals are expensive.",
            "Critical strike for healing spells.",
            "Mail armor, then shields with healing stats.",
        ],
        competes_with=[
            "Holy Paladins, Holy and Discipline Priests, and Restoration Druids for healing gear.",
            "Elemental Shamans for Intellect and mana items.",
        ],
    ),
    # ---------------------------------------------------------------- Warlock
    ("warlock", "affliction"): dict(
        dungeon_role="Ranged damage over time, with curses and fear to control enemies and a stone that lets an ally return to life.",
        raid_role="Ranged damage from many damage-over-time spells at once, plus curses that weaken the enemy for the whole raid.",
        gear=[
            "Shadow spell damage, Stamina and Intellect.",
            "Spell hit, so your damage-over-time spells are not resisted.",
            "Spell critical strike chance, which helps when you stack many effects.",
            "Cloth only; wands, staves and off-hand items with spell stats.",
        ],
        competes_with=[
            "Shadow Priests for shadow damage items.",
            "Mages and Balance Druids for spell hit and spell damage gear.",
            "Demonology and Destruction Warlocks for cloth.",
        ],
    ),
    ("warlock", "demonology"): dict(
        dungeon_role="A pet-driven caster: your demon can tank or control an enemy for you, and you bring a health-sharing bond, summoning and healing stones.",
        raid_role="A utility caster: healthstones, summoning and a sturdy pet help the whole raid, though your damage is usually below a pure caster's.",
        gear=[
            "Stamina, which also improves your demon and your own survival.",
            "Spell damage and Intellect.",
            "Spell hit and critical strike chance.",
            "Cloth only; wands, staves and off-hand items with spell stats.",
        ],
        competes_with=[
            "Affliction and Destruction Warlocks for cloth and spell damage items.",
            "Mages and Shadow Priests for spell hit gear.",
        ],
    ),
    ("warlock", "destruction"): dict(
        dungeon_role="Burst ranged damage from fire and shadow spells; you pull the most when the group moves fast.",
        raid_role="High burst ranged damage, usually among the top caster damage dealers when well geared.",
        gear=[
            "Spell damage, especially Fire and Shadow, with Intellect.",
            "Spell critical strike chance, which your talents multiply.",
            "Spell hit, so your burst is not resisted.",
            "Cloth only; wands, staves and off-hand items with spell stats.",
        ],
        competes_with=[
            "Fire Mages for fire damage items.",
            "Shadow Priests and Affliction Warlocks for shadow damage items.",
            "Mages and Balance Druids for spell hit gear.",
        ],
    ),
    # ---------------------------------------------------------------- Warrior
    ("warrior", "arms"): dict(
        dungeon_role="Melee damage with a strong opening: big two-handed hits, and an interrupt and slow for a fleeing enemy.",
        raid_role="Melee damage and enemy-weakening debuffs. A good Arms Warrior can also stand in as an off-tank for short periods.",
        gear=[
            "A slow, hard-hitting two-handed weapon is the most important item.",
            "Strength, critical strike and hit.",
            "Plate armor with Strength and Stamina.",
            "Stamina for survival, since you take hits in melee.",
        ],
        competes_with=[
            "Fury Warriors for plate and Strength gear.",
            "Retribution Paladins and Enhancement Shamans for two-handed weapons.",
            "Protection Warriors and Paladins for plate with Stamina.",
        ],
    ),
    ("warrior", "fury"): dict(
        dungeon_role="Melee damage who fights with two weapons: fast and persistent, and good at keeping pressure on an enemy.",
        raid_role="Top-end melee damage when well geared and supported by group buffs.",
        gear=[
            "Two fast one-handed weapons, ideally with good damage and stats.",
            "Strength, critical strike and hit; hit is especially important with two weapons.",
            "Plate armor with Strength and Stamina.",
            "Attack power from any slot once the basics are covered.",
        ],
        competes_with=[
            "Combat Rogues for one-handed weapons.",
            "Arms Warriors, Retribution Paladins and Enhancement Shamans for Strength plate.",
            "Protection Warriors and Paladins for plate with Stamina.",
        ],
    ),
    ("warrior", "protection"): dict(
        dungeon_role="The tank: you hold the enemies' attention with taunts and a shield, and the rest of the group rely on you not to fall.",
        raid_role="Main tank, who holds the strongest enemy while the raid fights it; healers watch your health more closely than anyone's.",
        gear=[
            "A shield with good armor and block value, and a one-handed weapon with good stats.",
            "Stamina and armor to survive hits.",
            "Defense, dodge, parry and block to avoid them.",
            "Strength and hit, which keep your threat high enough to keep enemies on you.",
        ],
        competes_with=[
            "Protection Paladins for shields and Stamina plate.",
            "Feral (bear) Druids for Stamina and armor items.",
            "Arms and Fury Warriors for plate and weapons.",
        ],
    ),
}

#: Shown wherever a guide is shown: the guidance is not read from Forever's item list.
GUIDE_NOTE = (
    "General guidance for how these roles and gear types work in Classic-style World of Warcraft. "
    "World of Warcraft: Forever may differ, so check the in-game item and talent tooltips."
)
