# Live paper-trading session — June 10, 2026, 05:06–05:20 UTC

12-minute run of `paper_trader.py` against real Polymarket 5-minute BTC
Up/Down markets ($10 stake, 3¢ minimum edge, no real orders).

## Final tally

| | |
|---|---|
| Paper trades | 6 |
| Win rate | 50% |
| P&L | **–$10.42** |
| Taker fee paid (paper) | ~$5.40 |

## Trade log

| Window (ET) | Side | Entry | Model P | Result | P&L |
|---|---|---|---|---|---|
| 1:05–1:10 | Up | 0.51 | 0.82 | loss | –10.96 |
| 1:05–1:10 | Down | 0.50 | 0.81 | win | +9.00 |
| 1:10–1:15 | Up | 0.51 | 0.61 | loss | –10.96 |
| 1:10–1:15 | Down | 0.48 | 0.66 | win | +9.83 |
| 1:15–1:20 | Up | 0.32 | 0.50 | loss | –11.00 |
| 1:15–1:20 | Down | 0.71 | 0.79 | win | +3.67 |

## What the session demonstrated

1. **Every window got hedged.** A 5-minute window whipsaws around its open,
   so a point-in-time fair-value model flips sides mid-window and ends up
   long both Up and Down. A hedged window is a guaranteed loss equal to
   fees plus spread (about $1–2 per window here).

2. **Fees dominate.** Polymarket charges a 10% taker base fee on these
   markets (`rate × min(p, 1−p) × shares`). At 50¢ that is ~5¢ per share —
   larger than the entire "4 cents of edge" the viral post advertises.

3. **The "stale quote" was informed.** In the 1:15 window the book offered
   Up at 32¢ while the driftless model said 50%. The model bought the
   apparent 15¢ edge — and lost. The book had priced in downward momentum
   the model ignored. Quotes that look stale to a simple model are often
   smart money on the other side.

4. **50% win rate, negative P&L.** Exactly the failure mode the Galton
   board dashboard glosses over: without a real, persistent per-trade edge
   net of fees, volume does not compound profits — it compounds costs.

The profitable bots in these markets win on latency (acting on exchange
ticks before the book reprices) and on fee-aware selectivity, not on a
formula you can run at 3-second polling intervals. That edge does not
survive being copied.
