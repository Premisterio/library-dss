"""PDF report: a cover page, then every section from a new page with its notes, KPIs, charts and
tables; each page has a footer with the title and "N з M".

Text is set in DejaVu Sans (embedded), which covers Ukrainian. How the cover is laid out and how
each chart is shown is in DESIGN.md §2.10. Long tables are cut; the XLSX and CSV exports carry
every row.
"""

import io
import re
from collections.abc import Callable
from functools import cache, partial
from pathlib import Path
from typing import Any, override
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
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from app.exports import ReportDocument
from app.exports.labels import (
    EMPTY,
    Column,
    cell_text,
    chart_title,
    columns,
    created_text,
    label,
    value_text,
    window_text,
)
from app.utils.format import decimals_for, number, percent

FONTS = Path(__file__).parent / "fonts"
FONT, BOLD = "DejaVuSans", "DejaVuSans-Bold"
PAGE = landscape(A4)
MARGIN = 14 * mm
BOTTOM = 18 * mm  # the bottom margin leaves room for the footer
FOOTER_Y = 8 * mm
WIDTH = PAGE[0] - 2 * MARGIN
HEIGHT = PAGE[1] - MARGIN - BOTTOM
FOOTER_TITLE = 120  # characters of the title in the footer
MAX_ROWS = 30  # rows of a table in the PDF
MAX_TIME_ROWS = 12  # the most recent rows of a time series (the line shows the rest)
MAX_BARS = 25
MAX_PIVOT_COLUMNS = 24
MAX_PIVOT_ROWS = 60
MIN_SPLIT_ROWS = 5
KEY_WIDTH, VALUE_WIDTH = 170, 400  # the cover's key/value tables
CELL_SIZE = 7  # font size of table cells
CELL_PADDING = 13  # a cell's left and right padding (6 each) and a point against rounding
MIN_COLUMN = 28  # the narrowest text a column holds
MAX_WORD = WIDTH / 4  # a longer word gets no column of its own width: it is broken
BREAKABLE = re.compile(r"[^\S\xa0]+")  # where a line may break: any whitespace but U+00A0
H2_SIZE, H2_BEFORE, H2_AFTER = 10.5, 14, 5  # a chart's heading
ACCENT = colors.HexColor("#3B6EA5")
HEADER_FILL = colors.HexColor("#EDF1F6")
GRID = colors.HexColor("#C8CED6")
MUTED = colors.HexColor("#666666")
FAINT = colors.HexColor("#888888")

# How the charts of decisions are shown; every other chart follows the generic rules.
DECISION_FORMS = {
    "budget_curve": "line",
    "actions_by_segment": "pivot",
    "action_effects": "table",
    "planned_members": "table",
    "criterion_weights": "bars",
    "title_ranking": "table",
    "inconsistent_judgements": "table",
}
OMIT_WHEN_EMPTY = {"inconsistent_judgements"}

# A decision's parameters (`reports.params`) in the order the cover lists them.
PARAM_LABELS = {
    "run_id": "Модель (запуск №)",
    "budget": "Бюджет",
    "horizon_months": "Горизонт, місяців",
    "email_cost": "Вартість листа",
    "max_emails": "Найбільше листів",
    "max_discounts": "Найбільше знижок",
    "cautious": "Обережний режим",
    "by_segment": "Ефекти за сегментами",
    "assumed": "Припущені ефекти",
    "discount_pct": "Знижка",
    "max_per_genre": "Найбільше назв одного жанру",
    "judgements": "Порівняння критеріїв",
}
PARAM_UNITS = {
    "budget": "UAH",
    "email_cost": "UAH",
    "discount_pct": "ratio",
    "horizon_months": "count",
    "max_emails": "count",
    "max_discounts": "count",
    "max_per_genre": "count",
}
NONE_TEXT = {  # what an empty parameter means
    "max_emails": "без обмеження",
    "max_discounts": "без обмеження",
    "max_per_genre": "без обмеження",
    "assumed": "ні, ефекти кампанії",
}
JUDGEMENTS_NOTE = (
    "×n: перший критерій пари важливіший за другий у n разів, ×1/n — навпаки. "
    "Пари, яких немає в списку, однаково важливі."
)


