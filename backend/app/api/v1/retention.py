"""Retention plans: the best e-mails and discounts for a churn run's members at risk under a
budget, previewed on the fly and approved as a decision (a report of kind `retention`)."""

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentAnalyst
from app.api.schemas import Text
from app.api.v1.analytics import ReportSectionOut
from app.api.v1.reports import ReportOut, report_out
from app.core.db import SessionDep
from app.services import churn, retention

router = APIRouter(prefix="/churn-runs/{run_id}/plan", tags=["retention"])


class AssumedEffects(BaseModel):
    """The analyst's own effects, used instead of the campaign's."""

    email: float = Field(
        0.0, ge=-1, le=1, description="Change of the churn rate an e-mail makes (0..1)."
    )
    discount: float = Field(0.0, ge=-1, le=1, description="Change a discount makes (0..1).")
    discount_pct: float = Field(0.2, gt=0, lt=1, description="Share of the renewal price off.")


class PlanIn(BaseModel):
    budget: float = Field(
        ge=0, le=1e9, description="UAH: the expected spend on e-mails and discounts."
    )
    horizon_months: int = Field(
        12, ge=1, le=60, description="Months of a kept member's price counted as gained."
    )
    email_cost: float = Field(2.0, ge=0, le=1e5, description="UAH per e-mail.")
    max_emails: int | None = Field(None, ge=0, le=10**6)
    max_discounts: int | None = Field(None, ge=0, le=10**6)
    cautious: bool = Field(
        False, description="Use the least favourable 95% bound of each campaign effect."
    )
    by_segment: bool = Field(
        False,
        description="Use each segment's own (shrunk) campaign effect instead of the action's "
        "overall one. On a small campaign the segment estimates are noisy and tend to cost more "
        "than they gain.",
    )
    assumed: AssumedEffects | None = Field(
        None,
        description="Effects to use instead of the campaign's (then any discount size goes); "
        "with the campaign's, the campaign's discount is offered.",
    )


class ApproveIn(BaseModel):
    title: Text = Field(min_length=1, max_length=200)
    plan: PlanIn


def _choice(body: PlanIn) -> retention.Choice:
    assumed = body.assumed
    return retention.Choice(
        budget=body.budget,
        horizon_months=body.horizon_months,
        email_cost=body.email_cost,
        max_emails=body.max_emails,
        max_discounts=body.max_discounts,
        cautious=body.cautious,
        by_segment=body.by_segment,
        assumed=None if assumed is None else {"email": assumed.email, "discount": assumed.discount},
        assumed_discount_pct=0.2 if assumed is None else assumed.discount_pct,
    )


@router.post("", summary="Preview the best plan of actions under a budget")
def preview_retention_plan(
    run_id: int, body: PlanIn, analyst: CurrentAnalyst, session: SessionDep
) -> ReportSectionOut:
    run = churn.get_for(session, run_id, analyst)
    section = retention.preview(session, run, _choice(body))
    return ReportSectionOut.model_validate(
        {**section.to_dict(), **retention.snapshot_of(session, run)}
    )


@router.post(
    "/approve",
    status_code=status.HTTP_201_CREATED,
    summary="Approve a plan: freeze it as a decision (a report of kind `retention`)",
)
def approve_retention_plan(
    run_id: int, body: ApproveIn, analyst: CurrentAnalyst, session: SessionDep
) -> ReportOut:
    run = churn.get_for(session, run_id, analyst)
    report = retention.approve(session, analyst, run, title=body.title, choice=_choice(body.plan))
    return ReportOut.model_validate(report_out(report))
