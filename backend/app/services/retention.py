"""Retention plans: a what-if preview over the members at risk of a churn run, and approving one
as a decision, kept as a report of kind `retention` (DESIGN.md §2.9)."""

from dataclasses import asdict, dataclass
from typing import Any

import polars as pl
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.domain.analytics.model import Section
from app.domain.retention.effects import ACTIONS, Action, Effect
from app.domain.retention.plan import (
    Scenario,
    capped,
    curve,
    effect_table,
    members,
    plan,
)
from app.domain.retention.report import plan_section
from app.models import Analyst, ChurnRun, ChurnScore, Dataset, Report
from app.services import churn, reports


@dataclass(frozen=True)
class Choice:
    """What the analyst chooses for a plan."""

    budget: float
    horizon_months: int = 12
    email_cost: float = 2.0
    max_emails: int | None = None
    max_discounts: int | None = None
    cautious: bool = False
    by_segment: bool = False
    # The analyst's own effects (differences of churn rates) and discount, instead of the
    # campaign's; None: the campaign's.
    assumed: dict[str, float] | None = None
    assumed_discount_pct: float = 0.2


def _effects(run: ChurnRun) -> tuple[list[Effect], float | None]:
    result = run.result or {}
    if "effects" not in result:
        raise ApiError(
            409,
            "retention.no_effects",
            "The run was trained before action effects were estimated; train the model again",
        )
    return [Effect(**effect) for effect in result["effects"]], result.get("campaign_discount")


def _members(session: Session, run: ChurnRun) -> pl.DataFrame:
    scores = session.scalars(select(ChurnScore).where(ChurnScore.run_id == run.id))
    rows = [
        {
            "user_id": s.user_id,
            "probability": s.probability,
            "period_price": s.period_price,
            **s.features,
        }
        for s in scores
    ]
    if not rows:
        raise ApiError(409, "retention.nobody_at_risk", "Nobody is at risk in this run")
    return members(pl.DataFrame(rows, infer_schema_length=None))


def _scenario(run: ChurnRun, choice: Choice) -> tuple[list[Effect], Scenario]:
    effects, campaign_discount = _effects(run)
    if choice.assumed is None and not any(e.difference is not None for e in effects):
        raise ApiError(
            409,
            "retention.no_campaign",
            "The dataset has no campaign to measure effects on; give the effects as assumptions",
        )
    # The campaign measured one discount, so a plan on its effects offers that one.
    assumed: dict[Action, float] | None
    if choice.assumed is None:
        assumed, discount_pct = None, campaign_discount or 0.0
    else:
        assumed = {action: choice.assumed.get(action, 0.0) for action in ACTIONS}
        discount_pct = choice.assumed_discount_pct
    return effects, Scenario(
        budget=choice.budget,
        discount_pct=discount_pct,
        horizon_months=choice.horizon_months,
        email_cost=choice.email_cost,
        max_emails=choice.max_emails,
        max_discounts=choice.max_discounts,
        cautious=choice.cautious,
        by_segment=choice.by_segment,
        assumed=assumed,
    )


def _plan(session: Session, run: ChurnRun, choice: Choice) -> tuple[Section, Scenario]:
    churn.ensure_trained(run)
    effects, scenario = _scenario(run, choice)
    people = _members(session, run)
    base_rate = people.select(pl.col("probability").mean()).item()
    table = effect_table(effects, scenario, base_rate=base_rate)
    section = plan_section(
        plan(people, table, scenario),
        curve(people, table, scenario),
        people,
        effects,
        scenario,
        capped(effects, scenario, base_rate),
    )
    return section, scenario


def preview(session: Session, run: ChurnRun, choice: Choice) -> Section:
    """The best plan for the run's members at risk, with the budget curve and the effects."""
    return _plan(session, run, choice)[0]


def snapshot_of(session: Session, run: ChurnRun) -> dict[str, Any]:
    """The date and time zone the run's dataset describes."""
    dataset = session.get_one(Dataset, run.dataset_id)
    return {"as_of": dataset.as_of, "timezone": dataset.timezone}


def approve(
    session: Session, analyst: Analyst, run: ChurnRun, *, title: str, choice: Choice
) -> Report:
    """Freeze the plan as a decision: a `retention` report with the parameters it was made with.
    Decisions use the active run only."""
    if not run.active:
        raise ApiError(
            409, "retention.not_active", "Activate the run first: decisions use the active model"
        )
    section, scenario = _plan(session, run, choice)
    dataset = session.get_one(Dataset, run.dataset_id)
    chosen = {k: v for k, v in asdict(choice).items() if k != "assumed_discount_pct"}
    # The discount offered: the campaign's, or the analyst's with assumed effects.
    params: dict[str, Any] = {"run_id": run.id, **chosen, "discount_pct": scenario.discount_pct}
    return reports.freeze(
        session,
        analyst,
        dataset,
        kind="retention",
        title=title,
        payloads=[section.to_dict()],
        params=params,
    )
