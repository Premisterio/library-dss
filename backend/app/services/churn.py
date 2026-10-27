"""Churn use cases: queue a training run, train it (worker), list, activate, delete, scores.

Training also estimates the effects of retention actions from the dataset's past campaign, so a
run holds everything a retention plan needs.
"""

from dataclasses import asdict
from typing import Any

import polars as pl
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.domain.churn import examples
from app.domain.churn.scoring import score
from app.domain.churn.training import NotEnoughHistoryError, summarize, train
from app.domain.enums import JobKind, JobStage
from app.domain.retention.effects import estimate, participants
from app.ingest import reader
from app.models import Analyst, ChurnRun, ChurnScore, Dataset, DatasetFile, Job
from app.services import jobs


def create_run(session: Session, analyst: Analyst, dataset: Dataset) -> ChurnRun:
    """Queue the training of a churn model on a ready dataset with retention data."""
    if dataset.status != "ready":
        raise ApiError(409, "dataset.not_ready", f"The dataset is {dataset.status}, not ready")
    if "retention" not in dataset.capabilities:
        raise ApiError(
            409,
            "churn.not_supported",
            "The dataset has no subscription periods or retention campaign to learn from",
        )
    job = jobs.enqueue(
        session, kind=JobKind.TRAIN_CHURN, owner_id=analyst.id, dataset_id=dataset.id
    )
    run = ChurnRun(owner_id=analyst.id, dataset_id=dataset.id, job_id=job.id)
    session.add(run)
    session.commit()
    return run


def run_training(session: Session, job: Job, progress: jobs.Progress) -> dict[str, Any]:
    """Worker handler: train, backtest and explain a model, then score the members at risk."""
    run = session.scalar(select(ChurnRun).where(ChurnRun.job_id == job.id))
    file = session.get(DatasetFile, job.dataset_id)
    if run is None or file is None:
        raise ApiError(409, "churn.missing", "The run or its dataset was deleted before training")
    progress(0.05, JobStage.PARSE)
    parsed = reader.parse(reader.decode(file.content))
    progress(0.25, JobStage.FEATURES)
    rows = examples(parsed.frames, parsed.as_of, parsed.timezone)
    progress(0.4, JobStage.BACKTEST)
    try:
        training = train(rows)
    except NotEnoughHistoryError as exc:
        raise ApiError(422, "churn.not_enough_history", str(exc)) from exc
    progress(0.8, JobStage.SCORING)
    scores = score(training, parsed.frames, parsed.as_of, parsed.timezone)
    progress(0.9, JobStage.EFFECTS)
    effects = estimate(participants(parsed.frames, parsed.timezone))
    discounts = parsed.frames["campaign_assignments"].filter(pl.col("arm") == "discount")
    run.chosen_model = training.chosen
    run.result = {
        "summary": {
            "examples": rows.height,
            "cutoffs": rows["k"].n_unique(),
            "churn_rate": rows.select(pl.col("churned").mean()).item(),
            "scored": len(scores),
            "expected_churners": sum(s.probability for s in scores),
        },
        "models": [asdict(summary) for summary in summarize(training.evaluations)],
        "backtest": [asdict(evaluation) for evaluation in training.evaluations],
        "importance": [asdict(item) for item in training.importance],
        "coefficients": [asdict(item) for item in training.coefficients],
        "typical": training.typical,
        "effects": [asdict(effect) for effect in effects],
        # the campaign's discount, whose effect was measured; null without a campaign
        "campaign_discount": discounts.select(pl.col("discount_pct").median()).item(),
    }
    session.add_all(
        ChurnScore(
            run_id=run.id,
            user_id=s.user_id,
            rank=s.rank,
            probability=s.probability,
            plan=s.plan,
            period_end=s.period_end,
            period_price=s.period_price,
            features=s.features,
            reasons=[asdict(reason) for reason in s.reasons],
        )
        for s in scores
    )
    progress(1.0, JobStage.DONE)
    return {"run_id": run.id, "chosen_model": training.chosen, "scored": len(scores)}


def get_for(session: Session, run_id: int, analyst: Analyst) -> ChurnRun:
    run = session.get(ChurnRun, run_id)
    if run is None or run.owner_id != analyst.id:
        raise ApiError(404, "churn.not_found", "No such churn run")
    return run


def list_for(
    session: Session,
    analyst: Analyst,
    *,
    dataset_id: int | None,
    active: bool | None = None,
    limit: int,
    offset: int,
) -> tuple[list[ChurnRun], int]:
    query = select(ChurnRun).where(ChurnRun.owner_id == analyst.id)
    if dataset_id is not None:
        query = query.where(ChurnRun.dataset_id == dataset_id)
    if active is not None:
        query = query.where(ChurnRun.active == active)
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = session.scalars(
        query.order_by(ChurnRun.created_at.desc(), ChurnRun.id.desc()).limit(limit).offset(offset)
    )
    return list(items), total


def ensure_trained(run: ChurnRun) -> None:
    if run.job.status != "succeeded":
        raise ApiError(409, "churn.not_trained", f"The run is {run.job.status}, not trained")


def activate(session: Session, run: ChurnRun) -> ChurnRun:
    """Make this run the one decisions use for its dataset."""
    ensure_trained(run)
    # One activation per dataset at a time: concurrent ones would lock the runs in turn.
    session.execute(select(Dataset.id).where(Dataset.id == run.dataset_id).with_for_update())
    session.execute(
        update(ChurnRun)
        .where(ChurnRun.dataset_id == run.dataset_id, ChurnRun.id != run.id)
        .values(active=False)
    )
    run.active = True
    session.commit()
    return run


def delete(session: Session, run: ChurnRun) -> None:
    if run.job.status not in jobs.TERMINAL:
        raise ApiError(409, "churn.busy", "The run is being trained; try again when it finishes")
    session.delete(run)  # its scores cascade in the database
    session.commit()


def scores_for(
    session: Session, run: ChurnRun, *, limit: int, offset: int
) -> tuple[list[ChurnScore], int]:
    """The members at risk, the riskiest first."""
    ensure_trained(run)
    query = select(ChurnScore).where(ChurnScore.run_id == run.id)
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = session.scalars(query.order_by(ChurnScore.rank).limit(limit).offset(offset))
    return list(items), total


def score_for(session: Session, run: ChurnRun, user_id: str) -> ChurnScore:
    ensure_trained(run)
    found = session.get(ChurnScore, (run.id, user_id))
    if found is None:
        raise ApiError(404, "churn.member_not_scored", "The member is not at risk in this run")
    return found
