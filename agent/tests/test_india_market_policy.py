from __future__ import annotations

import pandas as pd
import pytest

from backtest.loaders.base import NoAvailableSourceError
from src.market_policy import (
    MarketPolicyError,
    enforce_india_request,
    is_india_symbol,
    market_policy_mode,
)


def _bars() -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=3, freq="D")
    return pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0],
            "high": [102.0, 103.0, 104.0],
            "low": [99.0, 100.0, 101.0],
            "close": [101.0, 102.0, 103.0],
            "volume": [1000.0, 1100.0, 1200.0],
        },
        index=index,
    )


@pytest.mark.parametrize(
    "symbol",
    ["RVNL.NS", "500325.BO", "M&M.NS", "^NSEI", "^NSEBANK", "^BSESN"],
)
def test_approved_india_symbols(symbol: str) -> None:
    assert is_india_symbol(symbol)


def test_fork_defaults_to_india_strict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIBE_TRADING_MARKET_POLICY", raising=False)
    assert market_policy_mode() == "india_strict"


@pytest.mark.parametrize("symbol", ["AAPL.US", "700.HK", "000001.SZ", "BTC-USDT"])
def test_non_india_symbols_are_rejected(symbol: str) -> None:
    with pytest.raises(MarketPolicyError, match="VOIDED"):
        enforce_india_request([symbol], "auto")


@pytest.mark.parametrize("source", ["yfinance", "tushare", "akshare", "auto-global"])
def test_cross_provider_sources_are_rejected(source: str) -> None:
    with pytest.raises(MarketPolicyError, match="Provider switching is disabled"):
        enforce_india_request(["RVNL.NS"], source)


def test_auto_is_pinned_to_yahoo() -> None:
    symbols, source = enforce_india_request(["rvnl.ns", "^nsei"], "auto")
    assert symbols == ["RVNL.NS", "^NSEI"]
    assert source == "yahoo"


def test_backtest_fetch_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    from backtest import runner

    class EmptyYahoo:
        name = "yahoo"

        def fetch(self, *args, **kwargs):
            return {}

    monkeypatch.setenv("VIBE_TRADING_MARKET_POLICY", "india_strict")
    monkeypatch.setattr(runner, "get_loader_cls_exact", lambda source: EmptyYahoo)

    with pytest.raises(NoAvailableSourceError, match="fallback is disabled"):
        runner.fetch_data_map(
            {
                "codes": ["RVNL.NS", "^NSEI"],
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "source": "auto",
                "interval": "1D",
            }
        )


def test_backtest_fetch_uses_only_exact_yahoo(monkeypatch: pytest.MonkeyPatch) -> None:
    from backtest import runner

    calls: list[tuple[list[str], str]] = []

    class Yahoo:
        name = "yahoo"

        def fetch(self, codes, start_date, end_date, **kwargs):
            calls.append((list(codes), kwargs["interval"]))
            return {code: _bars() for code in codes}

    monkeypatch.setenv("VIBE_TRADING_MARKET_POLICY", "india_strict")
    monkeypatch.setattr(runner, "get_loader_cls_exact", lambda source: Yahoo)

    result = runner.fetch_data_map(
        {
            "codes": ["RVNL.NS", "^NSEI"],
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "source": "auto",
            "interval": "1D",
        }
    )

    assert calls == [(["RVNL.NS", "^NSEI"], "1D")]
    assert result.source == "yahoo"
    assert result.effective_sources == ["yahoo"]
    assert set(result.data_map) == {"RVNL.NS", "^NSEI"}


def test_market_data_tool_uses_exact_yahoo(monkeypatch: pytest.MonkeyPatch) -> None:
    from src import market_data

    class Yahoo:
        def fetch(self, codes, start_date, end_date, **kwargs):
            return {code: _bars() for code in codes}

    monkeypatch.setenv("VIBE_TRADING_MARKET_POLICY", "india_strict")
    monkeypatch.setattr(market_data, "get_loader_exact", lambda source: Yahoo)

    result = market_data.fetch_market_data(
        codes=["RVNL.NS", "^NSEI"],
        start_date="2025-01-01",
        end_date="2025-12-31",
        source="auto",
        max_rows=0,
    )

    assert set(result) == {"RVNL.NS", "^NSEI"}
    assert result["RVNL.NS"][-1]["close"] == 103.0


def test_market_data_tool_voids_empty_required_data(monkeypatch: pytest.MonkeyPatch) -> None:
    from src import market_data

    class EmptyYahoo:
        def fetch(self, codes, start_date, end_date, **kwargs):
            return {}

    monkeypatch.setenv("VIBE_TRADING_MARKET_POLICY", "india_strict")
    monkeypatch.setattr(market_data, "get_loader_exact", lambda source: EmptyYahoo)

    with pytest.raises(RuntimeError, match="VOIDED.*fallback is disabled"):
        market_data.fetch_market_data(
            codes=["RVNL.NS"],
            start_date="2025-01-01",
            end_date="2025-12-31",
            source="yahoo",
        )
