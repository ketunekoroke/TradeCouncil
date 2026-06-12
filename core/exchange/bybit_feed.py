"""Bybit 公開市場データフィード(ADR-0008)。

PriceFeed Protocol の実装。確定した直近 1m kline を返し、新バー確定まで
ポーリング待機する(同一バーを二重に返さない)。公開データのみを扱い
API キー不要。environment は testnet(既定・執行と整合)/ mainnet
(testnet の価格が歪むときの代替)を選べる — 発注はアダプタ側で常に testnet。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime

from core.config import BybitFeedConfig
from core.exchange.base import Bar, Ticker

_TIMEFRAMES = {60: "1m", 300: "5m", 900: "15m", 3600: "1h"}


class BybitFeed:
    """同期 ccxt による REST ポーリングフィード(1 BOT = 1 プロセス前提)。"""

    def __init__(
        self,
        instrument_id: str,
        symbol: str,
        config: BybitFeedConfig | None = None,
        client: object | None = None,  # テスト用 DI(フェイク注入)
        sleep_fn: Callable[[float], None] = time.sleep,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._instrument_id = instrument_id
        self._symbol = symbol
        self._config = config or BybitFeedConfig()
        timeframe = _TIMEFRAMES.get(self._config.bar_interval_sec)
        if timeframe is None:
            raise ValueError(
                f"未対応の bar_interval_sec: {self._config.bar_interval_sec}"
                f"(対応: {sorted(_TIMEFRAMES)})"
            )
        self._timeframe = timeframe
        self._sleep = sleep_fn
        self._now = now_fn or (lambda: datetime.now(UTC))
        self._last_ts_ms: int | None = None
        if client is None:
            client = self._build_client(self._config.environment)
        self._client = client

    @staticmethod
    def _build_client(environment: str) -> object:
        import ccxt  # 遅延 import(ローカルペーパーのみの構成では不要)

        client = ccxt.bybit()
        if environment == "testnet":
            client.set_sandbox_mode(True)
        return client

    @property
    def bar_interval_sec(self) -> int:
        return self._config.bar_interval_sec

    # ------------------------------------------------------------------

    def next_bar(self) -> Bar:
        """確定した直近バーを返す。前回と同じバーなら新バー確定まで待つ。"""
        while True:
            row = self._fetch_last_closed()
            if row is not None and (self._last_ts_ms is None or row[0] > self._last_ts_ms):
                self._last_ts_ms = int(row[0])
                return Bar(
                    instrument_id=self._instrument_id,
                    timeframe=self._timeframe,
                    ts=datetime.fromtimestamp(row[0] / 1000, tz=UTC),
                    o=float(row[1]),
                    h=float(row[2]),
                    l=float(row[3]),
                    c=float(row[4]),
                    v=float(row[5]) if len(row) > 5 and row[5] is not None else 0.0,
                )
            self._sleep(self._config.poll_sec)

    def _fetch_last_closed(self) -> list[float] | None:
        """OHLCV の確定済み最終行を返す(末尾行は形成中のため1本前)。"""
        rows = self._client.fetch_ohlcv(self._symbol, self._timeframe, limit=2)
        if not rows:
            return None
        if len(rows) >= 2:
            return rows[-2]
        return rows[-1]  # 1本しか返らない場合はそれを確定扱い

    def current_ticker(self) -> Ticker:
        t = self._client.fetch_ticker(self._symbol)
        ts_ms = t.get("timestamp")
        return Ticker(
            instrument_id=self._instrument_id,
            bid=float(t["bid"]),
            ask=float(t["ask"]),
            last=float(t["last"]),
            ts=datetime.fromtimestamp(ts_ms / 1000, tz=UTC) if ts_ms else self._now(),
        )

    def data_age_sec(self) -> float:
        """直近バーの鮮度 = now − (バー開始 + 足の長さ)。確定直後ほぼ 0。"""
        if self._last_ts_ms is None:
            return 0.0
        closed_at = (self._last_ts_ms / 1000) + self._config.bar_interval_sec
        return max(0.0, self._now().timestamp() - closed_at)
