"""Mathematical strategies and the extension registry used by the India lab."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


def _close(frame: pd.DataFrame) -> pd.Series:
    if "close" not in frame:
        raise ValueError("market frame must contain a 'close' column")
    return frame["close"].astype(float)


def _target(index: pd.Index, values: Any, max_weight: float) -> pd.Series:
    result = pd.Series(values, index=index, dtype=float)
    return result.replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(0.0, max_weight)


class MathematicalStrategy(ABC):
    """Interface for long-only, end-of-day target-weight strategies."""

    name = "base"

    def __init__(self, max_weight: float = 0.05) -> None:
        if not 0 < max_weight <= 1:
            raise ValueError("max_weight must be in the (0, 1] range")
        self.max_weight = float(max_weight)

    @abstractmethod
    def generate(self, frame: pd.DataFrame) -> pd.Series:
        """Return target weights indexed exactly like *frame*."""


class MovingAverageTrendStrategy(MathematicalStrategy):
    """Long-only trend strategy with inverse-volatility position scaling."""

    name = "moving_average_trend"

    def __init__(
        self,
        fast_window: int = 50,
        slow_window: int = 200,
        volatility_window: int = 20,
        target_volatility: float = 0.12,
        max_weight: float = 0.05,
    ) -> None:
        super().__init__(max_weight=max_weight)
        if not 1 < fast_window < slow_window:
            raise ValueError("windows must satisfy 1 < fast_window < slow_window")
        self.fast_window = int(fast_window)
        self.slow_window = int(slow_window)
        self.volatility_window = int(volatility_window)
        self.target_volatility = float(target_volatility)

    def generate(self, frame: pd.DataFrame) -> pd.Series:
        close = _close(frame)
        fast = close.rolling(self.fast_window).mean()
        slow = close.rolling(self.slow_window).mean()
        trend = (close > fast) & (fast > slow)
        annual_volatility = close.pct_change().rolling(self.volatility_window).std() * np.sqrt(252)
        scaled = (self.target_volatility / annual_volatility).clip(upper=1.0)
        return _target(frame.index, trend.astype(float) * scaled * self.max_weight, self.max_weight)


class DualMomentumStrategy(MathematicalStrategy):
    """Absolute and relative-time momentum with a long-term trend filter."""

    name = "dual_momentum"

    def __init__(
        self,
        short_lookback: int = 63,
        long_lookback: int = 252,
        trend_window: int = 200,
        max_weight: float = 0.05,
    ) -> None:
        super().__init__(max_weight=max_weight)
        if not 1 < short_lookback < long_lookback:
            raise ValueError("lookbacks must satisfy 1 < short_lookback < long_lookback")
        self.short_lookback = int(short_lookback)
        self.long_lookback = int(long_lookback)
        self.trend_window = int(trend_window)

    def generate(self, frame: pd.DataFrame) -> pd.Series:
        close = _close(frame)
        short_return = close.pct_change(self.short_lookback)
        long_return = close.pct_change(self.long_lookback)
        score = 0.4 * short_return + 0.6 * long_return
        trend = close > close.rolling(self.trend_window).mean()
        strength = (score / 0.30).clip(lower=0.0, upper=1.0)
        return _target(frame.index, trend.astype(float) * strength * self.max_weight, self.max_weight)


class DonchianBreakoutStrategy(MathematicalStrategy):
    """Stateful channel breakout with a shorter channel exit."""

    name = "donchian_breakout"

    def __init__(
        self,
        entry_window: int = 20,
        exit_window: int = 10,
        max_weight: float = 0.03,
    ) -> None:
        super().__init__(max_weight=max_weight)
        if not 1 < exit_window < entry_window:
            raise ValueError("windows must satisfy 1 < exit_window < entry_window")
        self.entry_window = int(entry_window)
        self.exit_window = int(exit_window)

    def generate(self, frame: pd.DataFrame) -> pd.Series:
        close = _close(frame)
        high = frame.get("high", close).astype(float)
        low = frame.get("low", close).astype(float)
        entry = close > high.rolling(self.entry_window).max().shift(1)
        exit_signal = close < low.rolling(self.exit_window).min().shift(1)
        values = pd.Series(0.0, index=frame.index, dtype=float)
        invested = False
        for position in range(len(frame)):
            if not invested and bool(entry.iloc[position]):
                invested = True
            elif invested and bool(exit_signal.iloc[position]):
                invested = False
            values.iloc[position] = self.max_weight if invested else 0.0
        return values


class ZScoreMeanReversionStrategy(MathematicalStrategy):
    """Long-only rolling z-score reversion strategy."""

    name = "zscore_mean_reversion"

    def __init__(
        self,
        window: int = 20,
        entry_z: float = -2.0,
        exit_z: float = -0.25,
        trend_window: int = 100,
        max_weight: float = 0.02,
    ) -> None:
        super().__init__(max_weight=max_weight)
        if window < 5 or trend_window <= window:
            raise ValueError("trend_window must be greater than a window of at least five")
        if entry_z >= exit_z:
            raise ValueError("entry_z must be below exit_z")
        self.window = int(window)
        self.entry_z = float(entry_z)
        self.exit_z = float(exit_z)
        self.trend_window = int(trend_window)

    def generate(self, frame: pd.DataFrame) -> pd.Series:
        close = _close(frame)
        mean = close.rolling(self.window).mean()
        std = close.rolling(self.window).std().replace(0.0, np.nan)
        zscore = (close - mean) / std
        long_term_trend = close > close.rolling(self.trend_window).mean()
        values = pd.Series(0.0, index=frame.index, dtype=float)
        invested = False
        for position in range(len(frame)):
            if not invested and bool(long_term_trend.iloc[position]) and zscore.iloc[position] <= self.entry_z:
                invested = True
            elif invested and zscore.iloc[position] >= self.exit_z:
                invested = False
            values.iloc[position] = self.max_weight if invested else 0.0
        return values


@dataclass(frozen=True)
class StrategyRegistration:
    name: str
    strategy_class: type[MathematicalStrategy]


class StrategyRegistry:
    """Registry that supports built-ins and user-supplied strategy classes."""

    def __init__(self) -> None:
        self._strategies: dict[str, type[MathematicalStrategy]] = {}

    def register(self, strategy_class: type[MathematicalStrategy], *, replace: bool = False) -> None:
        if not issubclass(strategy_class, MathematicalStrategy):
            raise TypeError("strategy_class must inherit MathematicalStrategy")
        name = str(strategy_class.name).strip()
        if not name or name == "base":
            raise ValueError("strategy classes must define a unique non-empty name")
        if name in self._strategies and not replace:
            raise ValueError(f"strategy {name!r} is already registered")
        self._strategies[name] = strategy_class

    def create(self, name: str, parameters: dict[str, Any] | None = None) -> MathematicalStrategy:
        try:
            strategy_class = self._strategies[name]
        except KeyError as exc:
            available = ", ".join(self.names())
            raise KeyError(f"unknown strategy {name!r}; available: {available}") from exc
        return strategy_class(**(parameters or {}))

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._strategies))

    def registrations(self) -> tuple[StrategyRegistration, ...]:
        return tuple(StrategyRegistration(name, self._strategies[name]) for name in self.names())


def default_registry() -> StrategyRegistry:
    registry = StrategyRegistry()
    for strategy_class in (
        MovingAverageTrendStrategy,
        DualMomentumStrategy,
        DonchianBreakoutStrategy,
        ZScoreMeanReversionStrategy,
    ):
        registry.register(strategy_class)
    return registry
