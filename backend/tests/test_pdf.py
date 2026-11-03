"""The structured PDF report on hand-made documents, without a database: the cover, a page per
section, the footer, a decision's parameters and the forms of decision charts; and what the XLSX
and JSON exports of the same documents add."""

import io
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import openpyxl
import orjson
import pytest
from pypdf import PdfReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Frame, Spacer

from app.domain.analytics.model import Chart, Dimension, Kpi, Measure, Note, Section, Unit
from app.domain.content.decision import COMPARED, CRITERIA, CRITERION
from app.domain.enums import ENUMS
from app.domain.retention.report import ACTION, EFFECT_SEGMENT, SEGMENT
from app.exports import ExportFormat, ReportDocument, render
from app.exports.pdf import (
    CELL_PADDING,
    MIN_COLUMN,
    WIDTH,
    column_widths,
    data_table,
    form_of,
    render_pdf,
)
from app.exports.tables import render_json
from app.exports.xlsx import render_xlsx
from app.models import Report
from app.services import reports

TITLE = "Перевірка звіту"
CREATED = datetime(2026, 11, 2, 14, 19, tzinfo=timezone(timedelta(hours=1)))  # 13:19 UTC
SECTION = ENUMS["analytics_section"]
CHART = ENUMS["chart"]
FORMATS: tuple[ExportFormat, ...] = ("pdf", "xlsx", "csv", "json")

USAGE = Section(
    "usage",
    kpis=[Kpi("sessions", 1234, "count", 30)],
    charts=[
        Chart(
            "devices",
            (Dimension("device", "category"),),
            (Measure("sessions", "count"), Measure("share", "ratio")),
            [
                {"device": "Android", "sessions": 800, "share": 0.65},
                {"device": "iPhone", "sessions": 434, "share": 0.35},
            ],
        )
    ],
)
COHORTS = Section(
    "cohorts",
    kpis=[],
    charts=[
        Chart(
            "activity_retention",
            (Dimension("cohort", "time"), Dimension("month_offset", "number")),
            (Measure("members", "count"), Measure("retention", "ratio")),
            [
                {"cohort": cohort, "month_offset": offset, "members": 10, "retention": 0.5}
                for cohort in ("2026-07-01", "2026-08-01")
                for offset in (0, 1)
            ],
        )
    ],
)
PLAN = Section(
    "retention_plan",
    kpis=[Kpi("plan_value", 1900.0, "UAH")],
    charts=[
        Chart(
            "budget_curve",
            (Dimension("budget", "number"),),
            (Measure("plan_value", "UAH"),),
            [
                {"budget": budget, "plan_value": value}
                for budget, value in [
                    (0.0, 0.0),
                    (1500.0, 900.0),
                    (3000.0, 1500.0),
                    (4500.0, 1800.0),
                    (6000.0, 1900.0),
                ]
            ],
        ),
        Chart(
            "actions_by_segment",
            (SEGMENT, ACTION),
            (Measure("members", "count"),),
            [
                {"segment": "dormant", "action": "email", "members": 12},
                {"segment": "steady", "action": "discount", "members": 3},
            ],
        ),
        Chart(
            "action_effects",
            (ACTION, EFFECT_SEGMENT),
            (Measure("effect_shrunk", "ratio"), Measure("effect", "ratio")),
            [{"action": "email", "segment": "all", "effect_shrunk": -0.02, "effect": -0.021}],
        ),
        Chart(
            "planned_members",
            (Dimension("user_id", "category"),),
            (Measure("p_none", "ratio"), Measure("gain", "UAH")),
            [
                {
                    "user_id": "u001",
                    "action": "email",
                    "segment": "dormant",
                    "p_none": 0.3,
                    "gain": 90.0,
                }
            ],
            attributes=(ACTION, SEGMENT),
        ),
    ],
    notes=[Note("retention.noisy_effects", "Ефекти оцінено на учасниках минулої кампанії.")],
)
PORTFOLIO = Section(
    "content_portfolio",
    kpis=[Kpi("consistency_ratio", 0.04, "ratio")],
    charts=[
        Chart(
            "criterion_weights",
            (CRITERION,),
            (Measure("weight", "ratio"),),
            [{"criterion": criterion, "weight": 0.25} for criterion in CRITERIA],
        ),
        Chart(
            "title_ranking",
            (Dimension("title", "category"),),
            (Measure("rank_topsis", "count"), Measure("topsis", "ratio")),
            [
                {"title": "Тигролови", "rank_topsis": 1, "topsis": 0.7},
                {"title": "Intermezzo", "rank_topsis": 2, "topsis": 0.5},
            ],
        ),
        Chart(
            "inconsistent_judgements",
            (CRITERION, COMPARED),
            (Measure("judgement_given", "count"), Measure("judgement_consistent", "count")),
            [],
        ),
    ],
)
# In the order PostgreSQL's JSONB gives the keys back, not the order the cover lists them.
RETENTION_PARAMS = {
    "budget": 5000.0,
    "run_id": 7,
    "assumed": {"email": -0.02, "discount": -0.05},
    "cautious": True,
    "by_segment": False,
    "email_cost": 2.0,
    "max_emails": 1000,
    "discount_pct": 0.15,
    "max_discounts": None,
    "horizon_months": 12,
}
CONTENT_PARAMS = {
    "budget": 20000.0,
    "judgements": [
        {"criterion": "demand_searches", "compared_with": "genre_loans", "value": 3.0},
        {"criterion": "author_loans", "compared_with": "genre_holds_per_copy", "value": 1 / 3},
    ],
    "max_per_genre": 3,
}


