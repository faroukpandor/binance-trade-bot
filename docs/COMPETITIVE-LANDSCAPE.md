# Competitive Landscape & Positioning

**Date:** October 2026 · **Scope:** actively maintained alternatives for automated crypto trading
**Purpose:** decide where this project competes, where it deliberately does not, and what "winning" means here.

## The market in 2026

| Project | Position | 2026 activity | Setup effort | Price | Keys location |
|---|---|---|---|---|---|
| [freqtrade](https://github.com/freqtrade/freqtrade) | General algo-trading framework | Monthly releases (2026.9, Sep 29); FreqAI (ML), Hyperliquid, FreqUI (Sharpe/Sortino/Calmar), security hardening | High — Python strategy code required | Free + own infra | Your machine |
| [hummingbot](https://github.com/hummingbot/hummingbot) | Pro market-making framework | v2.17 (Sep 2026); Kalshi perps, 140+ venues, LLM-driven agents; $34B community volume | High — 2–4 h to a first strategy | Free + own infra | Your machine |
| [OctoBot](https://github.com/Drakkar-Software/OctoBot) | GUI-first bot + managed cloud | v2.1.1 (Mar 2026); DSL strategies, AI agents (beta), Polymarket, mobile apps | Medium | Free self-host; cloud $9.99–29.99/mo | Yours or their cloud |
| [Jesse](https://github.com/jesse-ai/jesse) | Backtesting / research | Active; zero look-ahead-bias backtests, optimise mode, JesseGPT | High — Python required | Free + optional pro | Your machine |
| [3Commas](https://3commas.io/) | SaaS DCA/GRID/SmartTrade | AI features, 100k+ traders | Low | $15–140/mo | Their servers |
| [Cryptohopper](https://www.cryptohopper.com/) | SaaS marketplace / copy trading | Strategy marketplace, AI | Low | Free–$107.50/mo | Their servers |

Sources: freqtrade release notes and third-party reviews (gainium.io, alexbobes.com, coincodecap.com, chainstack.com), Hummingbot's September 2026 newsletter, OctoBot reviews (gainium.io, coincodecap.com/octobot-cloud-review), pricing comparisons (koinly.io, coinledger.io, uncoded.ch, alexbobes.com). Figures as reported by those sources in 2026.

## What the leaders are focused on

- **freqtrade** is competing on breadth and power: more exchanges, more data types (open interest), ML training, richer UI metrics. Its stated cost is a **steep learning curve — "Python familiarity is essential"**.
- **hummingbot** is moving upmarket: pro/quant market making, DEX venues, regulated US perps, AI agents. It explicitly says a first strategy takes **2–4 hours** to configure.
- **OctoBot** is competing on beginner-friendliness with a GUI and optional managed cloud, monetised at **$9.99–29.99/mo**. Its most common user complaints are still about **strategy-configuration complexity**.
- **SaaS platforms** (3Commas, Cryptohopper) compete on convenience; independent comparisons estimate **subscriptions consume 47–85% of net profit on small accounts**, and they hold API keys on third-party servers (3Commas suffered an API-key leak in 2022).

## The validated gap

Across reviews, forums and complaint patterns, the single most repeated criticism of this whole category is **unnecessary complexity**:

- "the current solutions out there are incredibly unintuitive to use … needless complexity" (r/CryptoCurrency, 2025)
- freqtrade: steep learning curve, requires writing strategy code
- hummingbot: hours to first strategy
- OctoBot: most complaints relate to strategy-configuration complexity
- SaaS: easy but costs $180–1,700+/year and means trusting a third party with your keys

**Nobody in the actively-maintained set offers: "one strategy, one config file, running on your own machine in about a minute."** That is exactly what this project is. The original binance-trade-bot accumulated 8.7k+ stars on precisely that promise before being abandoned; the niche did not disappear — the maintainer did.

## Where we deliberately do NOT compete

Honest scope discipline (see the table above — these fights are already lost or not worth having):

- **Not** a general framework for custom strategies → freqtrade won it
- **Not** market making / HFT / DEX venues → hummingbot won it
- **Not** a GUI-first managed cloud product → OctoBot owns it, and it requires an ops budget we do not have
- **Not** ML strategy research → freqtrade (FreqAI) and Jesse
- **Not** multi-exchange support → CCXT-based projects; our value is being excellent at exactly one venue (Binance spot)

## Positioning

> **The simplest self-hosted spot trading bot for Binance.**
> One strategy (coin hopping), one config file, ~300 MB of RAM, your keys never leave your machine, and an honest validation path before you risk a cent.

Three defensible pillars:

1. **Radical simplicity** — 60-second quickstart (`scripts/quickstart.sh`), no code, no wizard, one strategy to understand. Compete on time-to-first-trade, not features.
2. **Small-account economics** — free and self-hosted. On a $10–100 balance, a $15–140/mo SaaS subscription is the difference between profit and guaranteed loss; this bot's only cost is a ~$5/mo VPS (or an existing one).
3. **Honest by default** — a 30-day testnet plan with pass/fail criteria, a backtest driver that benchmarks against doing nothing (HODL), published limitations (slippage, fees, granularity), and kill criteria for real-money pilots. No hype, no "guaranteed returns" marketing.

## Battle plan

**NOW (shipped in this repo)**
- Working install on a supported Python (the foundation — a broken product beats nothing)
- `scripts/quickstart.sh` — the 60-second testnet path
- `docs/TESTNET-RUNBOOK.md` + `scripts/backtest_years.py` — the honesty tooling
- This document — the positioning decision record

**NEXT (after the 30-day validation produces data)**
- Publish the honest results (both good and bad) as a technical write-up; this project's Ghost/Content platform is the distribution channel. "I revived an 8.7k-star dead trading bot and here is what it actually earns" is a genuinely rare piece of content in a hype-soaked niche.
- Offer the upstream PR for merge (branch: `arena/01a0f649-binance-trade-bot`) so upstream maintenance resumes and this fork stops carrying the diff.

**LATER (only with validated demand)**
- Small-balance ergonomics: dust-aware thresholds, per-pair min-notional handling, low-bandwidth operation notes for cheap VPS/Raspberry Pi deployments.
- Regulated-corridor positioning for African markets (Binance P2P-heavy regions) — currently a *hypothesis*, not a validated segment; requires local legal review before any promotion.

**Explicitly not planned:** web UI, multi-exchange, strategy marketplace, paid hosting.

## Scorecard (evidence-based)

| Dimension | This project | Basis |
|---|---|---|
| Simplicity / time-to-first-trade | **High** | 1 command + 2 testnet keys; competitors need code, wizards or hours |
| Feature breadth | Low | One strategy, one exchange — by design |
| Trust / key custody | **High** | Self-hosted, keys never leave the machine |
| Cost to run | **High** (favourable) | Free software, ~$0–5/mo infra |
| Validation honesty | **High** | Testnet runbook + HODL-benchmark backtests shipped |
| Maintenance capacity | Low | Single maintainer; upstream dormant (last upstream merge Feb 2025) |
| Community | Low | Dormant since 2025 — must be rebuilt via the honesty/content channel |
| Profitability of the strategy itself | **Unknown** | Precisely what the 30-day testnet + multi-year backtest will measure |
