"""Pydantic models: stored configuration, API requests, and API responses.

The configuration models (``Config`` and everything it contains) are the single
source of truth for quiz content and scoring rules. They are plain data: the
scoring engine in ``scoring.py`` is a pure function of a ``Config`` and a set of
selected answers.
"""
from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------
# Shared field types
# --------------------------------------------------------------------------

#: Non-negative, finite weight. ``allow_inf_nan=False`` rejects NaN/Infinity.
Weight = Annotated[float, Field(ge=0, allow_inf_nan=False)]
#: Stable machine identifier (class, trait, question, answer, build ...).
Slug = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_\-]*$")]
ShortText = Annotated[str, Field(min_length=1, max_length=600)]
LongText = Annotated[str, Field(max_length=4000)]

BuildStatus = Literal["verified", "draft", "unverified", "pending"]
QuestionType = Literal["choice", "scale", "pick_two", "ranking", "allocation"]
QuizLength = Literal["short", "medium", "long"]
#: Shortest to longest. A question with ``min_length`` L is asked in quiz length L and every longer one, so the quizzes are nested.
LENGTHS: tuple[str, ...] = ("short", "medium", "long")
#: "class_id/specialization_id", e.g. "warrior/fury"
SpecKey = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_\-]*/[a-z0-9][a-z0-9_\-]*$", max_length=130)]
SCALE_MIN, SCALE_MAX = 1, 10
ALLOCATION_POINTS = 6   # points a participant spends across the four items of an 'allocation' question

KNOWN_BUILD_PURPOSES = (
    "leveling_pve",
    "solo_leveling",
    "dungeon_healing",
    "dungeon_tanking",
    "dungeon_damage",
    "raid_60",
    "pvp",
    "hybrid",
)

#: Talent points begin at level 10, so a character of level L has L - 9 points.
FIRST_TALENT_LEVEL = 10
MAX_LEVEL = 60


class Strict(BaseModel):
    """Base class that rejects unknown fields, so typos in imports are caught."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------
# Talent catalog (game data imported from outside the application)
# --------------------------------------------------------------------------


class TalentPrerequisite(Strict):
    talent_id: Slug
    rank: int = Field(ge=1, description="Points required in the prerequisite talent.")


class CatalogTalent(Strict):
    id: Slug
    name: ShortText
    tier: int = Field(ge=0, description="Zero-based row within the tree (top row = 0).")
    column: int = Field(ge=0)
    max_rank: int = Field(ge=1)
    requires: list[TalentPrerequisite] = Field(default_factory=list)
    description: LongText = ""


class CatalogTree(Strict):
    id: Slug = Field(description="Matches the specialization id of the same class.")
    name: ShortText
    talents: list[CatalogTalent]


class CatalogClass(Strict):
    id: Slug
    trees: list[CatalogTree]


class TalentCatalog(Strict):
    """Game-version-specific talent data used to validate builds."""

    game: ShortText = "World of Warcraft: Forever"
    client_version: ShortText
    source: ShortText
    retrieved_at: Optional[date] = None
    data_status: Literal["verified", "draft"] = Field(
        default="verified",
        description="'draft' data was not read from the game client; builds can be checked against it but never marked verified.",
    )
    notes: LongText = ""
    source_updated: Optional[date] = Field(
        default=None, description="Date of the newest source behind this data (for example the latest developer notes it reflects).",
    )
    points_per_tier: int = Field(
        default=5,
        ge=0,
        description="Points that must be spent in a tree, in earlier rows, per row of depth.",
    )
    classes: list[CatalogClass]


# --------------------------------------------------------------------------
# Builds
# --------------------------------------------------------------------------


class Build(Strict):
    id: Slug
    class_id: Slug
    specialization_id: Slug
    name: ShortText
    role: Slug = Field(description="Intended role, e.g. melee_damage, ranged_damage, tank, healer.")
    purpose: Slug = "leveling_pve"
    level: int = Field(default=MAX_LEVEL, ge=FIRST_TALENT_LEVEL, le=MAX_LEVEL)
    total_points: int = Field(default=MAX_LEVEL - FIRST_TALENT_LEVEL + 1, ge=0, le=MAX_LEVEL)
    allocations: dict[Slug, Annotated[int, Field(ge=1)]] = Field(default_factory=dict)
    leveling_order: list[Slug] = Field(
        default_factory=list,
        description="Talent ids in the order points are spent (one entry per point, first = level 10).",
    )
    combat_priorities: list[ShortText] = Field(default_factory=list)
    equipment_notes: list[ShortText] = Field(default_factory=list)
    professions: list[ShortText] = Field(default_factory=list)
    source: Annotated[str, Field(max_length=600)] = ""
    source_url: Annotated[str, Field(max_length=600)] = ""
    calculator_url: Annotated[str, Field(max_length=600)] = ""
    verified_at: Optional[date] = None
    client_version: Annotated[str, Field(max_length=100)] = ""
    status: BuildStatus = "pending"
    is_default: bool = False
    notes: LongText = ""


class BuildValidation(Strict):
    valid: bool
    can_verify: bool
    complete: bool
    errors: list[str]
    warnings: list[str]
    verification_problems: list[str]
    points_spent: int
    points_remaining: int
    expected_points: int
    tree_distribution: dict[str, int]
    catalog_available: bool


class ResolvedTalent(Strict):
    talent_id: str
    name: Optional[str] = None
    tree_id: Optional[str] = None
    tier: Optional[int] = None
    rank: int
    max_rank: Optional[int] = None


class TreeTalent(Strict):
    id: str
    name: str
    tier: int
    column: int
    max_rank: int
    rank: int = 0
    requires: list[TalentPrerequisite] = Field(default_factory=list)
    description: str = ""


class TreeView(Strict):
    """One talent tree of the class with the build's ranks filled in, for drawing the tree."""

    id: str
    name: str
    points: int = 0
    talents: list[TreeTalent] = Field(default_factory=list)


