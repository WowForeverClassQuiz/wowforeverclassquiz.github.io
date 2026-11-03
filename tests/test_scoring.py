"""Unit tests for the pure scoring engine and the seed dataset."""
import itertools
from collections import Counter
import random

import pytest

from app import scoring
from app.models import AnswerOverride, SpecOverride
from app.scoring import (
    IncompleteAssessmentError,
    UnknownAnswerError,
    UnknownQuestionError,
    compile_config,
    evaluate,
)
from app.seed import build_default_config

from .conftest import first_answers

# Independent transcription of the specification's encoding: [primary class, secondary class | primary trait, secondary trait]
GOLDEN = """
q01 a druid hunter wild healer
q01 b mage shaman scholar focus
q01 c priest paladin duty guardian
q01 d warlock rogue shadow scholar
q02 a paladin warrior guardian duty
q02 b mage rogue focus scholar
q02 c priest druid healer bond
q02 d warlock shaman shadow power
q03 a rogue hunter trickster freedom
q03 b warrior shaman instinct bond
q03 c druid priest wild healer
q03 d mage warlock scholar shadow
q04 a hunter druid wild instinct
q04 b shaman mage power wild
q04 c paladin priest duty focus
q04 d rogue warlock shadow trickster
q05 a rogue hunter trickster instinct
q05 b warrior paladin guardian power
q05 c shaman druid wild instinct
q05 d mage warlock scholar focus
q06 a hunter warlock bond wild
q06 b paladin priest duty healer
q06 c mage rogue scholar shadow
q06 d druid shaman wild freedom
q07 a mage priest focus guardian
q07 b druid shaman healer wild
q07 c warrior shaman power instinct
q07 d rogue warlock shadow trickster
q08 a paladin warrior guardian duty
q08 b mage rogue focus scholar
q08 c priest druid healer bond
q08 d warlock hunter power freedom
q09 a shaman warrior instinct power
q09 b warlock priest shadow scholar
q09 c hunter paladin bond guardian
q09 d rogue druid trickster wild
q10 a druid hunter wild bond
q10 b rogue mage focus trickster
q10 c priest paladin healer duty
q10 d warlock shaman shadow power
q11 a mage paladin focus scholar
q11 b druid warlock wild shadow
q11 c warrior hunter guardian instinct
q11 d rogue priest trickster healer
q12 a paladin priest guardian duty
q12 b warrior shaman power instinct
q12 c mage warlock scholar focus
q12 d rogue hunter trickster freedom
q13 a druid shaman healer wild
q13 b warrior paladin power duty
q13 c mage priest scholar focus
q13 d rogue warlock shadow freedom
q14 a priest druid healer bond
q14 b paladin warrior duty guardian
q14 c mage rogue focus scholar
q14 d warlock shaman shadow power
q15 a hunter druid wild freedom
q15 b shaman warrior bond instinct
q15 c priest paladin healer guardian
q15 d mage warlock scholar shadow
q16 a rogue mage trickster focus
q16 b priest paladin healer duty
q16 c druid hunter wild bond
q16 d shaman warlock power shadow
"""

PROFILES = {
    ("druid", "balance"): ("scholar", "wild", "focus"),
    ("druid", "feral_combat"): ("wild", "instinct", "freedom"),
    ("druid", "restoration"): ("healer", "bond", "guardian"),
    ("hunter", "beast_mastery"): ("bond", "wild", "guardian"),
    ("hunter", "marksmanship"): ("focus", "freedom", "scholar"),
    ("hunter", "survival"): ("instinct", "trickster", "wild"),
    ("mage", "arcane"): ("scholar", "focus", "shadow"),
    ("mage", "fire"): ("power", "instinct", "freedom"),
    ("mage", "frost"): ("focus", "guardian", "scholar"),
    ("paladin", "holy"): ("healer", "duty", "bond"),
    ("paladin", "protection"): ("guardian", "duty", "focus"),
    ("paladin", "retribution"): ("duty", "power", "instinct"),
    ("priest", "discipline"): ("focus", "healer", "scholar"),
    ("priest", "holy"): ("healer", "bond", "duty"),
    ("priest", "shadow"): ("shadow", "scholar", "power"),
    ("rogue", "assassination"): ("focus", "shadow", "instinct"),
    ("rogue", "combat"): ("instinct", "power", "freedom"),
    ("rogue", "subtlety"): ("trickster", "shadow", "focus"),
    ("shaman", "elemental_combat"): ("power", "wild", "scholar"),
    ("shaman", "enhancement"): ("instinct", "duty", "power"),
    ("shaman", "restoration"): ("healer", "wild", "bond"),
    ("warlock", "affliction"): ("shadow", "focus", "scholar"),
    ("warlock", "demonology"): ("bond", "shadow", "guardian"),
    ("warlock", "destruction"): ("power", "shadow", "instinct"),
    ("warrior", "arms"): ("focus", "duty", "instinct"),
    ("warrior", "fury"): ("power", "instinct", "freedom"),
    ("warrior", "protection"): ("guardian", "duty", "bond"),
}