def stored(section: Section) -> dict[str, Any]:
    """A section as a report keeps it (JSON)."""
    return orjson.loads(orjson.dumps(section.to_dict()))


def document(*sections: Section, **fields: Any) -> ReportDocument:
    defaults: dict[str, Any] = {
        "title": TITLE,
        "dataset_name": "Демо-бібліотека",
        "as_of": "2026-09-30",
        "timezone": "Europe/Kyiv",
        "created_at": CREATED,
    }
    return ReportDocument(sections=[stored(s) for s in sections], **(defaults | fields))


def pages(pdf: bytes) -> list[list[str]]:
    """The lines of text of each page, with no-break spaces as plain ones."""
    return [
        [line.replace("\xa0", " ").strip() for line in page.extract_text().splitlines()]
        for page in PdfReader(io.BytesIO(pdf)).pages
    ]


def after(lines: list[str], key: str, count: int = 1) -> list[str]:
    """The lines after `key`: its value in a key/value table."""
    at = lines.index(key)
    return lines[at + 1 : at + 1 + count]


def summary_value(xlsx: bytes, key: str) -> Any:
    sheet = openpyxl.load_workbook(io.BytesIO(xlsx))["Звіт"]
    return next(row[1] for row in sheet.iter_rows(values_only=True) if row[0] == key)


def test_the_same_report_gives_the_same_bytes() -> None:
    for same in (
        document(USAGE, COHORTS),
        document(PLAN, kind="retention", params=RETENTION_PARAMS),
        document(PORTFOLIO, kind="content", params=CONTENT_PARAMS),
    ):
        assert render_pdf(same) == render_pdf(same)


def test_a_cover_then_each_section_from_a_new_page() -> None:
    """Regression: sections ran on from one another, several to a page, after a title line."""
    cover, usage, cohorts = pages(render_pdf(document(USAGE, COHORTS)))
    text = "\n".join(cover)
    for shown in (TITLE, "Аналітика", "Зміст", "1. Використання", "2. Когорти"):
        assert shown in cover, shown
    assert after(cover, "Датасет") == ["Демо-бібліотека"]
    assert after(cover, "Дата зрізу") == ["2026-09-30"]
    assert after(cover, "Часовий пояс") == ["Europe/Kyiv"]
    assert "Пристрої" not in text  # no chart on the cover
    assert SECTION["usage"] in usage
    assert SECTION["cohorts"] not in usage
    assert SECTION["cohorts"] in cohorts
    assert SECTION["usage"] not in cohorts


def test_every_page_has_the_title_and_its_number_in_the_footer() -> None:
    texts = pages(render_pdf(document(USAGE, COHORTS)))
    assert len(texts) == 3
    for number, lines in enumerate(texts, start=1):
        assert f"{number} з 3" in lines
        assert TITLE in lines


def test_a_retention_decision_lists_its_parameters() -> None:
    cover = pages(render_pdf(document(PLAN, kind="retention", params=RETENTION_PARAMS)))[0]
    assert cover[0] == "План утримання"
    assert "Параметри рішення" in cover
    assert after(cover, "Модель (запуск №)") == ["7"]
    assert after(cover, "Бюджет") == ["5 000,00 грн"]
    assert after(cover, "Горизонт, місяців") == ["12"]
    assert after(cover, "Вартість листа") == ["2,00 грн"]
    assert after(cover, "Найбільше листів") == ["1 000"]
    assert after(cover, "Найбільше знижок") == ["без обмеження"]
    assert after(cover, "Обережний режим") == ["так"]
    assert after(cover, "Ефекти за сегментами") == ["ні"]
    assert after(cover, "Припущені ефекти", 2) == ["E-mail: -2,0 %", "Знижка: -5,0 %"]
    assert after(cover, "Знижка") == ["15,0 %"]
    # The cover's order, whatever order the stored parameters come in.
    assert cover.index("Модель (запуск №)") < cover.index("Бюджет") < cover.index("Знижка")


