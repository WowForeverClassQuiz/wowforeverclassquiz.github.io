"""Tuning overlay for the seed quiz (seed version 1.3.0).

The original sixteen questions were written for a quiz whose trait profiles could not, under any answers, make
some specializations win, and whose answers favoured some classes far more often than others. Under uniformly random
answers the worst specialization won 7.7% of its class's results, and a search found no way for the original sixteen
questions alone to reach some of the 27 specializations. This overlay keeps the original wording and weights except
where listed here, and adds direct specialization weights (also for the added questions). It was produced with
``tools/balance.py`` and a greedy search, then reviewed by hand against each answer's meaning; the numbers it achieves
are checked by ``tests/test_balance.py``.

Every entry is documented data, not a hidden adjustment: edit or delete any of them in the administrative interface.

  TYPE_CHANGES         original questions turned into "ranking" or "allocation" questions (same four answers and
                       weights; see scoring.py for how a ranking or a split of six points weighs them).
  ORIGINAL_CLASS_PAIRS original answers whose (primary, secondary) classes changed, to even out how often each class
                       is favoured.
  SPEC_WEIGHTS         direct specialization weights ('class/spec' keys) for answers of any question.
  MIN_LENGTH           which questions the short and medium quizzes ask; the rest are asked only in the long quiz.
"""
from __future__ import annotations

TYPE_CHANGES = {
    "q07": ("ranking", "Rank these kinds of weather from the one you would most like to the one you would least like."),
    "q09": ("allocation", "You have six hours at a large festival. How do you divide them among these places?"),
    "q11": ("ranking", "Rank these objects from the one you would most want to preserve for its beauty to the one you would least."),
    "q15": ("allocation", "After an exceptionally difficult day you have six hours to yourself. How do you spend them?"),
}

ORIGINAL_CLASS_PAIRS = {
    ("q02", "b"): ("mage", "hunter"),
    ("q03", "a"): ("hunter", "rogue"),
    ("q05", "a"): ("hunter", "rogue"),
    ("q09", "d"): ("hunter", "rogue"),
    ("q10", "b"): ("rogue", "hunter"),
    ("q12", "c"): ("warlock", "mage"),
    ("q13", "a"): ("shaman", "druid"),
    ("q13", "c"): ("priest", "mage"),
}

#: Questions asked in the short and medium quizzes (every other question is asked only in the long quiz). The quizzes are
#: nested: medium = short + medium, long = all thirty. Chosen with tools/balance.py so that every length is balanced (see
#: tests/test_balance.py) and mixes the question types; the short quiz asks 10 questions, the medium 20 and the long 30.
MIN_LENGTH = {
    "q01": "short", "q06": "short", "q09": "short", "q11": "short", "q12": "short",
    "q13": "short", "q19": "short", "q23": "short", "q24": "short", "q27": "short",
    "q02": "medium", "q03": "medium", "q04": "medium", "q14": "medium", "q16": "medium",
    "q17": "medium", "q18": "medium", "q20": "medium", "q22": "medium", "q26": "medium",
}

