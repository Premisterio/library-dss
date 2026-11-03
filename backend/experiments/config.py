"""The experiment grid and its parameters, read from a TOML file (`config.toml`)."""

import tomllib
from dataclasses import dataclass
from pathlib import Path

from libsim.params import CampaignParams

DEFAULT = Path(__file__).parent / "config.toml"
CAMPAIGN_MONTHS = CampaignParams().months  # every library but the campaign-size experiment's


@dataclass(frozen=True)
class RetentionConfig:
    budget_shares: tuple[float, ...]  # of the cost of a discount for every member at risk
    horizon_months: int
    email_cost: float  # UAH
    assumed: dict[str, float]  # "DSS with assumptions": differences of churn rates per action


@dataclass(frozen=True)
class ContentConfig:
    budget_shares: tuple[float, ...]  # of the licence cost of the whole offer
    max_per_genre: int  # the DSS portfolios' cap per genre


@dataclass(frozen=True)
class CampaignConfig:
    preset: str
    months: tuple[int, ...]  # campaign lengths to compare
    budget_share: float  # the retention budget they are compared at


@dataclass(frozen=True)
class Config:
    seeds: int  # seeds 1, 2, …, seeds of every preset
    presets: tuple[str, ...]
    members: int
    months: int
    horizon_days: int  # simulated past as_of: the window of the titles' true demand
    retention: RetentionConfig
    content: ContentConfig
    campaign: CampaignConfig

    def cases(self) -> list[tuple[str, int, int]]:
        """(preset, seed, campaign months): every preset with libsim's campaign, then the
        campaign-size experiment's other lengths."""
        seeds = range(1, self.seeds + 1)
        grid = [(preset, seed, CAMPAIGN_MONTHS) for preset in self.presets for seed in seeds]
        sizes = [(self.campaign.preset, seed, m) for m in self.campaign.months for seed in seeds]
        return grid + [case for case in sizes if case not in grid]


def load(path: Path = DEFAULT) -> Config:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    retention, content, campaign = data["retention"], data["content"], data["campaign"]
    return Config(
        seeds=data["seeds"],
        presets=tuple(data["presets"]),
        members=data["members"],
        months=data["months"],
        horizon_days=data["horizon_days"],
        retention=RetentionConfig(
            budget_shares=tuple(retention["budget_shares"]),
            horizon_months=retention["horizon_months"],
            email_cost=retention["email_cost"],
            assumed=dict(retention["assumed"]),
        ),
        content=ContentConfig(
            budget_shares=tuple(content["budget_shares"]),
            max_per_genre=content["max_per_genre"],
        ),
        campaign=CampaignConfig(
            preset=campaign["preset"],
            months=tuple(campaign["months"]),
            budget_share=campaign["budget_share"],
        ),
    )
