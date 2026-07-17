"""Research-only RVNL trend-recovery signal engine."""

import pandas as pd


class SignalEngine:
    """Generate a capped, long-only target position for RVNL."""

    def __init__(
        self,
        allocation=0.05,
        fast_window=50,
        slow_window=200,
        breakout_window=20,
        volume_multiple=1.5,
        atr_window=14,
        initial_stop_atr=2.0,
        trailing_stop_atr=2.5,
        max_holding_bars=63,
    ):
        self.allocation = allocation
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.breakout_window = breakout_window
        self.volume_multiple = volume_multiple
        self.atr_window = atr_window
        self.initial_stop_atr = initial_stop_atr
        self.trailing_stop_atr = trailing_stop_atr
        self.max_holding_bars = max_holding_bars

    def generate(self, data_map):
        """Return symbol-to-target-position series in the [-1, 1] range."""
        result = {}
        for symbol, frame in data_map.items():
            result[symbol] = self._generate_one(frame)
        return result

    def _generate_one(self, frame):
        close = frame["close"].astype(float)
        high = frame["high"].astype(float)
        low = frame["low"].astype(float)
        volume = frame["volume"].astype(float)

        fast = close.rolling(self.fast_window).mean()
        slow = close.rolling(self.slow_window).mean()
        fast_rising = fast.diff(10) > 0
        prior_high = high.rolling(self.breakout_window).max().shift(1)
        prior_volume = volume.rolling(20).mean().shift(1)

        previous_close = close.shift(1)
        true_range = pd.concat(
            [
                high - low,
                (high - previous_close).abs(),
                (low - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = true_range.rolling(self.atr_window).mean()

        entry_condition = (
            (close > fast)
            & (close > slow)
            & fast_rising
            & (close > prior_high)
            & (volume > self.volume_multiple * prior_volume)
            & atr.notna()
        )

        target = pd.Series(0.0, index=frame.index, dtype=float)
        in_position = False
        entry_price = 0.0
        entry_atr = 0.0
        peak_close = 0.0
        bars_held = 0

        for index in range(len(frame)):
            current_close = close.iloc[index]
            current_atr = atr.iloc[index]

            if not in_position and bool(entry_condition.iloc[index]):
                in_position = True
                entry_price = current_close
                entry_atr = current_atr
                peak_close = current_close
                bars_held = 0
            elif in_position:
                bars_held += 1
                peak_close = max(peak_close, current_close)
                initial_stop = entry_price - self.initial_stop_atr * entry_atr
                trailing_stop = peak_close - self.trailing_stop_atr * current_atr
                trend_failed = current_close < fast.iloc[index]
                timed_out = bars_held >= self.max_holding_bars
                stop_hit = current_close <= max(initial_stop, trailing_stop)

                if trend_failed or timed_out or stop_hit:
                    in_position = False
                    bars_held = 0

            target.iloc[index] = self.allocation if in_position else 0.0

        return target.fillna(0.0)

