"""Questions q51 to q74: personality questions that tell classes apart, asked only in confidence mode (the "adaptive" tier).

When the Oracle cannot decide among its three leading classes it needs questions where each answer belongs to a different class.
The first fifty questions have a good separator for every trio of classes but few of them: the trio with the least evidence had one
question that told its three classes apart well, and a person who is a blend of several classes needs several. These twenty-four are
aimed at that gap. The four primary classes of each question were chosen by a greedy covering design (every trio of the nine
classes gets a question that separates all three, many times over), and the questions are written to fit them:

  q51 to q60  ten four-answer choices
  q61 to q67  seven rankings of four items (the full order shows how a person splits their preference among their top classes)
  q68 to q74  seven six-point splits (the split shows the proportions)

Every answer names one class as its primary (2 points) and a different one as its secondary (1 point), and no two answers of a
question share either. The trait weights come from the primary class (its two characteristic traits, 2 and 1), so class and trait tell
the same story. There are no direct specialization weights: these questions settle the class, and the questions q31 to q50 and the
trait profiles settle the specialization within it. The associations are playstyle lore and a best guess, like all of them.
"""
from __future__ import annotations

from .models import Answer, Question

#: The two traits that characterize each class, as (first, second); an answer takes both from its primary class.
CLASS_TRAITS = {
    "druid": ("wild", "healer"), "hunter": ("freedom", "focus"), "mage": ("scholar", "focus"), "paladin": ("duty", "guardian"),
    "priest": ("healer", "bond"), "rogue": ("trickster", "shadow"), "shaman": ("bond", "instinct"), "warlock": ("shadow", "power"),
    "warrior": ("power", "instinct"),
}

