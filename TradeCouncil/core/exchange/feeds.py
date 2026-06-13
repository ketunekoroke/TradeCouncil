"""価格フィード(ダミーBOT用)。

既定は RandomWalkFeed(ADR-0001 §7):
  - ネットワーク不要で 24h 無人稼働の DoD が外部要因で落ちない
  - シード固定で再現可能(テストと本稼働が同コード)
  - 売り買い両経路を確実に通せる
公開 REST ticker フィードは Phase 1(market_collector)で追加する。
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from typing import Protocol

from core.config import RandomWalkConfig
from core.exchange.base import Bar, Ticker


class PriceFeed(Protocol):
    def next_bar(self) -> Bar: ...

    def current_ticker(self) -> Ticker: ...

    def data_age_sec(self) -> float:
        """直近バーのデータ鮮度(秒)。P-04 の stale_data チェックに渡る(ADR-0008)。"""
        ...


class RandomWalkFeed:
    """幾何ランダムウォークの1分バー生成器(決定的: seed 固定で再現可能)。"""

    def __init__(
        self,
        instrument_id: str,
        config: RandomWalkConfig | None = None,
        start_ts: datetime | None = None,
    ) -> None:
        self._instrument_id = instrument_id
        self._config = config or RandomWalkConfig()
        self._rng = random.Random(self._config.seed)
        self._price = self._config.start_price
        self._ts = start_ts or datetime.now(UTC)
        self._timeframe = f"{max(1, self._config.bar_interval_sec // 60)}m"

    @property
    def bar_interval_sec(self) -> int:
        return self._config.bar_interval_sec

    def next_bar(self) -> Bar:
        drift = self._config.drift_bps_per_bar / 10_000
        vol = self._config.vol_bps_per_bar / 10_000
        o = self._price
        ret = self._rng.gauss(drift, vol)
        c = max(o * (1 + ret), 1.0)
        wiggle = abs(self._rng.gauss(0, vol / 2))
        h = max(o, c) * (1 + wiggle)
        low = min(o, c) * (1 - wiggle)
        self._price = c
        self._ts = self._ts + timedelta(seconds=self._config.bar_interval_sec)
        return Bar(
            instrument_id=self._instrument_id,
            timeframe=self._timeframe,
            ts=self._ts,
            o=o,
            h=h,
            l=low,
            c=c,
            v=abs(self._rng.gauss(1.0, 0.3)),
        )

    def data_age_sec(self) -> float:
        return 0.0  # フィード直結(生成と同時に消費)のため常に新鮮

    def current_ticker(self) -> Ticker:
        half_spread = self._price * 0.0001  # 1bp の半スプレッド(ペーパー用固定)
        return Ticker(
            instrument_id=self._instrument_id,
            bid=self._price - half_spread,
            ask=self._price + half_spread,
            last=self._price,
            ts=self._ts,
        )
