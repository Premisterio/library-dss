"""The thesis tables from a run's results: the mean over seeds ± the half-width of its 95%
t-interval, labelled in Ukrainian for the thesis text (DESIGN.md §6)."""

import math
from datetime import datetime
from pathlib import Path

import numpy as np
import polars as pl
import xlsxwriter
from scipy import stats

WORKBOOK = "tables.xlsx"
CREATED = datetime(2026, 9, 30)  # fixed, so the same results give the same file
PRESET_LABELS = {
    "demo": "Базовий",
    "weak-signal": "Слабкий сигнал",
    "no-heterogeneity": "Однакові ефекти",
    "misspecified": "Прихований чинник",
    "high-scarcity": "Дефіцит ліцензій",
}
RETENTION_LABELS = {
    "random": "Знижки випадковим",
    "inactive": "Знижки неактивним 14+ днів",
    "risk": "Знижки за ризиком",
    "dss_assumed": "СППР із припущеннями",
    "dss": "СППР",
    "dss_segments": "СППР, ефекти сегментів",
    "dss_cautious": "СППР, обережна межа",
    "oracle": "Оракул",
}
CONTENT_LABELS = {
    "random": "Випадкові назви",
    "cheapest": "Найдешевші",
    "most_searched": "Найшукаваніші",
    "searches_per_uah": "Пошуки на гривню",
    "top_genre": "Найпопулярніший жанр",
    "saw": "SAW, рівні ваги",
    "dss": "СППР: TOPSIS, рівні ваги",
    "dss_searches": "СППР: TOPSIS, пошуки ×3",
    "oracle": "Оракул",
}

Table = tuple[list[str], list[list[str]]]  # header, rows


def number(value: float, digits: int = 0) -> str:
    """Ukrainian style: a space between thousands, a decimal comma and a true minus sign."""
    rounded = round(value, digits) + 0.0  # no "−0"
    return f"{rounded:,.{digits}f}".replace(",", " ").replace(".", ",").replace("-", "−")


def summary(values: np.ndarray, digits: int = 0) -> str:
    """The mean ± the half-width of its 95% t-interval; the mean alone for one value."""
    if values.size == 0:
        return "—"
    mean = float(values.mean())
    if values.size == 1:
        return number(mean, digits)
    half = stats.t.ppf(0.975, values.size - 1) * values.std(ddof=1) / math.sqrt(values.size)
    return f"{number(mean, digits)} ± {number(float(half), digits)}"


def by_budget(
    frame: pl.DataFrame,
    column: str,
    labels: dict[str, str],
    *,
    scale: float = 1.0,
    digits: int = 0,
) -> Table:
    """One row per preset and policy (in the order of `labels`), one column per budget."""
    shares = sorted(frame["budget_share"].unique().to_list())
    header = ["Сценарій", "Політика", *(f"Бюджет {number(100 * s)} %" for s in shares)]
    rows = []
    for preset in frame["preset"].unique(maintain_order=True).to_list():
        label = PRESET_LABELS.get(preset, preset)
        for policy, policy_label in labels.items():
            mine = frame.filter((pl.col("preset") == preset) & (pl.col("policy") == policy))
            if mine.is_empty():
                continue
            cells = [
                summary(
                    mine.filter(pl.col("budget_share") == s)[column].drop_nulls().to_numpy()
                    * scale,
                    digits,
                )
                for s in shares
            ]
            rows.append([label, policy_label, *cells])
            label = ""
    return header, rows


def share_of_oracle(frame: pl.DataFrame, column: str) -> pl.DataFrame:
    """`share`: each row's `column` over the oracle's for the same library and budget."""
    oracle = frame.filter(pl.col("policy") == "oracle").select(
        "preset", "seed", "budget_share", oracle=column
    )
    return frame.join(oracle, on=["preset", "seed", "budget_share"]).with_columns(
        share=pl.when(pl.col("oracle") > 0).then(pl.col(column) / pl.col("oracle"))
    )


def retention_tables(retention: pl.DataFrame) -> dict[str, Table]:
    """The true net gain, its share of the oracle's and the share of actions that pay off."""
    shared = share_of_oracle(retention, "value")
    return {
        "Утримання, виграш, грн": by_budget(retention, "value", RETENTION_LABELS),
        "Утримання, частка оракула, %": by_budget(shared, "share", RETENTION_LABELS, scale=100),
        "Утримання, точність дій, %": by_budget(
            retention, "precision", RETENTION_LABELS, scale=100
        ),
    }


def content_tables(content: pl.DataFrame) -> dict[str, Table]:
    """The true demand the licensed titles meet, and its share of the oracle's."""
    shared = share_of_oracle(content, "demand")
    return {
        "Закупівля, обслужений попит": by_budget(content, "demand", CONTENT_LABELS),
        "Закупівля, частка оракула, %": by_budget(shared, "share", CONTENT_LABELS, scale=100),
    }


def model_table(models: pl.DataFrame) -> Table:
    """The churn model against the best possible, and how often the campaign's 95% intervals
    contain the true effects."""
    header = [
        "Сценарій",
        "AUC моделі",
        "Найкраща AUC",
        "Розрив AUC",
        "Brier моделі",
        "Найкращий Brier",
        "Інтервал ефекту e-mail містить істину",
        "Інтервал ефекту знижки містить істину",
    ]
    rows = []
    for preset in models["preset"].unique(maintain_order=True).to_list():
        mine = models.filter(pl.col("preset") == preset)

        def column(expr: pl.Expr, frame: pl.DataFrame = mine) -> np.ndarray:
            return frame.select(expr).to_series().drop_nulls().to_numpy()

        def covered(action: str, frame: pl.DataFrame = mine) -> str:
            known = frame[f"{action}_covered"].drop_nulls()
            return f"{int(known.sum())} з {known.len()}"

        rows.append(
            [
                PRESET_LABELS.get(preset, preset),
                summary(column(pl.col("roc_auc")), 3),
                summary(column(pl.col("roc_auc_best")), 3),
                summary(column(pl.col("roc_auc_best") - pl.col("roc_auc")), 3),
                summary(column(pl.col("brier")), 4),
                summary(column(pl.col("brier_best")), 4),
                covered("email"),
                covered("discount"),
            ]
        )
    return header, rows


def write(out: Path) -> dict[str, Table]:
    """Every table from the results in `out`, also written to `out/tables.xlsx`, one sheet each."""
    tables = retention_tables(pl.read_csv(out / "retention.csv"))
    tables |= content_tables(pl.read_csv(out / "content.csv"))
    tables["Модель і ефекти"] = model_table(pl.read_csv(out / "models.csv"))
    workbook = xlsxwriter.Workbook(str(out / WORKBOOK))
    workbook.set_properties({"created": CREATED})
    bold = workbook.add_format({"bold": True})
    for name, (header, rows) in tables.items():
        sheet = workbook.add_worksheet(name)
        sheet.write_row(0, 0, header, bold)
        for i, row in enumerate(rows, start=1):
            sheet.write_row(i, 0, row)
        for j, cells in enumerate(zip(header, *rows, strict=True)):
            sheet.set_column(j, j, max(len(cell) for cell in cells) + 2)
    workbook.close()
    return tables


def text(table: Table) -> str:
    """A table as aligned plain text, for the terminal."""
    header, rows = table
    widths = [max(len(cell) for cell in cells) for cells in zip(header, *rows, strict=True)]
    return "\n".join(
        "  ".join(cell.ljust(width) for cell, width in zip(line, widths, strict=True)).rstrip()
        for line in (header, *rows)
    )
