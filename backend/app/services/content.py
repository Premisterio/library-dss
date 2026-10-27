"""Content acquisition: evaluate a dataset's offer under the analyst's judgements and budget, and
approve the result as a decision, kept as a report of kind `content` (DESIGN.md §2.9)."""

from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.domain.content.decision import CRITERIA, Choice, Decision, decide
from app.models import Analyst, Dataset, Report
from app.services import analytics, reports


def _offer(session: Session, dataset: Dataset) -> list[dict[str, Any]]:
    """The titles on offer with their criteria, from the stored `candidates` section."""
    section = analytics.section_for(session, dataset, "candidates")
    rows = next((c["rows"] for c in section["charts"] if c["key"] == "candidate_criteria"), [])
    if not rows:
        raise ApiError(409, "content.no_candidates", "The dataset has no titles on offer")
    return rows


def evaluate(session: Session, dataset: Dataset, choice: Choice) -> Decision:
    return decide(_offer(session, dataset), choice)


def approve(
    session: Session, analyst: Analyst, dataset: Dataset, *, title: str, choice: Choice
) -> Report:
    """Freeze the evaluation as a decision with the judgements and budget it was made with.
    Judgements too inconsistent to trust (CR above 0.10) cannot be approved."""
    decision = evaluate(session, dataset, choice)
    if not decision.weights.consistent_enough:
        raise ApiError(
            409,
            "content.inconsistent",
            "The judgements contradict each other (CR above 0.10); revise them first",
        )
    params = {
        "budget": choice.budget,
        "max_per_genre": choice.max_per_genre,
        "judgements": [
            {"criterion": CRITERIA[j.row], "compared_with": CRITERIA[j.column], "value": j.value}
            for j in choice.judgements
        ],
    }
    return reports.freeze(
        session,
        analyst,
        dataset,
        kind="content",
        title=title,
        payloads=[decision.section.to_dict()],
        params=params,
    )
