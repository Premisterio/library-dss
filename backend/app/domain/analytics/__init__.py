"""Descriptive analytics of a dataset, computed once at import (as of the dataset's `as_of`).

`compute_all` returns one `Section` per analytics page; the API serves them as stored JSON.
"""

from collections.abc import Callable
from datetime import date

from app.domain.analytics import (
    cohorts,
    content,
    overview,
    search,
    segments,
    subscriptions,
    usage,
)
from app.domain.analytics.common import Context, Frames
from app.domain.analytics.model import Section

SECTIONS: dict[str, Callable[[Frames, Context], Section]] = {
    "overview": overview.build,
    "usage": usage.build,
    "content": content.build,
    "segments": segments.build,
    "search": search.build,
    "subscriptions": subscriptions.build,
    "cohorts": cohorts.build,
}


def compute_all(frames: Frames, as_of: date, timezone: str) -> dict[str, Section]:
    ctx = Context.at(as_of, timezone)
    return {key: build(frames, ctx) for key, build in SECTIONS.items()}
