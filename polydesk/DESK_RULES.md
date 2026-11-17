# DESK_RULES.md

The only place strategy lives. Every seat rereads this file before acting.
Changing a rule is a proposal from the Auditor; a human approves it.

1. The Quant writes `fair/` before it may open `evidence/` or `board/`.
2. Maker only. Taker fee on crypto is `0.07 * p * (1 - p)`.
3. Trade only if `|fair - mid| > fee + 0.02` and the tape does not veto.
4. Size: Kelly x 0.10-0.25. One barrier <= 3% of bankroll.
   One "certainty" position <= 2-5% of bankroll.
5. Never pay >= 0.97 for something that has not already happened.
6. Any input "unavailable" -> SKIP. Missing data is not zero.
7. Nothing below daily markets. No sports.
8. Only one seat can spend money, and it is the human operator.
9. Daily loss limit: 2% of bankroll. Hit it -> read-only until tomorrow.
10. Every forecast goes in the journal, traded or not.

Definitions
- `fair` is the desk's own probability. It is computed blind, from price history only.
- `mid` is the market price, halfway between the best bid and best ask.
- `pp` means percentage points. `0.02` in rule 3 is 2 pp.
- Kelly sizing for a binary contract bought at price `p` with desk probability `q`:
  `f* = (q - p) / (1 - p)`. The desk stakes `f* x kelly_mult`.

Enforced in code
- Rules 2, 3, 4, 5, 6 and 9 are checked by `scripts/risk_gate.py`.
- Rule 10 is written by the Auditor seat to `journal/journal.csv` (one row per forecast).
- Rule 1 is a file-order check: `scripts/barrier.py` refuses to run if `board/` is
  populated before `fair/<slug>.json` exists.
