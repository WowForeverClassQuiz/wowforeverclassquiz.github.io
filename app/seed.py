"""Seed configuration: the original sixteen-question quiz, class/trait/specialization
definitions, and placeholder build records.

This module is data only. ``build_default_config()`` returns a fresh ``Config`` every
call, so the original configuration can always be recovered.

Answer encoding used below, per the project specification::

    (answer_id, text, (primary_class, secondary_class), (primary_trait, secondary_trait))

The primary class/trait receives 2 points and the secondary receives 1.

Questions q17-q30 (added in algorithm 1.1.0) are described in ``NEW_QUESTIONS`` below. They also carry direct
specialization weights; the sixteen original questions deliberately do not.
"""
from __future__ import annotations

from .seed_tuning import ORIGINAL_CLASS_PAIRS, SPEC_WEIGHTS, TYPE_CHANGES
from .models import (
    Answer,
    Build,
    Config,
    ConfidenceMargins,
    GameClass,
    Question,
    QuizMeta,
    ScoringSettings,
    Specialization,
    Trait,
)

ALGORITHM_VERSION = "1.2.0"

# Primary / secondary / tertiary multipliers for the original three-trait profiles.
SPEC_MULTIPLIERS = (1.5, 1.0, 0.45)

# --------------------------------------------------------------------------
# Traits: id, display name, description (spec table), reading sentence
# --------------------------------------------------------------------------

TRAITS = [
    ("wild", "Intuition", "Attraction to nature, spontaneity, and organic processes",
     "You trust natural rhythms and spontaneity over rigid structure."),
    ("scholar", "Curiosity", "Intellectual exploration and systematic understanding",
     "You are driven to understand how things work, and why."),
    ("duty", "Conviction", "Responsibility, principles, and moral commitment",
     "You hold firm principles and feel responsible for honoring them."),
    ("shadow", "Mystery", "Interest in hidden, ambiguous, or unconventional ideas",
     "You are intrigued by the hidden, the ambiguous, and the unconventional."),
    ("guardian", "Protectiveness", "Desire to preserve, defend, and provide stability",
     "You instinctively protect and steady the people around you."),
    ("focus", "Precision", "Deliberation, accuracy, and careful execution",
     "You value deliberation, accuracy, and careful execution."),
    ("healer", "Compassion", "Attentiveness to others' well-being",
     "You are attentive to other people's well-being."),
    ("power", "Intensity", "Decisiveness, ambition, and forceful expression",
     "You act decisively and with ambition, and you express yourself forcefully."),
    ("trickster", "Ingenuity", "Resourcefulness, creativity, and unconventional solutions",
     "You solve problems with resourcefulness and unconventional ideas."),
    ("instinct", "Spontaneity", "Immediate action, improvisation, and emotional responsiveness",
     "You respond in the moment, trusting improvisation and feeling."),
    ("bond", "Loyalty", "Companionship, belonging, and interpersonal commitment",
     "You are defined by companionship, belonging, and commitment to others."),
    ("freedom", "Independence", "Autonomy, exploration, and resistance to restrictions",
     "You prize autonomy and resist restrictions on where you may roam."),
]

# --------------------------------------------------------------------------
# Classes and specializations (order = display order = tie-break order)
# spec tuple: id, name, role, description, (primary, secondary, tertiary traits)
# --------------------------------------------------------------------------