@cache
def _register_fonts() -> None:
    pdfmetrics.registerFont(TTFont(FONT, str(FONTS / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(BOLD, str(FONTS / "DejaVuSans-Bold.ttf")))
    registerFontFamily(FONT, normal=FONT, bold=BOLD, italic=FONT, boldItalic=BOLD)


def _style(name: str, size: float, *, bold: bool = False, **extra: Any) -> ParagraphStyle:
    return ParagraphStyle(
        name, fontName=BOLD if bold else FONT, fontSize=size, leading=size * 1.25, **extra
    )


KIND = _style("kind", 10, bold=True, textColor=ACCENT, spaceAfter=6)
TITLE = _style("title", 22, bold=True, spaceAfter=18)
COVER_HEADING = _style("cover-heading", 11, bold=True, spaceBefore=20, spaceAfter=7)
CONTENTS = _style("contents", 9.5, spaceAfter=3)
KEY = _style("key", 8.5, bold=True)
VALUE = _style("value", 8.5)
H1 = _style("h1", 16, bold=True, spaceAfter=8, textColor=ACCENT, keepWithNext=1)
H2 = _style("h2", H2_SIZE, bold=True, spaceBefore=H2_BEFORE, spaceAfter=H2_AFTER, keepWithNext=1)
TABLE_HEADING = _style("table-heading", H2_SIZE, bold=True)  # H2 as the first row of a table
NOTE = _style("note", 7.5, textColor=MUTED, spaceAfter=3)
CAPTION = _style("caption", 7.5, textColor=MUTED)
CELL = _style("cell", CELL_SIZE)
CELL_NUMBER = _style("cell-number", CELL_SIZE, alignment=TA_RIGHT)
CELL_HEADER = _style("cell-header", CELL_SIZE, bold=True)


class _NumberedCanvas(Canvas):
    """Holds every page back until the document ends and the page count is known, then draws
    each page's footer: the report's title and "N з M"."""

    def __init__(self, *args: Any, footer: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._footer = footer
        self._pages: list[dict[str, Any]] = []

    @override
    def showPage(self) -> None:
        self._pages.append(dict(self.__dict__))
        self._startPage()  # pyright: ignore[reportAttributeAccessIssue]  (private, not in the stubs)

    @override
    def save(self) -> None:
        total = len(self._pages)
        for page_number, page in enumerate(self._pages, start=1):
            self.__dict__.update(page)
            self._draw_footer(f"{page_number} з {total}")
            super().showPage()
        super().save()

    def _draw_footer(self, page_text: str) -> None:
        self.saveState()
        self.setStrokeColor(GRID)
        self.setLineWidth(0.4)
        self.line(MARGIN, BOTTOM - 5 * mm, PAGE[0] - MARGIN, BOTTOM - 5 * mm)
        self.setFont(FONT, 7)
        self.setFillColor(FAINT)
        self.drawString(MARGIN, FOOTER_Y, self._footer)
        self.drawRightString(PAGE[0] - MARGIN, FOOTER_Y, page_text)
        self.restoreState()


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text), style)


def _shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


def _text_width(text: str, font: str) -> float:
    return pdfmetrics.stringWidth(text, font, CELL_SIZE)


def _words(text: str) -> list[str]:
    return BREAKABLE.split(text)


def column_widths(header: list[str], body: list[list[str]], numeric: set[int]) -> list[float]:
    """Each column as wide as its longest cell when the table fits the page. Otherwise every
    column keeps its narrowest width (its longest value for numbers, its longest word, at most
    MAX_WORD, for texts) and the columns that would wrap share the room left. When even that
    does not fit, the columns shrink toward MIN_COLUMN, so numbers may wrap too; with more
    columns than fit at that width, all get the same."""
    _register_fonts()  # the widths are measured in the report's fonts
    narrowest: list[float] = []
    widest: list[float] = []
    for i, title in enumerate(header):
        cells = [row[i] for row in body]
        whole = max((_text_width(cell, FONT) for cell in cells), default=0)
        word = max((_text_width(w, FONT) for cell in cells for w in _words(cell)), default=0)
        head_word = max((_text_width(w, BOLD) for w in _words(title)), default=0)
        low = min(max(head_word, whole if i in numeric else word), MAX_WORD)
        narrowest.append(max(low, MIN_COLUMN) + CELL_PADDING)
        widest.append(max(_text_width(title, BOLD), whole, low, MIN_COLUMN) + CELL_PADDING)
    if sum(widest) <= WIDTH:
        return widest
    if sum(narrowest) <= WIDTH:
        share = (WIDTH - sum(narrowest)) / (sum(widest) - sum(narrowest))
        return [lo + (hi - lo) * share for lo, hi in zip(narrowest, widest, strict=True)]
    floor, count = MIN_COLUMN + CELL_PADDING, len(header)
    if floor * count >= WIDTH:
        return [WIDTH / count] * count
    above = [w - floor for w in narrowest]
    return [floor + a * (WIDTH - floor * count) / sum(above) for a in above]


def _head(table: Any) -> int:
    """The rows above a table's body: through the header row, or those a split repeats."""
    repeated = table.repeatRows
    return repeated if isinstance(repeated, int) else max(repeated) + 1


class _Table(Table):
    """A table that splits across pages only where at least MIN_SPLIT_ROWS of its rows go on
    each side, so it never splits when it has at most twice as many. When fewer would stay on
    this page, it moves to the next one whole; when fewer would go, it splits earlier. At the
    top of a page, where moving gains nothing, it splits as it can."""

    @override
    def split(self, availWidth: float, availHeight: float) -> list[Any]:
        parts: list[Any] = super().split(availWidth, availHeight)
        if len(parts) < 2:
            return parts
        stays, goes = (len(part._cellvalues) - _head(part) for part in parts)
        frame = getattr(self, "_frame", None)  # set by the frame that asks for the split
        top = frame is None or frame._atTop
        if not top and (stays < MIN_SPLIT_ROWS or stays + goes <= 2 * MIN_SPLIT_ROWS):
            return []
        if goes < MIN_SPLIT_ROWS <= stays + goes - MIN_SPLIT_ROWS:
            table: Any = self  # its row heights are private, not in the stubs
            keep = len(table._rowHeights) - MIN_SPLIT_ROWS
            return super().split(availWidth, sum(table._rowHeights[:keep]) + 0.01)
        return parts


def data_table(
    header: list[str],
    body: list[list[str]],
    numeric: set[int],
    caption: str | None = None,
    heading: str | None = None,
) -> Table:
    """A table: a header row and the body, and above them a heading and a caption as rows of
    the table, so they always stay with its first rows. When the table splits, the caption and
    the header come again on the next page, the heading does not."""
    above = [
        [_p(text, style), *(_p("", CELL) for _ in header[1:])]
        for text, style in ((heading, TABLE_HEADING), (caption, CAPTION))
        if text
    ]
    cells = [*above, [_p(h, CELL_HEADER) for h in header]]
    cells += [
        [_p(v, CELL_NUMBER if i in numeric else CELL) for i, v in enumerate(row)] for row in body
    ]
    head = len(above)  # the header row
    commands: list[tuple[Any, ...]] = [
        ("GRID", (0, head), (-1, -1), 0.3, GRID),
        ("BACKGROUND", (0, head), (-1, head), HEADER_FILL),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, head), (-1, -1), 2),
        ("BOTTOMPADDING", (0, head), (-1, -1), 2),
    ]
    for row in range(head):
        commands += [
            ("SPAN", (0, row), (-1, row)),
            ("LEFTPADDING", (0, row), (-1, row), 0),
            ("TOPPADDING", (0, row), (-1, row), 0),
            ("BOTTOMPADDING", (0, row), (-1, row), 4),
        ]
    widths = column_widths(header, body, numeric)
    if heading:
        commands.append(("BOTTOMPADDING", (0, 0), (-1, 0), H2_AFTER))
        wanted = min(pdfmetrics.stringWidth(heading, BOLD, H2_SIZE) + 1, WIDTH)  # on one line
        if sum(widths) < wanted:
            widths = [w * wanted / sum(widths) for w in widths]
    table = _Table(
        cells,
        colWidths=widths,
        repeatRows=tuple(range(1 if heading else 0, head + 1)),
        hAlign="LEFT",
        spaceBefore=H2_BEFORE if heading else 0,
    )
    table.setStyle(TableStyle(commands))
    return table