class CatalogInfo(Strict):
    """Where the talent data behind a build came from and how current it is."""

    client_version: str = ""
    data_status: str = "draft"
    source: str = ""
    source_updated: Optional[date] = None
    retrieved_at: Optional[date] = None
    points_per_tier: int = 5
    notes: str = ""


class BuildDetail(Build):
    """A build plus derived display data."""

    points_spent: int = 0
    points_remaining: int = 0
    tree_distribution: dict[str, int] = Field(default_factory=dict)
    tree_distribution_text: str = ""
    allocation_pending: bool = True
    talents: list[ResolvedTalent] = Field(default_factory=list)
    status_note: str = ""
    trees: list[TreeView] = Field(default_factory=list, description="The class's talent trees with this build's ranks (empty without talent data).")
    catalog_info: Optional[CatalogInfo] = None
    validation: Optional[BuildValidation] = None


class BuildSummary(Strict):
    id: str
    name: str
    purpose: str
    role: str
    status: BuildStatus
    is_default: bool
    points_spent: int
    total_points: int
    allocation_pending: bool


# --------------------------------------------------------------------------
# Quiz configuration
# --------------------------------------------------------------------------


class Trait(Strict):
    id: Slug
    name: ShortText
    description: LongText = ""
    interpretation: LongText = Field(default="", description="Sentence used in the personality reading.")


class SpecGuide(Strict):
    """What a player of this specialization needs to know about roles and gear. General guidance that names no items."""

    dungeon_role: LongText = ""
    raid_role: LongText = ""
    note: LongText = Field(default="", description="A caveat shown with the guidance, for example that it is general and may not match the game.")
    gear: list[LongText] = Field(default_factory=list, description="What to look out for on gear.")
    competes_with: list[LongText] = Field(default_factory=list, description="Which specializations compete for similar gear.")


class Specialization(Strict):
    id: Slug
    name: ShortText
    description: LongText = ""
    overview: LongText = Field(default="", description="What this specialization does, in the quiz's own words.")
    guide: SpecGuide = Field(default_factory=SpecGuide)
    role: Slug
    trait_multipliers: dict[Slug, Weight] = Field(
        description="Ordered trait -> multiplier map. Order is primary, secondary, tertiary ...",
    )


