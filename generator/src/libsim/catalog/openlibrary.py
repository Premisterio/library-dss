"""Open Library dump → library catalogue (Polars).

`fetch` downloads only the needed columns of the Hugging Face mirror
(`open-index/open-library`, CC0) into a local cache once (~3 GB). `build` is then fully
offline and deterministic. Rows are works offered in one language: Ukrainian translations
with real reader signals, a long tail of Ukrainian books, and popular English works.
Russian-language editions never qualify (see AGENTS.md).
"""

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import polars as pl

from libsim import __version__
from libsim.catalog import genres, text

HF_DATASET = "open-index/open-library"
HF_BASE = f"hf://datasets/{HF_DATASET}/data"

CACHE_FILES = {
    "editions": "ol_editions.parquet",
    "works": "ol_works.parquet",
    "authors": "ol_authors.parquet",
    "ratings": "ol_ratings.parquet",
    "reading_log": "ol_reading_log.parquet",
}


@dataclass(frozen=True)
class CatalogConfig:
    n_english: int = 3000
    n_ukrainian_tail: int = 800
    min_signal_english: int = 20
    min_year_ukrainian_tail: int = 1991
    min_pages: int = 24
    max_pages: int = 2000
    max_title_length: int = 160
    trend_months: int = 12
    rating_prior_weight: int = 10


