#!/usr/bin/env python3
"""Honest multi-year backtest driver for the coin-hopping strategy.

Wraps binance_trade_bot.backtest.backtest() and produces a year-by-year
summary comparing the strategy against simply holding the starting coin,
holding BTC, and holding the bridge (USDT, i.e. doing nothing).

Honesty caveats of the underlying simulation (inherited from the project):
  - fills at 1-minute kline OPEN prices, no slippage or spread modelling
  - flat 0.075% fee per side (taker fee with BNB discount; 0.1% without)
  - testnet flags are ignored: klines are fetched from the REAL mainnet API
  - klines are cached in data/backtest_cache.db (resumable, can grow to GBs
    over multi-year, multi-coin runs)

Requirements: run with the project environment active, from any directory.
Network access to api.binance.com is required (public endpoints only; dummy
API keys are fine).

Example:
    python scripts/backtest_years.py --start 2021-01-01 --end 2026-10-01 \
        --interval 5 --coins "BTC ETH BNB SOL XRP ADA DOGE LTC TRX"
"""

import argparse
import csv
import os
import sys
from datetime import datetime

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse_args():
    parser = argparse.ArgumentParser(description="Multi-year backtest with HODL benchmarks")
    parser.add_argument("--start", default="2021-01-01", help="start date YYYY-MM-DD (default: 2021-01-01)")
    parser.add_argument("--end", default=None, help="end date YYYY-MM-DD (default: now)")
    parser.add_argument("--interval", type=int, default=5, help="virtual minutes between scouts (default: 5)")
    parser.add_argument("--yield-every", type=int, default=1440, help="yield/report every N intervals (default: 1440)")
    parser.add_argument("--coins", default="BTC ETH BNB SOL XRP ADA DOGE LTC TRX", help="space-separated coin symbols")
    parser.add_argument("--bridge", default="USDT", help="bridge symbol (default: USDT)")
    parser.add_argument("--strategy", default="default", help="default | multiple_coins")
    parser.add_argument("--starting-coin", default=None, help="coin to start on (default: first in list)")
    parser.add_argument("--balance", type=float, default=100.0, help="starting bridge balance (default: 100)")
    parser.add_argument("--scout-multiplier", default="5", help="scout_multiplier setting (default: 5)")
    parser.add_argument("--use-margin", default="no", help="yes to use scout_margin instead of multiplier")
    parser.add_argument("--scout-margin", default="0.8", help="scout_margin percentage (default: 0.8)")
    return parser.parse_args()


