# US and India research starter

This directory provides a research-only starting point for US and Indian
equities. It does not place broker orders and does not contain credentials.

## RVNL example

The RVNL example is a deterministic, long-only trend-recovery strategy for
`RVNL.NS`. It uses:

- price above rising 50-day and 200-day moving averages;
- a close above the previous 20-session high;
- volume above 1.5 times the prior 20-session average;
- a two-ATR initial stop;
- a 2.5-ATR trailing stop;
- a close-below-50-day-average exit; and
- a 63-session time stop.

The signal targets only 5% portfolio exposure. Vibe-Trading shifts signals by
one bar, so fills use next-bar semantics. The India equity engine applies its
delivery rules, circuit check, configured cost stack, and slippage.

From the repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .

VIBE_TRADING_ALLOWED_RUN_ROOTS="$PWD/examples/us_india" \
  python -m backtest.runner examples/us_india/rvnl_backtest
```

Review the generated run card, validation output, metrics, trades, and data
source before treating a result as evidence. Test other periods and parameter
values; do not promote this example directly to live execution.

## Natural-language research

After `vibe-trading init`, run:

```bash
vibe-trading run -f examples/us_india/rvnl_research_prompt.txt
```

## Adding another Indian stock

Copy `rvnl_backtest`, then replace `RVNL.NS` in `config.json`. NSE symbols use
`.NS`; BSE symbols use `.BO`.

## Adding a US stock

Copy the run directory and replace the code with a US ticker such as `AAPL`.
The central router will select the US loader chain and the global equity
engine. Review the US engine's simplified commission, borrowing, and slippage
assumptions before relying on a result.

