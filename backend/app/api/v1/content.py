"""Content acquisition: rank a dataset's titles on offer by the analyst's weighted criteria, pick
the portfolio within a budget, and approve it as a decision (a report of kind `content`)."""

from typing import Literal, Self

from fastapi import APIRouter, status
from pydantic import BaseModel, Field, model_validator

from app.api.deps import CurrentAnalyst
from app.api.schemas import Text
from app.api.v1.analytics import ReportSectionOut
from app.api.v1.reports import ReportOut, report_out
from app.core.db import SessionDep
from app.domain.content import ahp
from app.domain.content.decision import CRITERIA, Choice
from app.services import content, datasets

router = APIRouter(prefix="/datasets/{dataset_id}/content", tags=["content"])

CriterionKey = Literal["demand_searches", "author_loans", "genre_loans", "genre_holds_per_copy"]


class JudgementIn(BaseModel):
    """How many times more important `criterion` is than `compared_with` (Saaty's scale)."""

    criterion: CriterionKey
    compared_with: CriterionKey
    value: float = Field(ge=1 / ahp.SCALE_MAX, le=ahp.SCALE_MAX, description="1/9..9; 1: equal.")

    @model_validator(mode="after")
    def _two_criteria(self) -> Self:
        if self.criterion == self.compared_with:
            raise ValueError("a criterion is not compared with itself")
        return self


class ContentIn(BaseModel):
    judgements: list[JudgementIn] = Field(
        default_factory=list,
        max_length=50,
        description="Pairwise judgements; a pair left out counts as equally important, and a "
        "later judgement of the same pair wins.",
    )
    budget: float = Field(ge=0, le=1e9, description="UAH for the licences.")
    max_per_genre: int | None = Field(
        None, ge=1, le=1000, description="At most this many titles of one genre."
    )


class ContentApproveIn(BaseModel):
    title: Text = Field(min_length=1, max_length=200)
    decision: ContentIn


def _choice(body: ContentIn) -> Choice:
    index = {key: i for i, key in enumerate(CRITERIA)}
    return Choice(
        judgements=[
            ahp.Judgement(index[j.criterion], index[j.compared_with], j.value)
            for j in body.judgements
        ],
        budget=body.budget,
        max_per_genre=body.max_per_genre,
    )


@router.post("/evaluate", summary="Rank the titles on offer and pick the portfolio")
def evaluate_content(
    dataset_id: int, body: ContentIn, analyst: CurrentAnalyst, session: SessionDep
) -> ReportSectionOut:
    dataset = datasets.get_for(session, dataset_id, analyst)
    decision = content.evaluate(session, dataset, _choice(body))
    return ReportSectionOut.model_validate(
        {**decision.section.to_dict(), "as_of": dataset.as_of, "timezone": dataset.timezone}
    )


@router.post(
    "/approve",
    status_code=status.HTTP_201_CREATED,
    summary="Approve the portfolio: freeze it as a decision (a report of kind `content`)",
)
def approve_content(
    dataset_id: int, body: ContentApproveIn, analyst: CurrentAnalyst, session: SessionDep
) -> ReportOut:
    dataset = datasets.get_for(session, dataset_id, analyst)
    report = content.approve(
        session, analyst, dataset, title=body.title, choice=_choice(body.decision)
    )
    return ReportOut.model_validate(report_out(report))
