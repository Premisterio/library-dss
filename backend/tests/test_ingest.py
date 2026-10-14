"""Parsing and validation of dataset files (no database)."""

import gzip
from datetime import date
from typing import Any

import orjson
import pytest

from app.ingest import IngestError, reader, schema
from app.ingest.frames import ParsedDataset
from app.utils.dates import UTC_DATETIME


def parse(document: dict[str, Any]) -> ParsedDataset:
    return reader.parse(reader.decode(orjson.dumps(document)))


def rows(document: dict[str, Any], table: str) -> list[list[Any]]:
    return document["tables"][table]["rows"]


def column(document: dict[str, Any], table: str, name: str) -> int:
    return document["tables"][table]["columns"].index(name)


def invalid(document: dict[str, Any]) -> IngestError:
    with pytest.raises(IngestError) as caught:
        parse(document)
    return caught.value


def test_importer_schema_matches_the_generator() -> None:
    from libsim.schema import TABLES

    assert {name: list(cols) for name, cols in TABLES.items()} == schema.TABLES


def test_tabular_dataset_parses(tabular_document: dict[str, Any]) -> None:
    parsed = parse(tabular_document)
    assert parsed.format == "tabular"
    assert parsed.schema_version == 2
    assert parsed.as_of == date.fromisoformat(tabular_document["meta"]["as_of"])
    assert parsed.timezone == "Europe/Kyiv"
    assert parsed.capabilities == ["descriptive", "retention", "content"]
    assert parsed.row_counts == {name: len(rows(tabular_document, name)) for name in schema.TABLES}
    assert parsed.frames["loans"].schema["borrowed_at"] == UTC_DATETIME


def test_tabular_validation_reports_every_problem(tabular_document: dict[str, Any]) -> None:
    books, loans, users = (rows(tabular_document, t) for t in ("books", "loans", "users"))
    books[0][column(tabular_document, "books", "genre")] = "astrology"
    users[1][0] = users[0][0]  # duplicate user id
    loans[0][column(tabular_document, "loans", "book_id")] = "no-such-book"
    searches = rows(tabular_document, "searches")
    searches[0][column(tabular_document, "searches", "searched_at")] = "2099-01-01T00:00:00Z"

    error = invalid(tabular_document)
    assert error.code == "dataset.invalid"
    report = "\n".join(error.errors)
    assert "books.genre: unknown codes ['astrology']" in report
    assert "users.user_id: 1 duplicate ids" in report
    assert "loans.book_id: 1 rows point to unknown books" in report
    assert "searches.searched_at: 1 values after as_of" in report


def test_tabular_campaign_members_are_unique(tabular_document: dict[str, Any]) -> None:
    assignments = rows(tabular_document, "campaign_assignments")
    assignments.append(list(assignments[0]))
    assert (
        "campaign_assignments.campaign_id+user_id: 1 duplicate ids"
        in invalid(tabular_document).errors
    )


def test_tabular_required_values(tabular_document: dict[str, Any]) -> None:
    rows(tabular_document, "users")[0][column(tabular_document, "users", "registered_at")] = None
    assert "users.registered_at: 1 empty values" in invalid(tabular_document).errors


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d["tables"].pop("holds"), "Missing tables: holds"),
        (lambda d: d["tables"]["books"]["columns"].reverse(), "Table 'books' must have columns"),
        (lambda d: d["tables"]["books"]["rows"][0].pop(), "Table 'books' row 0 has a wrong length"),
        (lambda d: d["meta"].pop("as_of"), "meta.as_of must be a date"),
        (
            lambda d: d["tables"]["loans"]["rows"][0].__setitem__(3, "01.02.2026 10:00"),
            "Table 'loans': timestamps must look like",
        ),
    ],
)
def test_tabular_structure_errors(
    tabular_document: dict[str, Any], mutate: Any, message: str
) -> None:
    mutate(tabular_document)
    error = invalid(tabular_document)
    assert error.code == "dataset.invalid"
    assert message in error.detail


def test_unknown_format_version() -> None:
    error = invalid({"schema_version": 7, "tables": {}})
    assert error.code == "dataset.unsupported_version"


def test_nested_dataset_parses(nested_document: dict[str, Any]) -> None:
    parsed = parse(nested_document)
    assert parsed.format == "nested"
    assert parsed.schema_version is None
    assert parsed.capabilities == ["descriptive"]
    assert parsed.as_of == date(2025, 6, 18)  # the latest event: nested files carry no as_of
    books, loans = parsed.frames["books"], parsed.frames["loans"]
    # Audit 2026-10-08: the previous app counted only the top 10 books; every loan and title counts.
    assert loans.height == 6
    assert books.height == 5
    assert books["title"].n_unique() == 4
    genres = dict(zip(books["book_id"], books["genre"], strict=True))
    assert genres == {
        "b1": "fiction",
        "b3": "science_fiction",
        "b5": "science_fiction",
        "b2": "poetry_drama",
        "b4": "mystery_thriller",
    }
    periods = parsed.frames["subscription_periods"]
    assert periods.height == 3
    assert periods.filter(periods["plan"] == "annual")["paid_amount"].to_list() == [899.0]


def test_nested_bad_timestamp(nested_document: dict[str, Any]) -> None:
    nested_document["users"][0]["account"]["registration_date"] = "10.01.2025"
    error = invalid(nested_document)
    assert error.code == "dataset.invalid"
    assert "timestamps must look like" in error.detail


def test_nested_missing_field(nested_document: dict[str, Any]) -> None:
    del nested_document["users"][0]["activity"]["books_borrowed"][0]["title"]
    assert "'title'" in invalid(nested_document).detail


def test_gzip_is_read_and_bounded() -> None:
    payload = b"{" + b" " * 4096 + b"}"
    assert reader.decompress(gzip.compress(payload)) == payload
    with pytest.raises(IngestError) as caught:
        reader.decompress(gzip.compress(payload), limit=1024)  # a tiny "zip bomb"
    assert caught.value.code == "dataset.too_large"
    with pytest.raises(IngestError) as caught:
        reader.decompress(b"\x1f\x8b" + b"broken")
    assert caught.value.code == "dataset.unreadable"


@pytest.mark.parametrize("content", [b"not json", b"[1, 2, 3]"])
def test_unreadable_documents(content: bytes) -> None:
    with pytest.raises(IngestError) as caught:
        reader.decode(content)
    assert caught.value.code == "dataset.unreadable"
