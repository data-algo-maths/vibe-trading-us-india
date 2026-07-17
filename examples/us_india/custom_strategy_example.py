"""Example plug-in for ``vibe-india-lab --plugin``."""

import pandas as pd

from src.india_strategy_lab.strategies import MathematicalStrategy


class PriceChannelStrategy(MathematicalStrategy):
    """Example: hold while close is above its rolling median."""

    name = "price_channel_example"

    def __init__(self, window: int = 60, max_weight: float = 0.02) -> None:
        super().__init__(max_weight=max_weight)
        self.window = int(window)

    def generate(self, frame: pd.DataFrame) -> pd.Series:
        close = frame["close"].astype(float)
        median = close.rolling(self.window).median()
        return (close > median).astype(float).fillna(0.0) * self.max_weight