def _pairs(rows: list[tuple[str, list[str]]]) -> Table:
    """A key/value table without a header; a key with several values spans their rows."""
    cells: list[list[Paragraph]] = []
    commands: list[tuple[Any, ...]] = [
        ("GRID", (0, 0), (-1, -1), 0.3, GRID),
        ("BACKGROUND", (0, 0), (0, -1), HEADER_FILL),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    for key, lines in rows:
        first = len(cells)
        cells += [[_p(key if i == 0 else "", KEY), _p(line, VALUE)] for i, line in enumerate(lines)]
        if len(lines) > 1:
            commands.append(("SPAN", (0, first), (0, len(cells) - 1)))
    table = Table(cells, colWidths=[KEY_WIDTH, VALUE_WIDTH], hAlign="LEFT")
    table.setStyle(TableStyle(commands))
    return table


def _times(value: float) -> str:
    """A judgement as how many times the first criterion outweighs the second: ×3, or ×1/3."""
    ratio = round(value if value >= 1 else 1 / value, 1)
    text = number(ratio, decimals_for(ratio))
    return f"×{text}" if value >= 1 else f"×1/{text}"


def _judgements(judgements: list[dict[str, Any]]) -> list[str]:
    """The judgement that counts for each pair of criteria: the last one given, as the decision
    weighed them; pairs never compared count as equal."""
    last: dict[frozenset[str], dict[str, Any]] = {}
    for j in judgements:
        last[frozenset((j["criterion"], j["compared_with"]))] = j
    return [
        f"{label('content_criterion', j['criterion'])} проти "
        f"{label('content_criterion', j['compared_with'])}: {_times(j['value'])}"
        for j in last.values()
    ]


def _param_lines(key: str, value: Any) -> list[str]:
    """One line per value: a key with several gets a row for each."""
    if value is None:
        return [NONE_TEXT.get(key, EMPTY)]
    if isinstance(value, bool):
        return ["так" if value else "ні"]
    if key in PARAM_UNITS and isinstance(value, int | float):
        return [value_text(value, PARAM_UNITS[key])]
    if key == "assumed" and isinstance(value, dict):
        lines = [f"{label('retention_action', a)}: {percent(v)}" for a, v in value.items()]
        return lines or [EMPTY]
    if key == "judgements" and isinstance(value, list):
        return _judgements(value) or ["усі критерії однаково важливі"]
    return [str(value)]


def _params(params: dict[str, Any]) -> list[tuple[str, list[str]]]:
    """The known parameters in their order (JSONB keeps no key order), then any others as
    they are, so a new parameter never breaks the export."""
    keys = [k for k in PARAM_LABELS if k in params] + sorted(set(params) - set(PARAM_LABELS))
    return [(PARAM_LABELS.get(k, k), _param_lines(k, params[k])) for k in keys]


def _cover(document: ReportDocument) -> list[Flowable]:
    details = [
        ("Датасет", [document.dataset_name]),
        ("Дата зрізу", [document.as_of or EMPTY]),
        ("Часовий пояс", [document.timezone]),
        ("Створено", [created_text(document.created_at)]),
    ]
    parts: list[Flowable] = [
        _p(label("report_kind", document.kind), KIND),
        _p(document.title, TITLE),
        _pairs(details),
        _p("Зміст", COVER_HEADING),
    ]
    parts += [
        _p(f"{i}. {label('analytics_section', section['key'])}", CONTENTS)
        for i, section in enumerate(document.sections, start=1)
    ]
    if document.params:
        parts += [_p("Параметри рішення", COVER_HEADING), _pairs(_params(document.params))]
        if document.params.get("judgements"):
            parts += [Spacer(1, 4), _p(JUDGEMENTS_NOTE, NOTE)]
    return parts


def _kpis(kpis: list[dict[str, Any]]) -> Table:
    body = [
        [
            label("metric", k["key"]),
            value_text(k["value"], k["unit"]),
            window_text(k["window_days"]),
        ]
        for k in kpis
    ]
    return data_table(["Показник", "Значення", "Період"], body, {1})


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
    names = [cell_text(dim, r.get(dim.key)) if i % step == 0 else "" for i, r in enumerate(rows)]
    values = [r.get(measure.key) or 0 for r in rows]
    drawing = Drawing(WIDTH, 150)
    drawing.hAlign = "LEFT"
    line: Any = HorizontalLineChart()  # reportlab is untyped
    line.x, line.y, line.width, line.height = 60, 40, WIDTH - 90, 100
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


def _pivot(chart: dict[str, Any], cols: list[Column], heading: str) -> Table | None:
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
    numeric = set(range(1, len(header)))
    return data_table(header, body, numeric, f"Значення: {measure.title}", heading)


def _long(chart: dict[str, Any], cols: list[Column], heading: str | None = None) -> Table:
    rows = chart["rows"]
    time_series = chart["dimensions"] and chart["dimensions"][0]["kind"] == "time"
    shown = rows[-MAX_TIME_ROWS:] if time_series else rows[:MAX_ROWS]
    body = [[cell_text(c, r.get(c.key)) for c in cols] for r in shown]
    numeric = {i for i, c in enumerate(cols) if c.unit}
    header = [c.title for c in cols]
    if len(shown) == len(rows):
        return data_table(header, body, numeric, heading=heading)
    which = "останні" if time_series else "перші"
    cut = f"Показано {which} {len(shown)} з {len(rows)} рядків; усі рядки є в XLSX і CSV."
    return data_table(header, body, numeric, cut, heading)


def form_of(chart: dict[str, Any]) -> str:
    """How a chart is shown: "line" or "bars" above its table, "pivot" (a pivot table) or a
    "table" alone. A decision chart has a form of its own (DESIGN.md §2.10)."""
    dims, rows = chart["dimensions"], chart["rows"]
    if (form := DECISION_FORMS.get(chart["key"])) is not None:
        return "table" if form == "line" and len(rows) <= 2 else form
    if len(dims) == 2:
        return "pivot"
    if len(dims) == 1 and dims[0]["kind"] == "time" and len(rows) > 2:
        return "line"
    if len(dims) == 1 and len(rows) <= MAX_BARS:
        return "bars"
    return "table"


def _chart(chart: dict[str, Any]) -> list[Flowable]:
    """A drawing is kept with the heading above it; a table that comes first carries its
    heading as its own first row."""
    title = chart_title(chart)
    if not chart["rows"]:
        if chart["key"] in OMIT_WHEN_EMPTY:
            return []
        return [KeepTogether([_p(title, H2), _p("Немає даних.", NOTE)])]
    cols = columns(chart)
    match form_of(chart):
        case "line":
            return [KeepTogether([_p(title, H2), _line(chart, cols)]), _long(chart, cols)]
        case "bars":
            return [KeepTogether([_p(title, H2), _bars(chart, cols)]), _long(chart, cols)]
        case "pivot":  # too large for a pivot table: the long table
            return [_pivot(chart, cols, title) or _long(chart, cols, title)]
        case _:
            return [_long(chart, cols, title)]


def _section(section: dict[str, Any]) -> list[Flowable]:
    parts: list[Flowable] = [PageBreak(), _p(label("analytics_section", section["key"]), H1)]
    parts += [_p(note["message_uk"], NOTE) for note in section["notes"]]
    if section["kpis"]:
        parts += [_kpis(section["kpis"]), Spacer(1, 4)]
    for chart in section["charts"]:
        parts += _chart(chart)
    return parts


def render_pdf(document: ReportDocument) -> bytes:
    _register_fonts()
    buffer = io.BytesIO()
    doc = BaseDocTemplate(
        buffer,
        pagesize=PAGE,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=BOTTOM,
        title=document.title,
        author="library-dss",
        creator="library-dss",
        lang="uk",
        invariant=True,  # no timestamps or random ids: the same report gives the same bytes
    )
    # Without the frame's default padding, the content lines up with the footer.
    body = Frame(
        MARGIN,
        BOTTOM,
        WIDTH,
        HEIGHT,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
        id="body",
    )
    doc.addPageTemplates([PageTemplate(id="page", frames=[body])])
    story = _cover(document)
    for section in document.sections:
        story += _section(section)
    footer = _shorten(document.title, FOOTER_TITLE)
    doc.build(story, canvasmaker=partial(_NumberedCanvas, footer=footer))
    return buffer.getvalue()
