"""bot_runner — バー駆動BOTの実行コンテナ(FR-4.1 / 基本設計書 §1.1)。

1バーごとの流れ:
  キルフラグ確認 → バー取得・candles 保存 → 戦略 on_bar() → 意図ごとに
  trade_decisions 起票(根拠)→ risk_guard.check() → executor.submit()
  → heartbeat 打刻

- 拒否(RiskRejection)は orders に記録済みなのでログだけ残して継続する
- 最上位例外は incidents 記録 + 通知 + 終了(systemd 再起動は Phase 1)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from bots import STRATEGIES
from bots.base import BarData, Strategy, StrategyIntent
from core.exchange.base import Bar, BrokerAdapter
from core.exchange.feeds import PriceFeed
from core.execution.decisions import record_trade_decision
from core.execution.executor import Executor
from core.governance.registry import PolicyRegistry
from core.market.instrument import InstrumentSpec
from core.notify.notifier import Notifier
from core.risk import kill_switch
from core.risk.errors import RiskRejection
from core.risk.guard import MarketContext, OrderIntent, RiskGuard
from core.runner.heartbeat import beat

logger = logging.getLogger("tradecouncil.bot_runner")


class BotConfigDoc(BaseModel):
    bot_id: str
    strategy: str
    instrument_id: str
    enabled: bool = True
    params: dict = {}


def load_bot_config(bot_id: str, bots_dir: Path | None = None) -> BotConfigDoc:
    if bots_dir is None:
        from core.config import get_config

        bots_dir = get_config().bots_dir
    path = bots_dir / f"{bot_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"BOT設定が見つからない: {path}")
    return BotConfigDoc.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def snapshot_bot_config(
    session_factory: sessionmaker[Session], doc: BotConfigDoc, changed_by: str = "human"
) -> None:
    """bot_configs に設定スナップショットを保存(監査性)。内容が同じなら追加しない。"""
    from core.db.models import BotConfig

    snapshot = yaml.safe_dump(doc.model_dump(), allow_unicode=True, sort_keys=True)
    with session_factory() as session:
        last = (
            session.query(BotConfig)
            .filter(BotConfig.bot_id == doc.bot_id)
            .order_by(BotConfig.version.desc())
            .first()
        )
        if last is not None and last.yaml_snapshot == snapshot:
            return
        session.add(
            BotConfig(
                bot_id=doc.bot_id,
                version=(last.version + 1) if last else 1,
                yaml_snapshot=snapshot,
                changed_by=changed_by,
            )
        )
        session.commit()


class BotRunner:
    def __init__(
        self,
        bot_config: BotConfigDoc,
        instrument: InstrumentSpec,
        strategy: Strategy,
        feed: PriceFeed,
        adapter: BrokerAdapter,
        guard: RiskGuard,
        executor: Executor,
        session_factory: sessionmaker[Session],
        notifier: Notifier | None = None,
        kill_flag_path: Path | None = None,
        bar_sleep_sec: float | None = None,
        fx_rate_jpy: float = 1.0,
    ) -> None:
        self._config = bot_config
        self._instrument = instrument
        self._strategy = strategy
        self._feed = feed
        self._adapter = adapter
        self._guard = guard
        self._executor = executor
        self._session_factory = session_factory
        self._notifier = notifier
        self._kill_flag_path = kill_flag_path
        self._bar_sleep_sec = bar_sleep_sec
        # instrument 通貨 → JPY の換算レート(ADR-0008)。JPY 建ては 1.0
        self._fx_rate_jpy = fx_rate_jpy
        self._prev_close: float | None = None
        self._week_peak_equity: float = 0.0
        self.bars_processed = 0
        self.orders_submitted = 0
        self.orders_rejected = 0

    # ------------------------------------------------------------------

    async def run(self, max_bars: int | None = None) -> None:
        """メインループ。max_bars=None は無限(キルフラグ / Ctrl+C で停止)。"""
        component = f"bot:{self._config.bot_id}"
        logger.info(
            "BOT %s 起動(instrument=%s, strategy=%s)",
            self._config.bot_id,
            self._instrument.instrument_id,
            self._config.strategy,
        )
        try:
            while max_bars is None or self.bars_processed < max_bars:
                if kill_switch.is_active(self._kill_flag_path):
                    logger.warning("キルスイッチ検知 → BOT停止")
                    if self._notifier:
                        self._notifier.send(
                            f"{component}: キルスイッチにより停止", severity="warning"
                        )
                    break
                await self._process_one_bar()
                beat(self._session_factory, component)
                if self._bar_sleep_sec:
                    await asyncio.sleep(self._bar_sleep_sec)
        except KeyboardInterrupt:
            logger.info("Ctrl+C → BOT停止")
        except Exception as exc:
            self._record_incident(exc)
            raise

    # ------------------------------------------------------------------

    async def _process_one_bar(self) -> None:
        bar = self._feed.next_bar()
        self._persist_candle(bar)
        ctx = await self._build_context(bar)
        position_qty = self._current_position_qty()

        bar_data = BarData(ts=bar.ts, o=bar.o, h=bar.h, l=bar.l, c=bar.c, v=bar.v)
        intents = self._strategy.on_bar(bar_data, position_qty)

        for intent in intents:
            await self._handle_intent(intent, bar, ctx)

        self._prev_close = bar.c
        self.bars_processed += 1

    async def _handle_intent(self, intent: StrategyIntent, bar: Bar, ctx: MarketContext) -> None:
        # 1. 根拠の起票(全注文は必ずここから始まる — 不変条項3)
        decision_id = record_trade_decision(
            self._session_factory,
            bot_id=self._config.bot_id,
            source_type="strategy_rule",
            rationale=intent.rationale,
            source_ref=f"candle:{self._instrument.instrument_id}:{bar.ts.isoformat()}",
        )
        order_intent = OrderIntent(
            bot_id=self._config.bot_id,
            decision_id=decision_id,
            instrument_id=self._instrument.instrument_id,
            asset_class=self._instrument.asset_class,
            side=intent.side,
            qty=intent.qty,
            price=bar.c,  # instrument 通貨のまま(orders/fills と通貨を揃える)
            # 戦略の見積りは instrument 通貨建て(バー価格基準)→ JPY 換算(ADR-0008)
            est_max_loss_jpy=(
                intent.est_max_loss_jpy * self._fx_rate_jpy
                if intent.est_max_loss_jpy is not None
                else None
            ),
            reduces_position=intent.reduces_position,
            fx_rate_jpy=self._fx_rate_jpy,
        )
        # 2. risk_guard(唯一の関門)→ 3. executor
        try:
            approved = self._guard.check(order_intent, ctx)
        except RiskRejection as rejection:
            self.orders_rejected += 1
            logger.info("注文拒否: %s", rejection.reason_code)
            return
        order = await self._executor.submit(approved)
        self.orders_submitted += 1
        logger.info(
            "注文執行: %s %s qty=%s status=%s", order.order_id, intent.side, intent.qty, order.status
        )

    # ------------------------------------------------------------------

    async def _build_context(self, bar: Bar) -> MarketContext:
        # JPY 換算(ADR-0008): 現金は instrument 通貨(quote)の残高のみ評価し、
        # base 通貨(BTC 等)は建玉として exposure 側で評価する(二重計上しない)。
        # その他の通貨は評価しない = equity を過小評価する安全側
        rate = self._fx_rate_jpy
        balances = await self._adapter.fetch_balances()
        cash = sum(
            b.balance for b in balances if b.currency == self._instrument.currency
        ) * rate
        positions = await self._adapter.fetch_positions()
        exposure = sum(abs(p.qty) * bar.c for p in positions) * rate
        equity = cash + exposure
        self._week_peak_equity = max(self._week_peak_equity, equity)

        ticker = self._feed.current_ticker()
        price_change_pct_1m = (
            (bar.c - self._prev_close) / self._prev_close * 100.0
            if self._prev_close
            else 0.0
        )
        return MarketContext(
            equity_jpy=equity,
            total_exposure_jpy=exposure,
            daily_pnl_jpy=self._daily_pnl() * rate,  # pnl_daily は instrument 通貨建て
            week_peak_equity_jpy=self._week_peak_equity,
            bot_open_positions=len(positions),
            data_age_sec=self._feed.data_age_sec(),  # REST フィードは実測(P-04)
            price_change_pct_1m=price_change_pct_1m,
            spread_bps=ticker.spread_bps,
        )

    def _daily_pnl(self) -> float:
        from core.db.models import PnlDaily

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        with self._session_factory() as session:
            row = session.get(PnlDaily, (self._config.bot_id, today))
            return (row.realized + row.unrealized) if row else 0.0

    def _current_position_qty(self) -> float:
        from core.db.models import Position

        with self._session_factory() as session:
            pos = session.get(
                Position, (self._config.bot_id, self._instrument.instrument_id)
            )
            return pos.qty if pos else 0.0

    def _persist_candle(self, bar: Bar) -> None:
        from core.db.models import Candle

        with self._session_factory() as session:
            session.merge(
                Candle(
                    instrument_id=bar.instrument_id,
                    timeframe=bar.timeframe,
                    ts=bar.ts.replace(tzinfo=None) if bar.ts.tzinfo else bar.ts,
                    o=bar.o,
                    h=bar.h,
                    l=bar.l,
                    c=bar.c,
                    v=bar.v,
                )
            )
            session.commit()

    def _record_incident(self, exc: Exception) -> None:
        from core.db.models import Incident

        logger.exception("BOT異常終了")
        try:
            with self._session_factory() as session:
                session.add(
                    Incident(
                        severity="critical",
                        component=f"bot:{self._config.bot_id}",
                        summary="BOT異常終了",
                        detail=f"{type(exc).__name__}: {exc}",
                    )
                )
                session.commit()
        finally:
            if self._notifier:
                self._notifier.send(
                    f"bot:{self._config.bot_id} が異常終了: {type(exc).__name__}: {exc}",
                    severity="critical",
                )


# ----------------------------------------------------------------------------
# CLI エントリポイント(tc paper --bot <id>)
# ----------------------------------------------------------------------------


def build_runner(bot_id: str, bar_sleep: bool = True) -> BotRunner:
    """本番構成(config/ + var/ DB)の BotRunner を組み立てる。"""
    from core.config import get_config
    from core.db import get_session_factory, init_db
    from core.exchange.feeds import RandomWalkFeed
    from core.exchange.paper_crypto import PaperCryptoAdapter
    from core.governance.registry import default_registry
    from core.market.instrument import load_instruments, sync_instruments_to_db
    from core.notify import get_notifier

    cfg = get_config()
    init_db()
    session_factory = get_session_factory()

    bot_config = load_bot_config(bot_id)
    if not bot_config.enabled:
        raise RuntimeError(f"BOT {bot_id} は無効化されている(enabled: false)")
    snapshot_bot_config(session_factory, bot_config)

    instruments = load_instruments()
    if bot_config.instrument_id not in instruments:
        raise RuntimeError(f"未定義のinstrument: {bot_config.instrument_id}")
    instrument = instruments[bot_config.instrument_id]
    sync_instruments_to_db(session_factory, instruments)

    strategy_cls = STRATEGIES.get(bot_config.strategy)
    if strategy_cls is None:
        raise RuntimeError(f"未登録の戦略: {bot_config.strategy}")
    strategy = strategy_cls(bot_id, bot_config.params)

    # broker ごとに feed/adapter を組む(ADR-0008: ローカルペーパー / Bybit testnet の2系統)
    if instrument.broker == "paper":
        if cfg.feed.type != "random_walk":
            raise RuntimeError(
                f"paper ブローカーは random_walk フィードのみ対応: {cfg.feed.type}"
            )
        feed: PriceFeed = RandomWalkFeed(bot_config.instrument_id, cfg.feed.random_walk)
        adapter: BrokerAdapter = PaperCryptoAdapter(
            ticker_provider=lambda _iid: feed.current_ticker(),
            config=cfg.paper,
            currency=instrument.currency,
        )
    elif instrument.broker == "bybit_testnet":
        from core.exchange.bybit import BybitAdapter
        from core.exchange.bybit_feed import BybitFeed

        feed = BybitFeed(bot_config.instrument_id, instrument.symbol, cfg.feed.bybit)
        adapter = BybitAdapter({bot_config.instrument_id: instrument.symbol})
    else:
        raise RuntimeError(f"未対応のブローカー: {instrument.broker}(fail-closed)")

    # JPY 以外の instrument 通貨は保守的固定レートで換算(未対応通貨は即エラー)
    fx_rate_jpy = cfg.fx.rate_to_jpy(instrument.currency)
    registry = default_registry()
    guard = RiskGuard(
        registry=registry,
        session_factory=session_factory,
        kill_flag_path=cfg.kill_flag_path,
    )
    executor = Executor(adapter, session_factory)
    return BotRunner(
        bot_config=bot_config,
        instrument=instrument,
        strategy=strategy,
        feed=feed,
        adapter=adapter,
        guard=guard,
        executor=executor,
        session_factory=session_factory,
        notifier=get_notifier(),
        kill_flag_path=cfg.kill_flag_path,
        # REST フィード(bybit)は next_bar が新バー確定まで自前で待つためスリープ不要
        bar_sleep_sec=(
            float(feed.bar_interval_sec)
            if bar_sleep and instrument.broker == "paper"
            else None
        ),
        fx_rate_jpy=fx_rate_jpy,
    )


def run_paper_bot(bot_id: str) -> int:
    """`tc paper --bot <id>` 本体。ペーパーモード常駐。"""
    from core.logsetup import configure_logging

    configure_logging()
    runner = build_runner(bot_id)
    try:
        asyncio.run(runner.run())
    except KeyboardInterrupt:
        pass
    print(
        f"BOT停止: bars={runner.bars_processed} "
        f"submitted={runner.orders_submitted} rejected={runner.orders_rejected}"
    )
    return 0