def fetch(cache_dir: Path, *, refresh: bool = False) -> None:
    """Download the projected Open Library tables into `cache_dir` (skips existing files)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    sources = {
        "editions": pl.scan_parquet(f"{HF_BASE}/editions/*.parquet")
        .select("work_keys", "languages", "number_of_pages", "title", "publish_date")
        .filter(pl.col("languages").str.contains('"(eng|ukr)"')),
        "works": pl.scan_parquet(f"{HF_BASE}/works/*.parquet").select(
            "key", "author_keys", "subjects", "first_publish_date"
        ),
        "authors": pl.scan_parquet(f"{HF_BASE}/authors/*.parquet").select(
            "key", "name", "alternate_names"
        ),
        "ratings": pl.scan_parquet(f"{HF_BASE}/ratings/*.parquet").select(
            "work_key", "rating", "date"
        ),
        "reading_log": pl.scan_parquet(f"{HF_BASE}/reading-log/*.parquet").select(
            "work_key", "shelf", "date"
        ),
    }
    for name, frame in sources.items():
        target = cache_dir / CACHE_FILES[name]
        if refresh or not target.exists():
            frame.sink_parquet(target)


# ---------------------------------------------------------------- expressions


def _work_id(col: str) -> pl.Expr:
    return pl.col(col).str.extract(r"/works/(OL\d+W)")


def _clean_title(expr: pl.Expr) -> pl.Expr:
    expr = (
        expr.str.replace(r"\s+/\s+.*$", "").str.replace_all(r"\s+", " ").str.strip_chars(" :;,./")
    )
    return expr


def _fix_lookalikes(expr: pl.Expr) -> pl.Expr:
    for _ in range(2):
        for pattern, replacement in text.LOOKALIKE_FIXES:
            expr = expr.str.replace_all(pattern, replacement)
    return expr


def _subject_genre(subject: pl.Expr) -> pl.Expr:
    """The genre one subject votes for: the first rule it matches (genres.subject_genre)."""
    result: pl.Expr = pl.lit(None, dtype=pl.String)
    for genre, pattern in reversed(genres.RULES):  # first rule ends up outermost
        result = pl.when(subject.str.contains(pattern)).then(pl.lit(genre)).otherwise(result)
    return result


def _genre_votes(subjects: pl.LazyFrame) -> pl.LazyFrame:
    """work_key, subjects (list) → work_key, genre with most votes (ties: earlier rule)."""
    priority = {genre: i for i, genre in enumerate(genres.GENRE_ORDER)}
    return (
        subjects.explode("subjects")
        .drop_nulls("subjects")
        .with_columns(genre=_subject_genre(pl.col("subjects")))
        .drop_nulls("genre")
        .group_by("work_key", "genre")
        .len()
        .with_columns(
            priority=pl.col("genre").replace_strict(priority, return_dtype=pl.Int32),
            score=pl.col("len")
            * pl.col("genre").replace_strict(
                genres.VOTE_WEIGHT, default=1.0, return_dtype=pl.Float64
            ),
        )
        .group_by("work_key")
        .agg(genre=pl.col("genre").sort_by(["score", "priority"], descending=[True, False]).first())
    )


# ---------------------------------------------------------------- stages


def _editions_by_language(editions: pl.LazyFrame, cfg: CatalogConfig) -> pl.LazyFrame:
    """One row per (work, language) with a readable title, page count and edition year."""
    rows = (
        editions.with_columns(
            work_key=pl.col("work_keys").str.extract(r"/works/(OL\d+W)"),
            lang=pl.col("languages").str.extract_all(r"eng|ukr"),
            edition_year=pl.col("publish_date").str.extract(r"(1[5-9]\d\d|20\d\d)").cast(pl.Int32),
            pages=pl.col("number_of_pages"),
            title=_clean_title(pl.col("title")),
        )
        .filter(pl.col("work_key").is_not_null() & pl.col("title").is_not_null())
        .explode("lang")
        .with_columns(lang=pl.col("lang").replace({"eng": "en", "ukr": "uk"}))
        .with_columns(
            title=pl.when(pl.col("lang") == "uk")
            .then(_fix_lookalikes(pl.col("title")))
            .otherwise(pl.col("title"))
        )
    )
    n_cyr = pl.col("title").str.count_matches(text.CYRILLIC_CHAR)
    n_lat = pl.col("title").str.count_matches(text.LATIN_CHAR)
    script_ok = (
        pl.when(pl.col("lang") == "uk")
        .then(
            (n_cyr > 0)
            & (n_cyr >= 2 * n_lat)
            & ~pl.col("title").str.contains(text.RUSSIAN_ONLY_CHAR)
        )
        .otherwise((n_lat > 0) & (n_cyr == 0))
    )
    valid = rows.filter(
        script_ok
        & ~pl.col("title").str.contains(text.NON_BOOK)
        & ~pl.col("title").str.contains(text.RUSSIAN_LANGUAGE_MATERIAL)
        & ~pl.col("title").str.contains(text.SCHOOL_TEXTBOOK)
        & pl.col("title").str.len_chars().is_between(2, cfg.max_title_length)
    )
    in_range = pl.col("pages").is_between(cfg.min_pages, cfg.max_pages)
    stats = valid.group_by("work_key", "lang").agg(
        n_editions=pl.len(),
        pages=pl.col("pages").filter(in_range).median(),
        edition_year=pl.col("edition_year").min(),
    )
    titles = (
        valid.group_by("work_key", "lang", "title")
        .agg(n=pl.len())
        .group_by("work_key", "lang")
        .agg(pl.col("title").sort_by(["n", "title"], descending=[True, False]).first())
    )
    return stats.join(titles, on=["work_key", "lang"])


def _popularity(
    ratings: pl.LazyFrame, log: pl.LazyFrame, cfg: CatalogConfig
) -> tuple[pl.LazyFrame, dict]:
    ratings = ratings.with_columns(
        work_key=_work_id("work_key"), date=pl.col("date").str.to_date(strict=False)
    )
    log = log.with_columns(
        work_key=_work_id("work_key"), date=pl.col("date").str.to_date(strict=False)
    )
    as_of = max(
        ratings.select(pl.col("date").max()).collect().item(),
        log.select(pl.col("date").max()).collect().item(),
    )
    global_mean = ratings.select(pl.col("rating").mean()).collect().item()
    recent_from = as_of - _months(cfg.trend_months)
    prev_from = as_of - _months(2 * cfg.trend_months)
    rating_stats = ratings.group_by("work_key").agg(
        ol_ratings=pl.len(), ol_rating_mean=pl.col("rating").mean()
    )
    log_stats = log.group_by("work_key").agg(
        ol_want_to_read=(pl.col("shelf") == "Want to Read").sum(),
        ol_currently_reading=(pl.col("shelf") == "Currently Reading").sum(),
        ol_already_read=(pl.col("shelf") == "Already Read").sum(),
        recent=(pl.col("date") > recent_from).sum(),
        previous=((pl.col("date") > prev_from) & (pl.col("date") <= recent_from)).sum(),
    )
    m = cfg.rating_prior_weight
    pop = (
        log_stats.join(rating_stats, on="work_key", how="full", coalesce=True)
        .with_columns(
            pl.col(c).fill_null(0)
            for c in (
                "ol_want_to_read",
                "ol_currently_reading",
                "ol_already_read",
                "recent",
                "previous",
                "ol_ratings",
            )
        )
        .with_columns(
            ol_trend=((pl.col("recent") + 1) / (pl.col("previous") + 1)).round(3),
            quality_prior=(
                (
                    pl.col("ol_rating_mean").fill_null(global_mean) * pl.col("ol_ratings")
                    + global_mean * m
                )
                / (pl.col("ol_ratings") + m)
            ).round(3),
            ol_signal=pl.col("ol_want_to_read")
            + pl.col("ol_currently_reading")
            + pl.col("ol_already_read")
            + pl.col("ol_ratings"),
        )
        .drop("recent", "previous")
    )
    return pop, {"as_of": as_of.isoformat(), "global_mean_rating": round(global_mean, 4)}


def _months(n: int):
    from datetime import timedelta

    return timedelta(days=round(n * 30.4375))


def _works(works: pl.LazyFrame, authors: pl.LazyFrame, keys: pl.LazyFrame) -> pl.LazyFrame:
    """Genre (from subjects), first publication year and author names for the given works."""
    w = (
        works.with_columns(work_key=_work_id("key"))
        .join(keys, on="work_key", how="semi")
        .with_columns(
            author_ids=pl.col("author_keys").str.extract_all(r"OL\d+A").list.head(2),
            first_year=pl.col("first_publish_date")
            .str.extract(r"(1[0-9]\d\d|20\d\d)")
            .cast(pl.Int32),
            subjects=pl.col("subjects")
            .str.json_decode(pl.List(pl.String))
            .list.eval(
                pl.element()
                .filter(~pl.element().str.contains(text.RUSSIAN_ONLY_CHAR))
                .str.to_lowercase()
            ),
        )
        .with_columns(
            classic_marker=pl.col("subjects")
            .list.eval(pl.element().str.contains(genres.CLASSIC_MARKER))
            .list.any()
            .fill_null(False),
        )
    )
    w = w.join(_genre_votes(w.select("work_key", "subjects")), on="work_key", how="left")
    names = authors.select(
        author_id=pl.col("key").str.extract(r"(OL\d+A)"), name=pl.col("name").str.strip_chars()
    )
    work_authors = (
        w.select("work_key", "author_ids")
        .explode("author_ids")
        .join(names, left_on="author_ids", right_on="author_id", how="left")
        .group_by("work_key")
        .agg(
            authors=pl.col("name").drop_nulls().str.join(", "),
            authors_ok=pl.col("name").is_not_null().all()
            & ~pl.col("name").str.contains(text.RUSSIAN_ONLY_CHAR).any(),
        )
    )
    return w.select("work_key", "first_year", "genre", "classic_marker", "author_ids").join(
        work_authors, on="work_key", how="left"
    )


def _author_genre_fallback(items: pl.DataFrame) -> pl.DataFrame:
    """Works without subjects take the most common genre among the author's other works."""
    by_author = (
        items.filter(pl.col("genre").is_not_null())
        .unique(subset=["work_key"])
        .select("genre", author_id=pl.col("author_ids"))
        .explode("author_id")
        .drop_nulls("author_id")
        .group_by("author_id", "genre")
        .len()
        .group_by("author_id")
        .agg(
            author_genre=pl.col("genre").sort_by(["len", "genre"], descending=[True, False]).first()
        )
    )
    return (
        items.with_columns(first_author=pl.col("author_ids").list.first())
        .join(by_author, left_on="first_author", right_on="author_id", how="left")
        .with_columns(
            genre_source=pl.when(pl.col("genre").is_not_null())
            .then(pl.lit("subjects"))
            .when(pl.col("author_genre").is_not_null())
            .then(pl.lit("author"))
        )
        .with_columns(genre=pl.coalesce("genre", "author_genre"))
        .drop("first_author", "author_genre")
    )


