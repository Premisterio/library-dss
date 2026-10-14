"""Reader-behaviour calibration from goodbooks-10k (CC BY-SA 4.0).

goodbooks-10k holds ~6M ratings of the 10k most popular Goodreads books by ~53k users,
plus "to-read" shelves and user tags. We only derive *aggregate* parameters (activity
distribution, rating scale, popularity tail, taste concentration) for the simulator. The raw
data stays in the local cache and is never committed (share-alike; see AGENTS.md).
"""

import io
import json
import urllib.request
import zipfile
from pathlib import Path

import polars as pl

from libsim import __version__
from libsim.catalog import genres

RELEASE = "https://github.com/zygmuntz/goodbooks-10k/releases/download/v1.0"
FILES = ("ratings", "to_read", "books", "book_tags", "tags")
ATTRIBUTION = (
    "Derived from goodbooks-10k by Zygmunt Zając (https://github.com/zygmuntz/goodbooks-10k), "
    "licensed CC BY-SA 4.0. Only aggregate statistics are included."
)
# Shelf names that say nothing about genre.
NOISE_TAGS = r"(?i)^(to-?read|currently-?reading|favou?rites?|owned|books?-i-own|kindle|ebooks?|library|default|my-books|wish-?list|audio-?books?|re-?read|series|abandoned|did-not-finish|dnf|book-club|\d+.*)$"  # noqa: E501
TOP_TAGS_PER_BOOK = 15
MIN_RATINGS_FOR_TASTE = 50


def fetch(cache_dir: Path, *, refresh: bool = False) -> Path:
    target = cache_dir / "goodbooks"
    target.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        if refresh or not (target / f"{name}.csv").exists():
            with urllib.request.urlopen(f"{RELEASE}/{name}.zip", timeout=300) as resp:  # noqa: S310
                zipfile.ZipFile(io.BytesIO(resp.read())).extractall(target)
    return target