class GameClass(Strict):
    id: Slug
    name: ShortText
    description: LongText = ""
    overview: LongText = Field(default="", description="What this class does, in the quiz's own words.")
    overview_url: Annotated[str, Field(max_length=600)] = Field(
        default="", description="Where the official description the overview was written from can be read."
    )
    specializations: list[Specialization]


class Answer(Strict):
    """One selectable answer. For 'scale' questions the two answers are the 'agree' and 'disagree' poles."""

    id: Slug
    text: ShortText
    class_weights: dict[Slug, Weight] = Field(default_factory=dict)
    trait_weights: dict[Slug, Weight] = Field(default_factory=dict)
    spec_weights: dict[SpecKey, Weight] = Field(
        default_factory=dict, description="Direct specialization weights keyed 'class/spec'."
    )


class Question(Strict):
    id: Slug
    text: ShortText
    enabled: bool = True
    type: QuestionType = Field(
        default="choice",
        description=(
            "choice: pick one answer. pick_two: pick two of four (weights add). "
            "scale: rate 1-10; answers 'agree' and 'disagree' define the two poles. "
            "ranking: put the four answers in order. allocation: spend six points across the four answers."
        ),
    )
    low_label: Annotated[str, Field(max_length=80)] = "Strongly disagree"
    high_label: Annotated[str, Field(max_length=80)] = "Strongly agree"
    rationale: LongText = Field(default="", description="Administrator note: why the weights are what they are.")
    min_length: QuizLength = Field(
        default="long",
        description="The shortest quiz length that asks this question: short, medium or long. Longer quizzes also ask it.",
    )
    answers: list[Answer]


#: Placeholders a share template may use, in the order the admin interface lists them. Keep in step with SHARE_FIELDS in static/share.js.
SHARE_FIELDS = (
    "class", "spec", "spec_score", "class_scores", "traits", "confidence", "questions", "quiz_length", "also_class", "also_spec",
    "next_spec", "title", "link",
)

#: The blurb a participant copies to share a result, until an administrator changes it. Keep in step with static/share.js.
DEFAULT_SHARE_TEMPLATE = (
    "The stars say I'm a {spec} {class}! ✦\n"
    "Class scores: {class_scores} ({confidence}, {questions} questions; relative scores).\n"
    "Also in the stars: {also_spec} {also_class}. Closest in {class}: {next_spec}.\n"
    "Find yours on the Forever Character Oracle: {link}"
)


class QuizMeta(Strict):
    id: Slug = "wow-forever-oracle"
    title: ShortText = "The Stars Have Chosen"
    subtitle: Annotated[str, Field(max_length=300)] = ""
    share_template: Annotated[str, Field(min_length=1, max_length=1000)] = Field(
        default=DEFAULT_SHARE_TEMPLATE,
        description="The text a participant copies to share a result. {placeholders} (see SHARE_FIELDS) are filled in.",
    )
    expected_question_count: int = Field(default=16, ge=1)
    answers_per_question: int = Field(default=4, ge=2)


class ConfidenceMargins(Strict):
    strong: Weight = 3.0
    moderate: Weight = 1.25


class AdaptiveSettings(Strict):
    """Confidence mode: ask the most informative questions until the Oracle is sure of one specialization.

    The model behind the confidence figure is a logit choice model of how a person of each class/specialization type would answer;
    see docs/oracle-math.pdf. ``sharpness_*`` say how strongly an answer reveals the type (higher = people answer more consistently
    with their type, so fewer questions are needed and the confidence is more easily reached).
    """

    enabled: bool = True
    min_questions: int = Field(default=10, ge=1, description="Never reveal before this many questions have been answered.")
    max_questions: int = Field(default=30, ge=1, description="Reveal after this many questions even if the Oracle is not sure.")
    confidence: float = Field(default=0.90, gt=0, lt=1, description="Stop once the recommended specialization has this probability.")
    sharpness_class: float = Field(default=1.0, gt=0, le=10, description="How strongly a class's weights steer an answer (lambda_c).")
    sharpness_spec: float = Field(default=0.35, gt=0, le=10, description="How strongly a specialization's profile steers an answer (lambda_s).")


