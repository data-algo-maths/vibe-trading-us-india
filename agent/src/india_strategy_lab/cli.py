"""Command-line entry point for the India mathematical strategy lab."""

from __future__ import annotations

import argparse

from .runner import run_lab


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Screen Indian stocks with mathematical strategies")
    parser.add_argument("--config", required=True, help="Path to the YAML lab configuration")
    parser.add_argument("--output", required=True, help="Directory for paper-only reports")
    parser.add_argument("--profile", action="append", dest="profiles", help="Profile to run; repeatable")
    parser.add_argument(
        "--plugin",
        action="append",
        default=[],
        help="Custom strategy as /path/plugin.py:ClassName; repeatable",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report = run_lab(
        args.config,
        args.output,
        profile_names=args.profiles,
        plugins=args.plugin,
    )
    if report.empty:
        print("No rows produced. Check data availability and watchlists.")
        return
    columns = [
        "profile",
        "symbol",
        "strategy",
        "annual_return",
        "sharpe",
        "max_drawdown",
        "trade_count",
        "rank_score",
    ]
    print(report[columns].to_string(index=False))


if __name__ == "__main__":
    main()
