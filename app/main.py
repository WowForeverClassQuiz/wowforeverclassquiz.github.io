"""FastAPI application: routing, error mapping, and static file serving.

Layers:  browser UI -> REST API (this module) -> scoring (pure) -> repository -> SQLite.
"""
from __future__ import annotations

import hmac
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import builds as builds_mod
from . import scoring
from .models import (
    AnswerPatch,
    AnswerResponse,
    BatchSimulateRequest,
    BatchSimulateResponse,
    BuildCreate,
    BuildList,
    BuildPatch,
    BuildResponse,
    BuildValidateRequest,
    BuildValidation,
    CatalogResponse,
    CatalogSummaryClass,
    CatalogSummaryTree,
    CatalogUpdate,
    ClassesResponse,
    ClassListing,
    ClassPatch,
    ClassResponse,
    Config,
    DefaultBuildRequest,
    EvaluateRequest,
    ExpandRequest,
    QuestionExpansion,
    EvaluationResponse,
    Health,
    HistoryEntry,
    ImportRequest,
    MutationResult,
    PublicQuiz,
    QuestionPatch,
    QuestionResponse,
    ResetRequest,
    RestoreRequest,
    ScoringPatch,
    ScoringResponse,
    SimulateRequest,
    SimulationResponse,
    SpecListing,
    SpecPatch,
    SpecResponse,
    TraitPatch,
    TraitResponse,
)
from .public import public_quiz, with_builds
from .repository import (
    ConfigInvalid,
    NotFoundError,
    Repository,
    RevisionConflict,
)
from .seed import build_default_config

APP_VERSION = "1.0.0"
STATIC_DIR = Path(__file__).parent / "static"
DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "oracle.db"

TAGS = [
    {"name": "quiz", "description": "Participant-facing questions and evaluation. Never exposes scoring weights."},
    {"name": "config", "description": "Administrative scoring configuration, revisions, import/export."},
    {"name": "editing", "description": "Optimistic-concurrency edits to questions, answers, classes, traits and profiles."},
    {"name": "simulation", "description": "Side-effect-free what-if scoring and batch diagnostics."},
    {"name": "builds", "description": "Talent builds, talent catalog, and build validation. Independent of personality scoring."},
    {"name": "system", "description": "Health and version information."},
]


def _err(status: int, code: str, message: str, **extra) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message, **extra})


