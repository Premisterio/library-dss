"""Effects of retention actions: intervals and shrinkage by hand, participants of a hand-made
campaign, and the intervals against libsim's true effects (DESIGN.md §2.9)."""

from typing import Any

import orjson
import polars as pl
import pytest

from app.domain.retention.effects import Effect, Z, compare, estimate, participants, shrink
from app.ingest import reader
from app.ingest.frames import ParsedDataset


def people(churned: int, n: int, **columns: Any) -> pl.DataFrame:
    flags = pl.Series("churned", [i < churned for i in range(n)], dtype=pl.Boolean)
    return pl.DataFrame(flags).with_columns(
        **{key: pl.lit(value) for key, value in columns.items()}
    )


@pytest.mark.parametrize(
    ("treated", "control", "expected"),
    [
        # Newcombe (1998), Statistics in Medicine 17:873-890, table II, method 10
        ((56, 70), (48, 80), (0.2, 0.0524, 0.3339)),
        ((9, 10), (3, 10), (0.6, 0.1705, 0.8090)),
        ((6, 7), (2, 7), (0.5714, 0.0582, 0.8062)),
    ],
)
def test_newcombe_interval_by_hand(
    treated: tuple[int, int], control: tuple[int, int], expected: tuple[float, float, float]
) -> None:
    effect = compare("discount", None, people(*treated), people(*control))
    assert (effect.difference, effect.low, effect.high) == pytest.approx(expected, abs=5e-5)
    assert (effect.treated, effect.control) == (treated[1], control[1])


def test_no_one_to_compare() -> None:
    effect = compare("email", "dormant", people(0, 0), people(1, 5))
    assert (effect.difference, effect.low, effect.shrunk) == (None, None, None)


def effect(difference: float | None, se: float, segment: Any = None) -> Effect:
    low, high = (None, None) if difference is None else (difference - Z * se, difference + Z * se)
    return Effect("discount", segment, 50, 50, 5, 5, difference, low, high, difference, high)


def test_shrinkage_by_hand() -> None:
    overall = effect(-0.03, 0.01)
    # Segments that agree within their noise: no spread between them, so all take the overall.
    alike = shrink(overall, [effect(-0.03, 0.02, s) for s in ("dormant", "declining", "steady")])
    assert [e.shrunk for e in alike] == pytest.approx([-0.03] * 3)
    assert [e.cautious for e in alike] == pytest.approx([-0.03 + Z * 0.01] * 3)
    # Precise segments that clearly differ keep (almost) their own values.
    apart = shrink(overall, [effect(d, 0.001, "x") for d in (-0.1, 0.0, -0.03)])
    assert [e.shrunk for e in apart] == pytest.approx([-0.1, 0.0, -0.03], abs=1e-3)
    # A segment without data takes the overall effect.
    [empty] = shrink(overall, [effect(None, 0.0, "dormant")])
    assert (empty.difference, empty.shrunk) == (None, -0.03)


def test_email_is_compared_among_members_who_agreed() -> None:
    rows = pl.concat(
        [
            people(1, 10, arm="email", email_opt_in=True, segment="steady"),
            people(5, 10, arm="email", email_opt_in=False, segment="steady"),
            people(3, 10, arm="control", email_opt_in=True, segment="steady"),
            people(3, 10, arm="control", email_opt_in=False, segment="dormant"),
            people(2, 20, arm="discount", email_opt_in=False, segment="steady"),
        ]
    )
    found = {(e.action, e.segment): e for e in estimate(rows)}
    email = found["email", None]
    assert (email.treated, email.control, email.difference) == (10, 10, pytest.approx(-0.2))
    discount = found["discount", None]
    assert (discount.treated, discount.control) == (20, 20)
    assert discount.difference == pytest.approx(0.1 - 0.3)
    assert found["discount", "dormant"].treated == 0  # no discounts among dormant members


@pytest.fixture
def churn(churn_document: dict[str, Any]) -> ParsedDataset:
    return reader.parse(reader.decode(orjson.dumps(churn_document)))


def test_participants_by_hand(churn: ParsedDataset) -> None:
    """u4 got a discount (renewed), u5 was in the e-mail arm without consent (churned); neither
    read anything before the day of the assignment, so both are dormant."""
    assert participants(churn.frames, churn.timezone).rows() == [
        ("u4", "discount", True, "dormant", False),
        ("u5", "email", False, "dormant", True),
    ]


@pytest.mark.slow
def test_intervals_contain_the_true_effects(
    demo_simulation: tuple[ParsedDataset, dict[str, Any], pl.DataFrame],
) -> None:
    """Done criteria of M4b: the campaign's interval contains the true average effect."""
    parsed, truth, _ = demo_simulation
    found = participants(parsed.frames, parsed.timezone)
    effects = {e.action: e for e in estimate(found) if e.segment is None}
    consent = dict(found.select("user_id", "email_opt_in").iter_rows())
    for action, who in (("discount", consent), ("email", {u for u, c in consent.items() if c})):
        true = [
            row["p_true"][action] - row["p_true"]["none"]
            for row in truth["campaign"]
            if row["user_id"] in who
        ]
        estimated = effects[action]
        assert estimated.low is not None
        assert estimated.high is not None
        assert estimated.low <= sum(true) / len(true) <= estimated.high, action
