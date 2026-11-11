"""The thesis figures from a run's results, as PNG: how close each experiment's policies come to
the oracle as the budget grows, one panel per preset (DESIGN.md §6)."""

import itertools
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
from matplotlib import rc_context
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, MultipleLocator

from experiments.config import CAMPAIGN_MONTHS
from experiments.tables import (
    CONTENT_LABELS,
    PRESET_LABELS,
    RETENTION_LABELS,
    campaign_of,
    interval,
    number,
    share_of_oracle,
)

FOLDER = "figures"
# The reference palette's first three categorical slots (light), which stay apart for every pair
# of series across small multiples; each series also gets a marker, for print and colour-blind
# readers. At most three series per figure; the tables hold the rest.
SERIES = (("#2a78d6", "o"), ("#eb6834", "s"), ("#1baf7a", "^"))
SURFACE, INK, INK_SECONDARY, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
SIZE = (6.3, 5.0)  # inches: the text width of an A4 page
DPI = 200
LABEL_GAP = 0.07  # end labels closer than this share of the axis height would collide


@dataclass(frozen=True)
class Spec:
    results: str  # CSV in the run's folder
    column: str  # what the oracle's share is taken of
    policies: tuple[str, str, str]
    labels: dict[str, str]
    y_label: str
    x_label: str


FIGURES = {
    "retention.png": Spec(
        "retention.csv",
        "value",
        ("dss", "dss_assumed", "inactive_emails"),
        RETENTION_LABELS,
        "Виграш, % від виграшу оракула",
        "Бюджет, % від вартості знижки для всіх у групі ризику",
    ),
    "content.png": Spec(
        "content.csv",
        "demand",
        ("dss", "searches_per_uah", "random"),
        CONTENT_LABELS,
        "Обслужений попит, % від оракула",
        "Бюджет, % від вартості всієї пропозиції",
    ),
}


CAMPAIGN_POLICIES = ("dss", "dss_assumed")  # the same colours as in the retention figure


def write(out: Path) -> list[Path]:
    """Every figure from the results in `out`, into `out/figures`: one per experiment on the
    libraries with libsim's own campaign, and the campaign-size experiment's."""
    folder = out / FOLDER
    folder.mkdir(exist_ok=True)
    figures = {}
    for name, spec in FIGURES.items():
        results = pl.read_csv(out / spec.results)
        frame = share_of_oracle(
            results.filter(pl.col("campaign_months") == CAMPAIGN_MONTHS), spec.column
        )
        shares = sorted(frame["budget_share"].unique().to_list())
        presets: list[str] = frame["preset"].unique(maintain_order=True).to_list()
        panels = {
            PRESET_LABELS.get(preset, preset): [
                _band(frame.filter(pl.col("preset") == preset), p, "budget_share", shares)
                for p in spec.policies
            ]
            for preset in presets
        }
        ticks = [f"{number(100 * s)} %" for s in shares]
        labels = [spec.labels[p] for p in spec.policies]
        figures[name] = _figure(panels, ticks, labels, spec.y_label, spec.x_label)
    preset, budget_share = campaign_of(out)
    frame = share_of_oracle(
        pl.read_csv(out / "retention.csv").filter(pl.col("preset") == preset), "value"
    ).filter(pl.col("budget_share") == budget_share)
    months = sorted(frame["campaign_months"].unique().to_list())
    figures["campaign.png"] = _figure(
        {
            PRESET_LABELS.get(preset, preset): [
                _band(frame, p, "campaign_months", months) for p in CAMPAIGN_POLICIES
            ]
        },
        [str(m) for m in months],
        [RETENTION_LABELS[p] for p in CAMPAIGN_POLICIES],
        f"Виграш, % від виграшу оракула (бюджет {number(100 * budget_share)} %)",
        "Тривалість минулої кампанії, місяців",
    )
    written = []
    for name, figure in figures.items():
        figure.savefig(folder / name, dpi=DPI, metadata={"Software": None})
        written.append(folder / name)
    return written


