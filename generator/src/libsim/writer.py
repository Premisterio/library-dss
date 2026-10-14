"""Turn a simulation result into a dataset v2 file and a separate ground-truth file.

Only events up to the end of `as_of` reach the dataset; anything still in progress at that
moment (loans, holds, subscription periods) is written as open. Output is deterministic:
same params → byte-identical files (sorted keys, fixed rounding, gzip mtime=0).
"""

import gzip
import hashlib
import io
import json
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

from libsim import __version__
from libsim.catalog import goodbooks_attribution, openlibrary_attribution
from libsim.engine import Result
from libsim.params import AGE_RANGES, DEVICES, EDUCATION
from libsim.schema import SCHEMA_VERSION, columns
from libsim.world import GENRE_CODES, LANGUAGES

CAMPAIGN_ID = "camp-retention-1"


def _clock(start: date, days: int, tz_name: str) -> Callable[[int], str]:
    """Local seconds since `start` 00:00 → ISO UTC string (offset taken at local noon)."""
    tz = ZoneInfo(tz_name)

    def offset(day: int) -> int:
        delta = datetime.combine(start + timedelta(days=day), time(12), tzinfo=tz).utcoffset()
        return int(delta.total_seconds()) if delta is not None else 0

    offsets = [offset(d) for d in range(days + 1)]
    base = datetime(start.year, start.month, start.day)

    def iso(t: int) -> str:
        utc = base + timedelta(seconds=int(t) - offsets[min(max(int(t) // 86400, 0), days)])
        return utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    return iso


def params_hash(result: Result) -> str:
    blob = json.dumps(result.params.to_dict(), sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()


def simulation_id(result: Result) -> str:
    p = result.params
    return f"{p.preset}-s{p.seed}-{params_hash(result)[:8]}"


def build_dataset(result: Result) -> dict[str, Any]:
    p, b, pop, ev = result.params, result.books, result.population, result.events
    iso = _clock(result.start, result.observed_days, p.timezone)
    cut = result.observed_days * 86400
    uid = [f"u{i + 1:06d}" for i in range(pop.n)]
    bid = b.book_id

    users = [
        [
            uid[i],
            iso(int(pop.registered_day[i]) * 86400 + 9 * 3600),
            AGE_RANGES[pop.age[i]],
            EDUCATION[pop.education[i]],
            "uk" if pop.uk_only[i] else "uk+en",
            bool(pop.email_opt_in[i]),
            sorted({GENRE_CODES[g] for g in pop.interests[i]}),
        ]
        for i in range(pop.n)
    ]
    books = [
        [
            bid[i],
            b.title[i],
            b.authors[i],
            GENRE_CODES[b.genre[i]],
            LANGUAGES[b.language[i]],
            int(b.pages[i]),
            (int(b.first_year[i]) if b.first_year[i] > 0 else None),
            int(b.copies[i]),
        ]
        for i in np.flatnonzero(b.in_library)
    ]
    periods = []
    for user, plan, start, end, price, paid, discount, outcome in ev.subscription_periods:
        if start >= cut:
            continue
        decided = end < cut
        periods.append(
            [
                uid[user],
                plan,
                iso(start),
                iso(end),
                price,
                paid,
                discount,
                outcome if decided else "open",
            ]
        )
    loans = []
    for k, (user, book, borrowed, returned, completed, rating, via_hold) in enumerate(ev.loans):
        if borrowed >= cut:
            continue
        closed = returned is not None and returned < cut
        loans.append(
            [
                f"l{k + 1:07d}",
                uid[user],
                bid[book],
                iso(borrowed),
                iso(returned) if closed else None,
                completed if closed else None,
                rating if closed else None,
                via_hold,
            ]
        )
    sessions = [
        [uid[u], bid[bk], iso(t), m, pg, DEVICES[d]] for u, bk, t, m, pg, d in ev.reading_sessions
    ]
    searches = [[uid[u], iso(t), q, r] for u, t, q, r in ev.searches]
    holds = []
    for k, (user, book, placed, resolved, outcome) in enumerate(ev.holds):
        if placed >= cut:
            continue
        closed = resolved is not None and resolved < cut
        holds.append(
            [
                f"h{k + 1:06d}",
                uid[user],
                bid[book],
                iso(placed),
                iso(resolved) if closed else None,
                outcome if closed else "open",
            ]
        )
    sim = result.campaign
    has_campaign = sim["end_day"] > sim["start_day"]
    campaigns = [
        [
            CAMPAIGN_ID,
            "Утримання підписників: e-mail чи знижка",
            iso(sim["start_day"] * 86400),
            iso(sim["end_day"] * 86400 + 86399),
            "randomized_at_renewal",
            list(p.campaign.arms),
        ]
    ][: int(has_campaign)]
    assignments = [
        [CAMPAIGN_ID, uid[u], iso(t), arm, delivered, discount, iso(target)]
        for u, t, arm, delivered, discount, target in ev.campaign_assignments
    ]
    offered = iso((result.observed_days - 15) * 86400 + 10 * 3600)
    candidates = [
        [
            f"c{k + 1:03d}",
            b.title[i],
            b.authors[i],
            GENRE_CODES[b.genre[i]],
            LANGUAGES[b.language[i]],
            int(b.pages[i]),
            (int(b.first_year[i]) if b.first_year[i] > 0 else None),
            float(b.license_cost[i]),
            offered,
        ]
        for k, i in enumerate(np.flatnonzero(b.candidate))
    ]
    tables = {
        "users": users,
        "books": books,
        "subscription_periods": periods,
        "loans": loans,
        "reading_sessions": sessions,
        "searches": searches,
        "holds": holds,
        "campaigns": campaigns,
        "campaign_assignments": assignments,
        "candidate_titles": candidates,
    }
    phash = params_hash(result)
    return {
        "schema_version": SCHEMA_VERSION,
        "meta": {
            "generator": "libsim",
            "generator_version": __version__,
            "seed": p.seed,
            "preset": p.preset,
            "params_hash": phash,
            "simulation_id": simulation_id(result),
            "observed_from": result.start.isoformat(),
            "as_of": p.as_of.isoformat(),
            "timezone": p.timezone,
            "row_counts": {name: len(rows) for name, rows in tables.items()},
            "notes": "Synthetic library activity simulated by libsim over a real book catalogue.",
            "sources": {
                "catalogue": openlibrary_attribution(),
                "calibration": goodbooks_attribution(),
            },
        },
        "tables": {name: {"columns": columns(name), "rows": rows} for name, rows in tables.items()},
    }


def build_ground_truth(result: Result) -> dict[str, Any]:
    gt, b, pop = result.ground_truth, result.books, result.population
    uid = [f"u{i + 1:06d}" for i in range(pop.n)]
    users = {key: dict(zip(uid, values, strict=True)) for key, values in gt["users"].items()}
    at_risk = [{**row, "user_id": uid[row.pop("user")]} for row in gt["at_risk"]]
    candidate_idx = np.flatnonzero(b.candidate)
    return {
        "simulation_id": simulation_id(result),
        "params": gt["params"],
        "churn_logit": gt["churn_logit"],
        "users": users,
        "at_risk": at_risk,
        "campaign": [{**row, "user_id": uid[row.pop("user")]} for row in gt["campaign"]],
        "books": {
            "quality": dict(zip(b.book_id, gt["books"]["quality"], strict=True)),
            "popularity_weight": dict(zip(b.book_id, gt["books"]["weight"], strict=True)),
            "held_out": [b.book_id[i] for i in np.flatnonzero(~b.in_library)],
        },
        "candidates": {
            f"c{k + 1:03d}": {
                "book_id": b.book_id[i],
                "demand_last_90d_per_month": gt["candidates"]["demand_last_90d_per_month"][i],
                "demand_future_window": gt["candidates"]["demand_future_window"][i],
            }
            for k, i in enumerate(candidate_idx)
        },
    }


def _plain(value: object) -> object:
    """numpy scalars (from the simulation arrays) → plain JSON values."""
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def _dumps(data: dict[str, Any], *, indent: int | None = None) -> bytes:
    separators = (",", ":") if indent is None else (",", ": ")
    text = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        indent=indent,
        separators=separators,
        default=_plain,
    )
    return (text + "\n").encode()


def write(result: Result, out_dir: Path, *, compress: bool = True) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    sid = simulation_id(result)
    payload = _dumps(build_dataset(result))
    dataset_path = out_dir / (f"{sid}.json.gz" if compress else f"{sid}.json")
    if compress:
        buf = io.BytesIO()
        with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0, compresslevel=6) as fh:
            fh.write(payload)
        dataset_path.write_bytes(buf.getvalue())
    else:
        dataset_path.write_bytes(payload)
    truth_path = out_dir / f"{sid}.ground_truth.json"
    truth_path.write_bytes(_dumps(build_ground_truth(result)))
    return dataset_path, truth_path
