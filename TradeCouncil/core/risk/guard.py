"""risk_guard — 全注文の唯一の関門(FR-5 / 不変条項2・5)。

executor の手前に位置し、すべての注文がここを通る。
しきい値はすべて active なポリシーの value から読む(コード内デフォルト値なし。
キー欠落も拒否 = キー粒度の fail-closed)。

チェック順序(基本設計書 §6 + 計画):
  1. キルスイッチ
  2. 必須ポリシー P-01〜P-04 が active(No Policy, No Trade)
  3. 資産クラスが P-02 で上限 > 0(未決裁クラスの封鎖)
  4. データ鮮度(P-04)
  5. サーキットブレーカ: 価格急変・スプレッド(P-04)
  6. 1取引最大損失(P-03)
  7. 日次損失・週次ドローダウン(P-03)
  8. 総エクスポージャー・BOT別ポジション数(P-03)・実効レバレッジ(P-02)

拒否は orders テーブルに status='rejected' + reason_code で記録する(監査の一元化)。
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, PrivateAttr
from sqlalchemy.orm import Session, sessionmaker

from core.governance.errors import PolicyKeyMissingError, PolicyNotActiveError
from core.governance.registry import PolicyRegistry
from core.risk import kill_switch
from core.risk.errors import RiskRejection

# RiskApprovedOrder の生成を risk_guard 内に限定するためのモジュール私有トークン
_APPROVAL_TOKEN = object()


class OrderIntent(BaseModel):
    """BOT(戦略)が発する注文意図。executor はこの型を直接受け取らない。"""

    bot_id: str
    decision_id: str  # trade_decisions への参照(根拠)。必須
    instrument_id: str
    asset_class: str
    side: str  # buy / sell
    qty: float
    price: float  # 想定価格(instrument 通貨建て。成行でも notional 計算に使う)
    order_type: str = "market"
    est_max_loss_jpy: float | None = None  # 想定最大損失(JPY)。None なら notional 全額とみなす
    reduces_position: bool = False  # 決済方向(防御)の注文か
    # instrument 通貨 → JPY の換算レート(ADR-0008)。JPY 建ては 1.0。
    # 0 以下は不可(換算の無効化 = リスク過小評価を型レベルで拒否)
    fx_rate_jpy: float = Field(default=1.0, gt=0)

    @property
    def notional_jpy(self) -> float:
        return abs(self.qty * self.price * self.fx_rate_jpy)


class MarketContext(BaseModel):
    """チェック時点の市場・口座状態(呼び出し側 = bot_runner が用意する)。"""

    equity_jpy: float
    total_exposure_jpy: float
    daily_pnl_jpy: float
    week_peak_equity_jpy: float
    bot_open_positions: int
    data_age_sec: float
    price_change_pct_1m: float
    spread_bps: float


class RiskApprovedOrder(BaseModel):
    """risk_guard だけが生成できる承認済み注文。executor はこの型のみ受理する。"""

    bot_id: str
    decision_id: str
    instrument_id: str
    side: str
    qty: float
    price: float
    order_type: str

    _token: Any = PrivateAttr(default=None)

    def __init__(self, /, **data: Any) -> None:
        token = data.pop("_approval_token", None)
        if token is not _APPROVAL_TOKEN:
            raise PermissionError(
                "RiskApprovedOrder は risk_guard.check() のみが生成できる(原則2: 権限分離)"
            )
        super().__init__(**data)


class RiskGuard:
    def __init__(
        self,
        registry: PolicyRegistry,
        session_factory: sessionmaker[Session] | None = None,
        kill_flag_path: Path | None = None,
    ) -> None:
        self._registry = registry
        self._session_factory = session_factory
        self._kill_flag_path = kill_flag_path

    # ------------------------------------------------------------------

    def check(self, intent: OrderIntent, ctx: MarketContext) -> RiskApprovedOrder:
        """全チェックを通過した注文のみ RiskApprovedOrder にして返す。

        失敗は RiskRejection を raise し、orders に rejected として記録する。
        """
        try:
            self._check_kill_switch()
            self._check_required_policies()
            self._check_asset_class(intent)
            self._check_data_freshness(ctx)
            self._check_circuit_breaker(ctx)
            self._check_per_trade_loss(intent, ctx)
            self._check_daily_loss(ctx)
            self._check_weekly_drawdown(ctx)
            self._check_exposure(intent, ctx)
            self._check_max_positions(intent, ctx)
            self._check_effective_leverage(intent, ctx)
        except RiskRejection as rejection:
            self._record_rejection(intent, rejection)
            raise
        except (PolicyNotActiveError, PolicyKeyMissingError) as exc:
            rejection = RiskRejection(str(exc).split(" ")[0], str(exc))
            self._record_rejection(intent, rejection)
            raise rejection from exc

        return RiskApprovedOrder(
            _approval_token=_APPROVAL_TOKEN,
            bot_id=intent.bot_id,
            decision_id=intent.decision_id,
            instrument_id=intent.instrument_id,
            side=intent.side,
            qty=intent.qty,
            price=intent.price,
            order_type=intent.order_type,
        )

    # ------------------------------------------------------------------
    # 個別チェック(順序が仕様)
    # ------------------------------------------------------------------

    def _check_kill_switch(self) -> None:
        if kill_switch.is_active(self._kill_flag_path):
            raise RiskRejection("KILL_SWITCH", "キルスイッチが有効(全注文停止)")

    def _check_required_policies(self) -> None:
        # PolicyNotActiveError は check() で RiskRejection に変換される
        self._registry.require_all()

    def _value(self, policy_id: str, key: str) -> Any:
        return self._registry.require_value(policy_id, key)

    def _check_asset_class(self, intent: OrderIntent) -> None:
        per_class: dict[str, float] = self._value("P-02", "per_asset_class")
        limit = per_class.get(intent.asset_class)
        if limit is None or limit <= 0:
            raise RiskRejection(
                f"ASSET_CLASS_BLOCKED:{intent.asset_class}",
                "未決裁または使用禁止の資産クラス(fail-closed)",
            )

    def _check_data_freshness(self, ctx: MarketContext) -> None:
        limit = float(self._value("P-04", "stale_data_sec"))
        if ctx.data_age_sec > limit:
            raise RiskRejection("STALE_DATA", f"data_age={ctx.data_age_sec}s > {limit}s")

    def _check_circuit_breaker(self, ctx: MarketContext) -> None:
        jump_limit = float(self._value("P-04", "cb_price_jump_pct_1m"))
        if abs(ctx.price_change_pct_1m) > jump_limit:
            raise RiskRejection(
                "CIRCUIT_BREAKER_PRICE_JUMP",
                f"1分変動 {ctx.price_change_pct_1m}% > ±{jump_limit}%",
            )
        spread_limit = float(self._value("P-04", "cb_max_spread_bps"))
        if ctx.spread_bps > spread_limit:
            raise RiskRejection(
                "CIRCUIT_BREAKER_SPREAD", f"spread {ctx.spread_bps}bps > {spread_limit}bps"
            )

    def _check_per_trade_loss(self, intent: OrderIntent, ctx: MarketContext) -> None:
        limit_pct = float(self._value("P-03", "per_trade_max_loss_pct"))
        max_loss = (
            intent.est_max_loss_jpy
            if intent.est_max_loss_jpy is not None
            else intent.notional_jpy  # 見積りなし = 全損とみなす(保守的)
        )
        allowed = ctx.equity_jpy * limit_pct / 100.0
        if max_loss > allowed:
            raise RiskRejection(
                "PER_TRADE_LOSS", f"想定損失 {max_loss:.0f}円 > 許容 {allowed:.0f}円"
            )

    def _check_daily_loss(self, ctx: MarketContext) -> None:
        limit_pct = float(self._value("P-03", "max_daily_loss_pct"))
        if ctx.daily_pnl_jpy >= 0:
            return
        allowed = ctx.equity_jpy * limit_pct / 100.0
        if -ctx.daily_pnl_jpy > allowed:
            raise RiskRejection(
                "DAILY_LOSS_LIMIT",
                f"日次損失 {-ctx.daily_pnl_jpy:.0f}円 > 上限 {allowed:.0f}円(当日新規停止)",
            )

    def _check_weekly_drawdown(self, ctx: MarketContext) -> None:
        limit_pct = float(self._value("P-03", "max_weekly_drawdown_pct"))
        if ctx.week_peak_equity_jpy <= 0:
            raise RiskRejection("WEEKLY_DRAWDOWN", "週次ピーク資産が不正(0以下)")
        dd_pct = (ctx.week_peak_equity_jpy - ctx.equity_jpy) / ctx.week_peak_equity_jpy * 100.0
        if dd_pct > limit_pct:
            raise RiskRejection(
                "WEEKLY_DRAWDOWN", f"週次DD {dd_pct:.2f}% > 上限 {limit_pct}%(全停止)"
            )

    def _check_exposure(self, intent: OrderIntent, ctx: MarketContext) -> None:
        limit_pct = float(self._value("P-03", "max_total_exposure_pct"))
        new_exposure = ctx.total_exposure_jpy + (
            0.0 if intent.reduces_position else intent.notional_jpy
        )
        if new_exposure > ctx.equity_jpy * limit_pct / 100.0:
            raise RiskRejection(
                "EXPOSURE_LIMIT",
                f"建玉合計 {new_exposure:.0f}円 > {limit_pct}% of {ctx.equity_jpy:.0f}円",
            )

    def _check_max_positions(self, intent: OrderIntent, ctx: MarketContext) -> None:
        if intent.reduces_position:
            return  # 決済(防御)は妨げない
        limit = int(self._value("P-03", "per_bot_max_positions"))
        if ctx.bot_open_positions + 1 > limit:
            raise RiskRejection(
                "MAX_POSITIONS", f"BOT建玉数 {ctx.bot_open_positions}+1 > 上限 {limit}"
            )

    def _check_effective_leverage(self, intent: OrderIntent, ctx: MarketContext) -> None:
        limit = float(self._value("P-02", "account_max_effective"))
        if ctx.equity_jpy <= 0:
            raise RiskRejection("LEVERAGE_LIMIT", "口座資産が不正(0以下)")
        new_exposure = ctx.total_exposure_jpy + (
            0.0 if intent.reduces_position else intent.notional_jpy
        )
        effective = new_exposure / ctx.equity_jpy
        if effective > limit:
            raise RiskRejection(
                "LEVERAGE_LIMIT", f"実効レバレッジ {effective:.3f} > 上限 {limit}"
            )

    # ------------------------------------------------------------------

    def _record_rejection(self, intent: OrderIntent, rejection: RiskRejection) -> None:
        """拒否を orders に記録する(失敗しても発注拒否自体は維持)。"""
        if self._session_factory is None:
            return
        from core.db.models import Order

        try:
            with self._session_factory() as session:
                session.add(
                    Order(
                        order_id=f"O-{uuid.uuid4().hex[:12]}",
                        bot_id=intent.bot_id,
                        decision_id=intent.decision_id,
                        instrument_id=intent.instrument_id,
                        side=intent.side,
                        qty=intent.qty,
                        price=intent.price,
                        order_type=intent.order_type,
                        status="rejected",
                        reject_reason=rejection.reason_code[:120],
                    )
                )
                session.commit()
        except Exception:
            # 記録失敗は拒否判断に影響させない(fail-closed 優先)。
            # ただし握りつぶさず incident として残す試みは行う
            try:
                from core.db.models import Incident

                with self._session_factory() as session:
                    session.add(
                        Incident(
                            severity="warning",
                            component="risk_guard",
                            summary="拒否注文の記録に失敗",
                            detail=f"decision_id={intent.decision_id} reason={rejection.reason_code}",
                        )
                    )
                    session.commit()
            except Exception:
                pass
