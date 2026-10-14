"""PDF report: title page block, then every section with its KPIs, charts and tables.

Text is set in DejaVu Sans (embedded), which covers Ukrainian. A chart with one dimension is
drawn (bars for categories, a line for time); a chart with two dimensions becomes a pivot table.
Long tables are cut; the XLSX and CSV exports carry every row.
"""

import io
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.exports import ReportDocument
from app.exports.labels import (
    Column,
    cell_text,
    chart_title,
    columns,
    label,
    value_text,
    window_text,
)

FONTS = Path(__file__).parent / "fonts"
FONT, BOLD = "DejaVuSans", "DejaVuSans-Bold"
PAGE = landscape(A4)
MARGIN = 14 * mm
WIDTH = PAGE[0] - 2 * MARGIN
MAX_ROWS = 30  # rows of a table in the PDF
MAX_TIME_ROWS = 12  # the most recent rows of a time series (the line shows the rest)
MAX_BARS = 25
MAX_PIVOT_COLUMNS = 24
MAX_PIVOT_ROWS = 60
ACCENT = colors.HexColor("#3B6EA5")
HEADER_FILL = colors.HexColor("#EDF1F6")
GRID = colors.HexColor("#C8CED6")


@cache
def _register_fonts() -> None:
    pdfmetrics.registerFont(TTFont(FONT, str(FONTS / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(BOLD, str(FONTS / "DejaVuSans-Bold.ttf")))
    registerFontFamily(FONT, normal=FONT, bold=BOLD, italic=FONT, boldItalic=BOLD)


def _style(name: str, size: float, *, bold: bool = False, **extra: Any) -> ParagraphStyle:
    return ParagraphStyle(
        name, fontName=BOLD if bold else FONT, fontSize=size, leading=size * 1.25, **extra
    )


TITLE = _style("title", 18, bold=True, spaceAfter=4)
META = _style("meta", 9, textColor=colors.HexColor("#555555"), spaceAfter=10)
H1 = _style("h1", 14, bold=True, spaceBefore=10, spaceAfter=6, textColor=ACCENT, keepWithNext=1)
H2 = _style("h2", 10.5, bold=True, spaceBefore=8, spaceAfter=4, keepWithNext=1)
NOTE = _style("note", 7.5, textColor=colors.HexColor("#666666"), spaceAfter=3)
CAPTION = _style("caption", 7.5, textColor=colors.HexColor("#666666"), spaceAfter=3, keepWithNext=1)
CELL = _style("cell", 7)
CELL_NUMBER = _style("cell-number", 7, alignment=TA_RIGHT)
CELL_HEADER = _style("cell-header", 7, bold=True)


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text), style)


def _table(
    header: list[str], body: list[list[str]], widths: list[float], numeric: set[int]
) -> Table:
    cells = [[_p(h, CELL_HEADER) for h in header]] + [
        [_p(v, CELL_NUMBER if i in numeric else CELL) for i, v in enumerate(row)] for row in body
    ]
    table = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.3, GRID),
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_FILL),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return table


def _widths(cols: list[Column]) -> list[float]:
    weights = [1.0 if c.unit else (3.0 if c.key in {"title", "query"} else 1.8) for c in cols]
    scale = min(WIDTH / sum(weights), 120)
    return [w * scale for w in weights]


def _kpis(kpis: list[dict[str, Any]]) -> Table:
    body = [
        [
            label("metric", k["key"]),
            value_text(k["value"], k["unit"]),
            window_text(k["window_days"]),
        ]
        for k in kpis
    ]
    return _table(["Показник", "Значення", "Період"], body, [260, 120, 120], {1})


def _axis_text(unit: str) -> Callable[[float], str]:
    return lambda v: value_text(v, unit)


def _bars(chart: dict[str, Any], cols: list[Column]) -> Drawing:
    dim, measure = cols[0], next(c for c in cols if c.unit)
    rows = chart["rows"]
    names = [cell_text(dim, r.get(dim.key))[:40] for r in rows][::-1]  # first row on top
    values = [r.get(measure.key) or 0 for r in rows][::-1]
    height = 13 * len(rows)
    drawing = Drawing(WIDTH, height + 24)
    drawing.hAlign = "LEFT"
    bars: Any = HorizontalBarChart()  # reportlab is untyped
    bars.x, bars.y, bars.width, bars.height = 190, 16, WIDTH - 240, height
    bars.data = [values]
    bars.bars[0].fillColor = ACCENT
    bars.bars[0].strokeColor = None
    bars.categoryAxis.categoryNames = names
    bars.categoryAxis.labels.fontName = FONT
    bars.categoryAxis.labels.fontSize = 7
    bars.categoryAxis.labels.boxAnchor = "e"
    bars.valueAxis.valueMin = 0
    bars.valueAxis.valueMax = max(max(values, default=0), 1e-9) * 1.05
    bars.valueAxis.labels.fontName = FONT
    bars.valueAxis.labels.fontSize = 6.5
    bars.valueAxis.labelTextFormat = _axis_text(measure.unit or "count")
    drawing.add(bars)
    return drawing


