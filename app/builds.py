"""Talent build validation and presentation.

This module is deliberately independent of the personality scoring: the quiz decides
the class and specialization; builds only decorate that result.

No game data ships with the application. Talent trees are imported as a
``TalentCatalog`` (see README). Without a catalog for a class, a build for that class
can be stored but never marked ``verified``.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from .models import (
    FIRST_TALENT_LEVEL,
    Build,
    BuildDetail,
    BuildSummary,
    BuildValidation,
    CatalogClass,
    CatalogInfo,
    CatalogTalent,
    CatalogTree,
    Config,
    ResolvedTalent,
    TreeTalent,
    TreeView,
)


def expected_points(level: int) -> int:
    """Talent points begin at level 10, so level 60 has 51 points."""
    return max(0, level - FIRST_TALENT_LEVEL + 1)


def catalog_class(config: Config, class_id: str) -> Optional[CatalogClass]:
    if config.talent_catalog is None:
        return None
    return next((c for c in config.talent_catalog.classes if c.id == class_id), None)


def _talent_index(cat_cls: CatalogClass) -> dict[str, tuple[CatalogTree, CatalogTalent]]:
    return {t.id: (tree, t) for tree in cat_cls.trees for t in tree.talents}


def validate_build(build: Build, config: Config) -> BuildValidation:
    """Check a build against the class's talent catalog. Never raises."""
    errors: list[str] = []
    warnings: list[str] = []
    problems: list[str] = []

    cls = config.get_class(build.class_id)
    spec = config.get_spec(build.class_id, build.specialization_id)
    if cls is None:
        errors.append(f"Unknown class '{build.class_id}'.")
    elif spec is None:
        errors.append(f"Unknown specialization '{build.specialization_id}' for class '{build.class_id}'.")

    tree_ids = [s.id for s in cls.specializations] if cls else []
    distribution = {t: 0 for t in tree_ids}
    expected = expected_points(build.level)
    spent = sum(build.allocations.values())

    if build.total_points != expected:
        errors.append(
            f"total_points is {build.total_points} but level {build.level} grants {expected} talent points."
        )
    if spent > build.total_points:
        errors.append(f"{spent} points are allocated but only {build.total_points} are available.")

    cat_cls = catalog_class(config, build.class_id)
    catalog = config.talent_catalog
    catalog_available = cat_cls is not None
    index = _talent_index(cat_cls) if cat_cls else {}

    def points_above(counts: dict[str, int], tree_id: str, tier: int) -> int:
        return sum(r for tid, r in counts.items() if tid in index and index[tid][0].id == tree_id and index[tid][1].tier < tier)

    if catalog_available:
        assert cat_cls is not None and catalog is not None
        for tid, rank in build.allocations.items():
            if tid not in index:
                errors.append(f"Talent '{tid}' does not exist for {build.class_id} in client {catalog.client_version}.")
                continue
            tree, talent = index[tid]
            if rank > talent.max_rank:
                errors.append(f"{talent.name}: rank {rank} exceeds its maximum of {talent.max_rank}.")
            distribution[tree.id] = distribution.get(tree.id, 0) + rank
        for tid, rank in build.allocations.items():
            if tid not in index:
                continue
            tree, talent = index[tid]
            need = talent.tier * catalog.points_per_tier
            have = points_above(build.allocations, tree.id, talent.tier)
            if have < need:
                errors.append(
                    f"{talent.name} (row {talent.tier + 1}) needs {need} points in earlier rows of {tree.name}; build has {have}."
                )
            for req in talent.requires:
                got = build.allocations.get(req.talent_id, 0)
                if got < req.rank:
                    req_name = index[req.talent_id][1].name if req.talent_id in index else req.talent_id
                    errors.append(f"{talent.name} requires {req.rank} point(s) in {req_name}; build has {got}.")

        if build.leveling_order:
            counts: dict[str, int] = defaultdict(int)
            if len(build.leveling_order) > build.total_points:
                errors.append(f"Leveling order has {len(build.leveling_order)} steps but only {build.total_points} points exist.")
            for step, tid in enumerate(build.leveling_order, start=1):
                level = FIRST_TALENT_LEVEL + step - 1
                if tid not in index:
                    errors.append(f"Leveling step {step} (level {level}): unknown talent '{tid}'.")
                    continue
                tree, talent = index[tid]
                if counts[tid] >= talent.max_rank:
                    errors.append(f"Leveling step {step} (level {level}): {talent.name} is already at maximum rank.")
                if points_above(counts, tree.id, talent.tier) < talent.tier * catalog.points_per_tier:
                    errors.append(f"Leveling step {step} (level {level}): {talent.name} is not yet unlocked.")
                for req in talent.requires:
                    if counts.get(req.talent_id, 0) < req.rank:
                        errors.append(f"Leveling step {step} (level {level}): {talent.name} lacks its prerequisite.")
                counts[tid] += 1
            if dict(counts) != dict(build.allocations) and len(build.leveling_order) == spent:
                errors.append("Leveling order does not spend exactly the allocated ranks.")
            elif len(build.leveling_order) != spent:
                warnings.append(
                    f"Leveling order covers {len(build.leveling_order)} of {spent} allocated points."
                )

        # Role consistency (item 7 of the verification list).
        if spec is not None:
            if build.role not in spec.role.split("_or_"):
                errors.append(f"Build role '{build.role}' is not consistent with specialization role '{spec.role}'.")
            if spent and spec.id in distribution:
                top = max(distribution.values())
                if distribution[spec.id] < top:
                    leader = next(t for t, v in distribution.items() if v == top)
                    errors.append(
                        f"Primary specialization '{spec.id}' holds {distribution[spec.id]} points but '{leader}' holds {top}; "
                        "the allocation does not match the build's primary specialization."
                    )
    else:
        if build.allocations:
            warnings.append(
                f"No talent data has been imported for '{build.class_id}', so this allocation cannot be checked."
            )
        if spec is not None and build.role not in spec.role.split("_or_"):
            errors.append(f"Build role '{build.role}' is not consistent with specialization role '{spec.role}'.")

    complete = spent == build.total_points and spent > 0
    if spent < build.total_points and build.allocations:
        warnings.append(f"{build.total_points - spent} talent point(s) are unspent.")

    # What would be required to mark this build 'verified'?
    if errors:
        problems.append("the allocation has validation errors")
    if not catalog_available:
        problems.append(f"no imported talent data for class '{build.class_id}'")
    if not complete:
        problems.append(f"{spent} of {build.total_points} talent points are allocated")
    if not build.source.strip():
        problems.append("no source is recorded")
    if build.verified_at is None:
        problems.append("no verification date is recorded")
    if catalog is not None and catalog.data_status == "draft":
        problems.append("the imported talent data is marked draft (not read from the game client)")
    if catalog is not None and build.client_version != catalog.client_version:
        problems.append(
            f"client_version '{build.client_version}' does not match the talent data version '{catalog.client_version}'"
        )
    elif catalog is None and not build.client_version:
        problems.append("no client version is recorded")

    if build.status == "verified" and problems:
        errors.append("A verified build requires: " + "; ".join(problems) + ".")

    return BuildValidation(
        valid=not errors,
        can_verify=not problems,
        complete=complete,
        errors=errors,
        warnings=warnings,
        verification_problems=problems,
        points_spent=spent,
        points_remaining=max(0, build.total_points - spent),
        expected_points=expected,
        tree_distribution=distribution,
        catalog_available=catalog_available,
    )


