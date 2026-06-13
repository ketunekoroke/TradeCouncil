"""BybitFeed(core/exchange/bybit_feed.py)のテスト。

実ネットワークには出ない: 同期 ccxt クライアントをフェイク注入して検査する。
設計(ADR-0008):
  - next_bar() は「確定した直近 1m kline」を返す(形成中バーは返さない)
  - 同一バーを二重に返さない(新バー確定までポーリング待機)
  - data_age_sec() は実測(P-04 データ鮮度チェックを実質動かす)
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.config import BybitFeedConfig
from core.exchange.bybit_feed import BybitFeed

IID = "bybit_testnet.btc_usdt.spot"
T0 = 1_750_000_000_000  # ms
MIN = 60_000  # 1分(ms)


def _row(ts_ms: int, c: float = 50_000.0) -> list[float]:
    # ccxt OHLCV 行: [ts, o, h, l, c, v]
    return [ts_ms, c - 10, c + 20, c - 30, c, 1.5]


class FakeSyncClient:
    def __init__(self) -> None:
        # 既定: 確定バー(T0)+ 形成中バー(T0+1分)
        self.ohlcv: list[list[float]] = [_row(T0), _row(T0 + MIN, c=50_100.0)]
        self.ticker = {"bid": 49_990.0, "ask": 50_010.0, "last": 50_000.0, "timestamp": T0}
        self.fetch_calls = 0

    def fetch_ohlcv(self, symbol, timeframe, limit=2):
        self.fetch_calls += 1
        return self.ohlcv[-limit:]

    def fetch_ticker(self, symbol):
        return self.ticker


@pytest.fixture
def fake() -> FakeSyncClient:
    return FakeSyncClient()


def _feed(fake: FakeSyncClient, sleeps: list[float] | None = None) -> BybitFeed:
    return BybitFeed(
        IID,
        "BTC/USDT",
        config=BybitFeedConfig(poll_sec=0.1),
        client=fake,
        sleep_fn=(sleeps.append if sleeps is not None else lambda _s: None),
    )


class TestNextBar:
    def test_first_bar_is_last_closed(self, fake: FakeSyncClient) -> None:
        """形成中の最終行ではなく、確定済みの1本前を返す。"""
        bar = _feed(fake).next_bar()
        assert bar.ts == datetime.fromtimestamp(T0 / 1000, tz=UTC)
        assert bar.instrument_id == IID
        assert bar.timeframe == "1m"
        assert bar.c == 50_000.0
        assert bar.o == 49_990.0

    def test_waits_until_new_bar_closes(self, fake: FakeSyncClient) -> None:
        """同一バーを二重に返さず、新バー確定までポーリングする。"""
        sleeps: list[float] = []

        def sleep_and_advance(sec: float) -> None:
            sleeps.append(sec)
            if len(sleeps) == 2:  # 2回目の待機で新バーが確定する
                fake.ohlcv = [
                    _row(T0),
                    _row(T0 + MIN, c=50_100.0),
                    _row(T0 + 2 * MIN, c=50_200.0),
                ]

        feed = BybitFeed(
            IID, "BTC/USDT", config=BybitFeedConfig(poll_sec=0.1),
            client=fake, sleep_fn=sleep_and_advance,
        )
        first = feed.next_bar()
        second = feed.next_bar()

        assert first.ts != second.ts
        assert second.ts == datetime.fromtimestamp((T0 + MIN) / 1000, tz=UTC)
        assert second.c == 50_100.0
        assert len(sleeps) >= 2  # 実際に待機した


class TestTickerAndAge:
    def test_current_ticker_real_spread(self, fake: FakeSyncClient) -> None:
        ticker = _feed(fake).current_ticker()
        assert ticker.bid == 49_990.0
        assert ticker.ask == 50_010.0
        assert ticker.spread_bps == pytest.approx(4.0, rel=0.01)

    def test_data_age_is_measured(self, fake: FakeSyncClient) -> None:
        """age = now - (バー開始 + 足の長さ)。確定直後ほぼ0、時間経過で増える。"""
        now_ms = T0 + MIN + 30_000  # 確定(T0+1分)から30秒後
        feed = BybitFeed(
            IID, "BTC/USDT", config=BybitFeedConfig(poll_sec=0.1),
            client=fake, sleep_fn=lambda _s: None,
            now_fn=lambda: datetime.fromtimestamp(now_ms / 1000, tz=UTC),
        )
        feed.next_bar()
        assert feed.data_age_sec() == pytest.approx(30.0)

    def test_data_age_zero_before_first_bar(self, fake: FakeSyncClient) -> None:
        assert _feed(fake).data_age_sec() == 0.0

    def test_bar_interval_property(self, fake: FakeSyncClient) -> None:
        assert _feed(fake).bar_interval_sec == 60


class TestRandomWalkCompat:
    def test_random_walk_feed_has_data_age(self) -> None:
        """PriceFeed Protocol 拡張: RandomWalkFeed は常に 0.0(フィード直結)。"""
        from core.config import RandomWalkConfig
        from core.exchange.feeds import RandomWalkFeed

        feed = RandomWalkFeed("paper.btc_jpy.spot", RandomWalkConfig(seed=1))
        assert feed.data_age_sec() == 0.0
