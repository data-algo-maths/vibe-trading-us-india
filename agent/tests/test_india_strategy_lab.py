from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.india_strategy_lab.backtest import run_vector_backtest
from src.india_strategy_lab.strategies import (
    DonchianBreakoutStrategy,
    MathematicalStrategy,
    StrategyRegistry,
    default_registry,
)


def _frame(rows: int = 320) -> pd.DataFrame:
    index = pd.date_range("2020-01-01", periods=rows, freq="B")
    close = pd.Series(np.linspace(100.0, 180.0, rows), index=index)
    return pd.DataFrame(
        {
            "open": close.shift(1).fillna(close.iloc[0]),
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1_000_000.0,
        },
        index=index,
    )


@pytest.mark.parametrize("name", default_registry().names())
def test_default_strategies_return_bounded_aligned_targets(name: str) -> None:
    frame = _frame()
    target = default_registry().create(name).generate(frame)

    assert target.index.equals(frame.index)
    assert target.notna().all()
    assert (target >= 0).all()
    assert (target <= 0.05).all()


def test_vector_backtest_uses_next_bar_positions_and_costs() -> None:
    frame = _frame(40)
    target = pd.Series(0.05, index=frame.index)

    without_costs = run_vector_backtest(frame, target, fee_rate=0.0)
    with_costs = run_vector_backtest(frame, target, fee_rate=0.01)

    assert with_costs.total_return < without_costs.total_return
    assert with_costs.trade_count == 1
    assert with_costs.max_drawdown <= 0
    assert np.isfinite(with_costs.rank_score)


def test_registry_accepts_custom_strategy() -> None:
    class AlwaysCashStrategy(MathematicalStrategy):
        name = "always_cash"

        def generate(self, frame: pd.DataFrame) -> pd.Series:
            return pd.Series(0.0, index=frame.index)

    registry = StrategyRegistry()
    registry.register(AlwaysCashStrategy)

    assert registry.names() == ("always_cash",)
    assert registry.create("always_cash").generate(_frame()).eq(0.0).all()


def test_donchian_rejects_invalid_windows() -> None:
    with pytest.raises(ValueError, match="windows"):
        DonchianBreakoutStrategy(entry_window=10, exit_window=10)