def _line(chart: dict[str, Any], cols: list[Column]) -> Drawing:
    dim, measure = cols[0], next(c for c in cols if c.unit)
    rows = chart["rows"]
    step = max(1, len(rows) // 12)
    names = [str(r.get(dim.key)) if i % step == 0 else "" for i, r in enumerate(rows)]
    values = [r.get(measure.key) or 0 for r in rows]
    drawing = Drawing(WIDTH, 170)
    drawing.hAlign = "LEFT"
    line: Any = HorizontalLineChart()  # reportlab is untyped
    line.x, line.y, line.width, line.height = 60, 40, WIDTH - 90, 120
    line.data = [values]
    line.lines[0].strokeColor = ACCENT
    line.lines[0].strokeWidth = 1.4
    line.categoryAxis.categoryNames = names
    line.categoryAxis.labels.fontName = FONT
    line.categoryAxis.labels.fontSize = 6.5
    line.categoryAxis.labels.angle = 30
    line.categoryAxis.labels.boxAnchor = "ne"
    line.valueAxis.valueMin = 0
    line.valueAxis.labels.fontName = FONT
    line.valueAxis.labels.fontSize = 6.5
    line.valueAxis.labelTextFormat = _axis_text(measure.unit or "count")
    drawing.add(line)
    return drawing


def _ordered(values: list[Any], order: list[str] | None) -> list[Any]:
    seen = list(dict.fromkeys(values))
    if not order:
        return seen
    known = [v for v in order if v in seen]
    return known + [v for v in seen if v not in known]


def _pivot(chart: dict[str, Any], cols: list[Column]) -> list[Flowable] | None:
    """Two dimensions → rows × columns of one measure (a ratio when there is one)."""
    dims = chart["dimensions"]
    first, second = (c for c in cols if c.key in {dims[0]["key"], dims[1]["key"]})
    rows = chart["rows"]
    values = {
        c.key: _ordered([r.get(c.key) for r in rows], d.get("order"))
        for c, d in zip((first, second), dims, strict=True)
    }
    across, down = sorted((first, second), key=lambda c: len(values[c.key]))
    if len(values[across.key]) > MAX_PIVOT_COLUMNS or len(values[down.key]) > MAX_PIVOT_ROWS:
        return None
    measures = [c for c in cols if c.unit]
    measure = next((m for m in measures if m.unit == "ratio"), measures[0])
    cells = {(r.get(down.key), r.get(across.key)): r.get(measure.key) for r in rows}
    header = [down.title] + [cell_text(across, v) for v in values[across.key]]
    body = [
        [cell_text(down, d)]
        + [value_text(cells.get((d, a)), measure.unit or "count") for a in values[across.key]]
        for d in values[down.key]
    ]
    first_width = 110.0
    rest = min((WIDTH - first_width) / len(values[across.key]), 80)
    widths = [first_width] + [rest] * len(values[across.key])
    return [
        _p(f"Значення: {measure.title}", CAPTION),
        _table(header, body, widths, set(range(1, len(header)))),
    ]


def _long(chart: dict[str, Any], cols: list[Column]) -> list[Flowable]:
    rows = chart["rows"]
    time_series = chart["dimensions"] and chart["dimensions"][0]["kind"] == "time"
    shown = rows[-MAX_TIME_ROWS:] if time_series else rows[:MAX_ROWS]
    body = [[cell_text(c, r.get(c.key)) for c in cols] for r in shown]
    numeric = {i for i, c in enumerate(cols) if c.unit}
    parts: list[Flowable] = [_table([c.title for c in cols], body, _widths(cols), numeric)]
    if len(shown) < len(rows):
        which = "останні" if time_series else "перші"
        parts.append(
            _p(
                f"Показано {which} {len(shown)} з {len(rows)} рядків; усі рядки є в XLSX і CSV.",
                NOTE,
            )
        )
    return parts


def _chart(chart: dict[str, Any]) -> list[Flowable]:
    heading = _p(chart_title(chart), H2)
    rows, dims = chart["rows"], chart["dimensions"]
    if not rows:
        return [KeepTogether([heading, _p("Немає даних.", NOTE)])]
    cols = columns(chart)
    if len(dims) == 2 and (pivot := _pivot(chart, cols)):
        return [heading, *pivot]
    parts: list[Flowable] = [heading]
    if len(dims) == 1 and dims[0]["kind"] == "time" and len(rows) > 2:
        parts.append(_line(chart, cols))
    elif len(dims) == 1 and len(rows) <= MAX_BARS:
        parts.append(_bars(chart, cols))
    return parts + _long(chart, cols)


def _footer(title: str) -> Callable[[Canvas, Any], None]:
    def draw(canvas: Canvas, doc: Any) -> None:
        canvas.saveState()
        canvas.setFont(FONT, 7)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(MARGIN, 8 * mm, title[:120])
        canvas.drawRightString(PAGE[0] - MARGIN, 8 * mm, str(doc.page))
        canvas.restoreState()

    return draw


def render_pdf(document: ReportDocument) -> bytes:
    _register_fonts()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=PAGE,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN + 4 * mm,
        title=document.title,
        author="library-dss",
        creator="library-dss",
        lang="uk",
        invariant=True,  # no timestamps or random ids: the same report gives the same bytes
    )
    story: list[Flowable] = [
        _p(document.title, TITLE),
        _p(
            f"Датасет: {document.dataset_name} · дата зрізу: {document.as_of} "
            f"({document.timezone}) · створено: {document.created_at:%Y-%m-%d %H:%M} UTC",
            META,
        ),
    ]
    for section in document.sections:
        story.append(_p(label("analytics_section", section["key"]), H1))
        story.extend(_p(note["message_uk"], NOTE) for note in section["notes"])
        if section["kpis"]:
            story += [_kpis(section["kpis"]), Spacer(1, 4)]
        for chart in section["charts"]:
            story.extend(_chart(chart))
    footer = _footer(document.title)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
