"""Tests for the API server period filter and default configuration."""

from datetime import datetime, timedelta

from binance_trade_bot.api_server import app, filter_period
from binance_trade_bot.config import Config
from binance_trade_bot.models import CoinValue


class FakeQuery:  # pylint: disable=too-few-public-methods
    """Minimal stand-in for a SQLAlchemy query object."""

    def __init__(self):
        self.filters = []

    def filter(self, *criteria):
        self.filters.append(criteria)
        return self


def applied_cutoff_delta(period):
    """Return (now - cutoff) for the filter that `period` produces."""
    query = FakeQuery()
    with app.test_request_context(f"/?period={period}"):
        result = filter_period(query, CoinValue)
    assert result is query
    assert len(query.filters) == 1
    criterion = query.filters[0][0]
    return datetime.now() - criterion.right.value


def test_period_all_returns_unfiltered_query():
    query = FakeQuery()
    with app.test_request_context("/?period=all"):
        result = filter_period(query, CoinValue)
    assert result is query
    assert query.filters == []


def test_invalid_period_returns_unfiltered_query():
    query = FakeQuery()
    with app.test_request_context("/?period=notaperiod"):
        result = filter_period(query, CoinValue)
    assert result is query
    assert query.filters == []


def test_period_days_is_honoured():
    # Regression: the period used to be parsed from a hardcoded "1d", so
    # every request filtered only a single unit regardless of the amount
    delta = applied_cutoff_delta("7d")
    assert timedelta(days=7) - timedelta(seconds=1) < delta < timedelta(days=7) + timedelta(minutes=1)


def test_period_hours_is_honoured():
    delta = applied_cutoff_delta("12h")
    assert timedelta(hours=12) - timedelta(seconds=1) < delta < timedelta(hours=12) + timedelta(minutes=1)


def test_period_weeks_is_honoured():
    delta = applied_cutoff_delta("2w")
    assert timedelta(weeks=2) - timedelta(seconds=1) < delta < timedelta(weeks=2) + timedelta(minutes=1)


def test_period_months_is_honoured():
    delta = applied_cutoff_delta("3m")
    assert timedelta(days=84) - timedelta(seconds=1) < delta < timedelta(days=84) + timedelta(minutes=1)


def test_config_defaults_when_no_user_cfg(tmp_path, monkeypatch):
    # Regression: Config() used to raise NoOptionError ('api_key') when
    # user.cfg was missing, immediately after printing
    # "Assuming default config..."
    env_vars = [
        "API_KEY",
        "API_SECRET_KEY",
        "BRIDGE_SYMBOL",
        "TESTNET",
        "HOURS_TO_KEEP_SCOUTING_HISTORY",
        "SCOUT_MULTIPLIER",
        "SCOUT_SLEEP_TIME",
        "SUPPORTED_COIN_LIST",
        "CURRENT_COIN_SYMBOL",
        "STRATEGY",
        "SELL_TIMEOUT",
        "BUY_TIMEOUT",
        "USE_MARGIN",
        "SCOUT_MARGIN",
        "TLD",
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)

    config = Config()

    assert config.BRIDGE_SYMBOL == "USDT"
    assert config.CURRENT_COIN_SYMBOL == ""
    assert config.BINANCE_API_KEY == ""
    assert config.BINANCE_API_SECRET_KEY == ""
    assert config.SCOUT_MULTIPLIER == 5.0
    assert config.SUPPORTED_COIN_LIST == []
