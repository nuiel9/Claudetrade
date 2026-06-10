# Quincunx — Galton Board Simulation Dashboard

A self-contained dashboard that visualizes the **law of large numbers** using a
biased Galton board (quincunx), styled after a quant trading terminal. Open
`index.html` in any browser — no build step, no dependencies.

## What it shows

- **Animated Galton board**: balls fall through 8 rows of pegs. At each peg a ball
  goes right with probability `p` (the "bias" slider, 0.40–0.60).
- **Probability lattice**: the histogram of where balls land — a binomial
  distribution that shifts right as `p` rises above 0.50.
- **Win-rate convergence**: the running fraction of right-decisions, which
  converges to `p` as the number of balls grows. This is the law of large numbers
  in action — wild for the first few dozen balls, then it locks onto `p`.

## The honest version of the "trading edge" story

The viral pitch this is modeled on claims a biased Galton board is a money-making
trading engine. Here's what's actually true and what isn't:

- **True:** a board with `p = 0.54` genuinely shifts the bell curve right of
  center. Compounding a per-step bias over many independent steps is real
  binomial math.
- **Not true:** real markets are **not** independent coin flips with a fixed,
  harvestable 4¢ edge. Peg outcomes here are independent and the bias is constant
  by construction — markets are neither. A stable edge like that would be
  arbitraged away. "Copy this wallet / paste this link" pitches are copy-trading
  lures, not alpha.

Use this as an **educational probability tool**, not financial advice.

## Run it

```
open index.html      # macOS
xdg-open index.html  # Linux
```

Or serve it: `python3 -m http.server` then visit `http://localhost:8000`.
