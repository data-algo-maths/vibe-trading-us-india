# India research starter

This directory provides a research-only starting point for NSE and BSE
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

## Non-India symbols are disabled

The default strict policy rejects US, China, Hong Kong, and crypto symbols. It
also rejects mixed-market requests. This is deliberate: a failed India source
must void the run, never route the request to another market. Use a separate
upstream checkout if you need multi-market research.

## India mathematical strategy lab

The strategy lab screens reusable NSE/BSE watchlists across separate long-term,
monthly-swing, and daily-tactical research profiles. It ships four defaults:

- inverse-volatility moving-average trend;
- dual momentum;
- Donchian channel breakout; and
- rolling z-score mean reversion.

All targets are long-only and capped by the profile configuration. The screening
backtester applies next-bar positions and explicit turnover costs. It is intended
for broad comparison; promote shortlisted ideas to the main Vibe-Trading runner
for market-specific execution rules, run cards, and deeper validation.

Run all configured profiles:

```bash
vibe-india-lab \
  --config examples/us_india/india_strategy_lab.yaml \
  --output examples/us_india/strategy_lab_output
```

Run only the weekly one-month profile:

```bash
vibe-india-lab \
  --config examples/us_india/india_strategy_lab.yaml \
  --profile swing_monthly \
  --output examples/us_india/strategy_lab_output
```

The YAML symbols are research examples, not recommendations. Replace them with
your approved universe and verify current NSE/BSE identifiers. Keep the output
directory out of commits because it contains time-dependent market results.

### Adding a mathematical strategy

Subclass `MathematicalStrategy`, give the class a unique `name`, and implement
`generate(frame)` to return a pandas Series of target weights. The example plug-in
at `custom_strategy_example.py` can be loaded without changing the registry:

```bash
vibe-india-lab \
  --config examples/us_india/india_strategy_lab.yaml \
  --profile swing_monthly \
  --plugin examples/us_india/custom_strategy_example.py:PriceChannelStrategy \
  --output examples/us_india/strategy_lab_output
```

Custom strategies should avoid look-ahead data, emit finite weights, document
their assumptions, and be tested across multiple regimes before paper use.

## Fail-closed India market policy

This fork defaults to `VIBE_TRADING_MARKET_POLICY=india_strict`. The boundary
is enforced in code for both agent market-data calls and deterministic
backtests; it is not merely a prompt convention.

Under the strict policy:

- only NSE (`.NS`), BSE (`.BO`), and approved Indian benchmark symbols are
  accepted;
- `source: auto` is pinned to the repository's registered `yfinance` loader;
- explicit `yfinance`, `india_broker`, and `local` sources are allowed;
- direct `yahoo`, Tushare, AKShare, Eastmoney, crypto, US, HK, and mixed-market
  requests are rejected;
- source initialization, network, empty-data, and OHLC-validation failures
  void the run instead of activating another provider or market;
- the error begins with `VOIDED:` so schedulers and API clients can reject the
  result without parsing an LLM response.

Supported benchmark symbols currently include `^NSEI`, `^NSEBANK`, `^CNXIT`,
`^CNXPHARMA`, `^CNXAUTO`, and `^BSESN`.

Confirm the active policy before a run:

```bash
export VIBE_TRADING_MARKET_POLICY=india_strict
vibe-trading data status
```

A strict backtest configuration should use:

```json
{
  "codes": ["RVNL.NS", "^NSEI"],
  "source": "yfinance",
  "interval": "1D"
}
```

The upstream-compatible `global` policy remains available for maintainers and
the inherited test suite. Do not enable it in India production, scheduled, or
paper-account workflows; use a separate upstream checkout for global research.
