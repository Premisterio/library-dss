"""The tabular dataset format as the importer sees it: tables, codes, references and keys."""

from typing import Literal

from app.domain.enums import ENUMS

DatasetFormat = Literal["tabular", "nested"]
SCHEMA_VERSION = 2  # the `schema_version` a tabular file declares
ColumnType = Literal["string", "integer", "number", "boolean", "timestamp", "string[]"]

TABLES: dict[str, list[tuple[str, ColumnType, bool]]] = {
    "users": [
        ("user_id", "string", False),
        ("registered_at", "timestamp", False),
        ("age_range", "string", False),
        ("education", "string", False),
        ("language_pref", "string", False),
        ("email_opt_in", "boolean", False),
        ("interests", "string[]", False),
    ],
    "books": [
        ("book_id", "string", False),
        ("title", "string", False),
        ("authors", "string", False),
        ("genre", "string", False),
        ("language", "string", False),
        ("pages", "integer", False),
        ("first_year", "integer", True),
        ("copies", "integer", False),
    ],
    "subscription_periods": [
        ("user_id", "string", False),
        ("plan", "string", False),
        ("period_start", "timestamp", False),
        ("period_end", "timestamp", False),
        ("list_price", "number", False),
        ("paid_amount", "number", False),
        ("discount_pct", "number", True),
        ("outcome", "string", False),
    ],
    "loans": [
        ("loan_id", "string", False),
        ("user_id", "string", False),
        ("book_id", "string", False),
        ("borrowed_at", "timestamp", False),
        ("returned_at", "timestamp", True),
        ("completed", "boolean", True),
        ("rating", "integer", True),
        ("via_hold", "boolean", False),
    ],
    "reading_sessions": [
        ("user_id", "string", False),
        ("book_id", "string", False),
        ("started_at", "timestamp", False),
        ("minutes", "integer", False),
        ("pages", "integer", False),
        ("device", "string", False),
    ],
    "searches": [
        ("user_id", "string", False),
        ("searched_at", "timestamp", False),
        ("query", "string", False),
        ("results_count", "integer", False),
    ],
    "holds": [
        ("hold_id", "string", False),
        ("user_id", "string", False),
        ("book_id", "string", False),
        ("placed_at", "timestamp", False),
        ("resolved_at", "timestamp", True),
        ("outcome", "string", False),
    ],
    "campaigns": [
        ("campaign_id", "string", False),
        ("name", "string", False),
        ("starts_at", "timestamp", False),
        ("ends_at", "timestamp", False),
        ("design", "string", False),
        ("arms", "string[]", False),
    ],
    "campaign_assignments": [
        ("campaign_id", "string", False),
        ("user_id", "string", False),
        ("assigned_at", "timestamp", False),
        ("arm", "string", False),
        ("delivered", "boolean", False),
        ("discount_pct", "number", False),
        ("target_period_end", "timestamp", False),
    ],
    "candidate_titles": [
        ("candidate_id", "string", False),
        ("title", "string", False),
        ("authors", "string", False),
        ("genre", "string", False),
        ("language", "string", False),
        ("pages", "integer", False),
        ("first_year", "integer", True),
        ("license_cost", "number", False),
        ("offered_at", "timestamp", False),
    ],
}

DB_TABLE = {name: ("lib_users" if name == "users" else name) for name in TABLES}

# Column values restricted to known codes (table, column) -> allowed set.
ENUM_COLUMNS: dict[tuple[str, str], set[str]] = {
    ("users", "age_range"): set(ENUMS["age_range"]),
    ("users", "education"): set(ENUMS["education"]),
    ("users", "language_pref"): set(ENUMS["language_pref"]),
    ("books", "genre"): set(ENUMS["genre"]),
    ("books", "language"): set(ENUMS["language"]),
    ("subscription_periods", "plan"): set(ENUMS["plan"]),
    ("subscription_periods", "outcome"): set(ENUMS["period_outcome"]),
    ("reading_sessions", "device"): set(ENUMS["device"]),
    ("holds", "outcome"): set(ENUMS["hold_outcome"]),
    ("campaign_assignments", "arm"): set(ENUMS["campaign_arm"]),
    ("candidate_titles", "genre"): set(ENUMS["genre"]),
    ("candidate_titles", "language"): set(ENUMS["language"]),
}

# (table, column) -> (referenced table, referenced column)
REFERENCES: dict[tuple[str, str], tuple[str, str]] = {
    ("subscription_periods", "user_id"): ("users", "user_id"),
    ("loans", "user_id"): ("users", "user_id"),
    ("loans", "book_id"): ("books", "book_id"),
    ("reading_sessions", "user_id"): ("users", "user_id"),
    ("reading_sessions", "book_id"): ("books", "book_id"),
    ("searches", "user_id"): ("users", "user_id"),
    ("holds", "user_id"): ("users", "user_id"),
    ("holds", "book_id"): ("books", "book_id"),
    ("campaign_assignments", "user_id"): ("users", "user_id"),
    ("campaign_assignments", "campaign_id"): ("campaigns", "campaign_id"),
}

UNIQUE_KEYS: dict[str, tuple[str, ...]] = {
    "users": ("user_id",),
    "books": ("book_id",),
    "loans": ("loan_id",),
    "holds": ("hold_id",),
    "campaigns": ("campaign_id",),
    "campaign_assignments": ("campaign_id", "user_id"),
    "candidate_titles": ("candidate_id",),
}

# Timestamps that may legitimately lie after as_of (a subscription period still running).
MAY_EXCEED_AS_OF = {("subscription_periods", "period_end")}

# Required in tabular files, absent from nested ones (nullable in the database).
NESTED_MAY_BE_EMPTY = {
    ("users", "age_range"),
    ("users", "education"),
    ("users", "language_pref"),
    ("users", "email_opt_in"),
    ("books", "language"),
    ("books", "pages"),
    ("books", "copies"),
    ("subscription_periods", "outcome"),
    ("reading_sessions", "device"),
    ("searches", "results_count"),
}
