#!/usr/bin/env python3
"""Auditor seat: Brier scores and the strategy kill rule.

Brier = mean((p - outcome)^2), lower is better. 0.25 is a coin flip at 0.5.
Kill rule (strategy 1, reused by 3): after `min_n` resolved trades, the desk's
Brier score is no better than the market's -> the strategy is suspended.
"""
from __future__ import annotations

import sys


def brier(probs: list[float], outcomes: list[int]) -> float:
    if len(probs) != len(outcomes):
        raise ValueError("probs and outcomes must be the same length")
    if not probs:
        raise ValueError("no resolved forecasts")
    for p in probs:
        if not 0.0 <= p <= 1.0:
            raise ValueError(f"probability out of range: {p}")
    for o in outcomes:
        if o not in (0, 1):
            raise ValueError(f"outcome must be 0 or 1, got {o}")
    return sum((p - o) ** 2 for p, o in zip(probs, outcomes)) / len(probs)


def kill_check(desk: list[float], market: list[float], outcomes: list[int],
               min_n: int = 30) -> tuple[bool, str]:
    """Return (killed, reason). Not killed while there are fewer than min_n trades."""
    n = len(outcomes)
    if n < min_n:
        return False, f"{n}/{min_n} resolved trades: kill rule not yet active"
    bd = brier(desk, outcomes)
    bm = brier(market, outcomes)
    if bd >= bm:
        return True, f"brier_desk {bd:.4f} >= brier_market {bm:.4f} over {n} trades: suspend"
    return False, f"brier_desk {bd:.4f} < brier_market {bm:.4f} over {n} trades"


if __name__ == "__main__":
    print("import brier / kill_check; this module has no CLI", file=sys.stderr)
    sys.exit(1)