def tree_views(build: Build, config: Config) -> list[TreeView]:
    """The class's talent trees (in specialization order) with the build's ranks filled in; empty without talent data."""
    cat_cls = catalog_class(config, build.class_id)
    cls = config.get_class(build.class_id)
    if cat_cls is None or cls is None:
        return []
    order = [s.id for s in cls.specializations]
    trees = sorted(cat_cls.trees, key=lambda t: order.index(t.id) if t.id in order else 99)
    return [
        TreeView(
            id=tree.id,
            name=tree.name,
            points=sum(build.allocations.get(t.id, 0) for t in tree.talents),
            talents=[
                TreeTalent(
                    id=t.id, name=t.name, tier=t.tier, column=t.column, max_rank=t.max_rank,
                    rank=build.allocations.get(t.id, 0), requires=t.requires, description=t.description,
                )
                for t in tree.talents
            ],
        )
        for tree in trees
    ]


def describe_build(build: Build, config: Config, with_validation: bool = True, with_trees: bool = False) -> BuildDetail:
    """Build record plus derived, display-ready fields. ``with_trees`` adds the full talent trees for drawing the build."""
    validation = validate_build(build, config)
    cls = config.get_class(build.class_id)
    tree_order = [s.id for s in cls.specializations] if cls else []
    dist = {t: validation.tree_distribution.get(t, 0) for t in tree_order}

    cat_cls = catalog_class(config, build.class_id)
    index = _talent_index(cat_cls) if cat_cls else {}
    resolved: list[ResolvedTalent] = []
    for tid, rank in build.allocations.items():
        if tid in index:
            tree, t = index[tid]
            resolved.append(ResolvedTalent(talent_id=tid, name=t.name, tree_id=tree.id, tier=t.tier, rank=rank, max_rank=t.max_rank))
        else:
            resolved.append(ResolvedTalent(talent_id=tid, rank=rank))
    resolved.sort(key=lambda r: (tree_order.index(r.tree_id) if r.tree_id in tree_order else 99, r.tier if r.tier is not None else 99, r.talent_id))

    version = config.talent_catalog.client_version if config.talent_catalog else build.client_version
    if build.status == "verified":
        note = f"Verified against World of Warcraft: Forever talent data ({version}) on {build.verified_at}."
    elif build.status == "pending" or not build.allocations:
        note = "Talent allocation pending: it has not yet been verified against current World of Warcraft: Forever talent data."
    else:
        note = "Provisional build: not verified against current World of Warcraft: Forever talent data. Treat it as a draft, not a validated allocation."

    data = build.model_dump()
    return BuildDetail(
        **data,
        points_spent=validation.points_spent,
        points_remaining=validation.points_remaining,
        tree_distribution=dist,
        tree_distribution_text="/".join(str(v) for v in dist.values()) if any(dist.values()) else "",
        allocation_pending=not build.allocations,
        talents=resolved,
        status_note=note,
        trees=tree_views(build, config) if with_trees else [],
        catalog_info=catalog_info(config) if with_trees else None,
        validation=validation if with_validation else None,
    )


def catalog_info(config: Config) -> Optional[CatalogInfo]:
    cat = config.talent_catalog
    if cat is None:
        return None
    return CatalogInfo(
        client_version=cat.client_version, data_status=cat.data_status, source=cat.source, source_updated=cat.source_updated,
        retrieved_at=cat.retrieved_at, points_per_tier=cat.points_per_tier, notes=cat.notes,
    )


def summarize_build(build: Build) -> BuildSummary:
    return BuildSummary(
        id=build.id,
        name=build.name,
        purpose=build.purpose,
        role=build.role,
        status=build.status,
        is_default=build.is_default,
        points_spent=sum(build.allocations.values()),
        total_points=build.total_points,
        allocation_pending=not build.allocations,
    )


def builds_for(config: Config, class_id: str, spec_id: str) -> list[Build]:
    return [b for b in config.builds if b.class_id == class_id and b.specialization_id == spec_id]


def default_build(config: Config, class_id: str, spec_id: str) -> Optional[Build]:
    """The build flagged as default for a specialization, else the first available."""
    candidates = builds_for(config, class_id, spec_id)
    return next((b for b in candidates if b.is_default), candidates[0] if candidates else None)