def test_a_content_decision_lists_its_judgements() -> None:
    cover = pages(render_pdf(document(PORTFOLIO, kind="content", params=CONTENT_PARAMS)))[0]
    assert cover[0] == "Закупівля контенту"
    assert after(cover, "Бюджет") == ["20 000,00 грн"]
    assert after(cover, "Найбільше назв одного жанру") == ["3"]
    assert after(cover, "Порівняння критеріїв", 2) == [
        "Пошуки без результату проти Позичення в жанрі: ×3",
        "Позичення книг автора проти Бронювань на копію в жанрі: ×1/3",
    ]


def test_unknown_parameters_are_listed_as_they_are() -> None:
    params = {"budget": 100.0, "new_option": "x"}
    cover = pages(render_pdf(document(PLAN, kind="retention", params=params)))[0]
    assert after(cover, "new_option") == ["x"]


def test_a_dataset_without_an_as_of_date() -> None:
    """Regression: a report on a dataset without an as-of date printed "None" in the PDF and
    its XLSX export failed."""
    report = document(USAGE, as_of=None)
    texts = pages(render_pdf(report))
    assert after(texts[0], "Дата зрізу") == ["—"]
    assert not any("None" in line for lines in texts for line in lines)
    assert summary_value(render_xlsx(report), "Дата зрізу") == "—"
    assert orjson.loads(render_json(report))["as_of"] is None


def test_the_creation_time_is_in_utc() -> None:
    """Regression: the creation time was shown in the database session's time zone and
    labelled UTC."""
    report = document(USAGE)  # created at 14:19 +01:00
    assert after(pages(render_pdf(report))[0], "Створено") == ["2026-11-02 13:19 UTC"]
    xlsx = render_xlsx(report)
    assert summary_value(xlsx, "Створено") == "2026-11-02 13:19 UTC"
    created = openpyxl.load_workbook(io.BytesIO(xlsx)).properties.created
    assert created == datetime(2026, 11, 2, 13, 19)  # the workbook's own field, in UTC


def test_decision_charts_take_forms_that_fit_them() -> None:
    """Regression: the budget curve (a number dimension) was drawn as bars, one per budget;
    the ranking as bars of a rank; the effects as a pivot of one of their measures."""
    charts = {chart["key"]: chart for s in (PLAN, PORTFOLIO) for chart in stored(s)["charts"]}
    assert form_of(charts["budget_curve"]) == "line"
    assert form_of(charts["title_ranking"]) == "table"
    assert form_of(charts["action_effects"]) == "table"
    assert form_of(charts["planned_members"]) == "table"
    assert form_of(charts["actions_by_segment"]) == "pivot"
    assert form_of(charts["criterion_weights"]) == "bars"
    flat = charts["budget_curve"] | {"rows": charts["budget_curve"]["rows"][:2]}
    assert form_of(flat) == "table"  # two points make no curve
    # The analytics charts keep the generic rules.
    assert form_of(stored(USAGE)["charts"][0]) == "bars"
    assert form_of(stored(COHORTS)["charts"][0]) == "pivot"


def test_number_dimensions_are_formatted() -> None:
    """Regression: a number dimension showed as "3000.0"."""
    texts = pages(render_pdf(document(PLAN, kind="retention", params=RETENTION_PARAMS)))
    lines = [line for page in texts for line in page]
    assert CHART["budget_curve"] in lines
    assert "3 000" in lines
    assert not any("3000.0" in line for line in lines)


def test_empty_charts() -> None:
    """An analytics chart without rows says so; the inconsistent judgements, which an approved
    decision never has, leave no heading."""
    empty = Section(
        "usage",
        kpis=[],
        charts=[
            Chart(
                "devices", (Dimension("device", "category"),), (Measure("sessions", "count"),), []
            )
        ],
    )
    assert "Немає даних." in pages(render_pdf(document(empty)))[1]
    lines = pages(render_pdf(document(PORTFOLIO, kind="content", params=CONTENT_PARAMS)))[1]
    assert CHART["title_ranking"] in lines
    assert CHART["inconsistent_judgements"] not in lines
    assert "Немає даних." not in lines


