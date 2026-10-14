"""Bachelor-era v1 format (nested users JSON) → the v2 tables.

v1 has no licences, holds, campaigns or candidate titles, and its codes (age ranges, devices,
plans) predate the v2 taxonomy, so such datasets support descriptive analytics only. Book genres
are mapped onto the v2 taxonomy; every unmapped field is kept in `users.extra`.
"""

from datetime import date, datetime
from typing import Any

import orjson
import polars as pl

from app.ingest import IngestError
from app.ingest.frames import empty_frame
from app.utils.dates import DATE_FORMAT, parse_utc

V1_GENRES = {
    "fiction": "fiction",
    "mystery": "mystery_thriller",
    "thriller": "mystery_thriller",
    "science_fiction": "science_fiction",
    "fantasy": "fantasy",
    "biography": "biography",
    "history": "history",
    "romance": "romance",
    "self_help": "self_help",
    "business": "business",
    "science": "science",
    "poetry": "poetry_drama",
    "philosophy": "philosophy_religion",
    "technology": "technology",
    "travel": "arts",
}
PLAN_DAYS = {"monthly": 30, "quarterly": 91, "annual": 365}


def frames_from_v1(document: dict[str, Any]) -> dict[str, pl.DataFrame]:
    users_in = document.get("users")
    if not isinstance(users_in, list) or not users_in:
        raise IngestError("dataset.invalid", "A v1 file must have a non-empty 'users' list")
    users: list[dict[str, Any]] = []
    books: dict[str, dict[str, Any]] = {}
    loans: list[dict[str, Any]] = []
    sessions: list[dict[str, Any]] = []
    searches: list[dict[str, Any]] = []
    periods: list[dict[str, Any]] = []
    try:
        for user in users_in:
            uid, account, profile = user["user_id"], user["account"], user["profile"]
            activity = user.get("activity", {})
            users.append(
                {
                    "user_id": uid,
                    "registered_at": account["registration_date"],
                    "age_range": profile.get("age_range"),
                    "education": profile.get("education_level"),
                    "language_pref": None,
                    "email_opt_in": (account.get("communication_preferences") or {}).get(
                        "newsletters"
                    ),
                    "interests": list(profile.get("interests") or []),
                    "extra": orjson.dumps(
                        {
                            "account_type": account.get("account_type"),
                            "subscription_status": account.get("subscription_status"),
                            "subscription_plan": account.get("subscription_plan"),
                            "login_frequency": account.get("login_frequency"),
                            "last_login": account.get("last_login"),
                            "devices": account.get("devices"),
                            "profession": profile.get("profession"),
                            "language_preferences": profile.get("language_preferences"),
                        }
                    ).decode(),
                }
            )
            for b in activity.get("books_borrowed", []):
                books.setdefault(
                    b["book_id"],
                    {
                        "book_id": b["book_id"],
                        "title": b["title"],
                        "authors": b["author"],
                        "genre": V1_GENRES.get(b.get("genre"), "fiction"),
                    },
                )
                loans.append(
                    {
                        "loan_id": f"l{len(loans) + 1:07d}",
                        "user_id": uid,
                        "book_id": b["book_id"],
                        "borrowed_at": b["borrowed_date"],
                        "returned_at": b.get("return_date"),
                        "completed": b.get("completed"),
                        "rating": b.get("rating"),
                        "via_hold": False,
                    }
                )
            for s in activity.get("reading_sessions", []):
                sessions.append(
                    {
                        "user_id": uid,
                        "book_id": s["book_id"],
                        "started_at": s["date"],
                        "minutes": s["duration_minutes"],
                        "pages": s["pages_read"],
                        "device": s.get("device"),
                    }
                )
            for s in activity.get("search_history", []):
                searches.append(
                    {"user_id": uid, "searched_at": s["timestamp"], "query": s["query"]}
                )
            plan = account.get("subscription_plan") or "monthly"
            for pay in account.get("payment_history", []):
                periods.append(
                    {
                        "user_id": uid,
                        "plan": plan,
                        "period_start": pay["date"],
                        "days": PLAN_DAYS.get(plan, 30),
                        "amount": float(pay["amount"]),
                    }
                )
    except (KeyError, TypeError, ValueError) as exc:
        raise IngestError(
            "dataset.invalid", f"v1 file is missing or has a bad field: {exc}"
        ) from exc

    try:
        return _frames(users, list(books.values()), loans, sessions, searches, periods)
    except pl.exceptions.PolarsError as exc:
        raise IngestError(
            "dataset.invalid",
            "v1 file has values of the wrong type (timestamps must look like "
            "2025-02-01T17:17:09Z, payment dates like 2025-02-01)",
        ) from exc


