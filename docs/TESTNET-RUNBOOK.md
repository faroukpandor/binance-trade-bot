# 30-Day Testnet Run + Honest Backtest — Runbook

This is the operational plan for validating the bot before any real money is
used. It has two independent parts:

> **Fast path:** `./scripts/quickstart.sh` automates steps A1–A4 (config
> generation, coin-list trim, stack start). Read this runbook for the full
> plan, the caveats and the decision criteria.

| Part | Question it answers | Environment | Cost |
|---|---|---|---|
| A. 30-day testnet run | Does the bot *function* 24/7 — connect, scout, place orders, survive restarts, respect min-notional? | Binance **spot testnet** (fake funds) | 0 |
| B. Multi-year backtest | Does the *strategy* make money net of fees vs just holding? | Real mainnet 1-minute klines | 0 |

**Important:** the testnet has synthetic order books, so testnet profit/loss is
meaningless. Part A validates mechanics only. Part B is the only profitability
signal. Real money (even 10 USDT) enters only after both parts pass (Part C).

---

## Part A — 30-day testnet run (automated, 24/7)

### A1. Get testnet API keys

1. Go to <https://testnet.binance.vision> and log in with GitHub.
2. Generate an HMAC key pair. Testnet balances are pre-funded with fake assets.
3. Note the keys somewhere temporary — you will paste them into `user.cfg`.

Caveats: Binance periodically resets testnet data. If the bot suddenly reports
zero balances mid-run, log back into the testnet page, regenerate keys if
needed, and restart the stack. This is a testnet quirk, not a bot failure.

### A2. Pre-flight: check Binance reachability from your server

Binance geo-blocks API access by IP from some jurisdictions (e.g. US-based
servers are blocked for `binance.com`). Before choosing where to run the bot:

```bash
curl -m 10 https://api.binance.com/api/v3/ping && echo MAINNET_OK
curl -m 10 https://testnet.binance.vision/api/v3/ping && echo TESTNET_OK
```

Both must return quickly. If not, use a server in a region where Binance is
reachable. Reuse an existing VPS (e.g. the one hosting your Ghost site — the
bot is small: <300 MB RAM, near-zero CPU while scouting) or a free-tier VM
(e.g. Oracle Cloud Always Free ARM).

### A3. Configure (5 minutes, once)

From the repository root:

```bash
cp .user.cfg.example user.cfg
```

Edit `user.cfg` — the essential fields for the testnet run:

```ini
[binance_user_config]
api_key=PASTE_TESTNET_KEY
api_secret_key=PASTE_TESTNET_SECRET
testnet=true          # <-- THIS LINE IS THE WHOLE POINT. Set it to true.
current_coin=BTC
bridge=USDT
tld=com
scout_sleep_time=1
use_margin=no
scout_multiplier=5
strategy=default
buy_timeout=20
sell_timeout=20
```

**Do not set `TESTNET` as an environment variable.** Due to a quirk in
`config.py`, any non-empty value (even the string `"false"`) enables testnet.
The `testnet=true` line in `user.cfg` is parsed correctly as a boolean. Using
the config file is the safe path. (Fails safe: the quirk can only ever
unexpectedly enable testnet, never unexpectedly enable mainnet.)

Trim `supported_coin_list` to ~10 liquid coins (the testnet lists fewer
symbols than mainnet, and the backtest in Part B gets much cheaper):

```
BTC
ETH
BNB
SOL
XRP
ADA
DOGE
LTC
TRX
```

Optional — Telegram notifications when the bot trades: create a bot with
@BotFather, get a chat id (message your bot, then check
`https://api.telegram.org/bot<TOKEN>/getUpdates`), then:

```bash
cp config/apprise_example.yml config/apprise.yml
# edit config/apprise.yml and uncomment/add:
#   urls:
#     - tgram://<TOKEN>/<CHAT_ID>
```

### A4. Launch (Docker, survives reboots and crashes)

```bash
docker compose -f docker-compose.testnet.yml up -d --build
docker logs -f binance_trader_testnet   # watch the first few minutes
```

You should see, in order: `Starting` → `Chosen strategy: default` →
`Creating database schema` → `Setting initial coin to BTC` →
`I am scouting the best trades. Current coin: BTCUSDT`.

The stack: `restart: unless-stopped` on both services, the API is bound to
`127.0.0.1:5123` only (it is unauthenticated — never expose it), state lives in
`./data/crypto_trading.db`, logs in `./logs/`.

No Docker? Bare-metal works too:

```bash
python3 -m venv venv && venv/bin/pip install -r requirements.txt
mkdir -p data logs
venv/bin/python -m binance_trade_bot     # in tmux/screen/systemd
```