class ScoringSettings(Strict):
    algorithm_version: ShortText = "1.0.0"
    class_tie_break_order: list[Slug]
    confidence_margins: ConfidenceMargins = Field(default_factory=ConfidenceMargins)
    spec_weight_multiplier: Weight = Field(
        default=1.0,
        description="Scales the direct specialization weights before they are added to P_s. The seed uses 3.0: "
                    "at 1.0 two specializations cannot be reached by any answers.",
    )
    adaptive: AdaptiveSettings = Field(default_factory=AdaptiveSettings)
    tie_break_notes: LongText = (
        "Equal class scores are resolved by class_tie_break_order; equal specialization "
        "scores by the specialization order within the class; equal trait scores by trait order. "
        "Scores are compared after rounding to 9 decimal places."
    )


class Config(Strict):
    revision: int = Field(default=1, ge=1)
    quiz: QuizMeta = Field(default_factory=QuizMeta)
    scoring: ScoringSettings
    traits: list[Trait]
    classes: list[GameClass]
    questions: list[Question]
    builds: list[Build] = Field(default_factory=list)
    talent_catalog: Optional[TalentCatalog] = None

    # -- lookup helpers -----------------------------------------------------
    def get_class(self, class_id: str) -> Optional[GameClass]:
        return next((c for c in self.classes if c.id == class_id), None)

    def get_spec(self, class_id: str, spec_id: str) -> Optional[Specialization]:
        cls = self.get_class(class_id)
        return next((s for s in cls.specializations if s.id == spec_id), None) if cls else None

    def get_question(self, question_id: str) -> Optional[Question]:
        return next((q for q in self.questions if q.id == question_id), None)

    def get_trait(self, trait_id: str) -> Optional[Trait]:
        return next((t for t in self.traits if t.id == trait_id), None)

    def get_build(self, build_id: str) -> Optional[Build]:
        return next((b for b in self.builds if b.id == build_id), None)

    def enabled_questions(self) -> list[Question]:
        return [q for q in self.questions if q.enabled]


# --------------------------------------------------------------------------
# Participant-facing quiz
# --------------------------------------------------------------------------


class PublicAnswer(BaseModel):
    id: str
    text: str


class PublicQuestion(BaseModel):
    id: str
    text: str
    type: str = "choice"
    answers: list[PublicAnswer] = Field(default_factory=list, description="Empty for scale questions.")
    low_label: Optional[str] = None
    high_label: Optional[str] = None
    scale_min: Optional[int] = None
    scale_max: Optional[int] = None
    pick_count: Optional[int] = None
    points: Optional[int] = Field(default=None, description="Points to spend, for 'allocation' questions.")


class PublicLength(BaseModel):
    id: str
    name: str
    description: str
    question_count: int
    minutes: int = Field(description="A rough time to finish, assuming about twenty seconds a question.")
    question_ids: list[str] = Field(description="The questions of this length, in quiz order (for confidence mode: the pool it chooses from).")
    adaptive: bool = Field(default=False, description="True for confidence mode, whose questions are chosen one at a time.")
    minutes_max: Optional[int] = None
    min_questions: Optional[int] = None
    max_questions: Optional[int] = None
    confidence: Optional[float] = None


class PublicQuiz(BaseModel):
    quiz_id: str
    title: str
    subtitle: str
    question_count: int = Field(description="Questions in the longest quiz.")
    questions: list[PublicQuestion] = Field(description="Every question; a length lists which of them it asks.")
    lengths: list[PublicLength] = Field(default_factory=list, description="The quiz lengths on offer, shortest first.")
    default_length: str = "long"
    share_template: str = DEFAULT_SHARE_TEMPLATE


# --------------------------------------------------------------------------
# Classes listing
# --------------------------------------------------------------------------


class SpecListing(BaseModel):
    id: str
    name: str
    role: str
    description: str
    trait_multipliers: Optional[dict[str, float]] = None
    builds: Optional[list[BuildSummary]] = None


class ClassListing(BaseModel):
    id: str
    name: str
    description: str
    overview: str = ""
    overview_url: str = ""
    specializations: list[SpecListing]


class ClassesResponse(BaseModel):
    classes: list[ClassListing]


