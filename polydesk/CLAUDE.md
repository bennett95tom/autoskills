# CLAUDE.md

Folder access for the desk. A prompt is a rule. A folder is a wall.

| Seat          | May read                                        | May write                    |
|---------------|-------------------------------------------------|------------------------------|
| Scout         | public market API output                        | `board/board.csv`, `blind/`  |
| Quant         | `blind/`, candle data                           | `fair/`                      |
| Quant (2nd)   | `fair/`, then `board/` (only after `fair/` exists) | candidate list            |
| Tape Reader  | `blind/`, `board/`, live feeds                  | `evidence/`                  |
| Risk          | `fair/`, `board/`, `evidence/`                  | `tickets/`                   |
| Auditor       | `journal/`, resolutions                         | `journal/`                   |

Hard walls
- The Quant never reads `board/` before `fair/<slug>.json` exists.
- `blind/` contains rule text, level, expiry and resolution source. No prices.
- No seat holds a wallet key. `.env` holds read-only API keys only. Orders are placed by a human.
- Rules in `DESK_RULES.md` change only by human approval of an Auditor proposal.
