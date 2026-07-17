"""Configuration-driven multi-stock strategy screening runner."""

from __future__ import annotations

import importlib.util
import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from backtest.runner import fetch_data_map

from .backtest import run_vector_backtest
from .strategies import MathematicalStrategy, StrategyRegistry, default_registry


def _load_plugin(specification: str, registry: StrategyRegistry) -> None:
    """Load ``/path/to/plugin.py:ClassName`` and register its strategy class."""
    path_text, separator, class_name = specification.partition(":")
    if not separator or not class_name:
        raise ValueError("plugin must use the '/path/plugin.py:ClassName' format")
    path = Path(path_text).expanduser().resolve()
    module_spec = importlib.util.spec_from_file_location(f"india_strategy_plugin_{path.stem}", path)
    if module_spec is None or module_spec.loader is None:
        raise ValueError(f"cannot import strategy plugin from {path}")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    strategy_class = getattr(module, class_name, None)
    if not isinstance(strategy_class, type) or not issubclass(strategy_class, MathematicalStrategy):
        raise TypeError(f"{class_name} must inherit MathematicalStrategy")
    registry.register(strategy_class)


def _read_config(path: Path) -> dict[str, Any]:
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(content, dict):
        raise ValueError("lab configuration must be a YAML object")
    if not isinstance(content.get("watchlists"), dict) or not isinstance(content.get("profiles"), dict):
        raise ValueError("lab configuration requires watchlists and profiles objects")
    return content


def _symbols_for_profile(profile: dict[str, Any], watchlists: dict[str, list[str]]) -> list[str]:
    symbols: list[str] = []
    for name in profile.get("watchlists", []):
        if name not in watchlists:
            raise KeyError(f"profile references unknown watchlist {name!r}")
        symbols.extend(str(symbol).strip() for symbol in watchlists[name])
    return list(dict.fromkeys(symbol for symbol in symbols if symbol))


def _screen_profile(
    profile_name: str,
    profile: dict[str, Any],
    watchlists: dict[str, list[str]],
    registry: StrategyRegistry,
) -> list[dict[str, Any]]:
    symbols = _symbols_for_profile(profile, watchlists)
    if not symbols:
        raise ValueError(f"profile {profile_name!r} resolved to no symbols")
    end_date = str(profile.get("end_date") or date.today().isoformat())
    config = {
        "codes": symbols,
        "start_date": str(profile["start_date"]),
        "end_date": end_date,
        "source": str(profile.get("source", "auto")),
        "interval": "1D",
    }
    fetched = fetch_data_map(config)
    strategy_specs = profile.get("strategies") or []
    if not strategy_specs:
        raise ValueError(f"profile {profile_name!r} requires at least one strategy")

    rows: list[dict[str, Any]] = []
    fee_rate = float(profile.get("fee_rate", 0.001))
    for symbol, frame in fetched.data_map.items():
        for strategy_spec in strategy_specs:
            name = str(strategy_spec["name"])
            strategy = registry.create(name, dict(strategy_spec.get("parameters") or {}))
            target = strategy.generate(frame)
            result = run_vector_backtest(frame, target, fee_rate=fee_rate)
            rows.append(
                {
                    "profile": profile_name,
                    "symbol": symbol,
                    "strategy": name,
                    "data_source": ",".join(fetched.effective_sources),
                    "start_date": str(frame.index.min().date()),
                    "end_date": str(frame.index.max().date()),
                    **result.as_dict(),
                }
            )
    return rows


def run_lab(
    config_path: str | Path,
    output_dir: str | Path,
    *,
    profile_names: list[str] | None = None,
    plugins: list[str] | None = None,
) -> pd.DataFrame:
    """Run configured profiles and persist ranked CSV and JSON reports."""
    config = _read_config(Path(config_path))
    registry = default_registry()
    for specification in plugins or []:
        _load_plugin(specification, registry)

    profiles = config["profiles"]
    selected = profile_names or list(profiles)
    unknown = sorted(set(selected) - set(profiles))
    if unknown:
        raise KeyError(f"unknown profiles: {', '.join(unknown)}")

    rows: list[dict[str, Any]] = []
    for profile_name in selected:
        rows.extend(
            _screen_profile(
                profile_name,
                dict(profiles[profile_name]),
                config["watchlists"],
                registry,
            )
        )
    report = pd.DataFrame(rows)
    if not report.empty:
        report = report.sort_values(
            ["profile", "rank_score", "symbol", "strategy"],
            ascending=[True, False, True, True],
        ).reset_index(drop=True)

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    report.to_csv(destination / "strategy_rankings.csv", index=False)
    (destination / "strategy_rankings.json").write_text(
        json.dumps(report.to_dict(orient="records"), indent=2),
        encoding="utf-8",
    )
    manifest = {
        "generated_on": date.today().isoformat(),
        "profiles": selected,
        "strategies": list(registry.names()),
        "row_count": len(report),
        "paper_only": True,
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return report