CLASSES = [
    ("druid", "Druid", "Adaptable, intuitive, and attentive to natural rhythms", [
        ("balance", "Balance", "ranged_damage",
         "A contemplative seeker who reads patterns in the sky and the wild alike.",
         ("scholar", "wild", "focus")),
        ("feral_combat", "Feral Combat", "melee_damage_or_tank",
         "An untamed, instinctive spirit that thrives on motion and freedom.",
         ("wild", "instinct", "freedom")),
        ("restoration", "Restoration", "healer",
         "A nurturing presence that tends to others the way a gardener tends growth.",
         ("healer", "bond", "guardian")),
    ]),
    ("hunter", "Hunter", "Independent, observant, and most at ease beside a loyal companion", [
        ("beast_mastery", "Beast Mastery", "ranged_damage",
         "A loyal companion at heart, happiest working in partnership with a creature you trust.",
         ("bond", "wild", "guardian")),
        ("marksmanship", "Marksmanship", "ranged_damage",
         "A patient, precise observer who prizes the single perfectly placed decision.",
         ("focus", "freedom", "scholar")),
        ("survival", "Survival", "ranged_damage",
         "A resourceful improviser who trusts instinct and ingenuity in unfamiliar terrain.",
         ("instinct", "trickster", "wild")),
    ]),
    ("mage", "Mage", "Curious, analytical, and drawn to the hidden structure of things", [
        ("arcane", "Arcane", "ranged_damage",
         "A scholar of hidden mechanisms, drawn to the deepest and most abstract questions.",
         ("scholar", "focus", "shadow")),
        ("fire", "Fire", "ranged_damage",
         "A bold, intense personality that prefers decisive, high-energy expression.",
         ("power", "instinct", "freedom")),
        ("frost", "Frost", "ranged_damage",
         "A composed, deliberate mind that values control, patience, and a steady hand.",
         ("focus", "guardian", "scholar")),
    ]),
    ("paladin", "Paladin", "Principled, steadfast, and moved to defend what you believe is right", [
        ("holy", "Holy", "healer",
         "A devoted caretaker who turns conviction into compassion for others.",
         ("healer", "duty", "bond")),
        ("protection", "Protection", "tank",
         "A steadfast guardian whom others instinctively rely on in difficult moments.",
         ("guardian", "duty", "focus")),
        ("retribution", "Retribution", "melee_damage",
         "A driven champion of justice who acts on principle with conviction and force.",
         ("duty", "power", "instinct")),
    ]),
    ("priest", "Priest", "Compassionate, contemplative, and steady in service to others", [
        ("discipline", "Discipline", "healer",
         "A disciplined, thoughtful healer who values preparation and careful judgment.",
         ("focus", "healer", "scholar")),
        ("holy", "Holy", "healer",
         "A warm, communal spirit who finds meaning in caring for the people around you.",
         ("healer", "bond", "duty")),
        ("shadow", "Shadow", "ranged_damage",
         "A reflective, enigmatic thinker unafraid of the darker corners of the mind.",
         ("shadow", "scholar", "power")),
    ]),
    ("rogue", "Rogue", "Resourceful, perceptive, and comfortable beyond convention", [
        ("assassination", "Assassination", "melee_damage",
         "A meticulous, quietly intense planner who values exactness and timing.",
         ("focus", "shadow", "instinct")),
        ("combat", "Combat", "melee_damage",
         "A spirited improviser who enjoys the thrill of the moment and thinks on your feet.",
         ("instinct", "power", "freedom")),
        ("subtlety", "Subtlety", "melee_damage",
         "A clever, elusive strategist who prefers misdirection and unexpected solutions.",
         ("trickster", "shadow", "focus")),
    ]),
    ("shaman", "Shaman", "Spirited, grounded in the elements, and responsive to the moment", [
        ("elemental_combat", "Elemental Combat", "ranged_damage",
         "A vivid, forceful personality attuned to the energy of storms and stone.",
         ("power", "wild", "scholar")),
        ("enhancement", "Enhancement", "melee_damage",
         "A grounded, responsive spirit who channels conviction through instinct.",
         ("instinct", "duty", "power")),
        ("restoration", "Restoration", "healer",
         "A gentle, earth-rooted healer who draws strength from natural cycles and community.",
         ("healer", "wild", "bond")),
    ]),
    ("warlock", "Warlock", "Ambitious, enigmatic, and unafraid of what others avoid", [
        ("affliction", "Affliction", "ranged_damage",
         "A patient, analytical schemer who prefers slow, careful, inevitable outcomes.",
         ("shadow", "focus", "scholar")),
        ("demonology", "Demonology", "ranged_damage",
         "A relationship-minded dealmaker who finds power in bonds others overlook.",
         ("bond", "shadow", "guardian")),
        ("destruction", "Destruction", "ranged_damage",
         "An ambitious, intense force who embraces bold, high-stakes expression.",
         ("power", "shadow", "instinct")),
    ]),
    ("warrior", "Warrior", "Resolute, direct, and driven to meet challenges head-on", [
        ("arms", "Arms", "melee_damage",
         "A disciplined, methodical fighter who respects technique and measured force.",
         ("focus", "duty", "instinct")),
        ("fury", "Fury", "melee_damage",
         "A restless, high-intensity spirit who channels momentum and independence.",
         ("power", "instinct", "freedom")),
        ("protection", "Protection", "tank",
         "A resolute defender who shoulders responsibility so others do not have to.",
         ("guardian", "duty", "bond")),
    ]),
]

# --------------------------------------------------------------------------
# The sixteen questions
# --------------------------------------------------------------------------

