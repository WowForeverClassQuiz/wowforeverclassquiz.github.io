"""Questions q31 to q50: asked only in confidence mode (the "adaptive" tier), never in the short, medium or long quiz.

The first thirty questions separate classes well and separate the specializations of one class poorly: measured over all 351 pairs
of the 27 types, the weakest pairs are all within a class (Arcane against Frost Mage has almost no evidence behind it). These
twenty questions exist to fix that, so that once the Oracle leans toward a class it can verify the specialization:

  q31 to q48  two questions for each class, in class order. One is a three-answer choice with an answer per specialization; the
              other is a ranking or a six-point split of four items, three for the specializations and one unrelated to the
              class. Every answer gives the class its 2 primary points, so after baseline subtraction the question carries almost
              no class evidence and measures the choice among the class's specializations.
  q49         a role question across all classes (tank, healer, melee damage, ranged damage).
  q50         a scale question on keeping distance from the enemy, which splits ranged from melee specializations.

The weights follow the same conventions as the rest of the seed (2 and 1 for the classes and for the traits of each answer, and
direct specialization weights of 1 or 2 here, within the range the original questions use). The associations are playstyle lore
and a best guess, like all of them; edit them in the Question Editor.
"""
from __future__ import annotations

from .models import Answer, Question

#: Each answer is (text, (class1, class2), (trait1, trait2), {"class/spec": direct weight}).
EXTRA_QUESTIONS: dict[str, dict] = {
    "q31": dict(type="choice", text="You are given a rare gift of magic and one season to learn it. How do you spend the season?",
        rationale="Every answer gives Mage 2 points, so this question measures the choice among the three Mage specializations: Arcane builds one large spell, Fire commits to bold bursts, Frost controls the pace.",
        answers=[
            ("Studying how its parts fit together, so you can build one spell larger than any other.", ("mage", "warlock"), ("scholar", "focus"), {"mage/arcane": 2}),
            ("Pouring everything into something bold and bright, and trusting your nerve to carry it.", ("mage", "warrior"), ("power", "instinct"), {"mage/fire": 2}),
            ("Training it to be cool and exact, so you decide when and how a fight ends.", ("mage", "priest"), ("focus", "guardian"), {"mage/frost": 2}),
        ]),
    "q32": dict(type="ranking", text="Rank these ways of winning an argument from the one you would most like to use to the one you would least like.",
        rationale="Ranking: three items stand for Arcane, Fire and Frost, and the fourth, a Rogue trick, is there as a decoy so that ranking it low favours the Mage items a little.",
        answers=[
            ("Know the subject so completely that no objection survives.", ("mage", "warlock"), ("scholar", "focus"), {"mage/arcane": 2}),
            ("Hit hard and fast while they are still deciding what to say.", ("mage", "warrior"), ("power", "instinct"), {"mage/fire": 2}),
            ("Stay calm and let them wear themselves out.", ("mage", "paladin"), ("focus", "guardian"), {"mage/frost": 2}),
            ("Find the one detail they hoped nobody would check.", ("rogue", "hunter"), ("trickster", "shadow"), {"rogue/subtlety": 1}),
        ]),
    "q33": dict(type="choice", text="A storm has torn through an old forest. What do you do?",
        rationale="Every answer gives Druid 2 points, so this question measures the choice among Balance (reads the pattern), Feral Combat (moves with the land) and Restoration (tends what is hurt).",
        answers=[
            ("Wait and watch the sky. The storm followed a pattern, and you want to read it before the next one.", ("druid", "mage"), ("scholar", "wild"), {"druid/balance": 2}),
            ("Run the ridges at dawn and learn the changed land with your whole body.", ("druid", "hunter"), ("instinct", "freedom"), {"druid/feral_combat": 2}),
            ("Go straight to the broken trees and tend each one until it grows back.", ("druid", "shaman"), ("healer", "bond"), {"druid/restoration": 2, "shaman/restoration": 1}),
        ]),
    "q34": dict(type="ranking", text="Rank these jobs from the one you would most like to the one you would least like.",
        rationale="Ranking: three jobs stand for Balance, Feral Combat and Restoration Druid. The quartermaster is a decoy that favours Warrior and Paladin traits.",
        answers=[
            ("Keeper of a night watch on a hill, reading the weather and the stars.", ("druid", "mage"), ("scholar", "wild"), {"druid/balance": 2}),
            ("Tracker who crosses long distances alone.", ("druid", "rogue"), ("instinct", "freedom"), {"druid/feral_combat": 2}),
            ("Keeper of a healing garden.", ("druid", "shaman"), ("healer", "bond"), {"druid/restoration": 2}),
            ("Quartermaster counting the stores for an army.", ("warrior", "paladin"), ("duty", "guardian"), {}),
        ]),
    "q35": dict(type="choice", text="You are crossing hostile country for three days. What do you want with you?",
        rationale="Every answer gives Hunter 2 points, so this question measures the choice among Beast Mastery (a companion), Marksmanship (one precise tool) and Survival (many tricks).",
        answers=[
            ("A trained animal that trusts only you.", ("hunter", "druid"), ("bond", "wild"), {"hunter/beast_mastery": 2}),
            ("One excellent bow and a clear view of the far side of the valley.", ("hunter", "rogue"), ("focus", "freedom"), {"hunter/marksmanship": 2}),
            ("A pack of snares, tools and tricks for whatever turns up.", ("hunter", "shaman"), ("trickster", "instinct"), {"hunter/survival": 2}),
        ]),
    "q36": dict(type="allocation", text="You have six hours of daylight before you break camp. How do you divide them?",
        rationale="Allocation: three items stand for Beast Mastery, Marksmanship and Survival Hunter; resting by the fire is an unrelated fourth.",
        answers=[
            ("Training and feeding your animal companion.", ("hunter", "druid"), ("bond", "wild"), {"hunter/beast_mastery": 2}),
            ("Practicing your aim and finding the best sight lines.", ("hunter", "rogue"), ("focus", "freedom"), {"hunter/marksmanship": 2}),
            ("Setting snares and gathering supplies.", ("hunter", "shaman"), ("trickster", "instinct"), {"hunter/survival": 2}),
            ("Resting by the fire.", ("priest", "druid"), ("healer", "bond"), {}),
        ]),
    "q37": dict(type="choice", text="Someone you care about is in danger. What do you do?",
        rationale="Every answer gives Paladin 2 points, so this question measures the choice among Holy (heal), Protection (hold the ground) and Retribution (make the attacker answer).",
        answers=[
            ("Tend to them first and make sure they recover.", ("paladin", "priest"), ("healer", "duty"), {"paladin/holy": 2}),
            ("Stand between them and the danger and hold the ground.", ("paladin", "warrior"), ("guardian", "duty"), {"paladin/protection": 2, "warrior/protection": 1}),
            ("Go after whoever caused it and make them answer.", ("paladin", "hunter"), ("duty", "power"), {"paladin/retribution": 2}),
        ]),
    "q38": dict(type="ranking", text="Rank these oaths from the one you would most like to keep to the one you would least like.",
        rationale="Ranking: three oaths stand for Holy, Protection and Retribution Paladin. The oath to the wild is a decoy that favours Druid and Shaman.",
        answers=[
            ("To heal anyone who asks, whatever they have done.", ("paladin", "priest"), ("healer", "duty"), {"paladin/holy": 2}),
            ("To keep watch so that no one in your care comes to harm.", ("paladin", "warrior"), ("guardian", "duty"), {"paladin/protection": 2}),
            ("To bring wrongdoers to justice, whatever it costs you.", ("paladin", "hunter"), ("duty", "power"), {"paladin/retribution": 2}),
            ("To protect the old ways of the wild.", ("druid", "shaman"), ("wild", "bond"), {}),
        ]),
    "q39": dict(type="choice", text="A friend is about to face something hard. How do you help?",
        rationale="Every answer gives Priest 2 points, so this question measures the choice among Discipline (prepare and protect), Holy (be there and mend) and Shadow (face the fear).",
        answers=[
            ("Plan with them and put protections in place before it starts.", ("priest", "paladin"), ("focus", "healer"), {"priest/discipline": 2}),
            ("Be there afterward, listening and mending whatever needs it.", ("priest", "druid"), ("healer", "bond"), {"priest/holy": 2}),
            ("Help them look at the fear underneath and walk into it with them.", ("priest", "warlock"), ("shadow", "scholar"), {"priest/shadow": 2}),
        ]),
    "q40": dict(type="allocation", text="You have six hours in a temple. How do you divide them?",
        rationale="Allocation: three items stand for Discipline, Holy and Shadow Priest; mending the roof is an unrelated fourth.",
        answers=[
            ("Planning the wards and rituals so that nothing goes wrong.", ("priest", "paladin"), ("focus", "healer"), {"priest/discipline": 2}),
            ("Tending the sick in the infirmary.", ("priest", "druid"), ("healer", "bond"), {"priest/holy": 2}),
            ("Reading the forbidden texts alone.", ("priest", "warlock"), ("shadow", "scholar"), {"priest/shadow": 2}),
            ("Mending the roof.", ("hunter", "warrior"), ("guardian", "instinct"), {}),
        ]),
    "q41": dict(type="choice", text="You need something from a guarded house. What is your plan?",
        rationale="Every answer gives Rogue 2 points, so this question measures the choice among Assassination (one exact move), Combat (improvise in the open) and Subtlety (misdirection).",
        answers=[
            ("Watch the guards for days, then do one thing, quietly, at exactly the right moment.", ("rogue", "mage"), ("focus", "shadow"), {"rogue/assassination": 2}),
            ("Walk in, deal with whoever is there and improvise from that point.", ("rogue", "warrior"), ("instinct", "power"), {"rogue/combat": 2}),
            ("Send the guards the wrong way and walk through while they argue.", ("rogue", "hunter"), ("trickster", "shadow"), {"rogue/subtlety": 2}),
        ]),
    "q42": dict(type="ranking", text="Rank these tricks of the trade from the one you would most like to master to the one you would least like.",
        rationale="Ranking: three tricks stand for Assassination, Combat and Subtlety Rogue. The watchful animal is a decoy that favours Hunter and Druid.",
        answers=[
            ("A poison that works slowly and leaves no trace.", ("rogue", "warlock"), ("focus", "shadow"), {"rogue/assassination": 2}),
            ("A pair of fast blades and the nerve to use them.", ("rogue", "warrior"), ("instinct", "power"), {"rogue/combat": 2}),
            ("A disguise good enough to fool a friend.", ("rogue", "mage"), ("trickster", "shadow"), {"rogue/subtlety": 2}),
            ("A loyal animal that watches the door.", ("hunter", "druid"), ("bond", "wild"), {}),
        ]),
    "q43": dict(type="choice", text="A river is rising and the village sits below it. What is your part?",
        rationale="Every answer gives Shaman 2 points, so this question measures the choice among Elemental Combat (command the storm), Enhancement (meet it with a weapon) and Restoration (heal the people).",
        answers=[
            ("Break the storm overhead and send the rain away.", ("shaman", "mage"), ("power", "wild"), {"shaman/elemental_combat": 2}),
            ("Meet the flood at the bank with your weapon and the storm's strength in your arms.", ("shaman", "warrior"), ("instinct", "duty"), {"shaman/enhancement": 2}),
            ("Gather the families on high ground and heal whoever is hurt.", ("shaman", "druid"), ("healer", "wild"), {"shaman/restoration": 2, "druid/restoration": 1}),
        ]),
    "q44": dict(type="ranking", text="Rank these gifts from the spirits from the one you would most want to the one you would least want.",
        rationale="Ranking: three gifts stand for Elemental Combat, Enhancement and Restoration Shaman. The underground sense is a decoy that favours Rogue and Druid.",
        answers=[
            ("Command of lightning, to throw at any distance.", ("shaman", "mage"), ("power", "wild"), {"shaman/elemental_combat": 2}),
            ("A weapon that carries the storm in every strike.", ("shaman", "warrior"), ("instinct", "duty"), {"shaman/enhancement": 2}),
            ("Water that heals any wound it touches.", ("shaman", "priest"), ("healer", "wild"), {"shaman/restoration": 2}),
            ("The sense of what lies hidden underground.", ("rogue", "druid"), ("shadow", "wild"), {}),
        ]),
    "q45": dict(type="choice", text="You may make one bargain with a dark power. What do you ask for?",
        rationale="Every answer gives Warlock 2 points, so this question measures the choice among Affliction (patient wearing down), Demonology (a pact with a servant) and Destruction (one burst of ruin).",
        answers=[
            ("A curse that wears an enemy down a little more every day.", ("warlock", "priest"), ("shadow", "focus"), {"warlock/affliction": 2}),
            ("A loyal servant and a pact that makes you both stronger.", ("warlock", "hunter"), ("bond", "shadow"), {"warlock/demonology": 2}),
            ("One burst of ruin big enough to end the fight, whatever it costs you.", ("warlock", "mage"), ("power", "shadow"), {"warlock/destruction": 2}),
        ]),
    "q46": dict(type="allocation", text="You have six nights in a haunted tower. How do you divide them?",
        rationale="Allocation: three items stand for Affliction, Demonology and Destruction Warlock; reading the old histories is an unrelated fourth.",
        answers=[
            ("Waiting and watching while the traps do their slow work.", ("warlock", "priest"), ("shadow", "focus"), {"warlock/affliction": 2}),
            ("Learning the names of the creatures that serve you.", ("warlock", "hunter"), ("bond", "shadow"), {"warlock/demonology": 2}),
            ("Preparing one huge working to bring the tower down.", ("warlock", "mage"), ("power", "shadow"), {"warlock/destruction": 2}),
            ("Reading the old histories on the shelves.", ("mage", "priest"), ("scholar", "duty"), {}),
        ]),
    "q47": dict(type="choice", text="A battle is about to start and you may choose your post. Which do you take?",
        rationale="Every answer gives Warrior 2 points, so this question measures the choice among Arms (exact technique), Fury (momentum with two weapons) and Protection (the shield).",
        answers=[
            ("Wait for the moment and strike with exact technique.", ("warrior", "rogue"), ("focus", "duty"), {"warrior/arms": 2}),
            ("Charge in with a blade in each hand and keep the momentum.", ("warrior", "shaman"), ("power", "freedom"), {"warrior/fury": 2}),
            ("Plant yourself in front with a shield and let them come.", ("warrior", "paladin"), ("guardian", "duty"), {"warrior/protection": 2, "paladin/protection": 1}),
        ]),
    "q48": dict(type="ranking", text="Rank these ways of training from the one you would most like to the one you would least like.",
        rationale="Ranking: three drills stand for Arms, Fury and Protection Warrior. Reading maps is a decoy that favours Mage and Hunter.",
        answers=[
            ("Hours of drills until every move is exact.", ("warrior", "rogue"), ("focus", "duty"), {"warrior/arms": 2}),
            ("Sparring at full speed with no breaks.", ("warrior", "shaman"), ("power", "freedom"), {"warrior/fury": 2}),
            ("Holding a gate against everyone who tries to pass.", ("warrior", "paladin"), ("guardian", "duty"), {"warrior/protection": 2}),
            ("Reading maps and planning the route.", ("mage", "hunter"), ("scholar", "focus"), {}),
        ]),
    "q49": dict(type="choice", text="A group sets out through hostile country. Which job do you take?",
        rationale="A role question across all classes: tank, healer, melee damage and ranged damage. The direct weights go to every specialization in that role.",
        answers=[
            ("Walk in front and take the attacks.", ("warrior", "paladin"), ("guardian", "duty"),
             {"warrior/protection": 2, "paladin/protection": 2, "druid/feral_combat": 1}),
            ("Stay behind and keep everyone standing.", ("priest", "druid"), ("healer", "bond"),
             {"priest/discipline": 1, "priest/holy": 1, "paladin/holy": 1, "druid/restoration": 1, "shaman/restoration": 1}),
            ("Close in and hit the enemy hard.", ("rogue", "warrior"), ("power", "instinct"),
             {"rogue/combat": 1, "rogue/assassination": 1, "warrior/fury": 1, "warrior/arms": 1, "paladin/retribution": 1, "shaman/enhancement": 1}),
            ("Pick your targets from a distance.", ("mage", "hunter"), ("focus", "freedom"),
             {"mage/fire": 1, "mage/arcane": 1, "hunter/marksmanship": 1, "warlock/destruction": 1, "shaman/elemental_combat": 1, "priest/shadow": 1}),
        ]),
    "q50": dict(type="scale", text="In a fight I want distance between me and the enemy.",
        rationale="Scale: agreeing favours the ranged specializations, disagreeing the melee ones.",
        agree=("Keeps its distance.", ("hunter", "mage"), ("focus", "freedom"),
               {"hunter/marksmanship": 1, "hunter/beast_mastery": 1, "mage/frost": 1, "mage/arcane": 1, "warlock/affliction": 1, "druid/balance": 1, "shaman/elemental_combat": 1}),
        disagree=("Closes in.", ("warrior", "rogue"), ("instinct", "power"),
                  {"warrior/fury": 1, "warrior/arms": 1, "rogue/combat": 1, "rogue/assassination": 1, "paladin/retribution": 1, "shaman/enhancement": 1, "druid/feral_combat": 1})),
}

EXTRA_ORDER = [f"q{n}" for n in range(31, 51)]


def _answer(aid: str, text: str, classes, traits, specs) -> Answer:
    return Answer(
        id=aid, text=text,
        class_weights={classes[0]: 2.0, classes[1]: 1.0},
        trait_weights={traits[0]: 2.0, traits[1]: 1.0},
        spec_weights={k: float(w) for k, w in specs.items()},
    )


def build_extra_questions() -> list[Question]:
    """The twenty confidence-mode-only questions, in order."""
    out = []
    for qid in EXTRA_ORDER:
        d = EXTRA_QUESTIONS[qid]
        if d["type"] == "scale":
            answers = [_answer("agree", *d["agree"]), _answer("disagree", *d["disagree"])]
        else:
            answers = [_answer(chr(ord("a") + i), *a) for i, a in enumerate(d["answers"])]
        out.append(Question(id=qid, text=d["text"], type=d["type"], rationale=d["rationale"], answers=answers, min_length="adaptive"))
    return out
