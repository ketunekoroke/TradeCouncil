"""DBスキーマ定義(基本設計書 §4 準拠 + ADR-0001 の trade_decisions)。

すべてのテーブルに created_at を持つ(§4 記法)。
Phase 0 で実際に読み書きするのは:
  policies / policy_decisions / proposals / instruments / trade_decisions /
  orders / fills / positions / pnl_daily / heartbeats / incidents / accounts /
  bot_configs / candles
残りは定義のみ(Phase 1 以降で使用)。
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


# ----------------------------------------------------------------------------
# ガバナンス(§1.5)
# ----------------------------------------------------------------------------


class Policy(CreatedAtMixin, Base):
    """ポリシーの現在値(config/policies/*.yaml と同期)。"""

    __tablename__ = "policies"

    policy_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # draft..retired
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    value_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    effective_from: Mapped[str | None] = mapped_column(String(32))
    review_after: Mapped[str | None] = mapped_column(String(32))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class PolicyDecision(CreatedAtMixin, Base):
    """決裁履歴(append-only。不変条項3: 全決定の監査ログ)。"""

    __tablename__ = "policy_decisions"

    decision_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    policy_id: Mapped[str] = mapped_column(String(16), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # approve 等
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    session_ref: Mapped[str | None] = mapped_column(String(100))
    basis_refs_json: Mapped[list | None] = mapped_column(JSON)
    decided_by: Mapped[str] = mapped_column(String(40), nullable=False)
    decided_at: Mapped[str] = mapped_column(String(40), nullable=False)
    value_snapshot_json: Mapped[dict | None] = mapped_column(JSON)


class Proposal(CreatedAtMixin, Base):
    """審議中の提案・決裁キュー(decision_gate が範囲外提案を回送する先)。"""

    __tablename__ = "proposals"

    proposal_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False)  # council/weekly/user
    target_policy_id: Mapped[str | None] = mapped_column(String(16))
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="pending_decision"
    )  # pending_decision / approved / rejected / deferred / auto_applied
    resolution_ref: Mapped[str | None] = mapped_column(String(40))


# ----------------------------------------------------------------------------
# マーケット・口座(FR-8)
# ----------------------------------------------------------------------------


class Instrument(CreatedAtMixin, Base):
    __tablename__ = "instruments"

    instrument_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    asset_class: Mapped[str] = mapped_column(String(24), nullable=False)
    broker: Mapped[str] = mapped_column(String(24), nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    tick_size: Mapped[float] = mapped_column(Float, nullable=False)
    lot_size: Mapped[float] = mapped_column(Float, nullable=False)
    session_calendar: Mapped[str] = mapped_column(String(40), nullable=False)
    margin_rule: Mapped[str] = mapped_column(String(40), nullable=False)


class Account(CreatedAtMixin, Base):
    __tablename__ = "accounts"

    broker: Mapped[str] = mapped_column(String(24), primary_key=True)
    currency: Mapped[str] = mapped_column(String(8), primary_key=True)
    balance: Mapped[float] = mapped_column(Float, nullable=False)
    margin_used: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class FxRate(CreatedAtMixin, Base):
    __tablename__ = "fx_rates"

    pair: Mapped[str] = mapped_column(String(16), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    rate: Mapped[float] = mapped_column(Float, nullable=False)


class MarginSnapshot(CreatedAtMixin, Base):
    __tablename__ = "margin_snapshots"

    broker: Mapped[str] = mapped_column(String(24), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    equity_jpy: Mapped[float] = mapped_column(Float, nullable=False)
    margin_used_jpy: Mapped[float] = mapped_column(Float, nullable=False)
    maintenance_ratio: Mapped[float | None] = mapped_column(Float)
    effective_leverage: Mapped[float] = mapped_column(Float, nullable=False)


class Candle(CreatedAtMixin, Base):
    __tablename__ = "candles"

    instrument_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(8), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    o: Mapped[float] = mapped_column(Float, nullable=False)
    h: Mapped[float] = mapped_column(Float, nullable=False)
    l: Mapped[float] = mapped_column(Float, nullable=False)  # noqa: E741
    c: Mapped[float] = mapped_column(Float, nullable=False)
    v: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


# ----------------------------------------------------------------------------
# 取引の根拠と執行(FR-4 / 不変条項3)
# ----------------------------------------------------------------------------


class TradeDecision(CreatedAtMixin, Base):
    """全注文の根拠の結合点(ADR-0001 §5)。

    orders.decision_id はこのテーブルを参照し、source_type/source_ref で
    council_decisions / news_signals / 戦略ルールへ遡及できる。
    """

    __tablename__ = "trade_decisions"

    decision_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    bot_id: Mapped[str] = mapped_column(String(40), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(24), nullable=False
    )  # strategy_rule / council_decision / news_signal
    source_ref: Mapped[str | None] = mapped_column(String(80))
    rationale_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class Order(CreatedAtMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_orders_idempotency"),)

    order_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    bot_id: Mapped[str] = mapped_column(String(40), nullable=False)
    decision_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("trade_decisions.decision_id"), nullable=False
    )
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)  # buy / sell
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float | None] = mapped_column(Float)
    order_type: Mapped[str] = mapped_column(String(12), nullable=False, default="market")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # rejected / submitted / filled / canceled / failed
    reject_reason: Mapped[str | None] = mapped_column(String(120))
    exchange_order_id: Mapped[str | None] = mapped_column(String(64))
    idempotency_key: Mapped[str | None] = mapped_column(String(64))


class Fill(CreatedAtMixin, Base):
    __tablename__ = "fills"

    fill_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(40), ForeignKey("orders.order_id"), nullable=False)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    fee: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Position(CreatedAtMixin, Base):
    __tablename__ = "positions"

    bot_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    avg_price: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class PnlDaily(CreatedAtMixin, Base):
    __tablename__ = "pnl_daily"

    bot_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    date: Mapped[str] = mapped_column(String(10), primary_key=True)  # YYYY-MM-DD
    realized: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unrealized: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fees: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    equity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class BotConfig(CreatedAtMixin, Base):
    __tablename__ = "bot_configs"

    bot_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    yaml_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(16), nullable=False)  # human / gate
    decision_id: Mapped[str | None] = mapped_column(String(40))


# ----------------------------------------------------------------------------
# 監視・運用
# ----------------------------------------------------------------------------


class Heartbeat(Base):
    __tablename__ = "heartbeats"

    component: Mapped[str] = mapped_column(String(60), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Incident(CreatedAtMixin, Base):
    __tablename__ = "incidents"

    incident_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    severity: Mapped[str] = mapped_column(String(12), nullable=False)  # info/warning/critical
    component: Mapped[str] = mapped_column(String(60), nullable=False)
    summary: Mapped[str] = mapped_column(String(200), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)


class LlmUsage(CreatedAtMixin, Base):
    __tablename__ = "llm_usage"

    call_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    component: Mapped[str] = mapped_column(String(60), nullable=False)
    model: Mapped[str] = mapped_column(String(60), nullable=False)
    in_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    out_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_est: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# ----------------------------------------------------------------------------
# ニュース(FR-1/FR-2 — Phase 2 で使用。定義のみ)
# ----------------------------------------------------------------------------


class NewsRaw(CreatedAtMixin, Base):
    __tablename__ = "news_raw"

    news_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    source: Mapped[str] = mapped_column(String(60), nullable=False)
    url: Mapped[str | None] = mapped_column(String(500))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    dedup_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class NewsSignal(CreatedAtMixin, Base):
    __tablename__ = "news_signals"

    signal_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    news_id: Mapped[str] = mapped_column(String(40), ForeignKey("news_raw.news_id"), nullable=False)
    stage: Mapped[int] = mapped_column(Integer, nullable=False)
    impact: Mapped[int] = mapped_column(Integer, nullable=False)
    symbols_json: Mapped[list | None] = mapped_column(JSON)
    direction: Mapped[str | None] = mapped_column(String(12))
    confidence: Mapped[float | None] = mapped_column(Float)
    half_life_min: Mapped[int | None] = mapped_column(Integer)
    model: Mapped[str | None] = mapped_column(String(60))
    raw_json: Mapped[dict | None] = mapped_column(JSON)


# ----------------------------------------------------------------------------
# 戦略会議(FR-3 — 議事録は Phase 0 の council シナリオでも記録する)
# ----------------------------------------------------------------------------


class CouncilSession(CreatedAtMixin, Base):
    __tablename__ = "council_sessions"

    session_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # weekly/daily/adhoc/kickoff
    input_digest: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    minutes_path: Mapped[str | None] = mapped_column(String(300))


class CouncilOpinion(CreatedAtMixin, Base):
    __tablename__ = "council_opinions"

    opinion_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("council_sessions.session_id"), nullable=False
    )
    persona: Mapped[str] = mapped_column(String(40), nullable=False)
    round: Mapped[int] = mapped_column(Integer, nullable=False)
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class CouncilDecision(CreatedAtMixin, Base):
    __tablename__ = "council_decisions"

    decision_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("council_sessions.session_id"), nullable=False
    )
    decision_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    gate_result: Mapped[str | None] = mapped_column(String(16))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime)


class BotKpiWeekly(CreatedAtMixin, Base):
    __tablename__ = "bot_kpi_weekly"

    bot_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    week: Mapped[str] = mapped_column(String(10), primary_key=True)  # 2026-W24
    pf: Mapped[float | None] = mapped_column(Float)
    sharpe: Mapped[float | None] = mapped_column(Float)
    max_dd: Mapped[float | None] = mapped_column(Float)
    win_rate: Mapped[float | None] = mapped_column(Float)
    avg_r: Mapped[float | None] = mapped_column(Float)
    trades: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(String(12))  # ACTIVE/REDUCED/PAPER/RETIRED
