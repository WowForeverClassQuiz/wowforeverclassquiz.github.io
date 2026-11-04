"""Tiebreaker questions (q75 and up): forced choices between the finalists, asked only in confidence mode.

By the time the Oracle has narrowed a reading to two or three candidates, the useful question is the one that forces a decision
among exactly those candidates: "As a protector, do you trust more in the light to guard, the steel of the forge or the strength of
the wild?" is only worth asking when the finalists are Protection Paladin, Protection Warrior and Feral Combat Druid. So every
question here lists its ``finalists`` and is eligible only when those specializations together hold most of the probability (the
``tiebreak_mass`` setting, 80% by default). Two of three finalists are enough: the third answer then does no harm.

  q75 to q83  the three specializations of each class, one question per class
  q84 to q91  eight groups of three specializations that share a role (tanks, two groups of healers, two of melee damage,
              three of casters)
  q92 to q103 two-answer questions for the twelve closest pairs of finalists that no three-way question covers

Each answer names one finalist: it gives that specialization a direct weight of 2 and its class the primary 2 points, a different
class the secondary 1 point, and its profile's two main traits 2 and 1, the same conventions as the rest of the seed. The associations
are playstyle lore and a best guess, like all of them.
"""
from __future__ import annotations

from .models import Answer, Question

