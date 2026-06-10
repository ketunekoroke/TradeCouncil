"""最小KPI集計(`tc kpi`)— Phase 0 版。

注文・約定・損益のサマリと、**全注文の根拠連鎖(decision_id → trade_decisions)の
検証**を行う(不変条項3 の運用確認)。週次レビュー自動化は Phase 4。
"""

from __future__ import annotations


def print_kpi_report() -> int:
    from sqlalchemy import func

    from core.db import get_session_factory, init_db
    from core.db.models import Candle, Fill, Order, PnlDaily, TradeDecision

    init_db()
    session_factory = get_session_factory()

    with session_factory() as s:
        total_orders = s.query(Order).count()
        filled = s.query(Order).filter(Order.status == "filled").count()
        rejected = s.query(Order).filter(Order.status == "rejected").count()
        failed = s.query(Order).filter(Order.status == "failed").count()
        fills = s.query(Fill).count()
        candles = s.query(Candle).count()

        print("=== KPI(Phase 0 最小版)===")
        print(f"orders : total={total_orders} filled={filled} rejected={rejected} failed={failed}")
        print(f"fills  : {fills}")
        print(f"candles: {candles}")

        # 拒否理由の内訳
        reasons = (
            s.query(Order.reject_reason, func.count())
            .filter(Order.status == "rejected")
            .group_by(Order.reject_reason)
            .all()
        )
        if reasons:
            print("拒否理由内訳:")
            for reason, count in reasons:
                print(f"  {reason}: {count}")

        # 損益(BOT別)
        pnl_rows = (
            s.query(
                PnlDaily.bot_id,
                func.sum(PnlDaily.realized),
                func.sum(PnlDaily.fees),
                func.count(),
            )
            .group_by(PnlDaily.bot_id)
            .all()
        )
        print("損益(BOT別・実現):")
        if not pnl_rows:
            print("  (なし)")
        for bot_id, realized, fees, days in pnl_rows:
            print(f"  {bot_id}: realized={realized:.0f}円 fees={fees:.0f}円 days={days}")

        # 【検証】根拠連鎖: decision_id が trade_decisions に存在しない注文 = 0 件
        orphans = (
            s.query(Order)
            .outerjoin(TradeDecision, Order.decision_id == TradeDecision.decision_id)
            .filter(TradeDecision.decision_id.is_(None))
            .count()
        )
        if orphans == 0:
            print("根拠連鎖検証: OK(全注文が trade_decisions へ遡及可能)")
        else:
            print(f"根拠連鎖検証: NG! 根拠のない注文が {orphans} 件 — 調査が必要")
            return 1
    return 0
