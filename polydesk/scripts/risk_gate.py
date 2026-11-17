#!/usr/bin/env python3
"""Risk seat: plain-code veto. Cannot place orders.

Implements DESK_RULES.md rules 2, 3, 4, 5, 6 and 9.

  SKIP      any input missing ("unavailable" / None)          rule 6
  REJECTED  daily loss limit hit, or price >= 0.97 on an
            outcome not yet published, or gap <= fee + 2 pp  rules 9, 5, 3
  APPROVED  stake = min(Kelly * kelly_mult, cap) * bankroll  rule 4

Maker only: tickets are limit orders. The desk never takes liquidity.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

FEE_RATE = 0.07           # taker fee coefficient, rule 2 (used as the gap hurdle)
GAP_BUFFER = 0.02         # 2 pp, rule 3
NEVER_PAY_ABOVE = 0.97    # rule 5
DAILY_LOSS_FRAC = 0.02    # rule 9
DEFAULT_KELLY_MULT = 0.25
MIN_KELLY_MULT, MAX_KELLY_MULT = 0.10, 0.25
BARRIER_CAP = 0.03        # rule 4, one barrier
CERTAINTY_CAP = 0.05      # rule 4, certainty position (2-5%, use the top)


@dataclass(frozen=True)
class Ticket:
    decision: str          # APPROVED | REJECTED | SKIP
    reason: str
    side: str | None = None         # YES | NO
    limit_price: float | None = None
    stake_frac: float = 0.0
    stake: float = 0.0
    order_type: str = "limit_maker"


def fee(p: float) -> float:
    return FEE_RATE * p * (1.0 - p)


def _unavailable(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip().lower() == "unavailable")


def evaluate(*, fair, mid, bankroll: float, daily_pnl: float,
             kelly_mult: float = DEFAULT_KELLY_MULT, cap: float = BARRIER_CAP,
             happened: bool = False, inputs: dict | None = None) -> Ticket:
    """Return a decision for one candidate. `inputs` lists any evidence values
    the strategy needs (for example liquidation cluster, funding); any one
    marked unavailable makes the whole ticket SKIP."""
    for name, value in {"fair": fair, "mid": mid, **(inputs or {})}.items():
        if _unavailable(value):
            return Ticket("SKIP", f"input '{name}' unavailable (rule 6)")

    if not (MIN_KELLY_MULT <= kelly_mult <= MAX_KELLY_MULT):
        raise ValueError(f"kelly_mult must be in [{MIN_KELLY_MULT}, {MAX_KELLY_MULT}]")
    if not (0.0 < mid < 1.0) or not (0.0 <= fair <= 1.0):
        return Ticket("SKIP", "price or fair outside (0,1)")
    if bankroll <= 0:
        return Ticket("REJECTED", "bankroll must be positive")

    if daily_pnl <= -DAILY_LOSS_FRAC * bankroll:
        return Ticket("REJECTED", "daily loss limit hit: read-only until tomorrow (rule 9)")

    if mid >= NEVER_PAY_ABOVE and not happened:
        return Ticket("REJECTED", "price >= 0.97 on an outcome not yet published (rule 5)")

    gap = fair - mid
    side = "YES" if gap > 0 else "NO"
    p_side = mid if side == "YES" else 1.0 - mid
    q_side = fair if side == "YES" else 1.0 - fair
    hurdle = fee(p_side) + GAP_BUFFER
    if abs(gap) <= hurdle:
        return Ticket("REJECTED", f"gap {abs(gap):.4f} <= fee+2pp {hurdle:.4f} (rule 3)")

    kelly = (q_side - p_side) / (1.0 - p_side)
    if kelly <= 0:
        return Ticket("REJECTED", "Kelly fraction not positive")
    if not (0.0 < cap <= CERTAINTY_CAP):
        raise ValueError(f"cap must be in (0, {CERTAINTY_CAP}]")
    stake_frac = min(kelly * kelly_mult, cap)
    return Ticket(
        "APPROVED",
        f"gap {abs(gap):.4f} > hurdle {hurdle:.4f}; kelly {kelly:.4f} x {kelly_mult}",
        side=side,
        limit_price=round(p_side, 4),
        stake_frac=round(stake_frac, 6),
        stake=round(stake_frac * bankroll, 2),
    )


def render_ticket(slug: str, t: Ticket) -> str:
    line = f"- {slug}: {t.decision} - {t.reason}"
    if t.decision == "APPROVED":
        line += (f" | {t.side} limit {t.limit_price} (maker) | "
                 f"stake {t.stake_frac:.4%} = {t.stake}")
    return line


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Risk gate: one candidate, printed as a ticket line.")
    ap.add_argument("--fair", type=str, required=True)
    ap.add_argument("--mid", type=str, required=True)
    ap.add_argument("--bankroll", type=float, required=True)
    ap.add_argument("--daily-pnl", type=float, default=0.0)
    ap.add_argument("--kelly-mult", type=float, default=DEFAULT_KELLY_MULT)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--happened", action="store_true")
    ap.add_argument("--tickets-dir", type=Path, default=None,
                    help="if set, append the line to <dir>/<today>.md")
    args = ap.parse_args(argv)

    def parse(v: str):
        return None if v.strip().lower() == "unavailable" else float(v)

    ticket = evaluate(fair=parse(args.fair), mid=parse(args.mid), bankroll=args.bankroll,
                      daily_pnl=args.daily_pnl, kelly_mult=args.kelly_mult,
                      happened=args.happened)
    line = render_ticket(args.slug, ticket)
    print(line)
    if args.tickets_dir is not None:
        args.tickets_dir.mkdir(parents=True, exist_ok=True)
        with (args.tickets_dir / f"{date.today().isoformat()}.md").open("a") as fh:
            fh.write(line + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