#: Each answer is (text, primary class, secondary class).
CLASS_QUESTIONS: dict[str, dict] = {
    "q51": dict(type="choice", text="A stranger knocks at your door in a storm and asks for shelter. What is your first thought?", answers=[
        ("What is this person hiding, and why did they pick my door?", "rogue", "hunter"),
        ("The storm brought them to me. Let them in and share what the house has.", "shaman", "druid"),
        ("Let them in, and stand between them and the door in case they brought trouble.", "warrior", "paladin"),
        ("Anyone in need owes a debt. Let them in, and see what they can offer in return.", "warlock", "mage"),
    ]),
    "q52": dict(type="choice", text="Your group is stuck at a river with no bridge and night is coming. What do you suggest?", answers=[
        ("Scout up and down the bank. There is always a place where animals cross.", "hunter", "druid"),
        ("Ford it now, and I will go first.", "warrior", "paladin"),
        ("Make camp and keep everyone calm. Morning will show us a way.", "priest", "shaman"),
        ("Work out how deep it is and where the current is weakest, then choose the crossing.", "mage", "rogue"),
    ]),
    "q53": dict(type="choice", text="A friend asks for your honest advice about a risky plan. What do you say?", answers=[
        ("Suggest waiting a season. Good plans ripen, and bad ones show themselves.", "druid", "hunter"),
        ("If the prize is big enough, take the risk. Just know exactly what it will cost.", "warlock", "rogue"),
        ("Tell them plainly if it is wrong, even if it costs the friendship.", "paladin", "warrior"),
        ("Ask what they are most afraid of, and listen until they have said it.", "priest", "shaman"),
    ]),
    "q54": dict(type="choice", text="You find a sealed letter addressed to someone else. What do you do?", answers=[
        ("Read it. Information only does harm to the people who lack it.", "rogue", "warlock"),
        ("Track where it came from and who has handled it. The trail tells the story.", "hunter", "druid"),
        ("Deliver it unopened. It is not mine to read.", "paladin", "warrior"),
        ("Study the seal, the paper and the handwriting first. They say a lot before you open it.", "mage", "priest"),
    ]),
    "q55": dict(type="choice", text="You are given the night watch over a sleeping camp. How do you spend the hours?", answers=[
        ("Walk the edge of the camp with your weapon ready and let anything that comes find you first.", "warrior", "paladin"),
        ("Sit by the fire and feel the camp breathe. The mood of the place tells you more than any sight.", "shaman", "mage"),
        ("Settle into the shadows, watch the edge of the firelight and miss nothing.", "hunter", "rogue"),
        ("Listen to the night. The animals will tell you what is coming before you see it.", "druid", "priest"),
    ]),
    "q56": dict(type="choice", text="A rival asks you for a truce. What do you do?", answers=[
        ("Accept, and keep a close watch. A truce is a good time to learn their habits.", "rogue", "hunter"),
        ("Invite them to share a meal first. Peace is easier to keep once you have eaten together.", "shaman", "druid"),
        ("Name my price. A truce is a trade like any other.", "warlock", "mage"),
        ("Accept, and offer forgiveness. Grudges only grow.", "priest", "paladin"),
    ]),
    "q57": dict(type="choice", text="You come into a large sum of money you did not expect. What do you do with it?", answers=[
        ("Fund something that protects people who cannot protect themselves.", "paladin", "warrior"),
        ("Put it to work quietly in three places, so that no single loss can touch it.", "rogue", "hunter"),
        ("Buy a piece of wild land and help it recover, for people you will never meet.", "druid", "shaman"),
        ("Buy the one thing that turns it into real power.", "warlock", "mage"),
    ]),
    "q58": dict(type="choice", text="A young apprentice asks you to teach them one thing. What do you choose?", answers=[
        ("How to listen: to people, to the weather, to what the moment is asking for.", "shaman", "hunter"),
        ("How to ask the right question and keep going until it is answered.", "mage", "warlock"),
        ("How to be gentle with themselves and with others.", "priest", "druid"),
        ("How to keep a promise when it gets hard.", "paladin", "warrior"),
    ]),
    "q59": dict(type="choice", text="A contest offers a great prize to the winner. How do you enter?", answers=[
        ("Offer the judges something they cannot refuse.", "warlock", "shaman"),
        ("Find the rules and the scoring. The winner is whoever understands them best.", "mage", "priest"),
        ("Watch the first rounds from the edge, learn how each rival moves, then pick your moment.", "hunter", "rogue"),
        ("Straight into the arena. Strength settles it.", "warrior", "paladin"),
    ]),
    "q60": dict(type="choice", text="A rumor spreads that you did something you did not do. How do you deal with it?", answers=[
        ("Wait. Rumors fade, and meanwhile you learn who stays loyal.", "hunter", "druid"),
        ("Find who started it and make them quietly regret it.", "rogue", "warlock"),
        ("Talk with the people it hurts. A story is easier to mend when the whole group is in the room.", "shaman", "priest"),
        ("Face the people spreading it and set the record straight in public.", "paladin", "warrior"),
    ]),
    "q61": dict(type="ranking", text="Rank these ways to spend a free afternoon from the one you would most like to the one you would least like.", answers=[
        ("Working through a puzzle nobody has solved.", "mage", "rogue"),
        ("Sitting with someone who could use the company.", "priest", "paladin"),
        ("Training outdoors until you are tired and satisfied.", "warrior", "hunter"),
        ("Walking somewhere wild with no plan.", "druid", "shaman"),
    ]),
    "q62": dict(type="ranking", text="Rank these ways of crossing a wild country from the one you would most like to the one you would least like.", answers=[
        ("Following the seasons, with the herds and the birds.", "druid", "priest"),
        ("By the back roads that only smugglers know.", "rogue", "mage"),
        ("With a bound spirit that scouts ahead and answers to you.", "warlock", "shaman"),
        ("Alone and on foot, living off what you can track.", "hunter", "warrior"),
    ]),
    "q63": dict(type="ranking", text="Rank these gifts for a friend from the one you would most like to give to the one you would least like.", answers=[
        ("An hour of your full attention whenever they need it.", "priest", "mage"),
        ("A promise, kept for the rest of your life.", "paladin", "warrior"),
        ("A favor they will remember, and feel they owe.", "warlock", "rogue"),
        ("A seat at your fire whenever the weather turns.", "shaman", "druid"),
    ]),
    "q64": dict(type="ranking", text="Rank these places to live from the one you would most like to the one you would least like.", answers=[
        ("A quiet farmstead where the seasons set the schedule.", "druid", "priest"),
        ("A crowded port city, full of strangers and side streets.", "rogue", "warlock"),
        ("A village high in the mountains, close to the weather and to your neighbors.", "shaman", "hunter"),
        ("A border fortress with a hard winter and a harder garrison.", "warrior", "paladin"),
    ]),
    "q65": dict(type="ranking", text="Rank these ways of settling a dispute from the one you would most like to use to the one you would least like.", answers=[
        ("Lay out the evidence so completely that nothing is left to argue about.", "mage", "warlock"),
        ("Sit both sides down and help each hear the other.", "priest", "paladin"),
        ("Stay out of it until the facts are plain, then say one thing.", "hunter", "rogue"),
        ("Settle it in a fair fight and shake hands afterward.", "warrior", "shaman"),
    ]),
    "q66": dict(type="ranking", text="Rank these roles in a traveling troupe from the one you would most like to play to the one you would least like.", answers=[
        ("The one who leads the songs and brings everyone together.", "shaman", "priest"),
        ("The one who bargains with the patrons and keeps the troupe in funds.", "warlock", "rogue"),
        ("The one who writes the script and knows how every piece fits.", "mage", "paladin"),
        ("The one who keeps the horses and wagons, and knows every road.", "druid", "hunter"),
    ]),
    "q67": dict(type="ranking", text="Rank these things you might hear said about you at the end of your life, from the one you would most like to the one you would least like.", answers=[
        ("They went their own way, and went it well.", "hunter", "shaman"),
        ("They never broke their word.", "paladin", "warrior"),
        ("They were always one step ahead of everyone.", "rogue", "mage"),
        ("They made every room kinder.", "priest", "druid"),
    ]),
    "q68": dict(type="allocation", text="You have six days before a hard journey begins. How do you divide them?", answers=[
        ("Walking the first stretch yourself and scouting what lies ahead.", "hunter", "druid"),
        ("Settling your affairs and making sure those you leave are safe.", "paladin", "warrior"),
        ("Studying maps, accounts and anything written about the road.", "mage", "priest"),
        ("Arranging favors and debts that will matter along the way.", "warlock", "rogue"),
    ]),
    "q69": dict(type="allocation", text="You have six evenings in a festival week. How do you divide them?", answers=[
        ("Dancing and drumming around the big fire.", "shaman", "hunter"),
        ("Helping with the quiet jobs: cooking, clearing up and sitting with the elders.", "priest", "mage"),
        ("Wrestling, racing and every contest on offer.", "warrior", "paladin"),
        ("Slipping away to the meadows and woods at the edge of town.", "druid", "rogue"),
    ]),
    "q70": dict(type="allocation", text="You have six hours to prepare for a trial that will decide your future. How do you divide them?", answers=[
        ("Arranging a bargain so that you come out ahead whichever way it goes.", "warlock", "shaman"),
        ("Training your body and your nerve.", "warrior", "hunter"),
        ("Learning everything about the judges, the witnesses and the room.", "rogue", "mage"),
        ("Going over what is right, and what you owe the people who will judge you.", "paladin", "priest"),
    ]),
    "q71": dict(type="allocation", text="You have six months to build a new life in a place you have never been. How do you divide the time?", answers=[
        ("Visiting neighbors, listening to their troubles and being useful.", "priest", "paladin"),
        ("Reading everything: the histories, the records, how the town really works.", "mage", "warlock"),
        ("Exploring alone until you know the land better than the locals do.", "hunter", "rogue"),
        ("Planting something and learning how the place grows.", "druid", "shaman"),
    ]),
    "q72": dict(type="allocation", text="You have six nights at a crossroads inn. How do you divide them?", answers=[
        ("Working the room, learning who has coin and who owes whom.", "rogue", "warrior"),
        ("Singing and telling stories with whoever is at the fire.", "shaman", "priest"),
        ("Sleeping in the stable, close to the horses and the weather.", "druid", "hunter"),
        ("Making a private deal with the most dangerous guest.", "warlock", "mage"),
    ]),
    "q73": dict(type="allocation", text="A village needs a new shelter before winter, and you have six days. How do you divide your effort?", answers=[
        ("Organizing the work fairly, so that nobody is left out.", "paladin", "priest"),
        ("Gathering everyone to sing and work together, so spirits stay high.", "shaman", "mage"),
        ("Hauling timber and stone, the heaviest work of all.", "warrior", "rogue"),
        ("Finding game and firewood so the builders can eat.", "hunter", "druid"),
    ]),
    "q74": dict(type="allocation", text="You have six minutes to act in a crisis at a crowded market. How do you divide your attention?", answers=[
        ("Getting between the danger and the people closest to it.", "paladin", "warrior"),
        ("Watching the edges of the crowd for anyone who is up to something.", "rogue", "hunter"),
        ("Calming the frightened and helping the hurt.", "priest", "druid"),
        ("Working out what is actually happening and what will happen next.", "mage", "warlock"),
    ]),
}

