"""executor — 取引所アダプタ経由の発注・約定照合・冪等性管理(FR-4.2)。

- 受け取るのは RiskApprovedOrder のみ(risk_guard を通っていない注文は型エラー)
- 同一の (bot_id, decision_id, instrument_id, side, qty) は1度しか発注されない
  (idempotency_key の UNIQUE 制約 + 事前照会)
- orders → fills → positions → pnl_daily の更新を1トランザクションで行う
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker

from core.exchange.base import BrokerAdapter, OrderRequest
from core.execution.idempotency import make_idempotency_key
from core.risk.guard import RiskApprovedOrder


class Executor:
    def __init__(
        self,
        adapter: BrokerAdapter,
        session_factory: sessionmaker[Session],
    ) -> None:
        self._adapter = adapter
        self._session_factory = session_factory

    async def submit(self, approved: RiskApprovedOrder):
        """承認済み注文を執行し、Order 行(ORM)を返す。"""
        if not isinstance(approved, RiskApprovedOrder):
            raise TypeError(
                "executor は RiskApprovedOrder のみ受理する(risk_guard を通すこと)"
            )
        if not approved.decision_id:
            raise ValueError("decision_id のない注文は執行できない(FR-4.4)")

        from core.db.models import Order

        idem_key = make_idempotency_key(
            approved.bot_id,
            approved.decision_id,
            approved.instrument_id,
            approved.side,
            approved.qty,
        )

        # 冪等性: 既存注文があればそれを返す(二重発注防止)
        with self._session_factory() as session:
            existing = (
                session.query(Order).filter(Order.idempotency_key == idem_key).one_or_none()
            )
            if existing is not None:
                return existing

        result = await self._adapter.submit_order(
            OrderRequest(
                instrument_id=approved.instrument_id,
                side=approved.side,
                qty=approved.qty,
                order_type=approved.order_type,
                idempotency_key=idem_key,
            )
        )

        return self._persist(approved, idem_key, result)

    # ------------------------------------------------------------------

    def _persist(self, approved: RiskApprovedOrder, idem_key: str, result):
        from core.db.models import Fill, Order, PnlDaily, Position

        order_id = f"O-{uuid.uuid4().hex[:12]}"
        status = "filled" if result.status == "filled" else "failed"
        with self._session_factory() as session:
            order = Order(
                order_id=order_id,
                bot_id=approved.bot_id,
                decision_id=approved.decision_id,
                instrument_id=approved.instrument_id,
                side=approved.side,
                qty=approved.qty,
                price=approved.price,
                order_type=approved.order_type,
                status=status,
                reject_reason=result.reject_reason,
                exchange_order_id=result.broker_order_id,
                idempotency_key=idem_key,
            )
            session.add(order)
            # fills は orders に FK 依存する。relationship を定義していないため
            # 明示 flush で INSERT 順序(orders → fills)を保証する
            session.flush()

            realized = 0.0
            fees = 0.0
            for fill_info in result.fills:
                session.add(
                    Fill(
                        fill_id=f"F-{uuid.uuid4().hex[:12]}",
                        order_id=order_id,
                        qty=fill_info.qty,
                        price=fill_info.price,
                        fee=fill_info.fee,
                        ts=fill_info.ts.replace(tzinfo=None)
                        if fill_info.ts.tzinfo
                        else fill_info.ts,
                    )
                )
                fees += fill_info.fee
                realized += self._update_position(
                    session, approved, fill_info.qty, fill_info.price
                )

            if result.fills:
                self._update_pnl_daily(session, approved.bot_id, realized, fees)

            session.commit()
            session.refresh(order)
            return order

    def _update_position(self, session, approved: RiskApprovedOrder, qty: float, price: float) -> float:
        """positions を更新し、実現損益(売却時)を返す。"""
        from core.db.models import Position

        pos = session.get(Position, (approved.bot_id, approved.instrument_id))
        if approved.side == "buy":
            if pos is None:
                session.add(
                    Position(
                        bot_id=approved.bot_id,
                        instrument_id=approved.instrument_id,
                        qty=qty,
                        avg_price=price,
                    )
                )
            else:
                total = pos.qty + qty
                pos.avg_price = (pos.qty * pos.avg_price + qty * price) / total
                pos.qty = total
            return 0.0
        # sell
        if pos is None:
            return 0.0  # ポジション無しの売り(paperでは到達しない)
        realized = (price - pos.avg_price) * min(qty, pos.qty)
        pos.qty -= qty
        if pos.qty <= 1e-12:
            session.delete(pos)
        return realized

    def _update_pnl_daily(self, session, bot_id: str, realized: float, fees: float) -> None:
        from core.db.models import PnlDaily

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        row = session.get(PnlDaily, (bot_id, today))
        if row is None:
            session.add(
                PnlDaily(bot_id=bot_id, date=today, realized=realized, fees=fees)
            )
        else:
            row.realized += realized
            row.fees += fees

    # ------------------------------------------------------------------

    async def reconcile(self, bot_id: str) -> list[str]:
        """再起動時の建玉突合(FR-4.2)。取引所とDBの不整合を文字列で返す。"""
        from core.db.models import Position

        broker_positions = {p.instrument_id: p for p in await self._adapter.fetch_positions()}
        mismatches: list[str] = []
        with self._session_factory() as session:
            db_positions = session.query(Position).filter(Position.bot_id == bot_id).all()
            db_map = {p.instrument_id: p for p in db_positions}
        for iid, bp in broker_positions.items():
            dp = db_map.get(iid)
            if dp is None:
                mismatches.append(f"DBに無い建玉: {iid} qty={bp.qty}")
            elif abs(dp.qty - bp.qty) > 1e-9:
                mismatches.append(f"数量不一致: {iid} db={dp.qty} broker={bp.qty}")
        for iid, dp in db_map.items():
            if iid not in broker_positions:
                mismatches.append(f"取引所に無い建玉: {iid} qty={dp.qty}")
        return mismatches
