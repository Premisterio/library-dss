"""The structured PDF report on hand-made documents, without a database: the cover, a page per
section, the footer, a decision's parameters and the forms of decision charts; and what the XLSX
and JSON exports of the same documents add."""

import io
from datetime import datetime, timedelta, timezone
from typing import Any

import openpyxl
import orjson
from pypdf import PdfReader

from app.domain.analytics.model import Chart, Dimension, Kpi, Measure, Note, Section
from app.domain.content.decision import COMPARED, CRITERIA, CRITERION
from app.domain.enums import ENUMS
from app.domain.retention.report import ACTION, EFFECT_SEGMENT, SEGMENT
from app.exports import ReportDocument
from app.exports.pdf import form_of, render_pdf
from app.exports.tables import render_json
from app.exports.xlsx import render_xlsx

TITLE = "Перевірка звіту"
CREATED = datetime(2026, 11, 2, 14, 19, tzinfo=timezone(timedelta(hours=1)))  # 13:19 UTC
SECTION = ENUMS["analytics_section"]
CHART = ENUMS["chart"]

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
