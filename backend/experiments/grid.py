"""The experiment grid: each preset × seed simulated, decided on the way the app decides, and
judged against the ground truth (DESIGN.md §6)."""

import json
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from multiprocessing import get_context
from pathlib import Path
from typing import Any

import polars as pl

from app.domain.churn import examples
from app.domain.churn.scoring import score
from app.domain.churn.training import train
from app.domain.retention.effects import estimate, participants
from app.ingest import reader
from experiments import content, retention
from experiments.config import Config
from libsim import engine, writer
from libsim.params import preset as make_params

Rows = dict[str, list[dict[str, Any]]]  # results table → its rows


def library(preset: str, seed: int, config: Config) -> Rows:
    """The rows of every results table for one library (`_judge`). A failure comes as a plain
    RuntimeError naming the library, which a worker process can send back: an exception with
    its own constructor arguments, such as `IngestError`, cannot be unpickled and would break the
    whole pool without saying which library failed."""
    try:
        return _judge(preset, seed, config)
    except Exception as exc:
        detail = f" {vars(exc)}" if vars(exc) else ""
        raise RuntimeError(f"{preset} seed {seed}: {type(exc).__name__}: {exc}{detail}") from exc


def _judge(preset: str, seed: int, config: Config) -> Rows:
    """Simulate one library, import it, train and score a churn model and estimate the campaign's
    effects like a churn run does, read the offer like the `candidates` section does, then judge
    every retention and content policy against the truth."""
    params = make_params(
        preset,
        seed=seed,
        users=config.members,
        months=config.months,
        horizon_days=config.horizon_days,
    )
    simulated = engine.simulate(params)
    truth = writer.build_ground_truth(simulated)
    parsed = reader.parse(writer.build_dataset(simulated))
    del simulated  # the simulation's event lists are large; free them before training
    rows = examples(parsed.frames, parsed.as_of, parsed.timezone)
    training = train(rows)
    scores = score(training, parsed.frames, parsed.as_of, parsed.timezone)
    campaign = participants(parsed.frames, parsed.timezone)
    discounts = parsed.frames["campaign_assignments"].filter(pl.col("arm") == "discount")
    group = retention.RiskGroup(
        people=retention.people_at_risk(scores, truth),
        effects=estimate(campaign),
        discount_pct=float(discounts.select(pl.col("discount_pct").median()).item()),
        seed=seed,
    )
    key = {"preset": preset, "seed": seed}
    model = {
        **key,
        "model": training.chosen,
        "unmatched": len(scores) - group.people.height,  # scored but not at risk in the truth
        **retention.model_quality(group, rows.select(pl.col("churned").mean()).item()),
        **retention.effect_coverage(group.effects, campaign, truth),
    }
    return {
        "retention": [key | row for row in retention.evaluate_policies(group, config.retention)],
        "models": [model],
        "content": [
            key | row
            for row in content.evaluate_policies(
                content.offer(parsed.frames, parsed.as_of, parsed.timezone, truth),
                config.content,
                seed,
            )
        ],
    }


def run(config: Config, out: Path, *, workers: int, echo: Callable[[str], object] = print) -> None:
    """Every library of the grid, `workers` at a time, into one CSV per results table, in the
    grid's order whatever the order they finish in. The grid used goes to `config.json`."""
    cases = config.cases()
    results: dict[tuple[str, int], Rows] = {}
    started = time.perf_counter()

    def finished(case: tuple[str, int], rows: Rows) -> None:
        results[case] = rows
        elapsed = time.perf_counter() - started
        echo(f"{len(results)}/{len(cases)}  {case[0]} seed {case[1]}  ({elapsed:.0f} s)")

    if workers == 1:
        for case in cases:
            finished(case, library(*case, config))
    else:
        with ProcessPoolExecutor(workers, mp_context=get_context("spawn")) as pool:
            futures = {pool.submit(library, *case, config): case for case in cases}
            for future in as_completed(futures):
                finished(futures[future], future.result())
    out.mkdir(parents=True, exist_ok=True)
    for name in results[cases[0]]:
        rows = [row for case in cases for row in results[case][name]]
        pl.DataFrame(rows, infer_schema_length=None).write_csv(out / f"{name}.csv")
    (out / "config.json").write_text(json.dumps(asdict(config), indent=2) + "\n", encoding="utf-8")