CLASS_ORDER = ["druid", "hunter", "mage", "paladin", "priest", "rogue", "shaman", "warlock", "warrior"]
TRAITS = ["wild", "scholar", "duty", "shadow", "guardian", "focus", "healer", "power", "trickster", "instinct", "bond", "freedom"]


def answers_for(cfg):
    """A complete answer set made of the first response to every question."""
    return first_answers(cfg)


# ---------------------------------------------------------------- seed dataset


def test_seed_has_thirty_questions_and_the_original_sixteen_keep_their_four_answers(config):
    from app.seed_tuning import TYPE_CHANGES
    assert len(config.questions) == 30 and config.quiz.expected_question_count == 30
    assert sorted(q.id for q in config.questions) == [f"q{i:02d}" for i in range(1, 31)]
    for q in [x for x in config.questions if x.id <= "q16"]:
        assert [a.id for a in q.answers] == ["a", "b", "c", "d"], q.id
        assert q.type == (TYPE_CHANGES[q.id][0] if q.id in TYPE_CHANGES else "choice"), q.id
    assert Counter(q.type for q in config.questions) == {"choice": 15, "scale": 8, "pick_two": 2, "ranking": 3, "allocation": 2}


def test_new_questions_cover_the_question_types_and_every_class_and_specialization(config):
    new = [q for q in config.questions if q.id > "q16"]
    assert Counter(q.type for q in new) == {"scale": 8, "pick_two": 2, "ranking": 1, "choice": 3}
    for q in new:
        if q.type == "scale":
            assert [a.id for a in q.answers] == ["agree", "disagree"] and q.low_label and q.high_label
        elif q.type == "pick_two":
            assert len(q.answers) == 4
        assert q.rationale, q.id
    classes, specs = Counter(), Counter()
    for q in new:
        for a in q.answers:
            classes.update(a.class_weights.keys())
            specs.update(a.spec_weights.keys())
    assert set(classes) == {c.id for c in config.classes}
    assert set(specs) == {f"{c.id}/{s.id}" for c in config.classes for s in c.specializations}
    # no class is starved or dominant in the new questions
    weight = Counter()
    for q in new:
        for a in q.answers:
            for k, w in a.class_weights.items():
                weight[k] += w
    assert max(weight.values()) - min(weight.values()) <= 4, dict(weight)


def test_new_questions_only_credit_specializations_of_the_classes_their_answer_favours(config):
    for q in config.questions:
        for a in q.answers:
            for key in a.spec_weights:
                assert key.split("/")[0] in a.class_weights, (q.id, a.id, key)


def test_seed_has_nine_classes_in_original_order_and_27_specializations(config):
    assert [c.id for c in config.classes] == CLASS_ORDER
    assert config.scoring.class_tie_break_order == CLASS_ORDER
    assert all(len(c.specializations) == 3 for c in config.classes)
    assert sum(len(c.specializations) for c in config.classes) == 27


def test_seed_has_twelve_traits(config):
    assert [t.id for t in config.traits] == TRAITS
    names = {t.id: t.name for t in config.traits}
    assert names["wild"] == "Intuition" and names["power"] == "Intensity" and names["freedom"] == "Independence"