def main():
    args = parse_args()

    # The package opens data/ and logs/ paths relative to the CWD at import
    # time, so always run from the repository root, and make the package
    # importable regardless of how Python was invoked.
    os.chdir(REPO_ROOT)
    sys.path.insert(0, REPO_ROOT)
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)

    # Configure via environment before importing the package (environment
    # takes priority over any user.cfg, so a testnet user.cfg cannot leak
    # into the backtest). Dummy API keys are fine: only public kline
    # endpoints are used.
    os.environ.setdefault("API_KEY", "backtest-dummy-key")
    os.environ.setdefault("API_SECRET_KEY", "backtest-dummy-secret")
    os.environ["SUPPORTED_COIN_LIST"] = args.coins
    os.environ["BRIDGE_SYMBOL"] = args.bridge
    os.environ["STRATEGY"] = args.strategy
    os.environ["SCOUT_MULTIPLIER"] = args.scout_multiplier
    os.environ["USE_MARGIN"] = args.use_margin
    os.environ["SCOUT_MARGIN"] = args.scout_margin
    os.environ["TLD"] = "com"
    # Config() crashes without a user.cfg (missing 'current_coin' default);
    # the backtest ignores this value, but Config() must be able to build.
    os.environ["CURRENT_COIN_SYMBOL"] = args.starting_coin or args.coins.split()[0]

    try:
        import requests

        from binance_trade_bot.auto_trader import AutoTrader
        from binance_trade_bot.backtest import backtest as run_backtest
    except ImportError as exc:  # pragma: no cover
        print(f"Missing dependencies ({exc}). Run inside the project environment: pip install -r requirements.txt")
        return 1

    # Count hops (successful bridge jumps) without touching upstream code.
    hops = {"n": 0}
    original_jump = AutoTrader.transaction_through_bridge

    def counting_jump(self, pair):
        result = original_jump(self, pair)
        if result is not None:
            hops["n"] += 1
        return result

    AutoTrader.transaction_through_bridge = counting_jump

    start = datetime.fromisoformat(args.start)
    end = datetime.fromisoformat(args.end) if args.end else datetime.today()
    coins = args.coins.split()
    starting_coin = args.starting_coin or coins[0]

    print(f"Backtest: {start.date()} -> {end.date()}  interval={args.interval}m  strategy={args.strategy}")
    print(f"Coins: {coins}")
    print(f"Fees: flat 0.075% per side, no slippage. Prices: 1m kline opens (mainnet).")
    print(f"Kline cache: data/backtest_cache.db (first run downloads a lot and is resumable)")
    print("-" * 100)

    checkpoints = []  # (label, datetime, usd, btc, hops)
    start_usd = start_btc = None
    start_price = None
    current_year = None

    def checkpoint(manager, label):
        nonlocal start_usd, start_btc, start_price
        usd = manager.collate_coins(manager.config.BRIDGE.symbol)
        btc = manager.collate_coins("BTC")
        price = manager.get_ticker_price(starting_coin + manager.config.BRIDGE.symbol)
        if start_usd is None:
            start_usd, start_btc, start_price = usd, btc, price
        checkpoints.append((label, manager.datetime, usd, btc, price, hops["n"]))
        print(
            f"{label:<12} {str(manager.datetime):<20} "
            f"{manager.config.BRIDGE.symbol}: {usd:>10.2f} ({(usd / start_usd - 1) * 100:+7.2f}%)  "
            f"BTC: {btc:>10.6f} ({(btc / start_btc - 1) * 100:+7.2f}%)  hops: {hops['n']}"
        )

    generator = run_backtest(
        start_date=start,
        end_date=end,
        interval=args.interval,
        yield_interval=args.yield_every,
        start_balances={args.bridge: args.balance},
        starting_coin=starting_coin,
    )

    final_manager = None
    try:
        while True:
            manager = next(generator)
            if current_year is None:
                current_year = manager.datetime.year
                checkpoint(manager, "START")
            elif manager.datetime.year != current_year:
                current_year = manager.datetime.year
                checkpoint(manager, f"{current_year - 1}-END")
            else:
                # light progress heartbeat on every yield
                usd = manager.collate_coins(manager.config.BRIDGE.symbol)
                print(
                    f"  ... {str(manager.datetime):<20} {manager.config.BRIDGE.symbol}: {usd:>10.2f}  hops: {hops['n']}",
                    flush=True,
                )
    except StopIteration as stop:
        final_manager = stop.value
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        print()
        print(f"ERROR: cannot reach api.binance.com ({exc.__class__.__name__}).")
        print("Binance blocks API access from some regions (e.g. US-based servers).")
        print("Run this from a network/host where https://api.binance.com is reachable,")
        print("verify first with:  curl -m 10 https://api.binance.com/api/v3/ping")
        return 2

    if final_manager is not None:
        # The generator closes the shared kline cache when it exits; reopen it
        # so the final collation (END checkpoint) can still read prices.
        import sqlitedict  # project dependency

        bt_module = sys.modules["binance_trade_bot.backtest"]
        bt_module.cache = sqlitedict.SqliteDict("data/backtest_cache.db")
        try:
            checkpoint(final_manager, "END")
        finally:
            bt_module.cache.close()

    # --- summary with HODL benchmarks ---------------------------------------
    print("-" * 100)
    if len(checkpoints) < 2:
        print("Not enough data for a summary (did the run end immediately?)")
        return 1

    first, last = checkpoints[0], checkpoints[-1]
    strategy_pct = (last[2] / first[2] - 1) * 100
    hold_pct = ((last[4] / first[4]) - 1) * 100 if first[4] else float("nan")
    btc_hold_pct = (last[3] / first[3] - 1) * 100

    print(
        f"Strategy (hopping):    {strategy_pct:+8.2f}%  ({first[2]:.2f} -> {last[2]:.2f} {args.bridge}, {hops['n']} hops)"
    )
    print(f"Strategy in BTC terms: {btc_hold_pct:+8.2f}%  (start {first[3]:.6f} -> end {last[3]:.6f} BTC)")
    print(f"Hold {starting_coin}:        {hold_pct:+8.2f}%  (do-nothing benchmark)")
    print(f"Hold {args.bridge}:        {0.0:+8.2f}%  (baseline)")

    os.makedirs("data/backtest_reports", exist_ok=True)
    out_csv = os.path.join("data", "backtest_reports", f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    with open(out_csv, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["label", "datetime", f"{args.bridge}_value", "btc_value", f"{starting_coin}_price", "hops"])
        writer.writerows(checkpoints)
    print(f"\nWrote {out_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