QUESTIONS = [
    ("q01", "You are permitted to spend one evening in an unfamiliar estate. Which room attracts you first?", [
        ("a", "The conservatory, filled with plants from distant countries.", ("druid", "hunter"), ("wild", "healer")),
        ("b", "The observatory, with an extraordinary view of the stars.", ("mage", "shaman"), ("scholar", "focus")),
        ("c", "The chapel, illuminated by hundreds of candles.", ("priest", "paladin"), ("duty", "guardian")),
        ("d", "The locked library, whose books have no titles.", ("warlock", "rogue"), ("shadow", "scholar")),
    ]),
    ("q02", "Someone you care about has been treated unfairly. What is your immediate response?", [
        ("a", "Intervene directly and insist that the situation be corrected.", ("paladin", "warrior"), ("guardian", "duty")),
        ("b", "Determine exactly what happened before taking action.", ("mage", "rogue"), ("focus", "scholar")),
        ("c", "Concentrate first on the person who has been hurt.", ("priest", "druid"), ("healer", "bond")),
        ("d", "Find a way to make the responsible person face the consequences.", ("warlock", "shaman"), ("shadow", "power")),
    ]),
    ("q03", "You arrive alone in an unfamiliar city. Where do you spend your first evening?", [
        ("a", "Exploring quiet streets and discovering places few visitors know.", ("rogue", "hunter"), ("trickster", "freedom")),
        ("b", "At a crowded restaurant, joining an animated conversation.", ("warrior", "shaman"), ("instinct", "bond")),
        ("c", "In a peaceful garden, away from the busiest streets.", ("druid", "priest"), ("wild", "healer")),
        ("d", "At a gathering where people discuss unusual ideas.", ("mage", "warlock"), ("scholar", "shadow")),
    ]),
    ("q04", "A mysterious event occurs. Which would you find most compelling?", [
        ("a", "Animal tracks that lead to a place no map identifies.", ("hunter", "druid"), ("wild", "instinct")),
        ("b", "Lightning illuminating a perfectly clear night sky.", ("shaman", "mage"), ("power", "wild")),
        ("c", "A bell sounding from a tower that has been abandoned for centuries.", ("paladin", "priest"), ("duty", "focus")),
        ("d", "A shadow moving independently of the object that casts it.", ("rogue", "warlock"), ("shadow", "trickster")),
    ]),
    ("q05", "An important plan has failed unexpectedly. How do you respond?", [
        ("a", "Identify an alternative route that others have overlooked.", ("rogue", "hunter"), ("trickster", "instinct")),
        ("b", "Assume responsibility and organize the next attempt.", ("warrior", "paladin"), ("guardian", "power")),
        ("c", "Adapt to the situation and proceed according to intuition.", ("shaman", "druid"), ("wild", "instinct")),
        ("d", "Reconsider the assumptions on which the original plan depended.", ("mage", "warlock"), ("scholar", "focus")),
    ]),
    ("q06", "You are offered one unusual gift. Which would you accept?", [
        ("a", "A lifelong companion with whom you can communicate without words.", ("hunter", "warlock"), ("bond", "wild")),
        ("b", "A promise that someone you love will always be protected.", ("paladin", "priest"), ("duty", "healer")),
        ("c", "A book containing answers to questions no one has thought to ask.", ("mage", "rogue"), ("scholar", "shadow")),
        ("d", "The ability to travel anywhere without fear of getting lost.", ("druid", "shaman"), ("wild", "freedom")),
    ]),
    ("q07", "Which kind of weather appeals to you most?", [
        ("a", "Quiet snowfall, when everything becomes still.", ("mage", "priest"), ("focus", "guardian")),
        ("b", "Gentle rain after several unusually warm days.", ("druid", "shaman"), ("healer", "wild")),
        ("c", "An intense summer thunderstorm.", ("warrior", "shaman"), ("power", "instinct")),
        ("d", "Heavy fog that conceals a familiar landscape.", ("rogue", "warlock"), ("shadow", "trickster")),
    ]),
    ("q08", "If people remembered you for one quality, which would you choose?", [
        ("a", "Being dependable when others needed protection.", ("paladin", "warrior"), ("guardian", "duty")),
        ("b", "Understanding things that others found difficult to explain.", ("mage", "rogue"), ("focus", "scholar")),
        ("c", "Helping people through difficult periods of their lives.", ("priest", "druid"), ("healer", "bond")),
        ("d", "Having the courage to attempt what others considered impossible.", ("warlock", "hunter"), ("power", "freedom")),
    ]),
    ("q09", "At a large festival, where are you most likely to be found?", [
        ("a", "Among the musicians and dancers.", ("shaman", "warrior"), ("instinct", "power")),
        ("b", "Listening to a storyteller discussing ancient legends.", ("warlock", "priest"), ("shadow", "scholar")),
        ("c", "Arranging an excursion with a group of friends.", ("hunter", "paladin"), ("bond", "guardian")),
        ("d", "Exploring the less crowded parts of the city.", ("rogue", "druid"), ("trickster", "wild")),
    ]),
    ("q10", "You may possess an extraordinary ability, provided you accept its limitation. Which do you choose?", [
        ("a", "Understand every living creature, although you cannot command one.", ("druid", "hunter"), ("wild", "bond")),
        ("b", "Recognize every lie, although you must always tell the truth.", ("rogue", "mage"), ("focus", "trickster")),
        ("c", "Heal any wound, although doing so temporarily weakens you.", ("priest", "paladin"), ("healer", "duty")),
        ("d", "Change one person's fate, although your own remains beyond your control.", ("warlock", "shaman"), ("shadow", "power")),
    ]),
    ("q11", "Which object would you be most likely to preserve for its beauty?", [
        ("a", "A beautifully designed astronomical instrument.", ("mage", "paladin"), ("focus", "scholar")),
        ("b", "An ancient stone sculpture partly reclaimed by vegetation.", ("druid", "warlock"), ("wild", "shadow")),
        ("c", "A well-made tool that has been used for generations.", ("warrior", "hunter"), ("guardian", "instinct")),
        ("d", "A small, intricate piece of handmade jewelry.", ("rogue", "priest"), ("trickster", "healer")),
    ]),
    ("q12", "Which characteristic in other people frustrates you most?", [
        ("a", "A refusal to take responsibility for others.", ("paladin", "priest"), ("guardian", "duty")),
        ("b", "Complacency and an unwillingness to improve.", ("warrior", "shaman"), ("power", "instinct")),
        ("c", "Intellectual dishonesty.", ("mage", "warlock"), ("scholar", "focus")),
        ("d", "An insistence that everyone must follow the same conventions.", ("rogue", "hunter"), ("trickster", "freedom")),
    ]),
    ("q13", "If you disappeared from your ordinary life for a month, what would you most likely be doing?", [
        ("a", "Living in a small, remote community and learning its traditions.", ("druid", "shaman"), ("healer", "wild")),
        ("b", "Undertaking a demanding physical challenge.", ("warrior", "paladin"), ("power", "duty")),
        ("c", "Studying an unfamiliar subject or artistic discipline.", ("mage", "priest"), ("scholar", "focus")),
        ("d", "Traveling anonymously through several unfamiliar cities.", ("rogue", "warlock"), ("shadow", "freedom")),
    ]),
    ("q14", "When two friends disagree, what position do you naturally assume?", [
        ("a", "Mediator, helping them understand one another.", ("priest", "druid"), ("healer", "bond")),
        ("b", "Advocate, defending the position you consider justified.", ("paladin", "warrior"), ("duty", "guardian")),
        ("c", "Analyst, examining where their reasoning differs.", ("mage", "rogue"), ("focus", "scholar")),
        ("d", "Challenger, raising an uncomfortable point that everyone has avoided.", ("warlock", "shaman"), ("shadow", "power")),
    ]),
    ("q15", "After an exceptionally difficult day, what would restore you most?", [
        ("a", "Fresh air, solitude, and time outdoors.", ("hunter", "druid"), ("wild", "freedom")),
        ("b", "A meal with people whose company you enjoy.", ("shaman", "warrior"), ("bond", "instinct")),
        ("c", "A quiet, familiar ritual in a comfortable setting.", ("priest", "paladin"), ("healer", "guardian")),
        ("d", "Something intellectually absorbing that takes your mind elsewhere.", ("mage", "warlock"), ("scholar", "shadow")),
    ]),
    ("q16", "Finally, choose the symbol that appeals to you most, without explaining why.", [
        ("a", "An old silver key.", ("rogue", "mage"), ("trickster", "focus")),
        ("b", "A lantern burning in the darkness.", ("priest", "paladin"), ("healer", "duty")),
        ("c", "An antler with flowering branches.", ("druid", "hunter"), ("wild", "bond")),
        ("d", "A meteor crossing the night sky.", ("shaman", "warlock"), ("power", "shadow")),
    ]),
]