CLASS_ORDER = list(CLASS_QUESTIONS)

_FORMS = {
    "choice": "Choice: every answer names a different primary class",
    "ranking": "Ranking: four items, each with a different primary class, so the order shows how the respondent splits their preference",
    "allocation": "Allocation: four items, each with a different primary class, so the split shows the proportions",
}


def _rationale(d: dict) -> str:
    primaries = ", ".join(p.capitalize() for _, p, _ in d["answers"])
    return (f"{_FORMS[d['type']]} ({primaries}). Each answer gives its primary class 2 points and a different secondary class 1; its two traits are its primary class's. "
            "The question separates those classes and carries no direct specialization weights.")


def build_class_questions() -> list[Question]:
    """The twenty-four class-separating confidence-mode-only questions, in order."""
    out = []
    for qid in CLASS_ORDER:
        d = CLASS_QUESTIONS[qid]
        answers = [
            Answer(id=chr(ord("a") + i), text=text, class_weights={p: 2.0, s: 1.0}, trait_weights={CLASS_TRAITS[p][0]: 2.0, CLASS_TRAITS[p][1]: 1.0})
            for i, (text, p, s) in enumerate(d["answers"])
        ]
        out.append(Question(id=qid, text=d["text"], type=d["type"], rationale=_rationale(d), answers=answers, min_length="adaptive"))
    return out
