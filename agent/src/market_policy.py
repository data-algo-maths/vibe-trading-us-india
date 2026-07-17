"""Fail-closed market boundary for the India-focused distribution.

The upstream project supports many markets and normally falls through several
data providers.  This fork defaults to an India-only policy: a request must
contain only NSE/BSE symbols (or approved Indian indices), and the selected
provider must succeed without cross-market or cross-provider fallback.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable


class MarketPolicyError(ValueError):
    """Raised when a request crosses the configured market boundary."""


INDIA_STRICT = "india_strict"
GLOBAL = "global"

_INDIA_EQUITY = re.compile(r"^[A-Z0-9&.\-]+\.(NS|BO)$", re.I)
_INDIA_INDICES = frozenset(
    {
        "^NSEI",       # NIFTY 50
        "^NSEBANK",    # NIFTY Bank
        "^CNXIT",      # NIFTY IT
        "^CNXPHARMA",  # NIFTY Pharma
        "^CNXAUTO",    # NIFTY Auto
        "^BSESN",      # S&P BSE Sensex
    }
)

# Explicit providers are permitted, but they never fall through to another
# provider in strict mode.  Yahoo is the free default.  Broker/local sources
# are opt-in and must be configured by the operator. ``yfinance`` is the free
# default because it is the repository's registered, preflight-checked Yahoo
# implementation and natively preserves NSE/BSE suffixes.
INDIA_ALLOWED_SOURCES = frozenset({"yfinance", "india_broker", "local"})


def market_policy_mode() -> str:
    """Return the active market policy; this fork defaults to India strict."""
    value = os.getenv("VIBE_TRADING_MARKET_POLICY", INDIA_STRICT).strip().lower()
    if value not in {INDIA_STRICT, GLOBAL}:
        raise MarketPolicyError(
            "VIBE_TRADING_MARKET_POLICY must be 'india_strict' or 'global', "
            f"got {value!r}"
        )
    return value


def india_strict_enabled() -> bool:
    """Return whether fail-closed India routing is active."""
    return market_policy_mode() == INDIA_STRICT


def is_india_symbol(symbol: str) -> bool:
    """Return whether *symbol* is an approved NSE/BSE equity or index."""
    normalized = str(symbol).strip().upper()
    return bool(_INDIA_EQUITY.fullmatch(normalized)) or normalized in _INDIA_INDICES


def enforce_india_symbols(symbols: Iterable[str]) -> list[str]:
    """Validate and normalize an India-only symbol collection."""
    normalized = [str(symbol).strip().upper() for symbol in symbols]
    if not normalized:
        raise MarketPolicyError("VOIDED: an India-strict request requires at least one symbol")
    rejected = [symbol for symbol in normalized if not is_india_symbol(symbol)]
    if rejected:
        raise MarketPolicyError(
            "VOIDED: India-strict policy rejected non-India or unsupported symbols: "
            + ", ".join(rejected)
        )
    return normalized


def enforce_india_source(source: str) -> str:
    """Normalize and validate a provider without allowing fallback."""
    normalized = str(source or "auto").strip().lower()
    if normalized == "auto":
        return "yfinance"
    if normalized not in INDIA_ALLOWED_SOURCES:
        raise MarketPolicyError(
            "VOIDED: India-strict policy permits only "
            f"{sorted(INDIA_ALLOWED_SOURCES)}; got {normalized!r}. "
            "Provider switching is disabled."
        )
    return normalized


def enforce_india_request(symbols: Iterable[str], source: str) -> tuple[list[str], str]:
    """Validate an India request and return normalized symbols/provider."""
    return enforce_india_symbols(symbols), enforce_india_source(source)
