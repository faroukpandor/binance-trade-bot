#!/usr/bin/env python3
"""Daily health check for a running (or crashed) bot instance.

Checks the bot's own artifacts - SQLite database and log file - and prints a
cron-friendly PASS/WARN/FAIL verdict plus the experiment's day counter
(Day X of 30, per docs/TESTNET-RUNBOOK.md). Pure stdlib; safe to run while
the bot is running (opens the database read-only).

Checks:
  1. database exists and is readable
  2. freshness: value history updated recently (the bot logs values ~1/min)
  3. experiment progress: Day X of 30 from the first recorded value
  4. trades: stuck ORDERED (>24h) or STARTING (>1h) states
  5. log tail: ERROR lines and Binance API access failures
  6. disk: data/ and logs/ sizes (warn if logs are unrotated and huge)

Exit codes: 0 = PASS, 1 = WARN, 2 = FAIL (usable from cron/alerting).

Usage:
    python scripts/healthcheck.py [--db data/crypto_trading.db]
                                  [--log logs/crypto_trading.log] [--quiet]
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timedelta

FRESH_AFTER_MINUTES = 10  # value history is written every minute
STUCK_ORDERED_HOURS = 24
STUCK_STARTING_HOURS = 1
LOG_TAIL_LINES = 2000
LOG_WARN_BYTES = 500 * 1024 * 1024  # unrotated log above 500MB
EXPERIMENT_DAYS = 30

LEVEL_PASS, LEVEL_WARN, LEVEL_FAIL = "PASS", "WARN", "FAIL"
EXIT_CODES = {LEVEL_PASS: 0, LEVEL_WARN: 1, LEVEL_FAIL: 2}


def parse_dt(value):
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def dir_size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def human_bytes(num):
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.1f}{unit}"
        num /= 1024
    return f"{num:.1f}GB"


def main():
    parser = argparse.ArgumentParser(description="Bot health check (PASS/WARN/FAIL)")
    parser.add_argument("--db", default=os.path.join("data", "crypto_trading.db"))
    parser.add_argument("--log", default=os.path.join("logs", "crypto_trading.log"))
    parser.add_argument("--quiet", action="store_true", help="print the summary line only")
    args = parser.parse_args()

    worst = LEVEL_PASS

    def record(level, message):
        nonlocal worst
        if EXIT_CODES[level] > EXIT_CODES[worst]:
            worst = level
        if not args.quiet:
            print(f"[{level}] {message}")

    now = datetime.now()
    day_label = "-"
    trade_summary = "no db"
    error_count = None

    # --- database ----------------------------------------------------------
    first_value = last_value = None
    if not os.path.exists(args.db):
        record(LEVEL_FAIL, f"database not found: {args.db} - has the bot been started?")
    else:
        try:
            conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
            try:
                row = conn.execute("SELECT MIN(datetime), MAX(datetime) FROM coin_value").fetchone()
                first_value, last_value = parse_dt(row[0]), parse_dt(row[1])
            finally:
                conn.close()
        except sqlite3.Error as exc:
            record(LEVEL_FAIL, f"database not readable: {exc}")

        if last_value is not None:
            age_minutes = (now - last_value).total_seconds() / 60
            if age_minutes > FRESH_AFTER_MINUTES:
                record(
                    LEVEL_FAIL,
                    f"value history is stale: last update {int(age_minutes)} min ago "
                    f"(expected <{FRESH_AFTER_MINUTES} min) - is the bot running?",
                )
            else:
                record(LEVEL_PASS, f"value history fresh (updated {int(age_minutes)} min ago)")

            if first_value is not None:
                day = int((last_value - first_value).total_seconds() // 86400) + 1
                day_label = f"day {min(day, EXPERIMENT_DAYS)}/{EXPERIMENT_DAYS}" + (
                    " (due for final review)" if day >= EXPERIMENT_DAYS else ""
                )

        # trades
        try:
            conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
            try:
                by_state = dict(conn.execute("SELECT state, COUNT(*) FROM trade_history GROUP BY state").fetchall())
                stuck_ordered = conn.execute(
                    "SELECT COUNT(*) FROM trade_history WHERE state = 'ORDERED' AND datetime < ?",
                    ((now - timedelta(hours=STUCK_ORDERED_HOURS)).isoformat(sep=" "),),
                ).fetchone()[0]
                stuck_starting = conn.execute(
                    "SELECT COUNT(*) FROM trade_history WHERE state = 'STARTING' AND datetime < ?",
                    ((now - timedelta(hours=STUCK_STARTING_HOURS)).isoformat(sep=" "),),
                ).fetchone()[0]
            finally:
                conn.close()
            total_trades = sum(by_state.values())
            trade_summary = f"trades: {total_trades} {dict(by_state) if by_state else ''}".strip()
            if stuck_ordered:
                record(LEVEL_WARN, f"{stuck_ordered} order(s) stuck in ORDERED for >{STUCK_ORDERED_HOURS}h")
            if stuck_starting:
                record(LEVEL_WARN, f"{stuck_starting} trade(s) stuck in STARTING for >{STUCK_STARTING_HOURS}h")
            if total_trades:
                record(LEVEL_PASS, trade_summary)
        except sqlite3.Error as exc:
            record(LEVEL_WARN, f"could not inspect trade history: {exc}")

    # --- log tail ------------------------------------------------------------
    if os.path.exists(args.log):
        try:
            with open(args.log, "rb") as fh:
                fh.seek(0, os.SEEK_END)
                size = fh.tell()
                fh.seek(max(0, size - 2 * 1024 * 1024))  # read at most the last 2MB
                tail = fh.read().decode("utf-8", errors="replace").splitlines()[-LOG_TAIL_LINES:]
            error_count = sum(1 for line in tail if " - ERROR - " in line)
            if error_count:
                record(LEVEL_WARN, f"{error_count} ERROR line(s) in the last {len(tail)} log lines, e.g.:")
                for line in [line for line in tail if " - ERROR - " in line][-3:]:
                    record(LEVEL_WARN, f"    {line.strip()[:120]}")
            if any("Couldn't access Binance API" in line for line in tail):
                record(LEVEL_WARN, "Binance API access failure found in recent log - check API keys/permissions/geo")
        except OSError as exc:
            record(LEVEL_WARN, f"could not read log: {exc}")
    elif not args.quiet:
        print("[PASS] no log file yet (bot may not have started)")

    # --- disk ----------------------------------------------------------------
    data_size = dir_size(os.path.dirname(args.db) or ".") if os.path.exists(args.db) else 0
    log_size = dir_size(os.path.dirname(args.log) or ".") if os.path.exists(args.log) else 0
    if log_size > LOG_WARN_BYTES:
        record(LEVEL_WARN, f"log directory is {human_bytes(log_size)} - install the rotation cron (runbook A5)")

    summary = (
        f"HEALTH: {worst} | {day_label} | {trade_summary} | "
        f"errors(last {LOG_TAIL_LINES} lines): {error_count if error_count is not None else '-'} | "
        f"data: {human_bytes(data_size)} logs: {human_bytes(log_size)}"
    )
    print(summary)
    return EXIT_CODES[worst]


if __name__ == "__main__":
    sys.exit(main())
