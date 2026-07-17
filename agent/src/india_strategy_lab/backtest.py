"""Small causal vector backtester used for broad strategy screening."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BacktestResult:
    total_return: float
    annual_return: float
    benchmark_return: float
    excess_return: float
    annual_volatility: float
    sharpe: float
    max_drawdown: float
    turnover: float
    trade_count: int
    exposure: float
    rank_score: float

    def as_dict(self) -> dict[str, float | int]:
        return asdict(self)


def _finite(value: float) -> float:
    return float(value) if np.isfinite(value) else 0.0


def _annual_return(total_return: float, observations: int) -> float:
    years = observations / 252.0
    if years <= 0 or total_return <= -1:
        return 0.0
    return (1.0 + total_return) ** (1.0 / years) - 1.0


def run_vector_backtest(
    frame: pd.DataFrame,
    target_weight: pd.Series,
    *,
    fee_rate: float = 0.001,
) -> BacktestResult:
    """Evaluate a target-weight series using next-bar positions and explicit costs."""
    if "close" not in frame:
        raise ValueError("market frame must contain a 'close' column")
    if fee_rate < 0:
        raise ValueError("fee_rate must be non-negative")

    close = frame["close"].astype(float)
    target = target_weight.reindex(frame.index).fillna(0.0).astype(float).clip(0.0, 1.0)
    position = target.shift(1).fillna(0.0)
    returns = close.pct_change().fillna(0.0)
    turnover_series = position.diff().abs().fillna(position.abs())
    strategy_returns = position * returns - turnover_series * fee_rate
    equity = (1.0 + strategy_returns).cumprod()
    benchmark_equity = (1.0 + returns).cumprod()

    total_return = _finite(equity.iloc[-1] - 1.0) if not equity.empty else 0.0
    benchmark_return = _finite(benchmark_equity.iloc[-1] - 1.0) if not equity.empty else 0.0
    annual_return = _finite(_annual_return(total_return, len(strategy_returns)))
    annual_volatility = _finite(strategy_returns.std(ddof=0) * np.sqrt(252))
    sharpe = _finite(strategy_returns.mean() / strategy_returns.std(ddof=0) * np.sqrt(252)) if strategy_returns.std(ddof=0) > 0 else 0.0
    drawdown = equity / equity.cummax() - 1.0
    max_drawdown = _finite(drawdown.min()) if not drawdown.empty else 0.0
    turnover = _finite(turnover_series.sum())
    trade_count = int(((position > 0) & (position.shift(1).fillna(0.0) == 0)).sum())
    exposure = _finite((position > 0).mean())
    excess_return = total_return - benchmark_return

    score = (
        20.0 * np.clip(sharpe, -3.0, 3.0)
        + 100.0 * np.clip(annual_return, -1.0, 1.0)
        + 40.0 * np.clip(excess_return, -2.0, 2.0)
        - 100.0 * abs(max_drawdown)
        - 0.10 * turnover
    )
    if trade_count < 5:
        score -= 15.0

    return BacktestResult(
        total_return=total_return,
        annual_return=annual_return,
        benchmark_return=benchmark_return,
        excess_return=_finite(excess_return),
        annual_volatility=annual_volatility,
        sharpe=sharpe,
        max_drawdown=max_drawdown,
        turnover=turnover,
        trade_count=trade_count,
        exposure=exposure,
        rank_score=_finite(score),
    )