Str, Int, Bool = pl.String, pl.Int64, pl.Boolean
V1_SCHEMAS: dict[str, dict[str, Any]] = {
    "users": {
        "user_id": Str,
        "registered_at": Str,
        "age_range": Str,
        "education": Str,
        "language_pref": Str,
        "email_opt_in": Bool,
        "interests": pl.List(Str),
        "extra": Str,
    },
    "books": {"book_id": Str, "title": Str, "authors": Str, "genre": Str},
    "loans": {
        "loan_id": Str,
        "user_id": Str,
        "book_id": Str,
        "borrowed_at": Str,
        "returned_at": Str,
        "completed": Bool,
        "rating": Int,
        "via_hold": Bool,
    },
    "reading_sessions": {
        "user_id": Str,
        "book_id": Str,
        "started_at": Str,
        "minutes": Int,
        "pages": Int,
        "device": Str,
    },
    "searches": {"user_id": Str, "searched_at": Str, "query": Str},
    "subscription_periods": {
        "user_id": Str,
        "plan": Str,
        "period_start": Str,
        "days": Int,
        "amount": pl.Float64,
    },
}


def _frames(*tables: list[dict[str, Any]]) -> dict[str, pl.DataFrame]:
    users, books, loans, sessions, searches, periods = (
        pl.DataFrame(rows, schema=V1_SCHEMAS[name], strict=False)
        for name, rows in zip(V1_SCHEMAS, tables, strict=True)
    )

    frames = {
        name: empty_frame(name)
        for name in ("holds", "campaigns", "campaign_assignments", "candidate_titles")
    }
    frames["users"] = users.with_columns(parse_utc("registered_at"))
    frames["books"] = books.with_columns(
        language=pl.lit(None, Str),
        pages=pl.lit(None, Int),
        first_year=pl.lit(None, Int),
        copies=pl.lit(None, Int),
    )
    frames["loans"] = loans.with_columns(parse_utc("borrowed_at"), parse_utc("returned_at"))
    frames["reading_sessions"] = sessions.with_columns(parse_utc("started_at"))
    frames["searches"] = searches.with_columns(
        parse_utc("searched_at"), results_count=pl.lit(None, Int)
    )
    frames["subscription_periods"] = periods.with_columns(
        period_start=parse_utc("period_start", DATE_FORMAT)
    ).select(
        "user_id",
        "plan",
        "period_start",
        period_end=pl.col("period_start") + pl.duration(days=pl.col("days")),
        list_price="amount",
        paid_amount="amount",
        discount_pct=pl.lit(None, pl.Float64),
        outcome=pl.lit(None, Str),
    )
    return frames


def as_of_from(frames: dict[str, pl.DataFrame]) -> date:
    """v1 files carry no as_of: use the date of the latest activity."""
    latest = pl.concat(
        frames[table].select(pl.col(col).max().alias("at"))
        for table, col in (
            ("loans", "borrowed_at"),
            ("reading_sessions", "started_at"),
            ("searches", "searched_at"),
            ("users", "registered_at"),
        )
    )["at"].max()
    if not isinstance(latest, datetime):
        raise IngestError("dataset.invalid", "The v1 file has no dated activity")
    return latest.date()
