"""Run with: python3 -m unittest discover -s polydesk/tests -v"""
from __future__ import annotations

import csv
import json
import math
import random
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

import barrier  # noqa: E402
import brier  # noqa: E402
import risk_gate  # noqa: E402


def synthetic_candles(n: int, start: float = 100_000.0, sigma_h: float = 0.01, seed: int = 1) -> list[float]:
    rng = random.Random(seed)
    closes = [start]
    for _ in range(n):
        closes.append(closes[-1] * math.exp(rng.gauss(0, sigma_h)))
    return closes


class BarrierMath(unittest.TestCase):
    def test_norm_cdf_known_points(self):
        self.assertAlmostEqual(barrier.norm_cdf(0.0), 0.5, places=12)
        self.assertAlmostEqual(barrier.norm_cdf(1.96), 0.975, places=3)

    def test_touch_at_the_spot_is_certain(self):
        self.assertAlmostEqual(barrier.fair_touch(100, 100, 0.5, 0.1), 1.0)

    def test_touch_falls_as_the_level_moves_away(self):
        near = barrier.fair_touch(100, 105, 0.5, 0.1)
        far = barrier.fair_touch(100, 130, 0.5, 0.1)
        self.assertGreater(near, far)
        self.assertGreater(far, 0.0)

    def test_touch_is_at_least_the_above_probability(self):
        for level in (95, 105, 120):
            t = barrier.fair_touch(100, level, 0.6, 0.05)
            a = barrier.fair_above(100, level, 0.6, 0.05)
            if level > 100:
                self.assertGreaterEqual(t, a)

    def test_above_is_about_half_at_the_spot_with_tiny_vol(self):
        self.assertAlmostEqual(barrier.fair_above(100, 100, 1e-6, 0.1), 0.5, places=3)

    def test_nonpositive_inputs_are_unavailable(self):
        with self.assertRaises(barrier.Unavailable):
            barrier.fair_touch(100, 105, 0.0, 0.1)
        with self.assertRaises(barrier.Unavailable):
            barrier.fair_above(100, 105, 0.5, 0.0)


class Realised(unittest.TestCase):
    def test_short_history_is_unavailable(self):
        with self.assertRaises(barrier.Unavailable):
            barrier.realised_vol(synthetic_candles(50), 7 * 24, 100)

    def test_vol_roughly_matches_the_simulated_hourly_sigma(self):
        closes = synthetic_candles(800, sigma_h=0.01, seed=7)
        vol = barrier.realised_vol(closes, 720, 400)
        expected = 0.01 * math.sqrt(barrier.HOURS_PER_YEAR)
        self.assertAlmostEqual(vol / expected, 1.0, delta=0.2)