# --------------------------------------------------------------------------
# "What this class does" paragraphs shown with the result. Written in this project's own words from
# Blizzard's official class pages (worldofwarcraft.blizzard.com/en-us/game/classes/<class>), which
# describe the retail game, and from the Forever class deep dives for specialization playstyle. They are
# summaries, not Blizzard's text; each class links to the page it was written from. Edit freely.
# --------------------------------------------------------------------------

OVERVIEW_URL = "https://worldofwarcraft.blizzard.com/en-us/game/classes/{}"

OVERVIEWS = {
    "druid": (
        "Druids are shapeshifting guardians of the natural world. They change shape to fit the moment: a moonkin hurling magic "
        "from afar, a cat or bear fighting up close, or a healer tending a whole party with growth magic. Few classes can "
        "fill as many roles.",
        {
            "balance": "A ranged caster that takes the moonkin shape and wears enemies down with arcane and nature magic, much of it damage that lingers over time.",
            "feral_combat": "A shapeshifting fighter. As a cat it hunts with bleeds and quick bursts of energy; as a bear it can stand in front and absorb punishment for the group.",
            "restoration": "The nature healer. Restoration mends allies with growth magic, leaning on heals that tick over time and spread across a whole party.",
        },
    ),
    "hunter": (
        "Hunters make their lives out in the wild, tracking prey and fighting alongside animal companions. They shoot from range, set "
        "traps, and keep moving so their enemies never get to close the gap, and the pet at their side is the heart of the class.",
        {
            "beast_mastery": "A tamer who fights in partnership with a strong companion, directing the beast while firing from range.",
            "marksmanship": "A long-range sharpshooter. Marksmanship wins through precision: careful, steady output with well-timed bursts.",
            "survival": "An adaptable ranger who leans on traps, venoms and bleeds, and plays closer to the action than the other Hunter specializations.",
        },
    ),
    "mage": (
        "Mages study the arcane as a discipline of the mind. At range they unleash enormous spell damage, strike groups and "
        "shape the battlefield, and their utility spells can teleport a party or conjure a meal, yet they are fragile when anyone gets close.",
        {
            "arcane": "Raw arcane energy built into stacking surges of damage. It is a hard-hitting style that spends mana quickly and rewards careful management.",
            "fire": "The aggressive school: explosive, combustive spells that lean on critical strikes and reward bold, fast play.",
            "frost": "The controlling school. Frost chills and roots its targets, then breaks them with a well-timed burst, rewarding patience, positioning and tidy kiting.",
        },
    ),
    "paladin": (
        "Paladins are armored champions of the Light, sworn to shield the vulnerable and answer evil. They can heal, hold the line "
        "or take the offensive, backing steel with blessings, seals and judgements, and the Light can mend them as readily as their allies.",
        {
            "holy": "The armored healer. Holy channels divine light into powerful heals and protective magic while staying close to the people it protects.",
            "protection": "The sworn defender. Protection stands in front with a shield, draws enemy attention and uses holy magic to turn aside damage meant for others.",
            "retribution": "A crusading melee fighter that pairs a heavy weapon with seals and judgements, punishing enemies with strikes empowered by holy magic.",
        },
    ),
    "priest": (
        "Priests are servants of faith whose first duty is keeping their companions alive, through healing and protective shields. "
        "They can also strike with magic of their own, but their cloth robes leave them frail, so they weigh helping others against surviving themselves.",
        {
            "discipline": "The protective healer. Discipline wards allies ahead of the blow, and some of its tools turn offense into healing, so support and attack blur together.",
            "holy": "The versatile direct healer. Holy mends single allies or whole groups after the damage lands, with group tools such as Prayer of Mending.",
            "shadow": "The dark caster. Shadow draws on shadow magic and takes Shadowform to deal lingering damage over time alongside quick, heavy hits.",
        },
    ),
    "rogue": (
        "Rogues are cunning blades for hire who live by stealth and surprise. They open from the shadows, stack up combo points for "
        "finishing blows, and lean on poisons and trickery, picking their fights carefully and vanishing when the odds turn.",
        {
            "assassination": "The poisoner. Assassination prepares its kills with lethal poisons and quick, precise dagger work.",
            "combat": "The head-on duelist. Combat fights in the open with a weapon in each hand, trading on quick improvisation and strong finishing moves.",
            "subtlety": "The shadow stalker. Subtlety lives in stealth, ambushing from hiding and winning through misdirection, positioning and timing.",
        },
    ),
    "shaman": (
        "Shamans commune with the spirits of earth, air, fire and water, bargaining and balancing rather than commanding. Planted "
        "totems strengthen friends and hamper foes, and a Shaman may heal or fight, whether in the thick of melee or from a distance.",
        {
            "elemental_combat": "A ranged caster of lightning, tremors and molten rock, with totems backing up its destructive power.",
            "enhancement": "A melee fighter who fills its weapons with elemental force, fights in the thick of things and draws strength from its totems.",
            "restoration": "The healer who leans on ancestral spirits and the purifying power of water, mending allies with flowing heals, shields and well-placed totems.",
        },
    ),
    "warlock": (
        "Warlocks trade in forbidden power. They strike from range with shadow and fire, sap enemies with curses, and keep summoned "
        "demons in front to absorb the punishment while they work from behind.",
        {
            "affliction": "The patient tormentor. Affliction piles on drains and damage over time, wearing enemies down slowly and inevitably.",
            "demonology": "The demon commander. Demonology builds its strength around summoned demons and the power it draws from them.",
            "destruction": "The chaos specialist. Destruction burns and blasts targets with fire and shadow in quick, high-stakes bursts.",
        },
    ),
    "warrior": (
        "Warriors are the armored front line. They throw themselves into close combat, turn the fury of the fight into Rage, and spend it "
        "on a broad arsenal of weapon strikes, standing either as the wall that protects a group or as its heaviest hitter.",
        {
            "arms": "A veteran of weapon craft. Arms wins through technique, nimble footwork and punishing strikes, usually with a two-handed weapon.",
            "fury": "A frenzied berserker. Fury fights with a weapon in each hand, building Rage into fast, overwhelming flurries.",
            "protection": "The shield-bearer who stands in front. Protection soaks up damage and keeps enemies focused on it so the rest of the group can work.",
        },
    ),
}