def _stratified(pool: pl.DataFrame, n: int, shares: dict[str, float]) -> pl.DataFrame:
    """Pick n rows following the genre mix `shares`; top up from the remaining pool in order."""
    picked = [pool.filter(pl.col("genre") == g).head(round(n * s)) for g, s in shares.items()]
    chosen = pl.concat(picked) if picked else pool.head(0)
    rest = pool.join(chosen.select("work_key"), on="work_key", how="anti")
    return pl.concat([chosen, rest.head(max(0, n - chosen.height))])


def _polish(catalog: pl.DataFrame) -> pl.DataFrame:
    """Readable names and titles; one row per (language, title, authors)."""

    def authors(row: dict) -> str:
        names = row["authors"].split(", ")
        if row["language"] == "uk":
            names = [text.lc_to_ukrainian(n) for n in names]
        return ", ".join(names)

    return (
        catalog.with_columns(
            authors=pl.struct("authors", "language").map_elements(authors, return_dtype=pl.String),
            title=pl.struct("title", "language").map_elements(
                lambda r: text.fix_all_caps(r["title"], r["language"]), return_dtype=pl.String
            ),
        )
        .sort(["ol_signal", "book_id"], descending=[True, False])
        .unique(subset=["language", "title", "authors"], keep="first", maintain_order=True)
    )