def test_xlsx_and_json_name_the_kind() -> None:
    decision = document(PLAN, kind="retention", params=RETENTION_PARAMS)
    assert summary_value(render_xlsx(decision), "Вид звіту") == "План утримання"
    body = orjson.loads(render_json(decision))
    assert (body["kind"], body["params"]) == ("retention", RETENTION_PARAMS)


def ranking(titles: list[str]) -> Chart:
    """A content decision's title ranking with every column it has, a row per title."""
    measures: tuple[tuple[str, Unit], ...] = (
        ("rank_topsis", "count"),
        ("topsis", "ratio"),
        ("rank_saw", "count"),
        ("saw", "ratio"),
        ("stability", "ratio"),
        ("demand_searches", "count"),
        ("license_cost", "UAH"),
    )
    return Chart(
        "title_ranking",
        (Dimension("title", "category"),),
        tuple(Measure(key, unit) for key, unit in measures),
        [
            {
                "title": title,
                "authors": "Автор Один, Автор Два",
                "genre": "fantasy",
                "candidate_id": f"c{i:03}",
                "choice": "licensed",
                **{key: i + 1 if unit == "count" else 0.5 for key, unit in measures},
            }
            for i, title in enumerate(titles)
        ],
        attributes=(
            Dimension("authors", "category"),
            Dimension("genre", "category", enum="genre"),
            Dimension("candidate_id", "category"),
            Dimension("choice", "category", enum="content_choice"),
        ),
    )


def test_a_long_word_never_squeezes_the_columns() -> None:
    """Regression: one long word (a URL-like search query, a title without spaces) shrank every
    column below its padding, and the export failed."""
    word = "https://example.org/?" + "q" * 1000
    for header, body, numeric in (
        (["Запит", "Пошуки", "Читачі, що шукали"], [[word, "3", "2"]], {1, 2}),
        (
            ["Назва", *(f"Число {i}" for i in range(11))],
            [[word] + ["1 880,00 грн"] * 11],
            set(range(1, 12)),
        ),
    ):
        widths = column_widths(header, body, numeric)
        assert min(widths) >= MIN_COLUMN + CELL_PADDING
        assert sum(widths) <= WIDTH + 1e-6
    queries = Chart(
        "zero_result_queries",
        (Dimension("query", "category"),),
        (Measure("searches", "count"), Measure("searchers", "count")),
        [{"query": word, "searches": 3, "searchers": 2}],
        window_days=90,
    )
    for section in (
        Section("search", kpis=[], charts=[queries]),
        Section("content_portfolio", kpis=[], charts=[ranking([word, "Тигролови"])]),
    ):
        assert len(pages(render_pdf(document(section)))) >= 2


def test_judgements_list_the_one_that_counts_for_each_pair() -> None:
    """Regression: each judgement took a line of one table cell, so 47 of them (the API takes
    50) made the cover taller than a page and the export failed; the cover also listed the
    judgements that later ones replaced."""
    final = [
        ("demand_searches", "author_loans", 3.0),
        ("genre_loans", "demand_searches", 5.0),
        ("demand_searches", "genre_holds_per_copy", 1 / 3),
        ("author_loans", "genre_loans", 7.0),
        ("author_loans", "genre_holds_per_copy", 1.0),
        ("genre_loans", "genre_holds_per_copy", 1 / 9),
    ]
    replaced = [(a, b, 9.0) for a, b, _ in final] * 7 + [
        ("author_loans", "demand_searches", 2.0)
    ] * 2
    judgements = [{"criterion": a, "compared_with": b, "value": v} for a, b, v in replaced + final]
    assert len(judgements) == 50
    report = document(
        PORTFOLIO, kind="content", params={"budget": 1000.0, "judgements": judgements}
    )
    for fmt in FORMATS:
        render(report, fmt)
    cover = pages(render_pdf(report))[0]
    assert after(cover, "Порівняння критеріїв", 6) == [
        "Пошуки без результату проти Позичення книг автора: ×3",
        "Позичення в жанрі проти Пошуки без результату: ×5",
        "Пошуки без результату проти Бронювань на копію в жанрі: ×1/3",
        "Позичення книг автора проти Позичення в жанрі: ×7",
        "Позичення книг автора проти Бронювань на копію в жанрі: ×1",
        "Позичення в жанрі проти Бронювань на копію в жанрі: ×1/9",
    ]
    assert sum("проти" in line for line in cover) == 6


