"""A retention plan as an analytics-shaped section: KPIs, tidy charts and notes (DESIGN.md §2.9),
so every client and every report export can show it."""

import polars as pl

from app.domain.analytics.common import records
from app.domain.analytics.model import Chart, Dimension, Kpi, Measure, Note, Section
from app.domain.retention.effects import ACTIONS, SEGMENTS, Effect
from app.domain.retention.plan import Plan, Scenario

ACTION = Dimension("action", "category", enum="retention_action", order=ACTIONS)
SEGMENT = Dimension("segment", "category", enum="retention_segment", order=SEGMENTS)
ALL = "all"  # the segment code of an action's overall effect, the one plans use by default
EFFECT_SEGMENT = Dimension("segment", "category", enum="retention_segment", order=(ALL, *SEGMENTS))
ASSUMED = Note(
    "retention.assumed_effects",
    "Ефекти дій задав аналітик, а не оцінено з кампанії.",
)
CAUTIOUS = Note(
    "retention.cautious",
    "Обережний режим: для кожного ефекту взято найменш сприятливу межу 95-відсоткового інтервалу.",
)
NOISY = Note(
    "retention.noisy_effects",
    "Ефекти оцінено на учасниках минулої кампанії, і їхні 95-відсоткові інтервали широкі "
    "(див. «Ефекти дій»). Справжній виграш може бути помітно меншим за очікуваний.",
)
NO_CAMPAIGN = Note(
    "retention.no_campaign",
    "У датасеті немає даних кампанії, тому ефекти дій невідомі; задайте їх як припущення.",
)


def plan_section(
    plan: Plan,
    curve: list[tuple[float, float]],
    members: pl.DataFrame,
    effects: list[Effect],
    scenario: Scenario,
) -> Section:
    chosen = plan.chosen.join(members.select("user_id", "segment"), on="user_id")
    counts = dict(chosen.group_by("action").len().iter_rows())
    mix = chosen.group_by("segment", "action").agg(members=pl.len()).sort("segment", "action")
    notes = []
    if scenario.assumed is not None:
        notes.append(ASSUMED)
    elif not any(e.difference is not None for e in effects):
        notes.append(NO_CAMPAIGN)
    else:
        notes.append(NOISY)
    if scenario.cautious and scenario.assumed is None:
        notes.append(CAUTIOUS)
    return Section(
        "retention_plan",
        kpis=[
            Kpi("members_at_risk", members.height, "count"),
            Kpi("planned_emails", counts.get("email", 0), "count"),
            Kpi("planned_discounts", counts.get("discount", 0), "count"),
            Kpi("plan_spend", plan.spend, "UAH"),
            Kpi("plan_value", plan.value, "UAH"),
            Kpi("greedy_value", plan.greedy_value, "UAH"),
            Kpi("expected_saved", plan.saved, "count"),
        ],
        charts=[
            Chart(
                "budget_curve",
                (Dimension("budget", "number"),),
                (Measure("plan_value", "UAH"),),
                records(pl.DataFrame(curve, schema=["budget", "plan_value"], orient="row")),
            ),
            Chart(
                "actions_by_segment",
                (SEGMENT, ACTION),
                (Measure("members", "count"),),
                records(mix),
            ),
            Chart(
                "action_effects",
                (ACTION, EFFECT_SEGMENT),
                (
                    Measure("effect_shrunk", "ratio"),
                    Measure("effect", "ratio"),
                    Measure("effect_low", "ratio"),
                    Measure("effect_high", "ratio"),
                    Measure("effect_cautious", "ratio"),
                    Measure("treated", "count"),
                    Measure("control", "count"),
                ),
                [
                    {
                        "action": e.action,
                        "segment": e.segment or ALL,
                        "effect_shrunk": e.shrunk,
                        "effect": e.difference,
                        "effect_low": e.low,
                        "effect_high": e.high,
                        "effect_cautious": e.cautious,
                        "treated": e.treated,
                        "control": e.control,
                    }
                    for e in effects
                ],
            ),
            Chart(
                "planned_members",
                (Dimension("user_id", "category"),),
                (
                    Measure("p_none", "ratio"),
                    Measure("p_action", "ratio"),
                    Measure("gain", "UAH"),
                    Measure("spend", "UAH"),
                ),
                records(
                    chosen.select(
                        "user_id", "action", "segment", "p_none", "p_action", "gain", "spend"
                    )
                ),
                attributes=(ACTION, SEGMENT),
            ),
        ],
        notes=notes,
    )