def create_app(db_path: Optional[os.PathLike | str] = None, admin_token: Optional[str] = None) -> FastAPI:
    """Application factory. ``db_path`` defaults to ``$ORACLE_DB`` or ``data/oracle.db``."""
    path = Path(db_path or os.environ.get("ORACLE_DB") or DEFAULT_DB)
    token = admin_token if admin_token is not None else os.environ.get("ORACLE_ADMIN_TOKEN")

    repo = Repository(path)
    repo.initialize()

    app = FastAPI(
        title="WoW: Forever Character Oracle",
        version=APP_VERSION,
        description=(
            "Local personality assessment that recommends a World of Warcraft: Forever class, "
            "specialization and talent build. Scores are relative compatibility indicators, not probabilities."
        ),
        openapi_tags=TAGS,
    )
    app.state.repo = repo
    app.state.admin_token = token or None

    # ------------------------------------------------------------------ errors
    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": {"code": "not_found", "message": str(exc)}})

    @app.exception_handler(RevisionConflict)
    async def _conflict(_: Request, exc: RevisionConflict):
        return JSONResponse(
            status_code=409,
            content={"detail": {
                "code": "revision_conflict", "message": str(exc),
                "expected_revision": exc.expected, "current_revision": exc.current,
            }},
        )

    @app.exception_handler(ConfigInvalid)
    async def _invalid(_: Request, exc: ConfigInvalid):
        return JSONResponse(
            status_code=400,
            content={"detail": {"code": "invalid_configuration", "message": str(exc), "errors": exc.errors}},
        )

    @app.exception_handler(scoring.IncompleteAssessmentError)
    async def _incomplete(_: Request, exc: scoring.IncompleteAssessmentError):
        return JSONResponse(
            status_code=400,
            content={"detail": {"code": "incomplete_assessment", "message": str(exc), "missing_questions": exc.missing}},
        )

    @app.exception_handler(scoring.ScoringError)
    async def _scoring(_: Request, exc: scoring.ScoringError):
        return JSONResponse(status_code=400, content={"detail": {"code": "invalid_request", "message": str(exc)}})

    @app.exception_handler(RequestValidationError)
    async def _schema(_: Request, exc: RequestValidationError):
        # Drop the echoed `input`/`ctx`: they may hold NaN/Infinity, which JSON cannot encode.
        errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": errors})

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"detail": {"code": "internal_error", "message": "An unexpected server error occurred."}},
        )

    # ------------------------------------------------------------- dependencies
    def get_repo(request: Request) -> Repository:
        return request.app.state.repo

    def check_admin(request: Request) -> None:
        expected = request.app.state.admin_token
        if not expected:
            return
        given = request.headers.get("authorization", "")
        if not hmac.compare_digest(given.encode(), f"Bearer {expected}".encode()):
            raise HTTPException(
                status_code=401,
                detail={"code": "admin_required", "message": "This endpoint requires the administrator token."},
                headers={"WWW-Authenticate": "Bearer"},
            )

    admin = [Depends(check_admin)]

    # ======================================================================
    # Participant API
    # ======================================================================
    api = APIRouter(prefix="/api/v1")

    @api.get("/health", response_model=Health, tags=["system"], summary="Health and version information")
    def health(repo: Repository = Depends(get_repo)):
        cfg = repo.get_config()
        return Health(
            status="ok",
            app_version=APP_VERSION,
            algorithm_version=cfg.scoring.algorithm_version,
            config_revision=cfg.revision,
            game_target="World of Warcraft: Forever",
            class_count=len(cfg.classes),
            specialization_count=sum(len(c.specializations) for c in cfg.classes),
            question_count=len(cfg.enabled_questions()),
            admin_auth_required=bool(app.state.admin_token),
        )

    @api.get("/quiz", response_model=PublicQuiz, tags=["quiz"], summary="Participant questions (no scoring data)")
    def get_quiz(repo: Repository = Depends(get_repo)):
        return public_quiz(repo.get_config())

    @api.get(
        "/classes", response_model=ClassesResponse, response_model_exclude_none=True, tags=["quiz"],
        summary="Classes, specializations, roles and configured builds",
    )
    def get_classes(
        request: Request,
        include_scores: bool = Query(False, description="Include each specialization's trait multipliers (admin when a token is set)."),
        include_builds: bool = Query(True, description="Include build summaries for each specialization."),
        repo: Repository = Depends(get_repo),
    ):
        if include_scores:
            check_admin(request)
        cfg = repo.get_config()
        return ClassesResponse(
            classes=[
                ClassListing(
                    id=c.id,
                    name=c.name,
                    description=c.description,
                    specializations=[
                        SpecListing(
                            id=s.id,
                            name=s.name,
                            role=s.role,
                            description=s.description,
                            trait_multipliers=dict(s.trait_multipliers) if include_scores else None,
                            builds=[builds_mod.summarize_build(b) for b in builds_mod.builds_for(cfg, c.id, s.id)]
                            if include_builds else None,
                        )
                        for s in c.specializations
                    ],
                )
                for c in cfg.classes
            ]
        )

    @api.post(
        "/evaluate", response_model=EvaluationResponse, response_model_exclude_none=True, tags=["quiz"],
        summary="Evaluate a completed assessment",
        description=(
            "Requires an answer for every question unless `allow_partial` is set (administrative debugging). "
            "Explanations, counterfactuals and partial evaluation require the admin token when one is configured."
        ),
    )
    def evaluate(req: EvaluateRequest, request: Request, repo: Repository = Depends(get_repo)):
        if req.include_explanation or req.include_counterfactuals or req.allow_partial:
            check_admin(request)
        cfg = repo.get_config()
        ev = scoring.evaluate(
            cfg, req.answers, allow_partial=req.allow_partial,
            include_explanation=req.include_explanation or req.include_counterfactuals,
            include_counterfactuals=req.include_counterfactuals, length=req.length,
        )
        return with_builds(cfg, ev)

    # ======================================================================
    # Configuration (admin)
    # ======================================================================
    @api.get("/config", response_model=Config, tags=["config"], dependencies=admin,
             summary="Complete scoring configuration")
    def get_config(repo: Repository = Depends(get_repo)):
        return repo.get_config()

    @api.get("/config/default", response_model=Config, tags=["config"], dependencies=admin,
             summary="The immutable original (seed) configuration")
    def get_default_config():
        return build_default_config()

    @api.get("/config/export", tags=["config"], dependencies=admin, summary="Download the current configuration")
    def export_config(repo: Repository = Depends(get_repo)):
        cfg = repo.get_config()
        return Response(
            content=cfg.model_dump_json(indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="wow-oracle-config-r{cfg.revision}.json"'},
        )

    @api.post("/config/import", response_model=MutationResult, tags=["config"], dependencies=admin,
              summary="Validate and import a configuration (a backup is written first)")
    def import_config(req: ImportRequest, repo: Repository = Depends(get_repo)):
        done = repo.import_config(req.expected_revision, req.config, req.description)
        return MutationResult(revision=done.config.revision, description=done.description, backup_path=done.backup_path)

    @api.post("/config/reset", response_model=MutationResult, tags=["config"], dependencies=admin,
              summary="Restore the original seed configuration (requires confirm=true)")
    def reset_config(req: ResetRequest, repo: Repository = Depends(get_repo)):
        if not req.confirm:
            raise _err(400, "confirmation_required", "Resetting replaces all configuration. Send confirm=true to proceed.")
        done = repo.reset(req.expected_revision)
        return MutationResult(revision=done.config.revision, description=done.description, backup_path=done.backup_path)

    @api.get("/config/history", response_model=list[HistoryEntry], tags=["config"], dependencies=admin,
             summary="Past configuration revisions, newest first")
    def config_history(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0),
                       repo: Repository = Depends(get_repo)):
        return repo.history(limit, offset)

    @api.get("/config/history/{revision}", response_model=Config, tags=["config"], dependencies=admin,
             summary="The full configuration as of a past revision")
    def config_snapshot(revision: int, repo: Repository = Depends(get_repo)):
        return repo.snapshot(revision)

    @api.post("/config/history/{revision}/restore", response_model=MutationResult, tags=["config"],
              dependencies=admin, summary="Make a past revision current again (as a new revision)")
    def restore_revision(revision: int, req: RestoreRequest, repo: Repository = Depends(get_repo)):
        done = repo.restore(req.expected_revision, revision)
        return MutationResult(revision=done.config.revision, description=done.description, backup_path=done.backup_path)

    # ======================================================================
    # Editing (admin)
    # ======================================================================
    @api.patch("/questions/{question_id}/answers/{answer_id}", response_model=AnswerResponse, tags=["editing"],
               dependencies=admin, summary="Update an answer's text or weights")
    def patch_answer(question_id: str, answer_id: str, patch: AnswerPatch, repo: Repository = Depends(get_repo)):
        done = repo.update_answer(question_id, answer_id, patch)
        q = done.config.get_question(question_id)
        a = next(x for x in q.answers if x.id == answer_id)
        return AnswerResponse(revision=done.config.revision, question_id=question_id, answer=a)

    @api.patch("/questions/{question_id}", response_model=QuestionResponse, tags=["editing"], dependencies=admin,
               summary="Update a question's text or enabled flag")
    def patch_question(question_id: str, patch: QuestionPatch, repo: Repository = Depends(get_repo)):
        done = repo.update_question(question_id, patch)
        return QuestionResponse(revision=done.config.revision, question=done.config.get_question(question_id))

    @api.post("/questions/expand", response_model=QuestionExpansion, tags=["editing"], dependencies=admin,
              summary="Expand a (possibly unsaved) question into every possible response and its contributions")
    def expand_question(req: ExpandRequest, repo: Repository = Depends(get_repo)):
        return scoring.expand_question(repo.get_config(), req.question)

    @api.patch("/classes/{class_id}/specs/{spec_id}", response_model=SpecResponse, tags=["editing"],
               dependencies=admin, summary="Update a specialization's scoring profile and description")
    def patch_spec(class_id: str, spec_id: str, patch: SpecPatch, repo: Repository = Depends(get_repo)):
        done = repo.update_spec(class_id, spec_id, patch)
        return SpecResponse(
            revision=done.config.revision, class_id=class_id,
            specialization=done.config.get_spec(class_id, spec_id),
        )

    @api.patch("/classes/{class_id}", response_model=ClassResponse, tags=["editing"], dependencies=admin,
               summary="Update a class's name or description")
    def patch_class(class_id: str, patch: ClassPatch, repo: Repository = Depends(get_repo)):
        done = repo.update_class(class_id, patch)
        return ClassResponse(revision=done.config.revision, game_class=done.config.get_class(class_id))

    @api.patch("/traits/{trait_id}", response_model=TraitResponse, tags=["editing"], dependencies=admin,
               summary="Update a personality trait's display name, description or reading sentence")
    def patch_trait(trait_id: str, patch: TraitPatch, repo: Repository = Depends(get_repo)):
        done = repo.update_trait(trait_id, patch)
        return TraitResponse(revision=done.config.revision, trait=done.config.get_trait(trait_id))

    @api.patch("/scoring", response_model=ScoringResponse, tags=["editing"], dependencies=admin,
               summary="Update confidence margins or the class tie-break order")
    def patch_scoring(patch: ScoringPatch, repo: Repository = Depends(get_repo)):
        done = repo.update_scoring(patch)
        return ScoringResponse(revision=done.config.revision, scoring=done.config.scoring)

    # ======================================================================
    # Simulation (admin)
    # ======================================================================
    @api.post("/simulate", response_model=SimulationResponse, response_model_exclude_none=True, tags=["simulation"],
              dependencies=admin, summary="Compare the saved configuration with temporary overrides")
    def simulate(req: SimulateRequest, repo: Repository = Depends(get_repo)):
        return scoring.simulate(
            repo.get_config(), req.answers, req.overrides, req.specialization_overrides, req.include_explanation, req.length
        )

    @api.post("/simulate/batch", response_model=BatchSimulateResponse, tags=["simulation"], dependencies=admin,
              summary="Score many random answer sets to reveal systematic bias")
    def simulate_batch(req: BatchSimulateRequest, repo: Repository = Depends(get_repo)):
        return scoring.batch_simulate(
            repo.get_config(), req.count, req.seed, req.overrides, req.specialization_overrides, req.length
        )

    # ======================================================================
    # Builds (admin)
    # ======================================================================
    @api.get("/builds", response_model=BuildList, tags=["builds"], dependencies=admin, summary="List builds")
    def list_builds(class_id: Optional[str] = None, specialization_id: Optional[str] = None,
                    repo: Repository = Depends(get_repo)):
        cfg = repo.get_config()
        selected = [
            b for b in cfg.builds
            if (class_id is None or b.class_id == class_id)
            and (specialization_id is None or b.specialization_id == specialization_id)
        ]
        return BuildList(builds=[builds_mod.describe_build(b, cfg) for b in selected])

    @api.post("/builds/validate", response_model=BuildValidation, tags=["builds"], dependencies=admin,
              summary="Validate a build without saving it")
    def validate_build_endpoint(req: BuildValidateRequest, repo: Repository = Depends(get_repo)):
        return builds_mod.validate_build(req.build, repo.get_config())

    @api.post("/builds", response_model=BuildResponse, status_code=201, tags=["builds"], dependencies=admin,
              summary="Create a build")
    def create_build(req: BuildCreate, repo: Repository = Depends(get_repo)):
        done = repo.create_build(req.expected_revision, req.build)
        return BuildResponse(
            revision=done.config.revision,
            build=builds_mod.describe_build(done.config.get_build(req.build.id), done.config),
        )

    @api.get("/builds/{build_id}", response_model=BuildResponse, tags=["builds"], dependencies=admin,
             summary="Get one build with validation")
    def get_build(build_id: str, repo: Repository = Depends(get_repo)):
        cfg = repo.get_config()
        b = cfg.get_build(build_id)
        if b is None:
            raise NotFoundError("build", build_id)
        return BuildResponse(revision=cfg.revision, build=builds_mod.describe_build(b, cfg))

    @api.patch("/builds/{build_id}", response_model=BuildResponse, tags=["builds"], dependencies=admin,
               summary="Edit a build. Marking it 'verified' is refused unless it validates.")
    def patch_build(build_id: str, patch: BuildPatch, repo: Repository = Depends(get_repo)):
        done = repo.update_build(build_id, patch)
        return BuildResponse(
            revision=done.config.revision,
            build=builds_mod.describe_build(done.config.get_build(build_id), done.config),
        )

    @api.delete("/builds/{build_id}", response_model=MutationResult, tags=["builds"], dependencies=admin,
                summary="Delete a build")
    def delete_build(build_id: str, expected_revision: int = Query(...), repo: Repository = Depends(get_repo)):
        done = repo.delete_build(expected_revision, build_id)
        return MutationResult(revision=done.config.revision, description=done.description)

    @api.post("/builds/{build_id}/default", response_model=BuildResponse, tags=["builds"], dependencies=admin,
              summary="Make a build the default recommendation for its specialization")
    def default_build(build_id: str, req: DefaultBuildRequest, repo: Repository = Depends(get_repo)):
        done = repo.set_default_build(req.expected_revision, build_id)
        return BuildResponse(
            revision=done.config.revision,
            build=builds_mod.describe_build(done.config.get_build(build_id), done.config),
        )

    def catalog_response(cfg: Config, full: bool, downgraded: Optional[list[str]] = None) -> CatalogResponse:
        cat = cfg.talent_catalog
        if cat is None:
            return CatalogResponse(revision=cfg.revision, available=False, downgraded_builds=downgraded or [])
        return CatalogResponse(
            revision=cfg.revision,
            available=True,
            client_version=cat.client_version,
            source=cat.source,
            retrieved_at=cat.retrieved_at,
            data_status=cat.data_status,
            notes=cat.notes,
            points_per_tier=cat.points_per_tier,
            classes=[
                CatalogSummaryClass(
                    id=c.id,
                    trees=[CatalogSummaryTree(id=t.id, name=t.name, talent_count=len(t.talents)) for t in c.trees],
                )
                for c in cat.classes
            ],
            catalog=cat if full else None,
            downgraded_builds=downgraded or [],
        )

    @api.get("/talents/catalog", response_model=CatalogResponse, response_model_exclude_none=True, tags=["builds"],
             dependencies=admin, summary="The imported talent catalog (summary, or full with full=true)")
    def get_catalog(full: bool = False, repo: Repository = Depends(get_repo)):
        return catalog_response(repo.get_config(), full)

    @api.put("/talents/catalog", response_model=CatalogResponse, response_model_exclude_none=True, tags=["builds"],
             dependencies=admin,
             summary="Import (or remove) talent data. Verified builds that no longer validate are downgraded.")
    def put_catalog(req: CatalogUpdate, repo: Repository = Depends(get_repo)):
        done, downgraded = repo.set_catalog(req.expected_revision, req.catalog)
        return catalog_response(done.config, False, downgraded)

    app.include_router(api)

    # ======================================================================
    # Static front end
    # ======================================================================
    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


app = create_app()