def test_seed_matches_independent_transcription_except_for_the_documented_tuning(config):
    """GOLDEN is the original quiz as specified. The seed may differ only where app/seed_tuning.py says so."""
    from app.seed_tuning import ORIGINAL_CLASS_PAIRS
    seen, differing = 0, set()
    for line in GOLDEN.strip().splitlines():
        qid, aid, c1, c2, t1, t2 = line.split()
        answer = next(a for a in config.get_question(qid).answers if a.id == aid)
        assert answer.trait_weights == {t1: 2.0, t2: 1.0}, line               # traits are never retuned
        if answer.class_weights != {c1: 2.0, c2: 1.0}:
            differing.add((qid, aid))
            assert ORIGINAL_CLASS_PAIRS[(qid, aid)] == tuple(answer.class_weights), line
        seen += 1
    assert seen == 64
    assert differing == set(ORIGINAL_CLASS_PAIRS), "every overlay entry must really change an original answer"


def test_seed_specialization_profiles_match_specification(config):
    for (cid, sid), traits in PROFILES.items():
        spec = config.get_spec(cid, sid)
        assert spec is not None, (cid, sid)
        assert list(spec.trait_multipliers) == list(traits)
        assert list(spec.trait_multipliers.values()) == [1.5, 1.0, 0.45]
    assert len(PROFILES) == 27


def test_every_answer_uses_two_distinct_classes_and_traits(config):
    for q in config.questions:
        for a in q.answers:
            assert sorted(a.class_weights.values()) == [1.0, 2.0]
            assert sorted(a.trait_weights.values()) == [1.0, 2.0]


# ---------------------------------------------------------------- normalization


def test_q01_answer_a_contributions_match_specification(config):
    ev = evaluate(config, {"q01": "a"}, allow_partial=True)
    cc = ev.explanation.questions[0].class_contributions
    assert cc["druid"].adjusted == pytest.approx(1.5)
    assert cc["druid"].raw == 2.0 and cc["druid"].baseline == pytest.approx(0.5)
    assert cc["hunter"].adjusted == pytest.approx(0.75)
    assert cc["mage"].adjusted == pytest.approx(-0.5)
    assert cc["paladin"].adjusted == pytest.approx(0.0 - 0.25)
    assert ev.explanation.questions[0].class_adjusted_sum == pytest.approx(0.0)


def test_contributions_sum_to_zero_for_every_choice_and_pick_two_response(config):
    c = compile_config(config)
    for q in c.questions:
        if q.type == "scale":
            continue
        for ai in range(len(q.answer_ids)):
            assert sum(q.class_delta[ai]) == pytest.approx(0.0, abs=1e-12), (q.id, ai)
            assert sum(q.trait_delta[ai]) == pytest.approx(0.0, abs=1e-12), (q.id, ai)


def test_every_question_has_zero_mean_contribution_over_its_possible_responses(config):
    c = compile_config(config)
    for q in c.questions:
        n = len(q.answer_ids)
        for table, width in ((q.class_delta, c.n_classes), (q.trait_delta, c.n_traits), (q.spec_delta, c.n_specs)):
            for i in range(width):
                assert sum(row[i] for row in table) / n == pytest.approx(0.0, abs=1e-12), (q.id, i)


def test_sum_of_per_question_contributions_equals_total_score(config, druid_answers):
    ev = evaluate(config, druid_answers, include_explanation=True)
    for row in ev.rankings.classes:
        total = sum(q.class_contributions[row.id].adjusted for q in ev.explanation.questions)
        assert total == pytest.approx(row.score, abs=1e-8)
        assert row.raw_points - row.expected_points == pytest.approx(row.score, abs=1e-8)
    for row in ev.rankings.traits:
        total = sum(q.trait_contributions[row.id].adjusted for q in ev.explanation.questions)
        assert total == pytest.approx(row.score, abs=1e-8)


def test_class_scores_sum_to_zero_when_only_the_original_questions_are_answered(config, original_answers):
    ev = evaluate(config, original_answers, allow_partial=True)
    assert sum(r.score for r in ev.rankings.classes) == pytest.approx(0.0, abs=1e-8)