def _band(frame: pl.DataFrame, policy: str, by: str, steps: list[Any]) -> np.ndarray:
    """Per step of `by`: the mean share of the oracle (%) and its 95% interval, as rows mean,
    low and high; NaN where there are no results."""
    rows = []
    for step in steps:
        values = frame.filter((pl.col("policy") == policy) & (pl.col(by) == step))["share"]
        values = values.drop_nulls().to_numpy() * 100
        if values.size == 0:
            rows.append((math.nan,) * 3)
            continue
        mean, half = interval(values)
        rows.append((mean, mean - (half or 0.0), mean + (half or 0.0)))
    return np.array(rows).T


def _figure(
    panels: dict[str, list[np.ndarray]],
    ticks: list[str],
    labels: list[str],
    y_label: str,
    x_label: str,
) -> Figure:
    """One panel per entry of `panels` (its title → each series' band), on one y scale."""
    # From the means, not the bands: a run with few seeds has bands too wide to show whole.
    low = min(0.0, *(float(np.nanmin(band[0])) for bands in panels.values() for band in bands))
    limits = (math.floor(low / 25) * 25 - 5, 105.0)
    columns = min(len(panels), 2)
    with rc_context({"font.family": "DejaVu Sans", "font.size": 8}):
        size = SIZE if len(panels) > 1 else (SIZE[0], SIZE[1] * 0.6)
        figure = Figure(figsize=size, facecolor=SURFACE, layout="constrained")
        grid = figure.subplots(
            math.ceil(len(panels) / columns), columns, sharex=True, sharey=True, squeeze=False
        )
        for ax in grid.flat[len(panels) :]:
            ax.set_visible(False)
        for ax, (title, bands) in zip(grid.flat, panels.items(), strict=False):
            _panel(ax, title, bands, len(ticks), limits)
        ax = grid.flat[0]
        ax.set_xticks(range(len(ticks)), ticks)
        handles = [
            ax.plot([], [], color=color, marker=marker, linewidth=1.5, markersize=6)[0]
            for color, marker in SERIES[: len(labels)]
        ]
        figure.legend(
            handles,
            labels,
            loc="outside upper center",
            ncols=len(labels),
            frameon=False,
            labelcolor=INK,
        )
        figure.supylabel(y_label, color=INK_SECONDARY, fontsize=8)
        figure.supxlabel(x_label, color=INK_SECONDARY, fontsize=8)
    return figure


def _panel(
    ax: Axes, title: str, bands: list[np.ndarray], points: int, limits: tuple[float, float]
) -> None:
    x = np.arange(points)
    ax.set_facecolor(SURFACE)
    for (color, marker), (mean, low, high) in zip(SERIES, bands, strict=False):
        ax.fill_between(x, low, high, color=color, alpha=0.1, linewidth=0)
        ax.plot(
            x,
            mean,
            color=color,
            linewidth=1.5,
            solid_capstyle="round",
            solid_joinstyle="round",
            marker=marker,
            markersize=6,
            markeredgecolor=SURFACE,
            markeredgewidth=1.5,
        )
    ends = sorted(float(mean[-1]) for mean, _, _ in bands)
    if all(b - a > LABEL_GAP * (limits[1] - limits[0]) for a, b in itertools.pairwise(ends)):
        for mean, _, _ in bands:
            ax.annotate(
                f"{number(float(mean[-1]))} %",
                (x[-1], float(mean[-1])),
                xytext=(6, 0),
                textcoords="offset points",
                va="center",
                color=INK_SECONDARY,
                fontsize=7,
            )
    ax.set_title(title, loc="left", color=INK, fontsize=8.5)
    ax.set_ylim(*limits)
    ax.set_xlim(-0.3, points - 0.4)
    ax.yaxis.set_major_locator(MultipleLocator(25))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: number(value)))
    ax.grid(axis="y", color=GRID, linewidth=0.75)
    ax.set_axisbelow(True)
    ax.axhline(0, color=AXIS, linewidth=0.75)
    ax.tick_params(colors=MUTED, labelcolor=INK_SECONDARY, length=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_visible(False)
