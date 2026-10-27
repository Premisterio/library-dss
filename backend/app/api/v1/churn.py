"""Churn models: train one on a dataset (a job), read its quality and explanations, activate it,
and list the members at risk at the dataset's as_of with their probabilities and reasons."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Path, Query, Response, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentAnalyst
from app.api.schemas import JobOut, JobStatus, Page, TaskError, Text
from app.core.db import SessionDep
from app.domain.analytics.model import Unit
from app.domain.churn.features import FEATURES, FeatureGroup, FeatureKind
from app.domain.churn.models import ModelKey
from app.models import ChurnRun, ChurnScore
from app.services import churn, datasets

router = APIRouter(tags=["churn"])

FeatureValue = bool | float | str | None


class ChurnSummaryOut(BaseModel):
    examples: int = Field(description="Labelled renewals the models learned from.")
    cutoffs: int = Field(description="Rolling cutoffs with labelled renewals.")
    churn_rate: float = Field(description="Share of those renewals that ended in churn (0..1).")
    scored: int = Field(description="Members at risk at as_of, scored by the chosen model.")
    expected_churners: float = Field(description="Sum of their probabilities of churn.")


class ChurnRunOut(BaseModel):
    """A churn model trained by a job; `status` and `error` are the job's."""

    id: int
    dataset_id: int
    job_id: uuid.UUID = Field(description="The training job.")
    status: JobStatus
    error: TaskError | None
    active: bool = Field(description="Decisions on this dataset use this run.")
    chosen_model: ModelKey | None = Field(
        description="The learned model with the lowest mean Brier score; label in enums "
        "`churn_model`. null until trained."
    )
    summary: ChurnSummaryOut | None
    created_at: datetime
    finished_at: datetime | None


class CalibrationBinOut(BaseModel):
    predicted: float = Field(description="Mean predicted probability in the bin.")
    observed: float = Field(description="Share of the bin that churned.")
    members: int


class MetricsOut(BaseModel):
    """Quality on one test cutoff; labels in enums `churn_metric`. null: undefined."""

    members: int
    churned: int
    roc_auc: float | None
    pr_auc: float | None
    brier: float
    brier_skill: float | None
    ece: float
    lift: float | None
    calibration: list[CalibrationBinOut] = Field(description="Equal-count bins by risk.")


class EvaluationOut(BaseModel):
    origin: int = Field(description="Test cutoff k (0 is the newest); older cutoffs train.")
    model: ModelKey
    metrics: MetricsOut


class ModelSummaryOut(BaseModel):
    """A model's metrics averaged over the backtest origins where they are defined."""

    model: ModelKey
    origins: int
    roc_auc: float | None
    pr_auc: float | None
    brier: float
    brier_skill: float | None
    ece: float
    lift: float | None


class ImportanceOut(BaseModel):
    feature: str = Field(description="Feature key; label in enums `churn_feature`.")
    brier_increase: float = Field(description="Brier score increase when the feature is shuffled.")


class CoefficientOut(BaseModel):
    feature: str
    code: str | None = Field(description="Category code of a one-hot column.")
    missing: bool = Field(description="The column says the value is missing.")
    value: float = Field(description="Change of the log-odds per standard deviation.")


class ChurnRunDetailOut(ChurnRunOut):
    models: list[ModelSummaryOut] = Field(description="Every model, averaged over the backtest.")
    backtest: list[EvaluationOut]
    importance: list[ImportanceOut] = Field(description="Of the chosen model, highest first.")
    coefficients: list[CoefficientOut] = Field(description="Logistic regression only.")


class ChurnRunPage(Page[ChurnRunOut]):
    pass


class ChurnRunAccepted(BaseModel):
    run: ChurnRunOut
    job: JobOut


class Described(BaseModel):
    """How to show a feature's values."""

    kind: FeatureKind = Field(description="`number`, `flag` (true/false) or `category` (a code).")
    unit: Unit | None = Field(description="Unit of a number; null for a unitless number.")
    enum: str | None = Field(description="Enums group with the labels of a category's codes.")


class ReasonOut(Described):
    """Why the probability is high: with the typical value it would be `effect` lower."""

    feature: str = Field(description="Feature key; label in enums `churn_feature`.")
    value: FeatureValue = Field(description="The member's value.")
    typical: FeatureValue = Field(description="The typical value among members.")
    effect: float = Field(description="Probability drop with the typical value (0..1).")


class ChurnScoreOut(BaseModel):
    user_id: str
    rank: int = Field(description="1 is the highest probability.")
    probability: float = Field(description="Probability of churn at the renewal (0..1).")
    plan: str = Field(description="Plan code; label in enums `plan`.")
    period_end: datetime = Field(description="When the paid period ends and renewal is due.")
    reasons: list[ReasonOut] = Field(description="Up to three, strongest first.")


