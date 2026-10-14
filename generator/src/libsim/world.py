"""The library's stock: the real catalogue plus simulated licences and latent book traits.

Books come from `data/catalog.csv` (Open Library). The simulator adds what the dump cannot
know: how many licences (copies) the library holds, which titles it lacks (demand for them
only shows up as zero-result searches) and which of those a distributor offers.
"""

import csv
import json
from dataclasses import dataclass
from importlib import resources

import numpy as np

from libsim.catalog import genres
from libsim.params import Params

GENRE_CODES = list(genres.GENRES)
LANGUAGES = ["uk", "en"]


def _data_file(name: str):
    return resources.files("libsim").joinpath("data", name)


def load_calibration() -> dict:
    return json.loads(_data_file("calibration.json").read_text(encoding="utf-8"))


@dataclass
class Books:
    book_id: list[str]
    title: list[str]
    authors: list[str]
    genre: np.ndarray  # int index into GENRE_CODES
    language: np.ndarray  # 0 = uk, 1 = en
    pages: np.ndarray
    first_year: np.ndarray
    ol_signal: np.ndarray
    quality: np.ndarray  # latent, standardised (ground truth)
    weight: np.ndarray  # latent popularity weight (ground truth)
    in_library: np.ndarray  # bool
    copies: np.ndarray  # licences held (0 when not in library)
    candidate: np.ndarray  # bool: offered by the distributor
    license_cost: np.ndarray  # UAH per copy for candidates (0 otherwise)

    @property
    def n(self) -> int:
        return len(self.book_id)


def load_books(params: Params, rng: np.random.Generator) -> Books:
    with _data_file("catalog.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    n = len(rows)
    signal = np.array([int(r["ol_signal"]) for r in rows], dtype=float)
    quality_prior = np.array([float(r["quality_prior"]) for r in rows])
    ratings = np.array([int(r["ol_ratings"]) for r in rows], dtype=float)

    # Quality: OL rating prior, standardised, plus noise that shrinks with more ratings.
    q = (quality_prior - quality_prior.mean()) / quality_prior.std()
    q = q + rng.normal(0.0, 1.0, n) / np.sqrt(1.0 + ratings / 10.0)
    quality = (q - q.mean()) / q.std()
    # Popularity: real OL demand signal, sub-linear, with idiosyncratic noise.
    weight = (1.0 + signal) ** 0.55 * rng.lognormal(0.0, 0.3, n)

    held_out = _pick_held_out(signal, weight, params.held_out_titles, rng)
    candidate = np.zeros(n, dtype=bool)
    candidate[rng.choice(np.flatnonzero(held_out), size=params.candidates, replace=False)] = True
    in_library = ~held_out

    language = np.array([LANGUAGES.index(r["language"]) for r in rows])
    rel = weight / np.median(weight[in_library])
    # Licences grow sub-linearly with the member base (a library buys more copies as it grows).
    audience = (params.users / 1000) ** 0.75
    copies = np.clip(
        np.round(params.copies_scale * audience * (0.9 + 1.5 * np.sqrt(rel))), 1, 120
    ).astype(int)
    under = rng.random(n) < params.under_licensed_share
    copies = np.where(under, np.maximum(1, copies // 3), copies)
    copies = np.where(in_library, copies, 0)

    # Licence cost correlates with demand (popular titles are pricier) plus negotiation noise.
    pct = weight.argsort().argsort() / (n - 1)
    base_cost = np.where(language == 0, 450.0, 900.0)
    license_cost = np.where(
        candidate, np.round(base_cost * (0.7 + 0.8 * pct) * rng.lognormal(0.0, 0.25, n), -1), 0.0
    )
    return Books(
        book_id=[r["book_id"] for r in rows],
        title=[r["title"] for r in rows],
        authors=[r["authors"] for r in rows],
        genre=np.array([GENRE_CODES.index(r["genre"]) for r in rows]),
        language=language,
        pages=np.array([int(r["pages"]) for r in rows]),
        first_year=np.array(
            [int(r["first_year"]) if r["first_year"] else -1 for r in rows]
        ),  # -1 = unknown
        ol_signal=signal,
        quality=quality,
        weight=weight,
        in_library=in_library,
        copies=copies,
        candidate=candidate,
        license_cost=license_cost,
    )


def _pick_held_out(
    signal: np.ndarray, weight: np.ndarray, k: int, rng: np.random.Generator
) -> np.ndarray:
    """Titles the library lacks: drawn among books with real demand, favouring mid-popularity."""
    pool = np.flatnonzero(signal > 0)
    p = np.sqrt(weight[pool])
    chosen = rng.choice(pool, size=min(k, pool.size), replace=False, p=p / p.sum())
    held = np.zeros(signal.size, dtype=bool)
    held[chosen] = True
    return held