# --------------------------------------------------------------------------
# Questions added in 1.1.0 (q17-q30): 8 scale, 3 pick-two, 3 this-or-that.
#
# Mapping basis. Published studies find little or no link between player personality and class choice
# (Mosley 2010, Boise State; Bean et al. 2016, Entertainment Computing), so these are playstyle associations
# from community lore, not science: tanks as natural leaders, healers as dutiful and unseen, melee damage
# as risk-taking and attention-seeking, casters and stealth damage as independent and resourceful (Ten Ton
# Hammer, "Healer, DPS, or Tank: What's Your Archetype?"), plus each specialization's playstyle as described
# in Blizzard's Forever class deep dives (summarised by Maxroll): pets, damage-over-time juggling, totems,
# stealth and poisons, stance switching. All of it is a best guess and is meant to be edited.
#
# Each pole / answer is (text, (class1, class2), (trait1, trait2)). Class and trait pairs get 2 and 1 points like the
# original questions. Direct specialization weights ('class/spec' keys) are not listed here: they live in
# seed_tuning.SPEC_WEIGHTS, which was tuned for balance (see that module).
# --------------------------------------------------------------------------

_SCALE_NOTE = (
    "Scale question: the participant rates 1-10. Each rating blends the two poles "
    "(agree toward 10, disagree toward 1), so a strong 'disagree' counts for something too."
)

