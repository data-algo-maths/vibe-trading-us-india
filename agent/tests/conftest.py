"""Shared fixtures and sys.path setup for all tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure agent/ is on sys.path so imports like `backtest.*` and `src.*` work.
AGENT_DIR = Path(__file__).resolve().parent.parent
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

# Preserve upstream multi-market expectations in the existing test suite.
# India-policy tests opt into strict mode explicitly with monkeypatch.
os.environ["VIBE_TRADING_MARKET_POLICY"] = "global"


@pytest.fixture(autouse=True)
def _reset_env_config():
    """Clear the cached EnvConfig before each test so monkeypatch.setenv works."""
    from src.config.accessor import reset_env_config
    reset_env_config()
    yield
    reset_env_config()