def test_trait_raw_counts_are_separate_from_adjusted_scores(config, druid_answers):
    ev = evaluate(config, druid_answers)
    wild = next(t for t in ev.rankings.traits if t.id == "wild")
    assert wild.appearances > 0
    assert wild.raw_points != wild.score


def test_evaluation_is_deterministic(config, druid_answers):
    first = evaluate(config, druid_answers, include_explanation=True, include_counterfactuals=True)
    second = evaluate(config, dict(reversed(list(druid_answers.items()))), include_explanation=True, include_counterfactuals=True)
    assert first.model_dump() == second.model_dump()


def test_known_answer_set_produces_known_result(config, druid_answers):
    ev = evaluate(config, druid_answers)
    assert (ev.result.primary_class.id, ev.result.primary_specialization.id) == ("druid", "feral_combat")
    assert [r.id for r in ev.rankings.classes][:2] == ["druid", "hunter"]
    assert ev.alternatives.alternative_class.id == "hunter"
    assert ev.metadata.complete and not ev.metadata.provisional


def test_all_nine_classes_can_win(config):
    c = compile_config(config)
    for ci, cid in enumerate(c.class_ids):
        # Pick, for each question, the response with the highest adjusted contribution to this class.
        picks = {q.id: q.answer_ids[max(range(len(q.answer_ids)), key=lambda a: q.class_delta[a][ci])] for q in c.questions}
        assert evaluate(config, picks).result.primary_class.id == cid


def test_all_27_specializations_can_be_recommended_by_changing_profiles(config):
    # Every specialization is reachable: boost its own profile and it must win within its class.
    for cls in config.classes:
        for spec in cls.specializations:
            sim = scoring.apply_overrides(
                config, spec_overrides=[SpecOverride(class_id=cls.id, specialization_id=spec.id, trait_multipliers={"wild": 50.0})]
            )
            ev = evaluate(sim, {"q01": "a"}, allow_partial=True)
            by_class = [r for r in ev.rankings.all_specializations if r.class_id == cls.id]
            assert max(by_class, key=lambda r: r.score).id == spec.id


# ---------------------------------------------------------------- specialization stage


def test_specialization_scores_use_trait_multipliers_plus_the_direct_weights(config, druid_answers):
    ev = evaluate(config, druid_answers)
    traits = {t.id: t.score for t in ev.rankings.traits}
    for row in ev.rankings.all_specializations:
        spec = config.get_spec(row.class_id, row.id)
        from_traits = sum(m * traits[t] for t, m in spec.trait_multipliers.items())
        assert row.score == pytest.approx(from_traits + row.direct_score, abs=1e-8)
        assert [term.multiplier for term in row.terms] == list(spec.trait_multipliers.values())
        assert sum(term.contribution for term in row.terms) == pytest.approx(from_traits, abs=1e-8)


def test_direct_specialization_weights_follow_the_formula_and_the_multiplier(config, druid_answers):
    ev = evaluate(config, druid_answers, include_explanation=True)
    m = config.scoring.spec_weight_multiplier
    for row in ev.rankings.all_specializations:
        key = f"{row.class_id}/{row.id}"
        total = sum(q.spec_contributions[key].adjusted for q in ev.explanation.questions if key in q.spec_contributions)
        assert row.direct_score == pytest.approx(m * total, abs=1e-8), key
    off = config.model_copy(deep=True)
    off.scoring.spec_weight_multiplier = 0.0
    assert all(r.direct_score == 0 for r in evaluate(off, druid_answers).rankings.all_specializations)


def test_only_winning_class_specializations_decide_primary_result(config, druid_answers):
    ev = evaluate(config, druid_answers)
    assert ev.result.primary_specialization.class_id == ev.result.primary_class.id
    assert {r.class_id for r in ev.rankings.specializations} == {ev.result.primary_class.id}
    assert [r.rank for r in ev.rankings.specializations] == [1, 2, 3]
    assert ev.alternatives.second_specialization_in_primary_class.id == ev.rankings.specializations[1].id
    assert ev.alternatives.alternative_specialization.class_id == ev.alternatives.alternative_class.id