class VersionInfo(BaseModel):
    version: str
    build: str
    commit: str
    date: str
    developer: str
    developer_url: str


class SpecTraitInfo(BaseModel):
    """One trait of a specialization's profile: what defines it, in order of weight."""

    id: str
    name: str
    description: str = ""
    interpretation: str = ""
    multiplier: float
    order: int = Field(description="1 for the primary trait, 2 for the secondary, and so on.")


class SpecPage(BaseModel):
    """Everything the page of one specialization shows: its class, overview, defining traits, role and gear guide, and build."""

    class_id: str
    class_name: str
    class_description: str = ""
    class_overview: str = ""
    overview_url: str = ""
    id: str
    name: str
    role: str
    description: str = ""
    overview: str = ""
    guide: Optional[SpecGuide] = None
    traits: list[SpecTraitInfo] = Field(default_factory=list)
    build: Optional[BuildDetail] = None


# --------------------------------------------------------------------------
# Confidence mode
# --------------------------------------------------------------------------


class AdaptiveRequest(Strict):
    answers: dict[str, str] = Field(description="question id -> response id, for the questions answered so far")


class TypeProbability(BaseModel):
    class_id: str
    class_name: str
    specialization_id: str
    specialization_name: str
    probability: float


class AdaptiveStatus(BaseModel):
    """Where a confidence-mode quiz stands: how sure the Oracle is, whether to stop, and which question to ask next."""

    answered: int
    min_questions: int
    max_questions: int
    threshold: float
    confidence: float = Field(description="Probability the model gives the specialization the scoring currently recommends.")
    recommended: TypeProbability
    top: list[TypeProbability] = Field(description="The five most probable class/specialization pairs.")
    entropy: float = Field(description="Uncertainty about the type in nats (ln 27 = 3.30 before any answer).")
    done: bool
    reason: Optional[Literal["confident", "limit"]] = Field(
        default=None, description="'confident': the threshold was reached; 'limit': the question limit (or the pool) ran out."
    )
    can_reveal: bool = Field(description="True once the minimum number of questions has been answered.")
    next_question_id: Optional[str] = None
    expected_gain: Optional[float] = Field(default=None, description="Expected reduction of the uncertainty (nats) from the next question.")


# --------------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------------


class EvaluateRequest(Strict):
    answers: dict[str, str] = Field(description="question id -> answer id")
    length: Literal["short", "medium", "long", "adaptive"] = Field(
        default="long",
        description="Which quiz length these answers belong to; only its questions are scored. 'adaptive' scores exactly the questions answered.",
    )
    include_explanation: bool = False
    include_counterfactuals: bool = False
    allow_partial: bool = Field(
        default=False, description="Administrative/debug mode: score an incomplete answer set."
    )


class IdName(BaseModel):
    id: str
    name: str


class ClassScore(BaseModel):
    id: str
    name: str
    score: float
    rank: int
    raw_points: float
    expected_points: float
    gap_to_leader: float
    tied_with_previous: bool = False


class TraitScore(BaseModel):
    id: str
    name: str
    score: float
    rank: int
    raw_points: float
    expected_points: float
    appearances: int = Field(description="Number of selected answers that gave this trait a nonzero weight.")
    tied_with_previous: bool = False


class SpecTerm(BaseModel):
    trait_id: str
    trait_name: str
    multiplier: float
    trait_score: float
    contribution: float


class SpecScore(BaseModel):
    class_id: str
    id: str
    name: str
    role: str
    score: float
    rank: int
    tied_with_previous: bool = False
    direct_score: float = Field(default=0.0, description="Contribution of direct per-question specialization weights.")
    terms: list[SpecTerm]


class ContributionCell(BaseModel):
    raw: float
    baseline: float
    adjusted: float


class QuestionExplanation(BaseModel):
    question_id: str
    question_text: str
    question_type: str = "choice"
    answer_id: str
    answer_text: str
    class_contributions: dict[str, ContributionCell]
    trait_contributions: dict[str, ContributionCell]
    spec_contributions: dict[str, ContributionCell] = Field(
        default_factory=dict, description="Direct specialization weights; only specializations this question touches."
    )
    class_adjusted_sum: float
    trait_adjusted_sum: float
    leader_margin_effect: float = Field(
        description="This answer's adjusted contribution to the winning class minus the runner-up class."
    )