NEW_QUESTIONS = {
    "q17": dict(type="scale", text="When a group is lost, I'm the one who steps forward and decides.",
        rationale=_SCALE_NOTE + " Tanks are described as natural, outgoing leaders; stealth and ranged damage as independent and wary of leading.",
        agree=("Takes the lead and holds the line.", ("warrior", "paladin"), ("guardian", "power")),
        disagree=("Works independently and avoids leading.", ("hunter", "rogue"), ("freedom", "focus"))),
    "q18": dict(type="scale", text="I plan every step before I begin, rather than working it out as I go.",
        rationale=_SCALE_NOTE + " Arcane (stacked burst) and Affliction (stacked damage over time) reward preparation; Combat and Enhancement are reactive, weapon-driven styles.",
        agree=("Plans first.", ("warlock", "mage"), ("focus", "scholar")),
        disagree=("Improvises.", ("shaman", "rogue"), ("instinct", "trickster"))),
    "q19": dict(type="scale", text="I will gladly gamble a lot for the chance of a big reward.",
        rationale=_SCALE_NOTE + " Melee and burst damage players are characterised as risk-takers; shielding and healing roles as cautious and protective.",
        agree=("Risk-taker.", ("warlock", "mage"), ("power", "instinct")),
        disagree=("Cautious and protective.", ("priest", "paladin"), ("guardian", "focus"))),
    "q20": dict(type="scale", text="I do my best work at a steady, unhurried pace.",
        rationale=_SCALE_NOTE + " Slow, accumulating damage (Affliction), measured star-and-moon casting (Balance) and precise ranged shots suit a patient tempo; Fury, Enhancement and Feral are fast and frenetic.",
        agree=("Patient, steady tempo.", ("warlock", "druid"), ("focus", "wild")),
        disagree=("Fast, frenetic tempo.", ("warrior", "shaman"), ("instinct", "power"))),
    "q21": dict(type="scale", text="I do my best when someone loyal is at my side.",
        rationale=_SCALE_NOTE + " Pet partnership defines Beast Mastery (and Demonology's demons); Survival's Lone Wolf option and stealth classes suit people who work alone.",
        agree=("Partnership.", ("hunter", "warlock"), ("bond", "wild")),
        disagree=("Lone wolf.", ("rogue", "hunter"), ("freedom", "shadow"))),
    "q22": dict(type="scale", text="I would rather learn from the wild than from books.",
        rationale=_SCALE_NOTE + " Nature-attuned classes (Druid, Shaman, Hunter) against study-driven ones (Mage, Priest).",
        agree=("Learns from nature.", ("druid", "shaman"), ("wild", "instinct")),
        disagree=("Learns from study.", ("mage", "priest"), ("scholar", "focus"))),
    "q23": dict(type="scale", text="I enjoy being noticed when I do something well.",
        rationale=_SCALE_NOTE + " Melee damage players are described as outspoken and attention-seeking; healers as content to stay in the background.",
        agree=("Enjoys the spotlight.", ("warrior", "mage"), ("power", "instinct")),
        disagree=("Content in the background.", ("priest", "druid"), ("healer", "guardian"))),
    "q24": dict(type="scale", text="I enjoy juggling many things at once and keeping them all going.",
        rationale=_SCALE_NOTE + " Totem management, demon pets and stacked effects reward juggling; Retribution and Arms are single-purpose, technique-first styles.",
        agree=("Keeps many plates spinning.", ("shaman", "warlock"), ("focus", "trickster")),
        disagree=("One thing at a time, done deeply.", ("paladin", "warrior"), ("duty", "focus"))),
    "q25": dict(type="pick_two", text="You can carry only two of these on a long road. Which two do you take?",
        rationale="Pick two: the pair's weights add. Each item points at a role fantasy (protector, healer, trickster, scholar).",
        answers=[
            ("A well-worn shield and a whetstone", ("paladin", "warrior"), ("guardian", "duty")),
            ("A satchel of healing herbs and a small bell", ("druid", "shaman"), ("healer", "wild")),
            ("A set of lockpicks and a pack of marked cards", ("rogue", "warlock"), ("trickster", "shadow")),
            ("A travelling spellbook and an inkwell", ("mage", "warlock"), ("scholar", "focus")),
        ]),
    "q26": dict(type="pick_two", text="Two travelling companions ask to join you. Whom do you welcome?",
        rationale="Pick two: the pair's weights add. Companions stand for a pet bond, a scoundrel, a veteran and a gentle healer.",
        answers=[
            ("A silent grey wolf that matches your pace", ("hunter", "druid"), ("bond", "wild")),
            ("A cheerful scoundrel with a long list of debts", ("rogue", "warlock"), ("trickster", "instinct")),
            ("A battle-scarred veteran who sleeps with one eye open", ("warrior", "paladin"), ("duty", "guardian")),
            ("A gentle traveller who knows every herb and prayer", ("priest", "shaman"), ("healer", "bond")),
        ]),
    "q27": dict(type="pick_two", text="A storm is rolling in. Which two things do you do?",
        rationale="Pick two: the pair's weights add. Watching the storm, securing the camp, reading the clouds, and slipping away each stand for a different temperament.",
        answers=[
            ("Climb a ridge and watch it roll in", ("shaman", "hunter"), ("power", "wild")),
            ("Check the camp, tie everything down, count heads", ("paladin", "warrior"), ("guardian", "duty")),
            ("Sketch the clouds and guess where it will strike", ("hunter", "mage"), ("focus", "scholar")),
            ("Slip away early and find the dry spot nobody else knows", ("hunter", "druid"), ("trickster", "freedom")),
        ]),
    "q28": dict(type="choice", text="Which would you rather be?",
        rationale="This-or-that: a steady guide against a quick, fleeting strike.",
        answers=[
            ("A lantern: steady, and the reason others find their way", ("priest", "paladin"), ("healer", "guardian")),
            ("A blade: quick, and gone before the echo fades", ("rogue", "warrior"), ("shadow", "instinct")),
        ]),
    "q29": dict(type="choice", text="A stubborn locked gate stands between you and what you need. What do you do?",
        rationale="This-or-that: understand the mechanism against calling on something stronger than a key.",
        answers=[
            ("Study its mechanism until you understand it", ("mage", "rogue"), ("scholar", "focus")),
            ("Call on something stronger than a key", ("warlock", "priest"), ("power", "shadow")),
        ]),
    "q30": dict(type="choice", text="Which fire would you rather tend?",
        rationale="This-or-that: a hearth that sustains others against a forge that makes something lasting.",
        answers=[
            ("A hearth that keeps a whole house warm", ("druid", "shaman"), ("healer", "bond")),
            ("A forge that shapes something lasting", ("paladin", "warrior"), ("duty", "power")),
        ]),
}

