[![make.fun · tiny-chess-01](https://make.fun/badge/tiny-chess-01.svg)](https://make.fun/bounty/tiny-chess-01?utm_source=github&utm_medium=readme&utm_campaign=tiny-chess-01)
[![rank](https://make.fun/badge/tiny-chess-01/Iqbalmadani/tiny-chess/rank.svg)](https://make.fun/bounty/tiny-chess-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=tiny-chess-01)
[![reward](https://make.fun/badge/tiny-chess-01/Iqbalmadani/tiny-chess/reward.svg)](https://make.fun/bounty/tiny-chess-01?utm_source=github&utm_medium=readme&utm_campaign=tiny-chess-01)

# tiny-chess-01 — compact alpha-beta chess engine

A self-contained chess engine in a single `main.py` (<= 4,096 bytes),
Python 3.13 standard library only. The readable engine source is packed
with lzma + base85 into the file and unpacked at import; the decompressed
source is the program that plays.

## How it plays

- Negamax search with alpha-beta pruning and iterative deepening over a
  fixed budget of 90,000 nodes per move (never a clock — fully
  deterministic: same position, same move, every run).
- Quiescence search over captures, with in-check evasions generated when
  the side to move is in check (no stand-pat while in check).
- Check extensions, a transposition table, MVV-LVA capture ordering and
  previous-iteration root move ordering.
- Evaluation: material plus piece-square tables, with an endgame king
  table blended in as the phase decreases.

## Protocol

When `MAKEFUN_ENV_URL` is set, the program plays a full gauntlet against
the environment: it requests games with `POST /game` and answers each
position with `POST /move`, choosing among the environment's legal moves
by running the search on the given FEN.

## Practice record

Local practice gauntlet (trial-0 ladder: alpha-beta depth 2/3/4 and
100k/250k/500k-node engines): 1 win, 2 draws, 3 losses, no time forfeits.
