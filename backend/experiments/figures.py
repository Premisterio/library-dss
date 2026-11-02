"""The thesis figures from a run's results, as PNG: how close each experiment's policies come to
the oracle as the budget grows, one panel per preset (DESIGN.md §6)."""

import itertools
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import polars as pl
from matplotlib import rc_context
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, MultipleLocator

from experiments.tables import (
    CONTENT_LABELS,
    PRESET_LABELS,
    RETENTION_LABELS,
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
        ("dss", "dss_assumed", "inactive"),
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


def write(out: Path) -> list[Path]:
    """Every figure from the results in `out`, into `out/figures`."""
    folder = out / FOLDER
    folder.mkdir(exist_ok=True)
    written = []
    for name, spec in FIGURES.items():
        frame = share_of_oracle(pl.read_csv(out / spec.results), spec.column)
        path = folder / name
        _figure(frame, spec).savefig(path, dpi=DPI, metadata={"Software": None})
        written.append(path)
    return written


def _lines(frame: pl.DataFrame, policy: str, shares: list[float]) -> np.ndarray:
    """Per budget: the mean share of the oracle (%) and its 95% interval, as rows mean/low/high."""
    rows = []
    for share in shares:
        values = (
            frame.filter((pl.col("policy") == policy) & (pl.col("budget_share") == share))["share"]
            .drop_nulls()
            .to_numpy()
            * 100
        )
        mean, half = interval(values)
        rows.append((mean, mean - (half or 0.0), mean + (half or 0.0)))
    return np.array(rows).T


def _figure(frame: pl.DataFrame, spec: Spec) -> Figure:
    presets = frame["preset"].unique(maintain_order=True).to_list()
    shares = sorted(frame["budget_share"].unique().to_list())
    lines = {
        (preset, policy): _lines(frame.filter(pl.col("preset") == preset), policy, shares)
        for preset in presets
        for policy in spec.policies
    }
    # From the means, not the bands: a run with few seeds has bands too wide to show whole.
    low = min(0.0, *(float(band[0].min()) for band in lines.values()))
    limits = (math.floor(low / 25) * 25 - 5, 105.0)
    columns = min(len(presets), 2)
    with rc_context({"font.family": "DejaVu Sans", "font.size": 8}):
        figure = Figure(figsize=SIZE, facecolor=SURFACE, layout="constrained")
        grid = figure.subplots(
            math.ceil(len(presets) / columns), columns, sharex=True, sharey=True, squeeze=False
        )
        for ax in grid.flat[len(presets) :]:
            ax.set_visible(False)
        for ax, preset in zip(grid.flat, presets, strict=False):
            _panel(ax, preset, [lines[preset, p] for p in spec.policies], len(shares), limits)
        ax = grid.flat[0]
        ax.set_xticks(range(len(shares)), [f"{number(100 * s)} %" for s in shares])
        handles = [
            ax.plot([], [], color=color, marker=marker, linewidth=1.5, markersize=6)[0]
            for color, marker in SERIES
        ]
        figure.legend(
            handles,
            [spec.labels[p] for p in spec.policies],
            loc="outside upper center",
            ncols=3,
            frameon=False,
            labelcolor=INK,
        )
        figure.supylabel(spec.y_label, color=INK_SECONDARY, fontsize=8)
        figure.supxlabel(spec.x_label, color=INK_SECONDARY, fontsize=8)
    return figure


def _panel(
    ax: Axes, preset: str, bands: list[np.ndarray], points: int, limits: tuple[float, float]
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
    ax.set_title(PRESET_LABELS.get(preset, preset), loc="left", color=INK, fontsize=8.5)
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