#: Display order of all thirty questions: new types are interleaved between the original sixteen.
QUESTION_ORDER = [
    "q01", "q02", "q17", "q03", "q04", "q25", "q05", "q18", "q06", "q07", "q19", "q08", "q28", "q09", "q20",
    "q10", "q26", "q11", "q21", "q12", "q29", "q13", "q22", "q14", "q27", "q15", "q23", "q16", "q24", "q30",
]


def _weights(pair: tuple[str, str]) -> dict[str, float]:
    """Primary -> 2 points, secondary -> 1 point."""
    return {pair[0]: 2.0, pair[1]: 1.0}


def _spec_weights(pairs) -> dict[str, float]:
    return {key: float(w) for key, w in pairs}


def _new_question(qid: str, d: dict) -> Question:
    """Build a q17-q30 question from its NEW_QUESTIONS description (direct spec weights come from SPEC_WEIGHTS)."""
    def answer(aid, text, classes, traits):
        return Answer(id=aid, text=text, class_weights=_weights(classes), trait_weights=_weights(traits))

    if d["type"] == "scale":
        answers = [answer("agree", *d["agree"]), answer("disagree", *d["disagree"])]
    else:
        answers = [answer(chr(ord("a") + i), *a) for i, a in enumerate(d["answers"])]
    return Question(id=qid, text=d["text"], type=d["type"], rationale=d["rationale"], answers=answers)