class TieBreak(BaseModel):
    scope: str
    scope_id: Optional[str] = None
    tied: list[str]
    score: float
    positions: list[int]
    rule: str


class Counterfactual(BaseModel):
    question_id: str
    answer_id: str
    answer_text: str
    primary_class_id: str
    primary_class_name: str
    primary_specialization_id: str
    primary_specialization_name: str
    class_changed: bool
    specialization_changed: bool
    class_gap: float


class Explanation(BaseModel):
    questions: list[QuestionExplanation]
    tie_breaks: list[TieBreak]
    formulas: dict[str, str]
    counterfactuals: Optional[list[Counterfactual]] = None


class Confidence(BaseModel):
    label: str
    probability: Optional[float] = Field(
        default=None, description="Probability the model gives the recommended specialization given the answers (confidence model)."
    )
    class_gap: float
    strong_margin: float
    moderate_margin: float
    note: str


class SpecPick(BaseModel):
    class_id: str
    class_name: str
    id: str
    name: str
    role: str
    score: float
    description: str
    guide: Optional[SpecGuide] = None
    build: Optional[BuildDetail] = None


class Alternatives(BaseModel):
    alternative_class: ClassScore
    alternative_specialization: SpecPick
    second_specialization_in_primary_class: SpecPick


class ResultBlock(BaseModel):
    primary_class: ClassScore
    primary_class_description: str
    class_overview: str = ""
    specialization_overview: str = ""
    overview_url: str = ""
    primary_specialization: SpecPick
    dominant_traits: list[TraitScore]
    personality_interpretation: str
    specialization_interpretation: str
    confidence: Confidence
    build: Optional[BuildDetail] = None


class Rankings(BaseModel):
    classes: list[ClassScore]
    specializations: list[SpecScore] = Field(description="Specializations of the winning class.")
    alternative_class_specializations: list[SpecScore]
    all_specializations: list[SpecScore]
    traits: list[TraitScore]


class Metadata(BaseModel):
    config_revision: int
    algorithm_version: str
    answered_questions: int
    total_questions: int
    complete: bool
    provisional: bool
    missing_questions: list[str]
    spec_weight_multiplier: float = 1.0
    quiz_length: str = "long"
    scores_are_probabilities: bool = False
    note: str = (
        "Scores are relative compatibility indicators on a scale with no fixed maximum. "
        "Confidence labels are heuristics based on the gap between the top two class scores."
    )


class EvaluationResponse(BaseModel):
    result: ResultBlock
    alternatives: Alternatives
    rankings: Rankings
    explanation: Optional[Explanation] = None
    metadata: Metadata


# --------------------------------------------------------------------------
# Simulation
# --------------------------------------------------------------------------


class AnswerOverride(Strict):
    question_id: Slug
    answer_id: Slug
    class_weights: Optional[dict[Slug, Weight]] = None
    trait_weights: Optional[dict[Slug, Weight]] = None
    spec_weights: Optional[dict[SpecKey, Weight]] = None


class SpecOverride(Strict):
    class_id: Slug
    specialization_id: Slug
    trait_multipliers: dict[Slug, Weight]


class SimulateRequest(Strict):
    answers: dict[str, str]
    length: QuizLength = "long"
    overrides: list[AnswerOverride] = Field(default_factory=list)
    specialization_overrides: list[SpecOverride] = Field(default_factory=list)
    include_explanation: bool = False


class ExpandRequest(Strict):
    question: Question


class ExpandedOption(BaseModel):
    id: str
    label: str
    class_raw: dict[str, float]
    trait_raw: dict[str, float]
    spec_raw: dict[str, float]
    class_adjusted: dict[str, float]
    trait_adjusted: dict[str, float]
    spec_adjusted: dict[str, float]


class QuestionExpansion(BaseModel):
    """Every possible response to one question with its raw weights and adjusted (baseline-subtracted) contributions."""

    type: str
    options: list[ExpandedOption]
    class_baseline: dict[str, float]
    trait_baseline: dict[str, float]
    spec_baseline: dict[str, float]