#: Each question is (id, text, [(answer text, "class/spec" of the finalist it names, secondary class), ...]).
TIEBREAKERS = [
    # ---- one question for each class ------------------------------------------------------------------------------------------
    ("q75", "As a child of the wild, which call do you answer?", [
        ("The moon and the stars: patient, watchful and sure of the old patterns.", "druid/balance", "mage"),
        ("Tooth and claw: the chase, the strength to take a blow and a wild temper.", "druid/feral_combat", "hunter"),
        ("Root and rain: the slow work of mending what has been hurt.", "druid/restoration", "shaman"),
    ]),
    ("q76", "As a hunter, what do you trust most when the hunt is on?", [
        ("The bond with the companion at your side.", "hunter/beast_mastery", "druid"),
        ("One perfect shot, taken from far away.", "hunter/marksmanship", "rogue"),
        ("Snares, tools and a plan for every kind of trouble.", "hunter/survival", "warrior"),
    ]),
    ("q77", "As a student of magic, what do you want your power to do?", [
        ("Build into something vast, drawing on every hour of study.", "mage/arcane", "warlock"),
        ("Burn bright and fast, and finish the fight before it begins.", "mage/fire", "warrior"),
        ("Chill and slow everything around you until you rule the moment.", "mage/frost", "priest"),
    ]),
    ("q78", "As a follower of the light, do you prefer to seek retribution, stand in judgement, or spread forgiveness?", [
        ("Seek retribution, and bring the guilty to account.", "paladin/retribution", "warrior"),
        ("Stand in judgement over who may pass, and shield everyone behind you.", "paladin/protection", "druid"),
        ("Spread forgiveness, and lift up those who have fallen.", "paladin/holy", "priest"),
    ]),
    ("q79", "As a servant of the faith, how do you meet suffering?", [
        ("Shield the faithful before the blow lands.", "priest/discipline", "paladin"),
        ("Mend them gently when they are hurt.", "priest/holy", "druid"),
        ("Turn the darkness against itself, and teach them to fear less.", "priest/shadow", "warlock"),
    ]),
    ("q80", "As a master of the shadows, how do you end a quarrel?", [
        ("One precise strike, planned for days.", "rogue/assassination", "mage"),
        ("A fast, open fight, won on nerve.", "rogue/combat", "warrior"),
        ("Vanish, and leave them chasing nothing.", "rogue/subtlety", "hunter"),
    ]),
    ("q81", "As a speaker to the spirits, what do you ask of them?", [
        ("A storm to throw at your enemies.", "shaman/elemental_combat", "mage"),
        ("The storm's strength in your own weapon and arm.", "shaman/enhancement", "warrior"),
        ("Healing waters for your friends.", "shaman/restoration", "druid"),
    ]),
    ("q82", "As one who bargains with dark powers, what do you ask for?", [
        ("A curse that wears an enemy down, slowly and surely.", "warlock/affliction", "priest"),
        ("A servant bound to your will, and stronger than you.", "warlock/demonology", "hunter"),
        ("Ruin, all at once, with nothing held back.", "warlock/destruction", "mage"),
    ]),
    ("q83", "As a soldier, what do you trust to carry you through?", [
        ("A perfect blow, learned through years of drill.", "warrior/arms", "rogue"),
        ("Two blades and a rage that cannot be stopped.", "warrior/fury", "shaman"),
        ("A shield that never breaks.", "warrior/protection", "paladin"),
    ]),
    # ---- groups that share a role -----------------------------------------------------------------------------------------------
    ("q84", "As a protector, do you trust more in the light to guard, the structure and workmanship of steel, or the strength of the wild?", [
        ("The light, which guards everyone it touches.", "paladin/protection", "priest"),
        ("Steel, shaped and built to hold the line.", "warrior/protection", "rogue"),
        ("The wild, with a strength no forge can make.", "druid/feral_combat", "hunter"),
    ]),
    ("q85", "As a healer of the faithful, how do you keep them standing?", [
        ("Shield them before the blow falls.", "priest/discipline", "mage"),
        ("Mend them after it, with patience and care.", "priest/holy", "druid"),
        ("Stand beside them in the fight and heal as you go.", "paladin/holy", "warrior"),
    ]),
    ("q86", "As a healer of the living, what do you trust to mend the hurt?", [
        ("The growing earth, slow and certain.", "druid/restoration", "hunter"),
        ("The rushing water, which carries the hurt away.", "shaman/restoration", "warrior"),
        ("Quiet faith, and a hand held out.", "priest/holy", "paladin"),
    ]),
    ("q87", "As a champion on the front line, how do you strike?", [
        ("In the name of justice, for those who cannot fight.", "paladin/retribution", "priest"),
        ("With the precision of long training.", "warrior/arms", "rogue"),
        ("With a fury that nothing stops.", "warrior/fury", "shaman"),
    ]),
    ("q88", "As a fighter who answers to instinct, what do you fight with?", [
        ("The shape of a beast.", "druid/feral_combat", "hunter"),
        ("A storm carried in your weapons.", "shaman/enhancement", "warrior"),
        ("Quick blades and quicker wit.", "rogue/combat", "mage"),
    ]),
    ("q89", "As a caster who ends fights fast, what do you throw?", [
        ("Fire, bright and hungry.", "mage/fire", "warrior"),
        ("Ruin, and the shadows that come with it.", "warlock/destruction", "rogue"),
        ("Lightning, called down from the open sky.", "shaman/elemental_combat", "druid"),
    ]),
    ("q90", "As a caster who plays the long game, what do you trust?", [
        ("Cold control, and all the time in the world.", "mage/frost", "paladin"),
        ("A curse that lingers long after you have left.", "warlock/affliction", "rogue"),
        ("The darkness within, and what it will teach you.", "priest/shadow", "shaman"),
    ]),
    ("q91", "As a caster of patient study, where does your power come from?", [
        ("The arcane itself, studied until it obeys.", "mage/arcane", "shaman"),
        ("The pattern of the moon and the stars.", "druid/balance", "priest"),
        ("Bound servants that answer only to you.", "warlock/demonology", "hunter"),
    ]),
    # ---- the closest pairs no three-way question covers: two finalists, two answers -----------------------------------------------
    ("q92", "As a defender of the weak, do you strike down the threat, or hold the line until the danger breaks on you?", [
        ("Strike down whoever threatens them.", "paladin/retribution", "warrior"),
        ("Hold the line until the danger breaks on you.", "warrior/protection", "paladin"),
    ]),
    ("q93", "In the thick of a brawl, what carries you: the spirits' strength in your weapon, or a rage that needs no help?", [
        ("The spirits' strength in my weapon.", "shaman/enhancement", "druid"),
        ("A rage that needs no help.", "warrior/fury", "rogue"),
    ]),
    ("q94", "How do you master the dark: by looking into it, or by binding a servant to it?", [
        ("Look into it, and learn what you fear.", "priest/shadow", "paladin"),
        ("Bind a servant to it, and make it serve.", "warlock/demonology", "hunter"),
    ]),
    ("q95", "When trouble finds you, do you reach for a trap you set earlier, or draw steel and improvise?", [
        ("A trap set earlier, and a plan behind it.", "hunter/survival", "shaman"),
        ("Steel in hand, and make it up as I go.", "rogue/combat", "warrior"),
    ]),
    ("q96", "Do you hunt as the beast, or beside it?", [
        ("As the beast: claws, speed and the wild in my blood.", "druid/feral_combat", "shaman"),
        ("Beside it: a companion I trained and trust.", "hunter/beast_mastery", "druid"),
    ]),
    ("q97", "How do you win a fight: with a burst of flame, or a flurry of blows?", [
        ("A burst of flame, and it is over.", "mage/fire", "warlock"),
        ("A flurry of blows, and I keep it coming.", "warrior/fury", "rogue"),
    ]),
    ("q98", "With a blade in each hand, what do you rely on: speed and wit, or rage and strength?", [
        ("Speed and wit.", "rogue/combat", "hunter"),
        ("Rage and strength.", "warrior/fury", "shaman"),
    ]),
    ("q99", "Where do you learn the wild: from the sky above you, or from a companion's eyes?", [
        ("From the sky: the moon, the stars and the old patterns.", "druid/balance", "mage"),
        ("From a companion's eyes, which show me what I would miss.", "hunter/beast_mastery", "shaman"),
    ]),
    ("q100", "How do you win by patience: by understanding everything first, or by letting a curse do the work?", [
        ("Understand everything, then act.", "mage/arcane", "priest"),
        ("Let a curse do the slow work.", "warlock/affliction", "rogue"),
    ]),
    ("q101", "How do you protect those who depend on you: by mending them, or by standing in front of them?", [
        ("Mend them, and keep them on their feet.", "paladin/holy", "priest"),
        ("Stand in front of them.", "warrior/protection", "hunter"),
    ]),
    ("q102", "When the fight comes, do you stand your ground, or choose the moment to strike?", [
        ("Stand my ground, and make them come to me.", "paladin/protection", "priest"),
        ("Choose my moment, and strike with precision.", "warrior/arms", "rogue"),
    ]),
    ("q103", "How do you end an enemy: with one clean strike, or with a slow curse?", [
        ("One clean strike, planned in advance.", "rogue/assassination", "mage"),
        ("A curse that works while I wait.", "warlock/affliction", "priest"),
    ]),
]