def test_arbitrary_number_of_profile_traits_is_supported(config, druid_answers):
    sim = scoring.apply_overrides(
        config,
        spec_overrides=[SpecOverride(class_id="druid", specialization_id="balance",
                                     trait_multipliers={"wild": 1, "healer": 1, "bond": 1, "freedom": 1, "duty": 1})],
    )
    ev = evaluate(sim, druid_answers)
    row = next(r for r in ev.rankings.all_specializations if (r.class_id, r.id) == ("druid", "balance"))
    assert len(row.terms) == 5


# ---------------------------------------------------------------- weight edits


@pytest.mark.parametrize("chosen,expected_delta", [("a", 1.5), ("b", -0.5), ("c", -0.5), ("d", -0.5)])
def test_changing_a_weight_changes_scores_as_the_formula_predicts(config, chosen, expected_delta):
    # Raise Druid's weight on q01/a from 2 to 4 (+2). The average over four answers rises by 0.5.
    override = AnswerOverride(question_id="q01", answer_id="a", class_weights={"druid": 4.0, "hunter": 1.0})
    sim = evaluate(scoring.apply_overrides(config, [override]), {"q01": chosen}, allow_partial=True)
    base = evaluate(config, {"q01": chosen}, allow_partial=True)
    d = lambda ev: next(r for r in ev.rankings.classes if r.id == "druid").score
    assert d(sim) - d(base) == pytest.approx(expected_delta)


def test_editing_one_answer_does_not_modify_other_answers(config):
    sim = scoring.apply_overrides(config, [AnswerOverride(question_id="q01", answer_id="a", class_weights={"druid": 9})])
    for q_before, q_after in zip(config.questions, sim.questions):
        for a_before, a_after in zip(q_before.answers, q_after.answers):
            if (q_before.id, a_before.id) != ("q01", "a"):
                assert a_before == a_after


def test_apply_overrides_never_mutates_the_original(config):
    snapshot = config.model_dump()
    scoring.apply_overrides(config, [AnswerOverride(question_id="q03", answer_id="b", class_weights={"mage": 7})])
    assert config.model_dump() == snapshot


# ---------------------------------------------------------------- ties


def _flat_config(config):
    flat = config.model_copy(deep=True)
    for q in flat.questions:
        for a in q.answers:
            a.class_weights, a.trait_weights, a.spec_weights = {}, {}, {}
    return flat


def test_class_ties_follow_original_class_order(config):
    ev = evaluate(_flat_config(config), answers_for(config))
    assert [r.id for r in ev.rankings.classes] == CLASS_ORDER
    assert ev.result.primary_class.id == "druid" and ev.alternatives.alternative_class.id == "hunter"
    tie = next(t for t in ev.explanation.tie_breaks if t.scope == "class")
    assert tie.tied[:2] == ["druid", "hunter"] and tie.positions[0] == 1


def test_specialization_ties_follow_specialization_order(config):
    ev = evaluate(_flat_config(config), answers_for(config), include_explanation=True)
    assert [r.id for r in ev.rankings.specializations] == ["balance", "feral_combat", "restoration"]
    assert any(t.scope == "specialization" and t.scope_id == "druid" for t in ev.explanation.tie_breaks)


def test_tie_break_order_is_configurable(config):
    flat = _flat_config(config)
    flat.scoring.class_tie_break_order = list(reversed(CLASS_ORDER))
    assert evaluate(flat, answers_for(config)).result.primary_class.id == "warrior"


def test_floating_point_noise_does_not_decide_ties(config):
    # 0.1 + 0.2 and 0.3 differ by one ulp in binary floating point; the engine compares rounded scores.
    flat = _flat_config(config)
    a, b, c, d = flat.questions[0].answers
    a.class_weights, b.class_weights = {"druid": 0.1, "hunter": 0.3}, {"druid": 0.2}
    ev = evaluate(flat, {"q01": "c"}, allow_partial=True)
    ids = [r.id for r in ev.rankings.classes]
    assert ids[-2:] == ["druid", "hunter"]
    assert ev.rankings.classes[-1].tied_with_previous