class ScoreDiff(BaseModel):
    id: str
    name: str
    original: float
    simulated: float
    difference: float


class SpecDiff(BaseModel):
    class_id: str
    id: str
    name: str
    original: float
    simulated: float
    difference: float


class QuestionInfluence(BaseModel):
    question_id: str
    original_effect: float
    simulated_effect: float


class PrimaryPick(BaseModel):
    class_id: str
    class_name: str
    specialization_id: str
    specialization_name: str


class SimulationResponse(BaseModel):
    original: EvaluationResponse
    simulated: EvaluationResponse
    original_primary: PrimaryPick
    simulated_primary: PrimaryPick
    class_differences: list[ScoreDiff]
    trait_differences: list[ScoreDiff]
    specialization_differences: list[SpecDiff]
    winning_class_changed: bool
    winning_specialization_changed: bool
    question_influence: list[QuestionInfluence] = Field(
        description="Per-question contribution to (winner - runner-up) under each configuration, most influential first."
    )
    overrides_applied: int
    persisted: bool = False


class BatchSimulateRequest(Strict):
    length: QuizLength = "long"
    count: int = Field(default=5000, ge=1, le=20000)
    seed: Optional[int] = None
    overrides: list[AnswerOverride] = Field(default_factory=list)
    specialization_overrides: list[SpecOverride] = Field(default_factory=list)


class FrequencyRow(BaseModel):
    id: str
    name: str
    class_id: Optional[str] = None
    count: int
    frequency: float
    mean_score: Optional[float] = None


class BatchSide(BaseModel):
    class_frequencies: list[FrequencyRow]
    specialization_frequencies: list[FrequencyRow]
    mean_class_gap: float
    close_calls: int = Field(description="Runs whose top two class scores were within the 'moderate' margin.")


class BatchSimulateResponse(BaseModel):
    count: int
    seed: int
    uniform_class_frequency: float
    baseline: BatchSide
    simulated: Optional[BatchSide] = None
    note: str = (
        "Frequencies come from uniformly random answer sets. They diagnose the scoring "
        "rules and say nothing about how real people answer."
    )


# --------------------------------------------------------------------------
# Configuration management
# --------------------------------------------------------------------------


class AnswerPatch(Strict):
    expected_revision: int
    text: Optional[ShortText] = None
    class_weights: Optional[dict[Slug, Weight]] = Field(
        default=None, description="Replaces the whole class weight map; omitted classes become 0."
    )
    trait_weights: Optional[dict[Slug, Weight]] = Field(
        default=None, description="Replaces the whole trait weight map; omitted traits become 0."
    )
    spec_weights: Optional[dict[SpecKey, Weight]] = Field(
        default=None, description="Replaces the whole direct specialization weight map."
    )


class QuestionPatch(Strict):
    expected_revision: int
    text: Optional[ShortText] = None
    enabled: Optional[bool] = None
    low_label: Optional[Annotated[str, Field(min_length=1, max_length=80)]] = None
    high_label: Optional[Annotated[str, Field(min_length=1, max_length=80)]] = None
    rationale: Optional[LongText] = None
    min_length: Optional[QuizLength] = None


class QuizPatch(Strict):
    expected_revision: int
    title: Optional[ShortText] = None
    subtitle: Optional[Annotated[str, Field(max_length=300)]] = None
    share_template: Optional[Annotated[str, Field(min_length=1, max_length=1000)]] = None


class QuizResponse(BaseModel):
    revision: int
    quiz: QuizMeta


class SpecPatch(Strict):
    expected_revision: int
    name: Optional[ShortText] = None
    description: Optional[LongText] = None
    overview: Optional[LongText] = None
    guide: Optional[SpecGuide] = None
    role: Optional[Slug] = None
    trait_multipliers: Optional[dict[Slug, Weight]] = Field(
        default=None, description="Replaces the whole profile; key order is primary, secondary, tertiary ..."
    )


class ClassPatch(Strict):
    expected_revision: int
    name: Optional[ShortText] = None
    description: Optional[LongText] = None
    overview: Optional[LongText] = None


