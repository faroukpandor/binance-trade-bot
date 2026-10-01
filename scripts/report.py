#!/usr/bin/env python3
"""Summarise a bot database (data/crypto_trading.db) for the 30-day experiment.

Reads the SQLite database the trading bot writes to and prints:
  - the covered time range and row counts
  - the currently held coin and for how long
  - trade statistics and the most recent trades
  - portfolio value (USD/BTC) at start, end, peak and trough
  - optionally writes a CSV time series of portfolio value

Pure stdlib - no project dependencies required. Safe to run while the bot is
running (SQLite readers do not block the writer).

Usage:
    python scripts/report.py [--db data/crypto_trading.db] [--csv out.csv] [--top 10]
"""

import argparse
import csv
import os
import sqlite3
import sys
from datetime import datetime

DEFAULT_DB = os.path.join("data", "crypto_trading.db")


def parse_args():
    parser = argparse.ArgumentParser(description="Summarise the trading bot database")
    parser.add_argument("--db", default=DEFAULT_DB, help=f"path to the SQLite database (default: {DEFAULT_DB})")
    parser.add_argument("--csv", default=None, help="optional path to write a portfolio value time series CSV")
    parser.add_argument("--top", type=int, default=10, help="how many recent trades to list (default: 10)")
    return parser.parse_args()


def fmt_dt(value):
    if value is None:
        return "-"
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return str(value)


def fmt_num(value):
    if value is None:
        return "-"
    return f"{value:,.2f}"


def pct(first, last):
    if not first:
        return "-"
    return f"{(last - first) / first * 100:+.2f}%"


def load_series(conn):
    """Portfolio value per distinct timestamp.

    usd_price is NULL for the bridge coin itself (e.g. USDTUSDT does not exist),
    so its USD value is simply its balance.
    """
    rows = conn.execute(
        """
        SELECT datetime,
               SUM(CASE WHEN usd_price IS NULL THEN balance ELSE balance * usd_price END) AS usd,
               SUM(CASE WHEN btc_price IS NULL THEN NULL ELSE balance * btc_price END) AS btc
        FROM coin_value
        GROUP BY datetime
        ORDER BY datetime
        """
    ).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


def main():
    args = parse_args()

    if not os.path.exists(args.db):
        print(f"No database found at {args.db}. Has the bot been started?")
        return 1

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required = {"coins", "coin_value", "trade_history", "current_coin_history"}
    if not required.issubset(tables):
        print(f"Database at {args.db} is missing tables {required - tables}; it may not be a bot database.")
        return 1

    print("=" * 64)
    print(f"REPORT: {args.db}")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 64)

    # --- covered range -------------------------------------------------------
    counts = {
        "coin_value": conn.execute("SELECT COUNT(*) FROM coin_value").fetchone()[0],
        "trade_history": conn.execute("SELECT COUNT(*) FROM trade_history").fetchone()[0],
        "current_coin_history": conn.execute("SELECT COUNT(*) FROM current_coin_history").fetchone()[0],
    }
    print(f"\nRows: {counts}")

    # --- current coin --------------------------------------------------------
    row = conn.execute("SELECT coin_id, datetime FROM current_coin_history ORDER BY datetime DESC LIMIT 1").fetchone()
    if row:
        held_since = fmt_dt(row[1])
        try:
            held_for = datetime.now() - datetime.fromisoformat(row[1])
            held_for_s = f" ({str(held_for).split('.')[0]} ago)"
        except (ValueError, TypeError):
            held_for_s = ""
        print(f"\nCurrently held coin: {row[0]} (set {held_since}{held_for_s})")
    else:
        print("\nCurrently held coin: -")

    # --- trades --------------------------------------------------------------
    total = counts["trade_history"]
    by_state = dict(conn.execute("SELECT state, COUNT(*) FROM trade_history GROUP BY state").fetchall())
    print(f"\nTrades: {total}  by state: {by_state or '-'}")

    if total:
        print(f"\nLast {args.top} trades:")
        print(f"  {'datetime':<17} {'from':<6} {'to':<6} {'side':<6} {'state':<9}")
        trades = conn.execute(
            """
            SELECT datetime, alt_coin_id, crypto_coin_id, selling, state
            FROM trade_history ORDER BY datetime DESC LIMIT ?
            """,
            (args.top,),
        ).fetchall()
        for t in trades:
            side = "SELL" if t[3] else "BUY"
            print(f"  {fmt_dt(t[0]):<17} {str(t[1] or '-'):<6} {str(t[2] or '-'):<6} {side:<6} {str(t[4] or '-'):<9}")

    # --- portfolio value -----------------------------------------------------
    series = load_series(conn)
    if not series:
        print("\nNo value history recorded yet (the bot logs values once per minute).")
        conn.close()
        return 0

    first, last = series[0], series[-1]
    usd_vals = [s[1] for s in series if s[1] is not None]
    peak = max(usd_vals) if usd_vals else None
    trough = min(usd_vals) if usd_vals else None

    print(f"\nPortfolio value over {len(series)} snapshots:")
    print(f"  window:  {fmt_dt(first[0])}  ->  {fmt_dt(last[0])}")
    print(f"  USD:     start {fmt_num(first[1])}  end {fmt_num(last[1])}  ({pct(first[1], last[1])})")
    if peak is not None and trough is not None:
        print(f"           peak {fmt_num(peak)}  trough {fmt_num(trough)}")
    if first[2] is not None and last[2] is not None:
        print(f"  BTC:     start {fmt_num(first[2])}  end {fmt_num(last[2])}  ({pct(first[2], last[2])})")

    if args.csv:
        os.makedirs(os.path.dirname(os.path.abspath(args.csv)), exist_ok=True)
        with open(args.csv, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["datetime", "usd_value", "btc_value"])
            writer.writerows(series)
        print(f"\nWrote time series to {args.csv}")

    conn.close()
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