def _check(catalog: pl.DataFrame) -> None:
    """Hard guarantees of the published catalogue (see AGENTS.md hard rules)."""
    text_cols = pl.col("title") + " " + pl.col("authors")
    russian = catalog.filter(text_cols.str.contains(text.RUSSIAN_ONLY_CHAR))
    if russian.height:
        raise ValueError(
            f"Russian-only letters in {russian.height} rows: {russian['book_id'][:5].to_list()}"
        )
    bad_en = catalog.filter(
        (pl.col("language") == "en") & pl.col("title").str.contains(text.CYRILLIC_CHAR)
    )
    if bad_en.height:
        raise ValueError(f"Cyrillic in English titles: {bad_en['book_id'][:5].to_list()}")
    if catalog["book_id"].n_unique() != catalog.height:
        raise ValueError("duplicate book_id")


def build(cache_dir: Path, cfg: CatalogConfig | None = None) -> tuple[pl.DataFrame, dict]:
    cfg = cfg or CatalogConfig()
    scan = {name: pl.scan_parquet(cache_dir / file) for name, file in CACHE_FILES.items()}

    by_lang = _editions_by_language(scan["editions"], cfg).collect(engine="streaming")
    pop, pop_meta = _popularity(scan["ratings"], scan["reading_log"], cfg)
    keys = by_lang.select("work_key").unique().lazy()
    works = _works(scan["works"], scan["authors"], keys).collect(engine="streaming")

    any_pages = by_lang.group_by("work_key").agg(any_pages=pl.col("pages").median())
    items = (
        by_lang.join(works, on="work_key", how="inner")
        .join(any_pages, on="work_key", how="left")
        .join(pop.collect(), on="work_key", how="left")
        .with_columns(
            pl.col(c).fill_null(0)
            for c in (
                "ol_want_to_read",
                "ol_currently_reading",
                "ol_already_read",
                "ol_ratings",
                "ol_signal",
            )
        )
        .with_columns(
            pages=pl.coalesce("pages", "any_pages"),
            first_year=pl.coalesce("first_year", "edition_year"),
            quality_prior=pl.col("quality_prior").fill_null(pop_meta["global_mean_rating"]),
            ol_trend=pl.col("ol_trend").fill_null(1.0),
        )
        .filter(pl.col("authors_ok").fill_null(False) & (pl.col("authors").str.len_chars() > 0))
    )
    items = _author_genre_fallback(items).filter(pl.col("genre").is_not_null())
    genre_pages = items.group_by("genre").agg(genre_pages=pl.col("pages").median())
    items = (
        items.join(genre_pages, on="genre", how="left")
        .with_columns(
            pages=pl.coalesce("pages", "genre_pages").round(0).cast(pl.Int32),
            genre=pl.when(
                (
                    pl.col("genre").is_in(sorted(genres.FICTION_FOR_CLASSICS))
                    & (pl.col("first_year") < genres.CLASSICS_BEFORE_YEAR)
                )
                | (
                    pl.col("classic_marker")
                    & pl.col("genre").is_in(sorted(genres.CLASSIC_MARKER_GENRES))
                    & (pl.col("first_year") < genres.CLASSIC_MARKER_BEFORE_YEAR)
                )
            )
            .then(pl.lit("classics"))
            .otherwise(pl.col("genre")),
        )
        .with_columns(book_id=pl.col("lang") + "-" + pl.col("work_key"))
    )

    english = (
        items.filter((pl.col("lang") == "en") & (pl.col("ol_signal") >= cfg.min_signal_english))
        .sort(["ol_signal", "work_key"], descending=[True, False])
        .head(cfg.n_english)
        .with_columns(segment=pl.lit("english_popular"))
    )
    uk_translations = items.filter(
        (pl.col("lang") == "uk") & (pl.col("ol_signal") > 0)
    ).with_columns(segment=pl.lit("ukrainian_with_signal"))
    # The Ukrainian long tail follows the genre mix of reader demand (the English popular set),
    # in a deterministic pseudo-random order (Knuth multiplicative hash of the OL id).
    demand_mix = (
        english.group_by("genre").len().with_columns(share=pl.col("len") / pl.col("len").sum())
    )
    shuffle = (pl.col("work_key").str.extract(r"OL(\d+)W").cast(pl.UInt64) * 2654435761) % (2**32)
    tail_pool = items.filter(
        (pl.col("lang") == "uk")
        & (pl.col("ol_signal") == 0)
        & (pl.col("first_year") >= cfg.min_year_ukrainian_tail)
    ).sort(shuffle)
    uk_tail = _stratified(
        tail_pool, cfg.n_ukrainian_tail, dict(demand_mix.select("genre", "share").iter_rows())
    ).with_columns(segment=pl.lit("ukrainian_long_tail"))

    catalog = _polish(
        pl.concat([uk_translations, uk_tail, english]).select(
            "book_id",
            "work_key",
            pl.col("lang").alias("language"),
            "title",
            "authors",
            "genre",
            "genre_source",
            "pages",
            "first_year",
            "segment",
            "ol_signal",
            "ol_want_to_read",
            "ol_currently_reading",
            "ol_already_read",
            "ol_ratings",
            pl.col("ol_rating_mean").round(3),
            "quality_prior",
            "ol_trend",
        )
    ).sort(["language", "ol_signal", "book_id"], descending=[True, True, False])
    _check(catalog)
    return catalog, _meta(catalog, cfg, pop_meta)


