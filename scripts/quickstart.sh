#!/usr/bin/env bash
# 60-second TESTNET quickstart for binance-trade-bot.
#
# Generates user.cfg (testnet mode), optionally trims the supported coin
# list to liquid pairs, and boots the Docker testnet stack. Run from
# anywhere inside the repository:
#
#     ./scripts/quickstart.sh                 # interactive + start
#     ./scripts/quickstart.sh --no-start      # write config only
#
# Non-interactive (keys via env):
#     TESTNET_API_KEY=... TESTNET_API_SECRET_KEY=... ./scripts/quickstart.sh
#
# Testnet keys are free: https://testnet.binance.vision (log in with GitHub).
set -euo pipefail

cd "$(dirname "$0")/.."

CONFIG_FILE="user.cfg"
COIN_FILE="supported_coin_list"
COMPOSE_FILE="docker-compose.testnet.yml"

LIQUID_COINS="BTC
ETH
BNB
SOL
XRP
ADA
DOGE
LTC
TRX"

say() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }

say "binance-trade-bot :: 60-second TESTNET quickstart"
echo "Fake funds, zero risk. Free keys: https://testnet.binance.vision (log in with GitHub)"

# --- 1. user.cfg -------------------------------------------------------------
if [[ -f "$CONFIG_FILE" ]]; then
    say "$CONFIG_FILE already exists - keeping it (delete it to regenerate)"
else
    API_KEY="${TESTNET_API_KEY:-}"
    API_SECRET="${TESTNET_API_SECRET_KEY:-}"
    if [[ -z "$API_KEY" || -z "$API_SECRET" ]]; then
        echo
        read -r -p "Testnet API key: " API_KEY || true
        read -r -s -p "Testnet API secret: " API_SECRET || true
        echo
    fi
    if [[ -z "$API_KEY" || -z "$API_SECRET" ]]; then
        echo "No keys provided." >&2
        echo "Get free testnet keys at https://testnet.binance.vision, then re-run" >&2
        echo "(set TESTNET_API_KEY / TESTNET_API_SECRET_KEY or answer the prompts)." >&2
        exit 1
    fi
    # user.cfg contains secrets: create it with owner-only permissions
    (umask 177 && cat > "$CONFIG_FILE" <<EOF
[binance_user_config]
api_key=$API_KEY
api_secret_key=$API_SECRET
# Starting coin (empty = the bot picks one)
current_coin=BTC
# THE POINT OF THE QUICKSTART: fake-money testnet
testnet=true
bridge=USDT
tld=com
scout_sleep_time=1
use_margin=no
scout_multiplier=5
strategy=default
buy_timeout=20
sell_timeout=20
EOF
    )
    say "Wrote $CONFIG_FILE (testnet=true, owner-only permissions)"
fi

# --- 2. trim the coin list ---------------------------------------------------
# The shipped list contains illiquid/delisted-era coins (BTTC etc.).
# If it still looks stock, offer a trim to 9 liquid USDT pairs.
if [[ -f "$COIN_FILE" ]] && grep -qx "BTTC" "$COIN_FILE"; then
    read -r -p "Trim supported_coin_list to 9 liquid coins (recommended)? [Y/n] " ANSWER || true
    ANSWER="${ANSWER:-Y}"
    if [[ "${ANSWER,,}" == "y" ]]; then
        cp "$COIN_FILE" "$COIN_FILE.bak"
        printf '%s\n' "$LIQUID_COINS" > "$COIN_FILE"
        say "Trimmed $COIN_FILE (backup: $COIN_FILE.bak)"
    fi
else
    say "$COIN_FILE already customised - keeping it"
fi

# --- 3. start ----------------------------------------------------------------
if [[ "${1:-}" == "--no-start" || "${SKIP_START:-0}" == "1" ]]; then
    say "Config written. Start the bot later with:"
    echo "    docker compose -f $COMPOSE_FILE up -d --build"
    echo "Then follow: docs/TESTNET-RUNBOOK.md"
    exit 0
fi

if ! command -v docker >/dev/null 2>&1; then
    echo >&2
    echo "Docker not found." >&2
    echo "  - Install Docker and re-run, or" >&2
    echo "  - use config-only mode:  ./scripts/quickstart.sh --no-start" >&2
    exit 1
fi

say "Building and starting the testnet stack (first build takes a few minutes)..."
docker compose -f "$COMPOSE_FILE" up -d --build

say "RUNNING. Useful commands:"
echo "    docker logs -f binance_trader_testnet   # live log"
echo "    python scripts/report.py                # progress summary"
echo "    docker compose -f $COMPOSE_FILE down    # stop"
echo
echo "First run should show: Starting -> Chosen strategy: default ->"
echo "'I am scouting the best trades'. Full 30-day plan: docs/TESTNET-RUNBOOK.md"