def _num(value: object) -> float:
    """Polars aggregates are typed as broad unions; assert we really got a number."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"expected a number, got {value!r}")
    return float(value)


def _quantiles(values: pl.Series) -> dict[str, float]:
    qs = (0.1, 0.25, 0.5, 0.75, 0.9, 0.99)
    out = {f"p{round(q * 100)}": _num(values.quantile(q)) for q in qs}
    out |= {
        "mean": round(_num(values.mean()), 3),
        "min": _num(values.min()),
        "max": _num(values.max()),
    }
    return out


def _book_genres(src: Path) -> pl.DataFrame:
    books = pl.read_csv(src / "books.csv", columns=["book_id", "goodreads_book_id"])
    tags = pl.read_csv(src / "tags.csv")
    top_tags = (
        pl.read_csv(src / "book_tags.csv")
        .join(tags, on="tag_id")
        .filter(~pl.col("tag_name").str.contains(NOISE_TAGS))
        .sort(["goodreads_book_id", "count"], descending=[False, True])
        .group_by("goodreads_book_id", maintain_order=True)
        .agg(pl.col("tag_name").head(TOP_TAGS_PER_BOOK).str.replace_all(r"[-_]", " "))
    )
    with_tags = books.join(top_tags, on="goodreads_book_id", how="left")
    return with_tags.with_columns(
        genre=pl.col("tag_name").map_elements(
            lambda t: genres.classify(t) if t is not None else None, return_dtype=pl.String
        )
    ).select("book_id", "genre")


def calibrate(src: Path) -> dict:
    ratings = pl.read_csv(src / "ratings.csv")
    to_read = pl.read_csv(src / "to_read.csv")
    per_user = ratings.group_by("user_id").agg(n=pl.len(), mean=pl.col("rating").mean())
    per_book = ratings.group_by("book_id").agg(n=pl.len(), mean=pl.col("rating").mean())
    log_n = per_user["n"].log()

    # Popularity tail: slope of log(count) vs log(rank) over the middle of the ranking.
    counts = per_book.sort("n", descending=True).with_row_index("rank", offset=1)
    mid = counts.filter(pl.col("rank").is_between(10, 5000))
    slope = _ols_slope(mid["rank"].log(), mid["n"].log())
    total = _num(counts["n"].sum())

    taste = _taste(ratings, _book_genres(src))
    to_read_per_user = to_read.group_by("user_id").len()["len"]
    return {
        "source": {
            "dataset": "https://github.com/zygmuntz/goodbooks-10k",
            "license": "CC BY-SA 4.0",
            "attribution": ATTRIBUTION,
        },
        "builder": {"libsim": __version__, "polars": pl.__version__},
        "size": {"users": per_user.height, "books": per_book.height, "ratings": ratings.height},
        "books_per_user": _quantiles(per_user["n"])
        | {
            "lognormal_mu": round(_num(log_n.mean()), 4),
            "lognormal_sigma": round(_num(log_n.std()), 4),
        },
        "rating_distribution": {
            str(r): round(c / ratings.height, 4)
            for r, c in sorted(ratings.group_by("rating").len().iter_rows())
        },
        "user_mean_rating": {
            "mean": round(_num(per_user["mean"].mean()), 4),
            "sd": round(_num(per_user["mean"].std()), 4),
        },
        "book_mean_rating": {
            "mean": round(_num(per_book["mean"].mean()), 4),
            "sd": round(_num(per_book["mean"].std()), 4),
        },
        "popularity": {
            "rank_frequency_slope": round(slope, 4),
            "top_1pct_share": round(
                _num(counts.head(per_book.height // 100)["n"].sum()) / total, 4
            ),
            "top_10pct_share": round(
                _num(counts.head(per_book.height // 10)["n"].sum()) / total, 4
            ),
            "corr_log_count_mean_rating": round(
                _num(
                    pl.DataFrame({"a": per_book["n"].log(), "b": per_book["mean"]})
                    .select(pl.corr("a", "b"))
                    .item()
                ),
                4,
            ),
        },
        "to_read": {
            "share_of_users_with_list": round(to_read_per_user.len() / per_user.height, 4),
            "per_user_with_list": _quantiles(to_read_per_user),
        },
        "genre_taste": taste,
    }


def _ols_slope(x: pl.Series, y: pl.Series) -> float:
    xm, ym = _num(x.mean()), _num(y.mean())
    return _num(((x - xm) * (y - ym)).sum()) / _num(((x - xm) ** 2).sum())


def _taste(ratings: pl.DataFrame, book_genres: pl.DataFrame) -> dict:
    """How concentrated readers' genre choices are (Dirichlet concentration, top-genre share)."""
    rated = ratings.join(book_genres, on="book_id").drop_nulls("genre")
    base = rated.group_by("genre").len().with_columns(p=pl.col("len") / pl.col("len").sum())
    per_user = rated.group_by("user_id").agg(n=pl.len())
    active = per_user.filter(pl.col("n") >= MIN_RATINGS_FOR_TASTE)
    shares = (
        rated.join(active, on="user_id")
        .group_by("user_id", "genre")
        .agg(k=pl.len(), n=pl.col("n").first())
        .with_columns(x=pl.col("k") / pl.col("n"))
    )
    users = active.height
    n_bar_inv = _num((1 / active["n"]).mean())
    # Method of moments for a Dirichlet-multinomial: Var(x_g) = p(1-p)·(1/n + (1-1/n)/(1+a0)).
    estimates, weights = [], []
    for genre, share in base.select("genre", "p").iter_rows():
        p = _num(share)
        x = shares.filter(pl.col("genre") == genre)["x"]
        values = pl.concat([x, pl.Series([0.0] * (users - x.len()))])  # users without the genre
        ratio = _num(values.var()) / (p * (1 - p)) - n_bar_inv
        if ratio > 0:
            estimates.append((1 - n_bar_inv) / ratio - 1)
            weights.append(p)
    a0 = sum(e * w for e, w in zip(estimates, weights, strict=True)) / sum(weights)
    top = shares.group_by("user_id").agg(top=pl.col("x").max(), wide=(pl.col("x") >= 0.1).sum())
    return {
        "genre_base_share": {
            g: round(p, 4) for g, p in sorted(base.select("genre", "p").iter_rows())
        },
        "dirichlet_concentration": round(a0, 3),
        "mean_top_genre_share": round(_num(top["top"].mean()), 4),
        "mean_genres_over_10pct": round(_num(top["wide"].mean()), 3),
        "users_used": users,
        "books_with_genre_share": round(_num(book_genres["genre"].is_not_null().mean()), 4),
    }


def write(calibration: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "calibration.json").write_text(
        json.dumps(calibration, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
