"""Configurable mathematical strategy lab for Indian equities."""

from .backtest import BacktestResult, run_vector_backtest
from .runner import run_lab
from .strategies import MathematicalStrategy, StrategyRegistry, default_registry

__all__ = [
    "BacktestResult",
    "MathematicalStrategy",
    "StrategyRegistry",
    "default_registry",
    "run_lab",
    "run_vector_backtest",
]