def test_a_table_starts_under_its_heading() -> None:
    """Regression: a chart's heading could end a page alone when its table moved on (an 8-row
    ranking with long titles left "Рейтинг кандидатів" by itself)."""
    words = " ".join(f"слово{i}" for i in range(60))
    section = Section(
        "content_portfolio",
        kpis=[Kpi("portfolio_titles", 8, "count")],
        charts=[ranking([f"Назва {i} {words}" for i in range(8)])],
    )
    texts = ["\n".join(lines) for lines in pages(render_pdf(document(section, kind="content")))]
    with_heading = [text for text in texts if CHART["title_ranking"] in text]
    assert len(with_heading) == 1  # not repeated where the table goes on
    assert "Назва 0" in with_heading[0]


def test_a_table_that_comes_first_starts_on_the_page_of_the_kpis() -> None:
    """Regression: a table that came first never split, so it left most of a page blank and
    moved to the next one whole."""
    queries = Chart(
        "top_queries",
        (Dimension("query", "category"),),
        (Measure("searches", "count"), Measure("searchers", "count")),
        [{"query": f"запит{i:02}", "searches": 100 - i, "searchers": 50} for i in range(30)],
        window_days=90,
    )
    kpis = [Kpi("searches", 1000 + i, "count") for i in range(15)]
    first = "\n".join(
        pages(render_pdf(document(Section("search", kpis=kpis, charts=[queries]))))[1]
    )
    assert CHART["top_queries"] in first
    assert sum(f"запит{i:02}" in first for i in range(30)) >= 5


def test_every_format_gives_the_same_bytes_in_any_session_zone() -> None:
    """Regression: the JSON and CSV exports carried the creation time in the database
    session's time zone, so the same report gave other bytes in another zone."""
    instant = datetime(2026, 11, 2, 13, 19, tzinfo=UTC)
    files = []
    for hours in (0, 1):
        report = Report(
            id=1,
            kind="analytics",
            title=TITLE,
            params=None,
            created_at=instant.astimezone(timezone(timedelta(hours=hours))),
            content={
                "dataset_name": "Демо-бібліотека",
                "as_of": "2026-09-30",
                "timezone": "Europe/Kyiv",
                "sections": [stored(USAGE)],
            },
        )
        files.append({fmt: render(reports.document(report), fmt) for fmt in FORMATS})
    assert files[0] == files[1]


def split_rows(rows: int, room: float, *, at_top: bool) -> list[int]:
    """The body rows of each part when a table of `rows` rows meets a page with room for `room`
    of its rows (its header included), at the top of the page or under something else."""
    table = data_table(["Назва", "Число"], [[f"рядок {i}", str(i)] for i in range(rows)], {1})
    row = table.wrap(WIDTH, 10_000)[1] / (rows + 1)  # every row is one line here
    above = 0.0 if at_top else 100.0
    frame = Frame(0, 0, WIDTH, above + room * row, 0, 0, 0, 0)
    canvas = Canvas(io.BytesIO())
    if above:
        frame.add(Spacer(1, above), canvas)
    return [round(part.wrap(WIDTH, 10_000)[1] / row) - 1 for part in frame.split(table, canvas)]


@pytest.mark.parametrize(
    ("rows", "room", "at_top", "parts"),
    [
        (20, 3.5, False, []),  # fewer than five would stay: the table moves on whole
        (20, 13.5, False, [12, 8]),
        (20, 18.5, False, [15, 5]),  # fewer than five would go: it splits earlier
        (10, 8.5, False, []),  # ten rows or fewer never split
        (8, 6.5, True, [5, 3]),  # taller than a page: at its top, it splits as it can
    ],
)
def test_tables_split_with_at_least_five_rows_on_each_side(
    rows: int, room: float, at_top: bool, parts: list[int]
) -> None:
    assert split_rows(rows, room, at_top=at_top) == parts


def test_campaign_effects_and_the_legend_only_with_judgements() -> None:
    campaign = RETENTION_PARAMS | {"assumed": None}
    cover = pages(render_pdf(document(PLAN, kind="retention", params=campaign)))[0]
    assert after(cover, "Припущені ефекти") == ["ні, ефекти кампанії"]
    assert not any(line.startswith("×n") for line in cover)
    equal = CONTENT_PARAMS | {"judgements": []}
    cover = pages(render_pdf(document(PORTFOLIO, kind="content", params=equal)))[0]
    assert after(cover, "Порівняння критеріїв") == ["усі критерії однаково важливі"]
    assert not any(line.startswith("×n") for line in cover)
    cover = pages(render_pdf(document(PORTFOLIO, kind="content", params=CONTENT_PARAMS)))[0]
    assert any(line.startswith("×n:") for line in cover)
