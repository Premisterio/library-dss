"""Invariants of the committed catalogue and calibration files (run in CI, no polars needed)."""

import csv
import json
import re
from pathlib import Path

import pytest

from libsim.catalog import genres, text

DATA = Path(__file__).parents[1] / "src" / "libsim" / "data"


@pytest.fixture(scope="module")
def catalog() -> list[dict[str, str]]:
    with (DATA / "catalog.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_no_russian_content(catalog: list[dict[str, str]]) -> None:
    russian = re.compile(text.RUSSIAN_ONLY_CHAR)
    material = re.compile(text.RUSSIAN_LANGUAGE_MATERIAL)
    offenders = [
        row["book_id"]
        for row in catalog
        if russian.search(row["title"] + row["authors"]) or material.search(row["title"])
    ]
    assert not offenders


def test_scripts_match_language(catalog: list[dict[str, str]]) -> None:
    for row in catalog:
        if row["language"] == "uk":
            assert text.is_cyrillic_title(row["title"]), row["book_id"]
        else:
            assert row["language"] == "en"
            assert text.is_latin_title(row["title"]), row["book_id"]


def test_rows_are_well_formed(catalog: list[dict[str, str]]) -> None:
    assert len(catalog) > 3000
    assert len({row["book_id"] for row in catalog}) == len(catalog)
    for row in catalog:
        assert row["genre"] in genres.GENRES, row
        assert 24 <= int(row["pages"]) <= 2000, row
        assert row["authors"].strip(), row
        assert row["segment"] in {"english_popular", "ukrainian_with_signal", "ukrainian_long_tail"}


def test_meta_matches_catalog(catalog: list[dict[str, str]]) -> None:
    meta = json.loads((DATA / "catalog_meta.json").read_text(encoding="utf-8"))
    assert meta["rows"] == len(catalog)
    assert meta["source"]["license"] == "CC0-1.0"


def test_calibration_is_aggregate_and_attributed() -> None:
    calibration = json.loads((DATA / "calibration.json").read_text(encoding="utf-8"))
    assert calibration["source"]["license"] == "CC BY-SA 4.0"
    assert "goodbooks-10k" in calibration["source"]["attribution"]
    assert abs(sum(calibration["rating_distribution"].values()) - 1) < 1e-3
    assert calibration["genre_taste"]["dirichlet_concentration"] > 0
