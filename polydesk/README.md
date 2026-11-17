# polydesk

Offline scaffold for the Polymarket desk described in the course article:
rules, seat charters, pricing and risk math, and scoring. Stdlib Python only.

Not financial advice. Nothing here places an order, holds a wallet key, or
guarantees a return. The article's profit figures are its own claims and were
not verified.

## What works now

| Piece | File | Status |
|---|---|---|
| Rules | `DESK_RULES.md` | written |
| Folder walls | `CLAUDE.md` | written |
| Charters | `roles/*.md` | written (Scout, Quant, Tape Reader, Risk, Auditor) |
| Blind fair value (touch / above, realised vol, base rate) | `scripts/barrier.py` | works on a candle CSV |
| Risk gate (SKIP / REJECTED / APPROVED, fee + 2 pp, Kelly cap, 0.97 rule, daily loss) | `scripts/risk_gate.py` | works |
| Brier score and kill rule | `scripts/brier.py` | works |
| Tests | `tests/test_desk.py` | 23 passing |

## What is not wired

- **Live candles.** The Binance API is blocked from this environment (proxy 403).
  `barrier.py` takes a local CSV with a `close` column. Without candles it writes
  `status: unavailable` and exits 2.
- **Tape Reader.** The article's Minara feed needs an account and key, which this
  repo does not have. Per rule 6, any missing tape input means SKIP.
- **Polymarket board.** Scout (`board/board.csv`) is not implemented.

## Run

```bash
python3 -m unittest discover -s polydesk/tests -v
python3 polydesk/scripts/barrier.py --candles candles.csv --level 110000 --hours 168 \
        --kind touch --slug btc-110k-week --root polydesk --source "Binance BTCUSDT 1h"
python3 polydesk/scripts/risk_gate.py --fair 0.42 --mid 0.30 --bankroll 1000 --slug btc-110k-week
```

Rule 1 is by convention: run `barrier.py` (which never reads `board/`) before anyone
opens `board/`.