class FeatureValueOut(Described):
    feature: str
    group: FeatureGroup = Field(description="Label in enums `churn_feature_group`.")
    value: FeatureValue
    typical: FeatureValue


class ChurnScoreDetailOut(ChurnScoreOut):
    features: list[FeatureValueOut] = Field(description="Every feature, in the model's order.")


class ChurnScorePage(Page[ChurnScoreOut]):
    pass


def _run(run: ChurnRun) -> dict[str, Any]:
    result = run.result or {}
    return {
        "id": run.id,
        "dataset_id": run.dataset_id,
        "job_id": run.job_id,
        "status": run.job.status,
        "error": run.job.error,
        "active": run.active,
        "chosen_model": run.chosen_model,
        "summary": result.get("summary"),
        "created_at": run.created_at,
        "finished_at": run.job.finished_at,
    }


SPEC = {feature.key: feature for feature in FEATURES}


def _described(key: str) -> dict[str, Any]:
    feature = SPEC[key]
    return {"kind": feature.kind, "unit": feature.unit, "enum": feature.enum}


def _score(found: ChurnScore) -> dict[str, Any]:
    return {
        "user_id": found.user_id,
        "rank": found.rank,
        "probability": found.probability,
        "plan": found.plan,
        "period_end": found.period_end,
        "reasons": [{**reason, **_described(reason["feature"])} for reason in found.reasons],
    }


RunId = Annotated[int, Path(description="Churn run id.")]


@router.post(
    "/datasets/{dataset_id}/churn-runs",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Train a churn model on a dataset",
    description="Queues a job that backtests the models, chooses one, explains it and scores "
    "the members at risk at the dataset's as_of. The `Location` header points to the job.",
)
def create_churn_run(
    dataset_id: int, response: Response, analyst: CurrentAnalyst, session: SessionDep
) -> ChurnRunAccepted:
    run = churn.create_run(session, analyst, datasets.get_for(session, dataset_id, analyst))
    response.headers["Location"] = f"/api/v1/jobs/{run.job_id}"
    return ChurnRunAccepted(
        run=ChurnRunOut.model_validate(_run(run)), job=JobOut.model_validate(run.job)
    )


@router.get("/churn-runs", summary="Your churn runs, newest first")
def list_churn_runs(
    analyst: CurrentAnalyst,
    session: SessionDep,
    dataset_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ChurnRunPage:
    items, total = churn.list_for(
        session, analyst, dataset_id=dataset_id, limit=limit, offset=offset
    )
    return ChurnRunPage(
        items=[ChurnRunOut.model_validate(_run(run)) for run in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/churn-runs/{run_id}", summary="One churn run with its backtest and explanations")
def get_churn_run(run_id: RunId, analyst: CurrentAnalyst, session: SessionDep) -> ChurnRunDetailOut:
    run = churn.get_for(session, run_id, analyst)
    result = run.result or {}
    return ChurnRunDetailOut.model_validate(
        {
            **_run(run),
            "models": result.get("models", []),
            "backtest": result.get("backtest", []),
            "importance": result.get("importance", []),
            "coefficients": result.get("coefficients", []),
        }
    )


@router.post(
    "/churn-runs/{run_id}/activate",
    summary="Make a trained run the one decisions use for its dataset",
)
def activate_churn_run(run_id: RunId, analyst: CurrentAnalyst, session: SessionDep) -> ChurnRunOut:
    run = churn.activate(session, churn.get_for(session, run_id, analyst))
    return ChurnRunOut.model_validate(_run(run))


@router.delete(
    "/churn-runs/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a churn run with its scores",
)
def delete_churn_run(run_id: RunId, analyst: CurrentAnalyst, session: SessionDep) -> Response:
    churn.delete(session, churn.get_for(session, run_id, analyst))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/churn-runs/{run_id}/scores", summary="The members at risk, the riskiest first")
def list_churn_scores(
    run_id: RunId,
    analyst: CurrentAnalyst,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ChurnScorePage:
    run = churn.get_for(session, run_id, analyst)
    items, total = churn.scores_for(session, run, limit=limit, offset=offset)
    return ChurnScorePage(
        items=[ChurnScoreOut.model_validate(_score(found)) for found in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/churn-runs/{run_id}/scores/{user_id}",
    summary="One member at risk with every feature and its typical value",
)
def get_churn_score(
    run_id: RunId,
    user_id: Annotated[Text, Path(max_length=40)],
    analyst: CurrentAnalyst,
    session: SessionDep,
) -> ChurnScoreDetailOut:
    run = churn.get_for(session, run_id, analyst)
    found = churn.score_for(session, run, user_id)
    typical = (run.result or {}).get("typical", {})
    features = [
        {
            "feature": feature.key,
            "group": feature.group,
            **_described(feature.key),
            "value": found.features.get(feature.key),
            "typical": typical.get(feature.key),
        }
        for feature in FEATURES
    ]
    return ChurnScoreDetailOut.model_validate({**_score(found), "features": features})