def _traits(profile_by_key: dict[str, tuple[str, ...]], key: str) -> dict[str, float]:
    first, second = profile_by_key[key][:2]
    return {first: 2.0, second: 1.0}


def build_tiebreaker_questions() -> list[Question]:
    """The tiebreaker questions, in order. Each is asked only in confidence mode, and only when its finalists hold most of the probability."""
    from .seed import CLASSES                                           # imported here: seed builds on this module

    profile_by_key = {f"{cid}/{sid}": profile for cid, _, _, specs in CLASSES for sid, _, _, _, profile in specs}
    out = []
    for qid, text, answers in TIEBREAKERS:
        built, finalists = [], []
        for i, (answer_text, key, secondary) in enumerate(answers):
            primary = key.split("/")[0]
            built.append(Answer(
                id=chr(ord("a") + i), text=answer_text,
                class_weights={primary: 2.0, secondary: 1.0}, trait_weights=_traits(profile_by_key, key), spec_weights={key: 2.0},
            ))
            finalists.append(key)
        names = " and ".join(finalists) if len(finalists) == 2 else ", ".join(finalists)
        out.append(Question(
            id=qid, text=text, type="choice", answers=built, min_length="adaptive", finalists=finalists,
            rationale=(f"Tiebreaker for {names}. Each answer names one of them (direct weight 2, its class 2 points, a different class 1, its profile's two main traits). "
                       "Asked only when those specializations hold most of the probability" + ("; two of the three are enough." if len(finalists) == 3 else ".")),
        ))
    return out