class FairFileEndToEnd(unittest.TestCase):
    def _write_candles(self, path: Path, closes: list[float]) -> None:
        with path.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["open_time", "close"])
            for i, c in enumerate(closes):
                w.writerow([i, c])

    def test_writes_fair_json_with_all_fields(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            candles = root / "c.csv"
            self._write_candles(candles, synthetic_candles(900, seed=3))
            rc = barrier.main(["--candles", str(candles), "--level", "110000", "--hours", "168",
                               "--kind", "touch", "--slug", "btc-test", "--root", str(root),
                               "--source", "synthetic"])
            self.assertEqual(rc, 0)
            data = json.loads((root / "fair" / "btc-test.json").read_text())
            for key in ("spot", "sigma_7d", "sigma_30d", "fair_low", "fair_high",
                        "base_rate", "timestamp", "candle_source"):
                self.assertIn(key, data)
            self.assertLessEqual(data["fair_low"], data["fair_high"])
            self.assertTrue(0.0 <= data["base_rate"] <= 1.0)

    def test_missing_candles_write_unavailable_and_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            rc = barrier.main(["--candles", str(root / "nope.csv"), "--level", "1",
                               "--hours", "24", "--slug", "x", "--root", str(root)])
            self.assertEqual(rc, 2)
            data = json.loads((root / "fair" / "x.json").read_text())
            self.assertEqual(data["status"], "unavailable")


class RiskGate(unittest.TestCase):
    def test_unavailable_input_is_skip_not_zero(self):
        t = risk_gate.evaluate(fair=0.4, mid=0.2, bankroll=1000, daily_pnl=0,
                               inputs={"liq_cluster": "unavailable"})
        self.assertEqual(t.decision, "SKIP")

    def test_missing_fair_is_skip(self):
        t = risk_gate.evaluate(fair=None, mid=0.2, bankroll=1000, daily_pnl=0)
        self.assertEqual(t.decision, "SKIP")

    def test_never_pay_097_for_unpublished(self):
        t = risk_gate.evaluate(fair=0.999, mid=0.98, bankroll=1000, daily_pnl=0)
        self.assertEqual(t.decision, "REJECTED")

    def test_publish_allows_high_price(self):
        # gap 0.03 > fee(0.97)+2pp ~ 0.022, so only the 'happened' flag separates this from rule 5
        t = risk_gate.evaluate(fair=1.0, mid=0.97, bankroll=1000, daily_pnl=0, happened=True)
        self.assertEqual(t.decision, "APPROVED")
        t_unpub = risk_gate.evaluate(fair=1.0, mid=0.97, bankroll=1000, daily_pnl=0)
        self.assertEqual(t_unpub.decision, "REJECTED")

    def test_gap_below_fee_plus_2pp_is_rejected(self):
        # fee(0.50) = 0.07 * 0.25 = 0.0175, hurdle = 0.0375
        t = risk_gate.evaluate(fair=0.53, mid=0.50, bankroll=1000, daily_pnl=0)
        self.assertEqual(t.decision, "REJECTED")

    def test_clear_gap_is_approved_as_maker_limit_within_cap(self):
        t = risk_gate.evaluate(fair=0.70, mid=0.50, bankroll=1000, daily_pnl=0)
        self.assertEqual(t.decision, "APPROVED")
        self.assertEqual(t.side, "YES")
        self.assertEqual(t.order_type, "limit_maker")
        self.assertLessEqual(t.stake_frac, risk_gate.BARRIER_CAP)
        self.assertLessEqual(t.stake, 0.03 * 1000)

    def test_no_side_when_fair_is_below_mid(self):
        t = risk_gate.evaluate(fair=0.20, mid=0.50, bankroll=1000, daily_pnl=0)
        self.assertEqual(t.decision, "APPROVED")
        self.assertEqual(t.side, "NO")

    def test_daily_loss_limit_blocks(self):
        t = risk_gate.evaluate(fair=0.70, mid=0.50, bankroll=1000, daily_pnl=-20)
        self.assertEqual(t.decision, "REJECTED")
        self.assertIn("daily loss", t.reason)

    def test_kelly_multiplier_bounds_enforced(self):
        with self.assertRaises(ValueError):
            risk_gate.evaluate(fair=0.7, mid=0.5, bankroll=1000, daily_pnl=0, kelly_mult=0.5)


class Scoring(unittest.TestCase):
    def test_brier_of_perfect_forecast_is_zero(self):
        self.assertEqual(brier.brier([1.0, 0.0], [1, 0]), 0.0)

    def test_brier_of_coin_flip_is_quarter(self):
        self.assertAlmostEqual(brier.brier([0.5, 0.5], [1, 0]), 0.25)

    def test_kill_rule_inactive_before_30_trades(self):
        killed, _ = brier.kill_check([0.6] * 10, [0.5] * 10, [1] * 10)
        self.assertFalse(killed)

    def test_kill_rule_fires_when_desk_no_better_than_market(self):
        outcomes = [1, 0] * 15
        desk = [0.5] * 30
        market = [0.5] * 30
        killed, _ = brier.kill_check(desk, market, outcomes)
        self.assertTrue(killed)


if __name__ == "__main__":
    unittest.main()