def build_default_config() -> Config:
    """Return a fresh copy of the original configuration (revision 1)."""
    traits = [
        Trait(id=i, name=name, description=desc, interpretation=reading)
        for i, name, desc, reading in TRAITS
    ]
    classes = [
        GameClass(
            id=cid,
            name=name,
            description=desc,
            overview=OVERVIEWS[cid][0],
            overview_url=OVERVIEW_URL.format(cid),
            specializations=[
                Specialization(
                    id=sid,
                    name=sname,
                    role=role,
                    description=sdesc,
                    overview=OVERVIEWS[cid][1][sid],
                    trait_multipliers=dict(zip(profile, SPEC_MULTIPLIERS)),
                )
                for sid, sname, role, sdesc, profile in specs
            ],
        )
        for cid, name, desc, specs in CLASSES
    ]
    by_id = {
        qid: Question(
            id=qid,
            text=text,
            answers=[
                Answer(id=aid, text=atext, class_weights=_weights(cl), trait_weights=_weights(tr))
                for aid, atext, cl, tr in answers
            ],
        )
        for qid, text, answers in QUESTIONS
    }
    by_id.update({qid: _new_question(qid, d) for qid, d in NEW_QUESTIONS.items()})
    # tuning overlay (see seed_tuning.py): original questions may change type and class pairs; any answer may carry spec weights
    for qid, (qtype, qtext) in TYPE_CHANGES.items():
        by_id[qid].type, by_id[qid].text = qtype, qtext
    for q in by_id.values():
        for a in q.answers:
            if (q.id, a.id) in ORIGINAL_CLASS_PAIRS:
                a.class_weights = _weights(ORIGINAL_CLASS_PAIRS[(q.id, a.id)])
            a.spec_weights = _spec_weights(SPEC_WEIGHTS.get((q.id, a.id), {}).items())
    questions = [by_id[qid] for qid in QUESTION_ORDER]
    builds = [
        Build(
            id=f"{cls.id}-{spec.id}-leveling".replace("_", "-"),
            class_id=cls.id,
            specialization_id=spec.id,
            name=f"{spec.name} — Leveling & General PvE",
            role=spec.role.split("_or_")[0],
            purpose="leveling_pve",
            status="pending",
            is_default=True,
            notes=(
                "Talent allocation pending: no verified World of Warcraft: Forever talent data "
                "has been imported for this specialization yet."
            ),
        )
        for cls in classes
        for spec in cls.specializations
    ]
    return Config(
        revision=1,
        quiz=QuizMeta(
            id="wow-forever-oracle",
            title="The Stars Have Chosen",
            subtitle="A thirty-question reading of your temperament for World of Warcraft: Forever",
            expected_question_count=30,
            answers_per_question=4,
        ),
        scoring=ScoringSettings(
            algorithm_version=ALGORITHM_VERSION,
            class_tie_break_order=[c.id for c in classes],
            confidence_margins=ConfidenceMargins(strong=3.0, moderate=1.25),
            spec_weight_multiplier=5.0,
        ),
        traits=traits,
        classes=classes,
        questions=questions,
        builds=builds,
        talent_catalog=None,
    )
