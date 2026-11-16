"""Immutable input records and validated experiment configuration."""
from dataclasses import dataclass, asdict
from datetime import date
import math


@dataclass(frozen=True)
class Bar:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass(frozen=True)
class Config:
    fast: int = 20
    slow: int = 60
    initial_cash: float = 100_000.0
    allocation: float = 0.95
    spread_bps: float = 4.0  # Full spread; half is paid per fill.
    slippage_bps: float = 2.0
    impact_bps: float = 20.0  # At 100% participation in reference volume.
    commission_per_share: float = 0.005
    minimum_commission: float = 1.0
    participation: float = 0.01
    annualization: int = 252
    train_fraction: float = 0.65

    def __post_init__(self):
        for name, value in asdict(self).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number")
        for name in ("fast", "slow", "annualization"):
            if type(getattr(self, name)) is not int:
                raise ValueError(f"{name} must be an integer")
        if not 1 <= self.fast < self.slow:
            raise ValueError("Require 1 <= fast < slow")
        if not 0 < self.initial_cash <= 1e12:
            raise ValueError("initial_cash must be in (0, 1e12]")
        if not 0 < self.allocation <= 1 or not 0 < self.participation <= 1:
            raise ValueError("allocation and participation must be in (0, 1]")
        if not 0.2 <= self.train_fraction <= 0.8:
            raise ValueError("train_fraction must be in [0.2, 0.8]")
        if self.annualization < 1:
            raise ValueError("annualization must be positive")
        for name in ("spread_bps", "slippage_bps", "impact_bps", "commission_per_share", "minimum_commission"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be nonnegative")
        if self.spread_bps / 2 + self.slippage_bps + self.impact_bps >= 10_000:
            raise ValueError("Combined one-way price adjustment must be less than 10000 bps")
