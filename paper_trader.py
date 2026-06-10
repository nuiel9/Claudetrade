#!/usr/bin/env python3
"""Paper-trading simulator for Polymarket's 5-minute BTC Up/Down markets.

Educational tool — no orders are placed and no wallet is involved. It
demonstrates the mechanics behind the "fair value vs. book" edge:

  1. Stream BTC spot from Coinbase (Chainlink proxy; basis risk is real).
  2. Estimate short-horizon volatility from recent returns (EWMA).
  3. Model P(Up) = Phi( ln(S/K) / (sigma * sqrt(tau)) ) for the live window,
     where K is the window's opening price and tau is seconds remaining.
  4. Compare the model probability against the CLOB best ask for Up and
     Down. When the model says a share is underpriced by more than
     EDGE_THRESHOLD (after taker fees), record a paper trade.
  5. At window close, settle against the spot snapshot and log P&L.

Run:  python3 paper_trader.py [--minutes 15] [--stake 10] [--edge 0.04]
Logs: trades.ndjson (one JSON object per paper trade)
"""

import argparse
import json
import math
import time
import urllib.request
from collections import deque
from datetime import datetime, timezone

COINBASE_SPOT = "https://api.coinbase.com/v2/prices/BTC-USD/spot"
GAMMA_EVENT = "https://gamma-api.polymarket.com/events?slug=btc-updown-5m-{ts}"
CLOB_BOOK = "https://clob.polymarket.com/book?token_id={tid}"
WINDOW_SECS = 300
POLL_SECS = 3.0


