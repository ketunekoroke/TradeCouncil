"""trade_decisions の起票(全注文の根拠 — 不変条項3 / FR-4.4)。

bot_runner は risk_guard に注文を渡す**前に**必ずここで根拠レコードを作る。
根拠(rationale)へ遡及できない注文経路は存在しない。
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session, sessionmaker


def record_trade_decision(
    session_factory: sessionmaker[Session],
    bot_id: str,
    source_type: str,  # strategy_rule / council_decision / news_signal
    rationale: dict[str, Any],
    source_ref: str | None = None,
) -> str:
    """根拠レコードを作成し decision_id を返す。"""
    from core.db.models import TradeDecision

    decision_id = f"TD-{uuid.uuid4().hex[:12]}"
    with session_factory() as session:
        session.add(
            TradeDecision(
                decision_id=decision_id,
                bot_id=bot_id,
                source_type=source_type,
                source_ref=source_ref,
                rationale_json=rationale,
            )
        )
        session.commit()
    return decision_id
