"""The experiment grid and its parameters, read from a TOML file (`config.toml`)."""

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT = Path(__file__).parent / "config.toml"


@dataclass(frozen=True)
class RetentionConfig:
    budget_shares: tuple[float, ...]  # of the cost of a discount for every member at risk
    horizon_months: int
    email_cost: float  # UAH
    assumed: dict[str, float]  # "DSS with assumptions": differences of churn rates per action


@dataclass(frozen=True)
class Config:
    seeds: int  # seeds 1, 2, …, seeds of every preset
    presets: tuple[str, ...]
    members: int
    months: int
    retention: RetentionConfig

    def cases(self) -> list[tuple[str, int]]:
        return [(preset, seed) for preset in self.presets for seed in range(1, self.seeds + 1)]


def load(path: Path = DEFAULT) -> Config:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    retention = data["retention"]
    return Config(
        seeds=data["seeds"],
        presets=tuple(data["presets"]),
        members=data["members"],
        months=data["months"],
        retention=RetentionConfig(
            budget_shares=tuple(retention["budget_shares"]),
            horizon_months=retention["horizon_months"],
            email_cost=retention["email_cost"],
            assumed=dict(retention["assumed"]),
        ),
    )