class TraitPatch(Strict):
    expected_revision: int
    name: Optional[ShortText] = None
    description: Optional[LongText] = None
    interpretation: Optional[LongText] = None


class ScoringPatch(Strict):
    expected_revision: int
    adaptive: Optional[AdaptiveSettings] = None
    confidence_margins: Optional[ConfidenceMargins] = None
    spec_weight_multiplier: Optional[Weight] = None
    class_tie_break_order: Optional[list[Slug]] = None


class ImportRequest(Strict):
    expected_revision: int
    config: Config
    description: Optional[str] = None


class ResetRequest(Strict):
    expected_revision: int
    confirm: bool = False


class RestoreRequest(Strict):
    expected_revision: int


class MutationResult(BaseModel):
    revision: int
    description: str
    backup_path: Optional[str] = None


class AnswerResponse(BaseModel):
    revision: int
    question_id: str
    answer: Answer


class QuestionResponse(BaseModel):
    revision: int
    question: Question


class SpecResponse(BaseModel):
    revision: int
    class_id: str
    specialization: Specialization


class ClassResponse(BaseModel):
    revision: int
    game_class: GameClass


class TraitResponse(BaseModel):
    revision: int
    trait: Trait


class ScoringResponse(BaseModel):
    revision: int
    scoring: ScoringSettings


class HistoryEntry(BaseModel):
    revision: int
    created_at: str
    change_type: str
    change_description: str
    change_detail: Optional[dict] = None


class Health(BaseModel):
    status: str
    app_version: str
    algorithm_version: str
    config_revision: int
    game_target: str
    class_count: int
    specialization_count: int
    question_count: int
    admin_auth_required: bool


# --------------------------------------------------------------------------
# Build endpoints
# --------------------------------------------------------------------------


class BuildCreate(Strict):
    expected_revision: int
    build: Build


class BuildPatch(Strict):
    expected_revision: int
    name: Optional[ShortText] = None
    role: Optional[Slug] = None
    purpose: Optional[Slug] = None
    level: Optional[int] = Field(default=None, ge=FIRST_TALENT_LEVEL, le=MAX_LEVEL)
    total_points: Optional[int] = Field(default=None, ge=0, le=MAX_LEVEL)
    allocations: Optional[dict[Slug, Annotated[int, Field(ge=1)]]] = None
    leveling_order: Optional[list[Slug]] = None
    combat_priorities: Optional[list[ShortText]] = None
    equipment_notes: Optional[list[ShortText]] = None
    professions: Optional[list[ShortText]] = None
    source: Optional[Annotated[str, Field(max_length=600)]] = None
    source_url: Optional[Annotated[str, Field(max_length=600)]] = None
    calculator_url: Optional[Annotated[str, Field(max_length=600)]] = None
    verified_at: Optional[date] = None
    client_version: Optional[Annotated[str, Field(max_length=100)]] = None
    status: Optional[BuildStatus] = None
    notes: Optional[LongText] = None


class BuildValidateRequest(Strict):
    build: Build


class BuildResponse(BaseModel):
    revision: int
    build: BuildDetail


class BuildList(BaseModel):
    builds: list[BuildDetail]


class DefaultBuildRequest(Strict):
    expected_revision: int


class CatalogUpdate(Strict):
    expected_revision: int
    catalog: Optional[TalentCatalog] = Field(
        default=None, description="The new talent catalog, or null to remove the current one."
    )


class CatalogSummaryTree(BaseModel):
    id: str
    name: str
    talent_count: int


class CatalogSummaryClass(BaseModel):
    id: str
    trees: list[CatalogSummaryTree]


class CatalogResponse(BaseModel):
    revision: int
    available: bool
    client_version: Optional[str] = None
    source: Optional[str] = None
    retrieved_at: Optional[date] = None
    data_status: Optional[str] = None
    notes: Optional[str] = None
    points_per_tier: Optional[int] = None
    classes: list[CatalogSummaryClass] = Field(default_factory=list)
    catalog: Optional[TalentCatalog] = None
    downgraded_builds: list[str] = Field(default_factory=list)
