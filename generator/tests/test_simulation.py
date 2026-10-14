"""Fast structural tests of the simulator: determinism, schema and consistency rules."""

import json
import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from conftest import rows

from libsim import engine, schema, writer
from libsim.catalog import text
from libsim.engine import Result
from libsim.params import PRESETS, preset


@pytest.fixture(scope="module")
def result() -> Result:
    return engine.simulate(preset("demo", users=400, months=8, seed=7))


@pytest.fixture(scope="module")
def dataset(result: Result) -> dict[str, Any]:
    return writer.build_dataset(result)


@pytest.fixture(scope="module")
def truth(result: Result) -> dict[str, Any]:
    return writer.build_ground_truth(result)


def _ts(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def test_same_seed_gives_identical_files(tmp_path: Path) -> None:
    params = preset("demo", users=150, months=4, seed=3)
    first = writer.write(engine.simulate(params), tmp_path / "a")
    second = writer.write(engine.simulate(params), tmp_path / "b")
    assert first[0].read_bytes() == second[0].read_bytes()
    assert first[1].read_bytes() == second[1].read_bytes()


def test_different_seeds_differ() -> None:
    a = writer.build_dataset(engine.simulate(preset("demo", users=150, months=4, seed=3)))
    b = writer.build_dataset(engine.simulate(preset("demo", users=150, months=4, seed=4)))
    assert a["tables"]["loans"]["rows"] != b["tables"]["loans"]["rows"]


def test_tables_follow_the_schema(dataset: dict[str, Any]) -> None:
    assert dataset["schema_version"] == schema.SCHEMA_VERSION
    assert set(dataset["tables"]) == set(schema.TABLES)
    stamp = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    python_types = {"string": str, "integer": int, "number": (int, float), "boolean": bool}
    for name, spec in schema.TABLES.items():
        table = dataset["tables"][name]
        assert table["columns"] == schema.columns(name)
        for row in table["rows"]:
            assert len(row) == len(spec), name
            for value, (column, kind, nullable) in zip(row, spec, strict=True):
                if value is None:
                    assert nullable, f"{name}.{column} is null"
                elif kind == "timestamp":
                    assert stamp.match(value), f"{name}.{column}={value}"
                elif kind == "string[]":
                    assert all(isinstance(v, str) for v in value)
                else:
                    assert isinstance(value, python_types[kind]), f"{name}.{column}={value!r}"


def test_nothing_happens_after_as_of(dataset: dict[str, Any], result: Result) -> None:
    limit = datetime.combine(result.params.as_of + timedelta(days=1), datetime.min.time(), UTC)
    for name, spec in schema.TABLES.items():
        stamps = [i for i, (_, kind, _) in enumerate(spec) if kind == "timestamp"]
        for row in dataset["tables"][name]["rows"]:
            for i in stamps:
                if row[i] is not None and not (name == "subscription_periods" and i == 3):
                    assert _ts(row[i]) < limit, (name, row)


def test_concurrent_loans_never_exceed_licences(dataset: dict[str, Any]) -> None:
    copies = {b["book_id"]: b["copies"] for b in rows(dataset, "books")}
    events: dict[str, list[tuple[datetime, int]]] = defaultdict(list)
    for loan in rows(dataset, "loans"):
        events[loan["book_id"]].append((_ts(loan["borrowed_at"]), 1))
        if loan["returned_at"]:
            events[loan["book_id"]].append((_ts(loan["returned_at"]), -1))
    for book, changes in events.items():
        out = 0
        for _, delta in sorted(changes, key=lambda e: (e[0], e[1])):  # returns before borrows
            out += delta
            assert out <= copies[book], book


def test_reading_happens_only_during_a_loan(dataset: dict[str, Any]) -> None:
    spans = defaultdict(list)
    for loan in rows(dataset, "loans"):
        end = _ts(loan["returned_at"]) if loan["returned_at"] else datetime.max.replace(tzinfo=UTC)
        spans[(loan["user_id"], loan["book_id"])].append((_ts(loan["borrowed_at"]), end))
    for session in rows(dataset, "reading_sessions"):
        t = _ts(session["started_at"])
        windows = spans[(session["user_id"], session["book_id"])]
        assert any(start <= t <= end for start, end in windows), session


def test_no_paid_period_after_churn(dataset: dict[str, Any]) -> None:
    churned_at: dict[str, datetime] = {}
    periods = sorted(rows(dataset, "subscription_periods"), key=lambda r: r["period_start"])
    for period in periods:
        user = period["user_id"]
        assert user not in churned_at or _ts(period["period_start"]) < churned_at[user]
        if period["outcome"] == "churned":
            churned_at[user] = _ts(period["period_end"])


def test_holds_are_served_first_come_first_served(dataset: dict[str, Any]) -> None:
    fulfilled = defaultdict(list)
    for hold in rows(dataset, "holds"):
        if hold["outcome"] == "fulfilled":
            fulfilled[hold["book_id"]].append((hold["placed_at"], hold["resolved_at"]))
    for book, items in fulfilled.items():
        resolved = [r for _, r in sorted(items)]
        assert resolved == sorted(resolved), book


def test_no_russian_content(dataset: dict[str, Any]) -> None:
    russian = re.compile(text.RUSSIAN_ONLY_CHAR)
    for table, column in [
        ("books", "title"),
        ("books", "authors"),
        ("searches", "query"),
        ("candidate_titles", "title"),
    ]:
        assert not [r for r in rows(dataset, table) if russian.search(r[column])], (table, column)


def test_ground_truth_is_complete(truth: dict[str, Any], dataset: dict[str, Any]) -> None:
    users = {u["user_id"] for u in rows(dataset, "users")}
    assert set(truth["users"]["satisfaction_as_of"]) == users
    assert len(truth["candidates"]) == len(rows(dataset, "candidate_titles"))
    for row in truth["at_risk"]:
        assert set(row["p_true"]) == {"none", "email", "discount"}
        assert all(0.0 < p < 1.0 for p in row["p_true"].values())
    assert truth["campaign"], "the past campaign assigned nobody"


def test_hidden_traits_stay_out_of_the_dataset(dataset: dict[str, Any]) -> None:
    columns = {c for table in dataset["tables"].values() for c in table["columns"]}
    assert not columns & {"satisfaction", "price_sensitivity", "taste", "quality", "hidden_factor"}


@pytest.mark.parametrize("name", PRESETS)
def test_every_preset_runs(name: str) -> None:
    dataset = writer.build_dataset(engine.simulate(preset(name, users=120, months=3, seed=1)))
    assert dataset["meta"]["preset"] == name
    assert dataset["tables"]["loans"]["rows"]


def test_cli_generate_then_validate(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from libsim.cli import main

    assert main(["generate", "--users", "200", "--months", "10", "--out", str(tmp_path)]) == 0
    dataset = next(tmp_path.glob("*.json.gz"))
    assert main(["validate", str(dataset)]) == 0
    assert "churn_rates" in capsys.readouterr().out


def test_committed_json_schema_is_current() -> None:
    committed = Path(__file__).parents[2] / "docs" / "schema" / "dataset.schema.json"
    assert json.loads(committed.read_text(encoding="utf-8")) == schema.json_schema()