def _meta(catalog: pl.DataFrame, cfg: CatalogConfig, pop_meta: dict) -> dict:
    by = lambda col: dict(sorted(catalog.group_by(col).len().iter_rows()))  # noqa: E731
    return {
        "source": {
            "dataset": f"https://huggingface.co/datasets/{HF_DATASET}",
            "origin": "Open Library data dumps (https://openlibrary.org/developers/dumps)",
            "license": "CC0-1.0",
            "signals_as_of": pop_meta["as_of"],
            "global_mean_rating": pop_meta["global_mean_rating"],
        },
        "builder": {"libsim": __version__, "polars": pl.__version__, "config": asdict(cfg)},
        "rows": catalog.height,
        "by_language": by("language"),
        "by_segment": by("segment"),
        "by_genre": by("genre"),
        "rules": [
            "Russian-language editions never qualify; Ukrainian titles must be Cyrillic without "
            "Russian-only letters (ё, ъ, ы, э); subjects with those letters are ignored.",
            "Romanised (transliterated) Ukrainian catalogue titles are excluded.",
            "Conference proceedings, theses, bulletins and similar non-book records are excluded.",
            "Genre comes from Open Library subjects via libsim.catalog.genres rules.",
        ],
    }


def write(catalog: pl.DataFrame, meta: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    catalog.write_csv(out_dir / "catalog.csv", line_terminator="\n")
    (out_dir / "catalog_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _json_default(value: object) -> object:
    if isinstance(value, float) and math.isnan(value):
        return None
    return str(value)
