#!/usr/bin/env python3
"""Quant seat: blind fair value for a barrier or 'above' market.

Reads price candles only. Never reads board/ or any market price.
Writes fair/<slug>.json. If any input is missing, writes
{"status": "unavailable", ...} and exits with code 2. It never estimates.

Formulas (zero drift, lognormal price):
  touch = 2 * N(-|ln(X/S)| / (sigma * sqrt(T)))          one-touch barrier
  above = N(d2),  d2 = (ln(S/X) - 0.5 sigma^2 T) / (sigma sqrt(T))

Usage:
  barrier.py --candles candles.csv --level 100000 --hours 720 \
             --slug btc-hit-100k --root polydesk --source "Binance BTCUSDT 1h"

candles.csv needs a header with a 'close' column (oldest row first).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

HOURS_PER_YEAR = 8760  # 365 * 24, hourly candles
MIN_RETURNS_7D = 100
MIN_RETURNS_30D = 400


class Unavailable(Exception):
    """An input is missing. The desk writes 'unavailable' and stops."""


def norm_cdf(x: float) -> float:
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def load_closes(path: Path) -> list[float]:
    if not path.exists():
        raise Unavailable(f"candle file not found: {path}")
    closes: list[float] = []
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames or "close" not in reader.fieldnames:
            raise Unavailable("candle file has no 'close' column")
        for row in reader:
            raw = (row.get("close") or "").strip()
            if not raw:
                continue
            value = float(raw)
            if value <= 0 or math.isnan(value):
                raise Unavailable(f"non-positive close in candles: {raw}")
            closes.append(value)
    return closes


def realised_vol(closes: list[float], hours: int, min_returns: int) -> float:
    """Annualised sample stdev of hourly log returns over the last `hours` candles."""
    window = closes[-(hours + 1):]
    if len(window) < hours + 1:
        raise Unavailable(f"need {hours + 1} closes for a {hours}h window, have {len(window)}")
    rets = [math.log(b / a) for a, b in zip(window, window[1:])]
    if len(rets) < min_returns:
        raise Unavailable(f"only {len(rets)} returns, need {min_returns}")
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(HOURS_PER_YEAR)


def fair_touch(spot: float, level: float, sigma: float, years: float) -> float:
    if sigma <= 0 or years <= 0:
        raise Unavailable("sigma and time to expiry must be positive")
    z = abs(math.log(level / spot)) / (sigma * math.sqrt(years))
    return min(1.0, 2.0 * norm_cdf(-z))


def fair_above(spot: float, level: float, sigma: float, years: float) -> float:
    if sigma <= 0 or years <= 0:
        raise Unavailable("sigma and time to expiry must be positive")
    d2 = (math.log(spot / level) - 0.5 * sigma * sigma * years) / (sigma * math.sqrt(years))
    return norm_cdf(d2)


def base_rate(closes: list[float], level: float, horizon_h: int, up: bool) -> float:
    """Share of past windows of this length in which price reached `level`
    in the stated direction. Uses closes, so it understates intrabar touches."""
    if len(closes) <= horizon_h + 1:
        raise Unavailable("not enough history for the base rate")
    starts = range(0, len(closes) - horizon_h - 1)
    hits = 0
    for i in starts:
        seg = closes[i + 1 : i + 1 + horizon_h]
        if (up and max(seg) >= level) or (not up and min(seg) <= level):
            hits += 1
    return hits / len(starts)


def build_fair(closes: list[float], level: float, hours: int, kind: str,
               source: str) -> dict:
    if kind not in ("touch", "above"):
        raise Unavailable(f"unknown kind: {kind}")
    if level <= 0:
        raise Unavailable("level must be positive")
    spot = closes[-1]
    years = hours / HOURS_PER_YEAR
    sigma_7d = realised_vol(closes, 7 * 24, MIN_RETURNS_7D)
    sigma_30d = realised_vol(closes, 30 * 24, MIN_RETURNS_30D)
    price = fair_touch if kind == "touch" else fair_above
    f7 = price(spot, level, sigma_7d, years)
    f30 = price(spot, level, sigma_30d, years)
    return {
        "kind": kind,
        "status": "ok",
        "spot": spot,
        "level": level,
        "horizon_hours": hours,
        "sigma_7d": round(sigma_7d, 6),
        "sigma_30d": round(sigma_30d, 6),
        "fair_low": round(min(f7, f30), 6),
        "fair_high": round(max(f7, f30), 6),
        "base_rate": round(base_rate(closes, level, hours, up=level > spot), 6),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "candle_source": source,
        "note": "touch = intrabar-style reflection estimate; base_rate uses closes",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--candles", required=True, type=Path)
    ap.add_argument("--level", required=True, type=float)
    ap.add_argument("--hours", required=True, type=int, help="hours to expiry")
    ap.add_argument("--kind", default="touch", choices=["touch", "above"])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--root", default="polydesk", type=Path)
    ap.add_argument("--source", default="unspecified candle source")
    args = ap.parse_args(argv)

    out = args.root / "fair" / f"{args.slug}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        if args.hours <= 0:
            raise Unavailable("hours to expiry must be positive")
        closes = load_closes(args.candles)
        result = build_fair(closes, args.level, args.hours, args.kind, args.source)
    except Unavailable as exc:
        out.write_text(json.dumps({"status": "unavailable", "reason": str(exc),
                                   "slug": args.slug}, indent=2) + "\n")
        print(f"unavailable: {exc}", file=sys.stderr)
        return 2
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