# ---------------------------------------------------------------- input handling


def test_incomplete_assessment_is_rejected_by_default(config):
    with pytest.raises(IncompleteAssessmentError) as exc:
        evaluate(config, {"q01": "a"})
    assert len(exc.value.missing) == 29


def test_partial_evaluation_is_marked_provisional(config):
    ev = evaluate(config, {"q01": "a", "q02": "c"}, allow_partial=True)
    assert ev.metadata.provisional and not ev.metadata.complete
    assert ev.metadata.answered_questions == 2 and len(ev.metadata.missing_questions) == 28


def test_unknown_question_or_answer_is_rejected(config):
    with pytest.raises(UnknownQuestionError):
        evaluate(config, {"q99": "a"}, allow_partial=True)
    with pytest.raises(UnknownAnswerError):
        evaluate(config, {"q01": "z"}, allow_partial=True)


def test_confidence_labels_follow_configured_margins(config, druid_answers):
    ev = evaluate(config, druid_answers)
    gap = ev.result.confidence.class_gap
    assert gap == pytest.approx(ev.rankings.classes[0].score - ev.rankings.classes[1].score)
    cfg = config.model_copy(deep=True)
    cfg.scoring.confidence_margins.strong, cfg.scoring.confidence_margins.moderate = gap + 1, gap + 0.5
    assert evaluate(cfg, druid_answers).result.confidence.label == "Close call"
    assert "not a statistical" in ev.result.confidence.note
    assert ev.metadata.scores_are_probabilities is False


def test_counterfactuals_cover_every_alternative_answer(config, druid_answers):
    ev = evaluate(config, druid_answers, include_explanation=True, include_counterfactuals=True)
    cfs = ev.explanation.counterfactuals
    c = compile_config(config)
    assert len(cfs) == sum(len(q.answer_ids) - 1 for q in c.questions)   # 3 per original question, 9 per scale, 5 per pair, 1 per binary
    # Re-evaluating one counterfactual in full agrees with the shortcut.
    cf = cfs[0]
    changed = dict(druid_answers, **{cf.question_id: cf.answer_id})
    full = evaluate(config, changed)
    assert full.result.primary_class.id == cf.primary_class_id
    assert full.result.primary_specialization.id == cf.primary_specialization_id


# ---------------------------------------------------------------- simulation


def test_simulation_compares_without_modifying_config(config, druid_answers):
    before = config.model_dump()
    sim = scoring.simulate(
        config, druid_answers, [AnswerOverride(question_id="q01", answer_id="a", class_weights={"druid": 0.0})]
    )
    assert config.model_dump() == before
    druid = next(d for d in sim.class_differences if d.id == "druid")
    assert druid.difference < 0 and druid.simulated == pytest.approx(druid.original + druid.difference)
    assert sim.persisted is False
    assert sim.winning_class_changed == (sim.original_primary.class_id != sim.simulated_primary.class_id)


def test_simulation_can_flip_the_winner(config, druid_answers):
    sim = scoring.simulate(
        config, druid_answers,
        [AnswerOverride(question_id="q01", answer_id="a", class_weights={"mage": 40.0})],
    )
    assert sim.winning_class_changed and sim.simulated_primary.class_id == "mage"
    assert sim.question_influence[0].question_id  # influence ranking is populated


def test_batch_simulation_is_reproducible_and_mean_scores_are_near_zero(config):
    a = scoring.batch_simulate(config, 3000, seed=11)
    b = scoring.batch_simulate(config, 3000, seed=11)
    assert a.model_dump() == b.model_dump()
    assert sum(r.count for r in a.baseline.class_frequencies) == 3000
    assert sum(r.frequency for r in a.baseline.class_frequencies) == pytest.approx(1.0)
    # The normalization makes every class's expected score under uniform random answers exactly zero.
    assert all(abs(r.mean_score) < 0.25 for r in a.baseline.class_frequencies)
    assert a.simulated is None and "not empirical" in a.note
