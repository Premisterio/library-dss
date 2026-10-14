"""Tabular dataset format: table definitions shared by the writer, the JSON Schema and the backend.

A dataset file is `{"schema_version": 2, "meta": {...}, "tables": {name: {"columns": [...],
"rows": [[...], ...]}}}`. Tables map 1:1 onto the backend's import tables. Timestamps are
ISO-8601 UTC strings ("2026-09-30T18:42:05Z"); the local time zone is in `meta.timezone`.
"""

from typing import Any, Literal

SCHEMA_VERSION = 2
ColumnType = Literal["string", "integer", "number", "boolean", "timestamp", "string[]"]

# table -> [(column, type, nullable)]
TABLES: dict[str, list[tuple[str, ColumnType, bool]]] = {
    "users": [
        ("user_id", "string", False),
        ("registered_at", "timestamp", False),
        ("age_range", "string", False),
        ("education", "string", False),
        ("language_pref", "string", False),  # "uk" | "uk+en"
        ("email_opt_in", "boolean", False),
        ("interests", "string[]", False),  # declared genre codes
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
        ("plan", "string", False),  # trial | monthly | annual | student
        ("period_start", "timestamp", False),
        ("period_end", "timestamp", False),
        ("list_price", "number", False),
        ("paid_amount", "number", False),
        ("discount_pct", "number", True),
        ("outcome", "string", False),  # open | renewed | churned | converted | expired
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
        ("outcome", "string", False),  # open | fulfilled | lapsed | cancelled
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

_JSON_TYPES: dict[str, dict[str, Any]] = {
    "string": {"type": "string"},
    "integer": {"type": "integer"},
    "number": {"type": "number"},
    "boolean": {"type": "boolean"},
    "timestamp": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"},
    "string[]": {"type": "array", "items": {"type": "string"}},
}


def columns(table: str) -> list[str]:
    return [name for name, _, _ in TABLES[table]]


def json_schema() -> dict[str, Any]:
    """JSON Schema (2020-12) of a dataset file; used by the backend importer and docs."""

    def cell(kind: str, nullable: bool) -> dict[str, Any]:
        spec = dict(_JSON_TYPES[kind])
        return {"anyOf": [spec, {"type": "null"}]} if nullable else spec

    tables = {
        name: {
            "type": "object",
            "required": ["columns", "rows"],
            "properties": {
                "columns": {"const": [c for c, _, _ in cols]},
                "rows": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "prefixItems": [cell(kind, nullable) for _, kind, nullable in cols],
                        "minItems": len(cols),
                        "maxItems": len(cols),
                    },
                },
            },
        }
        for name, cols in TABLES.items()
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://github.com/Premisterio/library-dss/docs/schema/dataset.schema.json",
        "title": "Library DSS dataset",
        "type": "object",
        "required": ["schema_version", "meta", "tables"],
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "meta": {
                "type": "object",
                "required": ["generator", "seed", "preset", "params_hash", "as_of", "timezone"],
            },
            "tables": {
                "type": "object",
                "required": list(TABLES),
                "properties": tables,
                "additionalProperties": False,
            },
        },
    }