def http_json(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "paper-trader-edu/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def spot_price():
    return float(http_json(COINBASE_SPOT)["data"]["amount"])


def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


class VolEstimator:
    """EWMA volatility of log returns, expressed per sqrt(second)."""

    def __init__(self, halflife_secs=120.0):
        self.alpha = 1 - math.exp(math.log(0.5) / halflife_secs)
        self.var_per_sec = None
        self.last = None  # (t, price)

    def update(self, t, price):
        if self.last is not None:
            t0, p0 = self.last
            dt = max(t - t0, 1e-9)
            r = math.log(price / p0)
            inst_var = (r * r) / dt
            if self.var_per_sec is None:
                self.var_per_sec = inst_var
            else:
                a = 1 - (1 - self.alpha) ** dt
                self.var_per_sec = (1 - a) * self.var_per_sec + a * inst_var
        self.last = (t, price)

    def sigma(self):
        if self.var_per_sec is None or self.var_per_sec <= 0:
            return None
        return math.sqrt(self.var_per_sec)


def model_p_up(spot, open_price, secs_left, sigma):
    if sigma is None or secs_left <= 0:
        return None
    denom = sigma * math.sqrt(secs_left)
    if denom < 1e-12:
        return 1.0 if spot >= open_price else 0.0
    return norm_cdf(math.log(spot / open_price) / denom)


def fetch_market(window_start):
    evs = http_json(GAMMA_EVENT.format(ts=window_start))
    if not evs:
        return None
    m = evs[0]["markets"][0]
    up_id, down_id = json.loads(m["clobTokenIds"])
    fee_bps = int(m.get("takerBaseFee") or 0)
    return {"question": m["question"], "up": up_id, "down": down_id,
            "fee_rate": fee_bps / 10000.0}


def best_ask(token_id):
    book = http_json(CLOB_BOOK.format(tid=token_id))
    asks = book.get("asks") or []
    if not asks:
        return None, 0.0
    top = asks[-1]  # CLOB sorts asks descending; last entry is best
    return float(top["price"]), float(top["size"])


def taker_fee(price, shares, fee_rate):
    # Polymarket fee formula: rate * min(p, 1-p) * shares
    return fee_rate * min(price, 1 - price) * shares


def log_trade(path, rec):
    with open(path, "a") as f:
        f.write(json.dumps(rec) + "\n")


def run(minutes, stake, edge_threshold, log_path):
    vol = VolEstimator()
    open_positions = []  # settle at their window's end
    stats = {"trades": 0, "wins": 0, "pnl": 0.0}
    deadline = time.time() + minutes * 60
    window_start = None
    window_open_price = None
    market = None
    traded_sides = set()  # one paper trade per side per window

    print(f"paper trader | stake=${stake} edge>{edge_threshold:.2f} "
          f"run={minutes}min | NO REAL ORDERS")

    while time.time() < deadline or open_positions:
        now = time.time()
        try:
            s = spot_price()
        except Exception as e:
            print(f"  spot feed error: {e}; retrying")
            time.sleep(POLL_SECS)
            continue
        vol.update(now, s)

        ws = int(now // WINDOW_SECS) * WINDOW_SECS
        if ws != window_start:
            window_start = ws
            window_open_price = s  # our snapshot of the window open
            traded_sides = set()
            market = None
            try:
                market = fetch_market(ws)
            except Exception as e:
                print(f"  market lookup failed: {e}")
            if market:
                print(f"\n[{datetime.now(timezone.utc):%H:%M:%S}] window "
                      f"{ws} | {market['question']} | open≈{s:,.2f} "
                      f"fee={market['fee_rate']:.0%}")

        # settle any positions whose window ended
        still_open = []
        for pos in open_positions:
            if now >= pos["window_end"]:
                up_won = s >= pos["open_price"]
                won = (pos["side"] == "Up") == up_won
                payout = pos["shares"] if won else 0.0
                pnl = payout - pos["cost"] - pos["fee"]
                stats["trades"] += 1
                stats["wins"] += won
                stats["pnl"] += pnl
                wr = stats["wins"] / stats["trades"] * 100
                rec = {**pos, "close_price": s, "won": won,
                       "pnl": round(pnl, 4), "ts_settled": int(now)}
                log_trade(log_path, rec)
                print(f"  SETTLE {pos['side']:4s} {'WIN ' if won else 'LOSS'} "
                      f"pnl={pnl:+.2f} | total {stats['trades']} trades, "
                      f"{wr:.0f}% wr, P&L {stats['pnl']:+.2f}")
            else:
                still_open.append(pos)
        open_positions = still_open

        # look for edge in the live window (stop entering near the close,
        # where real fills are impossible anyway)
        secs_left = window_start + WINDOW_SECS - now
        entering = time.time() < deadline and market and secs_left > 20
        p_up = model_p_up(s, window_open_price, secs_left, vol.sigma())
        if entering and p_up is not None:
            for side, tid, p_model in (("Up", market["up"], p_up),
                                       ("Down", market["down"], 1 - p_up)):
                if side in traded_sides:
                    continue
                try:
                    ask, size = best_ask(tid)
                except Exception:
                    continue
                if ask is None or ask <= 0 or ask >= 1:
                    continue
                shares = min(stake / ask, size)
                fee = taker_fee(ask, shares, market["fee_rate"])
                ev_edge = p_model - ask - (fee / max(shares, 1e-9))
                if ev_edge > edge_threshold and shares * ask >= 1:
                    pos = {"window_start": window_start,
                           "window_end": window_start + WINDOW_SECS,
                           "question": market["question"], "side": side,
                           "entry_ask": ask, "shares": round(shares, 2),
                           "cost": round(shares * ask, 4),
                           "fee": round(fee, 4),
                           "model_p": round(p_model, 4),
                           "open_price": window_open_price,
                           "spot_at_entry": s, "ts_entry": int(now)}
                    open_positions.append(pos)
                    traded_sides.add(side)
                    print(f"  PAPER BUY {side:4s} @{ask:.2f} x{shares:.1f} "
                          f"model_p={p_model:.2f} edge={ev_edge:+.3f} "
                          f"spot={s:,.2f} t-{secs_left:.0f}s")

        time.sleep(POLL_SECS)

    wr = stats["wins"] / stats["trades"] * 100 if stats["trades"] else 0.0
    print(f"\ndone | {stats['trades']} paper trades | win rate {wr:.0f}% | "
          f"P&L {stats['pnl']:+.2f} | log: {log_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--minutes", type=float, default=15)
    ap.add_argument("--stake", type=float, default=10.0)
    ap.add_argument("--edge", type=float, default=0.04,
                    help="required model-vs-ask edge after fees")
    ap.add_argument("--log", default="trades.ndjson")
    a = ap.parse_args()
    run(a.minutes, a.stake, a.edge, a.log)