SPEC_WEIGHTS = {
    ("q01", "a"): {"druid/restoration": 2},
    ("q01", "b"): {"mage/frost": 1},
    ("q01", "c"): {"paladin/retribution": 1},
    ("q01", "d"): {"rogue/assassination": 1, "warlock/demonology": 1},
    ("q02", "c"): {"druid/restoration": 1},
    ("q03", "d"): {"warlock/demonology": 2},
    ("q04", "b"): {"mage/fire": 3},
    ("q05", "c"): {"druid/balance": 1},
    ("q06", "d"): {"druid/feral_combat": 1},
    ("q07", "a"): {"mage/frost": 1},
    ("q07", "b"): {"druid/balance": 1},
    ("q08", "a"): {"paladin/holy": 1},
    ("q08", "d"): {"hunter/marksmanship": 1},
    ("q09", "a"): {"shaman/enhancement": 2, "warrior/arms": 1},
    ("q09", "b"): {"priest/shadow": 3},
    ("q09", "c"): {"hunter/beast_mastery": 1},
    ("q10", "b"): {"rogue/assassination": 3},
    ("q11", "b"): {"druid/balance": 3},
    ("q11", "c"): {"warrior/arms": 1},
    ("q12", "a"): {"paladin/protection": 1},
    ("q12", "d"): {"hunter/marksmanship": 1, "rogue/combat": 2},
    ("q13", "a"): {"druid/restoration": 1, "shaman/restoration": 1},
    ("q13", "b"): {"paladin/protection": 1, "paladin/retribution": 1, "warrior/arms": 1},
    ("q13", "d"): {"rogue/assassination": 1},
    ("q16", "a"): {"rogue/assassination": 1},
    ("q17", "agree"): {"paladin/protection": 1, "warrior/protection": 2},
    ("q17", "disagree"): {"hunter/marksmanship": 2, "rogue/assassination": 2},
    ("q18", "agree"): {"mage/arcane": 2, "mage/frost": 2, "warlock/affliction": 1},
    ("q18", "disagree"): {"rogue/combat": 2, "shaman/enhancement": 1},
    ("q19", "agree"): {"mage/fire": 3, "warlock/destruction": 2},
    ("q19", "disagree"): {"paladin/holy": 1, "paladin/protection": 1, "priest/discipline": 2},
    ("q20", "agree"): {"druid/balance": 1, "warlock/affliction": 2},
    ("q20", "disagree"): {"shaman/enhancement": 1, "warrior/fury": 2},
    ("q21", "agree"): {"hunter/beast_mastery": 2, "warlock/demonology": 1},
    ("q21", "disagree"): {"hunter/survival": 1, "rogue/assassination": 1, "rogue/combat": 1, "rogue/subtlety": 2},
    ("q22", "agree"): {"druid/feral_combat": 2, "shaman/elemental_combat": 1},
    ("q22", "disagree"): {"priest/discipline": 1},
    ("q23", "agree"): {"mage/fire": 3, "warrior/fury": 2},
    ("q23", "disagree"): {"druid/restoration": 2, "priest/discipline": 1, "priest/holy": 2},
    ("q24", "agree"): {"shaman/restoration": 2, "warlock/affliction": 1, "warlock/demonology": 1},
    ("q24", "disagree"): {"paladin/retribution": 2, "warrior/arms": 2},
    ("q25", "a"): {"paladin/holy": 1, "paladin/protection": 2, "warrior/arms": 1},
    ("q25", "b"): {"druid/balance": 1, "druid/feral_combat": 1, "druid/restoration": 2, "shaman/restoration": 1},
    ("q25", "c"): {"rogue/combat": 1, "rogue/subtlety": 2},
    ("q25", "d"): {"warlock/affliction": 1},
    ("q26", "a"): {"druid/feral_combat": 1, "druid/restoration": 1, "hunter/beast_mastery": 1},
    ("q26", "b"): {"rogue/combat": 2, "warlock/demonology": 1},
    ("q26", "c"): {"paladin/retribution": 1, "warrior/arms": 3, "warrior/protection": 1},
    ("q26", "d"): {"priest/discipline": 2, "shaman/restoration": 1},
    ("q27", "a"): {"shaman/elemental_combat": 2},
    ("q27", "b"): {"paladin/holy": 3, "warrior/protection": 2},
    ("q27", "c"): {"hunter/marksmanship": 2, "mage/frost": 1},
    ("q27", "d"): {"druid/balance": 1, "druid/feral_combat": 2, "hunter/survival": 3},
    ("q28", "a"): {"paladin/holy": 1, "priest/holy": 2},
    ("q28", "b"): {"rogue/combat": 2, "warrior/fury": 1},
    ("q29", "a"): {"rogue/assassination": 1},
    ("q29", "b"): {"priest/shadow": 3, "warlock/demonology": 2},
    ("q30", "a"): {"druid/restoration": 2, "shaman/restoration": 1},
    ("q30", "b"): {"paladin/retribution": 2, "warrior/arms": 1},
}