### A5. Install the automation crontab (5 minutes, once)

The bot prunes its own history (hourly value snapshots kept 28 days, daily 1
year, trades forever) but does **not** rotate logs or watch itself. Install
the prepared crontab instead of hand-writing lines — it adds a daily health
check, a weekly report snapshot, log rotation and a 30-day-rotation database
backup:

```bash
cp scripts/cron.example /tmp/mycron
# edit /tmp/mycron: replace /path/to/binance-trade-bot and /path/to/backups
crontab -l 2>/dev/null | cat - /tmp/mycron | crontab -
crontab -l   # verify
```

The health check (`scripts/healthcheck.py`, pure stdlib) prints
`PASS/WARN/FAIL` plus a `Day X of 30` counter and exits 0/1/2 — wire the exit
code to your favourite notifier if you want alerts, or just read
`logs/healthcheck.log` when curious.

### A6. Weekly and final measurement

Daily status (also runs automatically via the crontab above):

```bash
python scripts/healthcheck.py
```

Full progress report, any time, from the repository root:

```bash
python scripts/report.py --csv data/report_$(date +%F).csv
```

It prints the held coin, trade count and states, last trades, and portfolio
value start/end/peak/trough (testnet values — remember: mechanics, not
profit), and writes a CSV time series. There is also the HTTP API on the
server (`ssh -L 5123:127.0.0.1:5123 user@server`, then open
`http://127.0.0.1:5123/api/total_value_history`).

### A7. What "passing" looks like after 30 days

- 0 unhandled crashes (`docker ps` shows both containers `Up`, restarts rare)
- orders actually placed and filled on the testnet (check trades in the report)
- `Couldn't access Binance API` / websocket errors: none after initial startup
- min-notional skips behave sanely (logged, no crash loop)
- database grew modestly, backups exist

---

## Part B — Honest backtest 2021–2026

Run from the repository root with the project environment active (inside the
Docker image: `docker run --rm -it -v $PWD/data:/app/data
binance-trade-bot:local python scripts/backtest_years.py ...`).

Long run at 5-minute scouting resolution (first run downloads ~5 years of
1-minute klines per coin — hours, several GB in `data/backtest_cache.db`,
resumable; later runs are fast):

```bash
python scripts/backtest_years.py --start 2021-01-01 --interval 5 \
  --coins "BTC ETH BNB SOL XRP ADA DOGE LTC TRX"
```

Fidelity run on the recent market only (1-minute resolution):

```bash
python scripts/backtest_years.py --start 2026-04-01 --interval 1 \
  --coins "BTC ETH BNB SOL XRP ADA DOGE LTC TRX"
```

It prints year-by-year checkpoints and a final verdict: strategy % vs holding
the starting coin vs holding BTC vs holding USDT. Results land in
`data/backtest_reports/run_<timestamp>.csv`.

**Known limitations of the simulation (be honest with yourself):**
fills at 1-minute kline open prices; no slippage or spread; flat 0.075%/side
fee (0.1% without BNB); the `multiple_coins` strategy and any parameter set
you didn't test are different experiments. A result that only wins in one
year is noise.

---

## Part C — Only then: a 10 USDT mainnet pilot

If (and only if) Part A passed mechanically **and** Part B shows the strategy
beating both USDT-hold and BTC-hold net of fees across most years:

1. **Security first:** create a new mainnet API key with *Enable Reading* +
   *Enable Spot Trading* only, **withdrawals disabled**, and — if your server
   IP is static — IP-restricted to it. Never commit `user.cfg`.
2. Create a **separate** `user.cfg` (copy again from `.user.cfg.example`)
   with `testnet=false` and the mainnet key.
3. Run with the mainnet compose file: `docker compose up -d --build`
   (it is identical except it uses whatever `user.cfg` says).
4. **Know the floor:** with 10 USDT the bot trades one coin at a time; most
   USDT pairs require a minimum order of ~5 USDT. A couple of losing hops
   can drop you below that floor and the bot will simply stop trading (it
   logs `Skipping sell`) — funds stay safe, but the experiment ends. 10 USDT
   is a tuition budget, not a profit expectation.
5. **Kill criteria:** stop the bot and end the experiment if the balance
   drops below ~7 USDT (−30%), or if it makes fewer than ~2 trades in 2
   weeks (fee threshold too high for the regime), or if any error loop
   appears in logs.

---

## Teardown / archiving

```bash
docker compose -f docker-compose.testnet.yml down
```

Keep `data/crypto_trading.db`, the `data/report_*.csv` files and
`data/backtest_reports/` — they are the experiment's actual output (the only
durable asset this project produces). Delete testnet API keys on the testnet
page. Everything can be deleted afterwards; the knowledge cannot.
