"""heartbeat 記録(FR-7.2)。各常駐コンポーネントが定期的に打刻する。"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker


def beat(session_factory: sessionmaker[Session], component: str) -> None:
    from core.db.models import Heartbeat

    with session_factory() as session:
        # 高速ループでは同一マイクロ秒の打刻があり得るため merge(upsert)にする
        session.merge(Heartbeat(component=component, ts=datetime.now(UTC).replace(tzinfo=None)))
        session.commit()


def last_beat(session_factory: sessionmaker[Session], component: str) -> datetime | None:
    from core.db.models import Heartbeat

    with session_factory() as session:
        row = (
            session.query(Heartbeat)
            .filter(Heartbeat.component == component)
            .order_by(Heartbeat.ts.desc())
            .first()
        )
        return row.ts if row else None


def all_components(session_factory: sessionmaker[Session]) -> dict[str, datetime]:
    """コンポーネントごとの最終 heartbeat。"""
    from sqlalchemy import func

    from core.db.models import Heartbeat

    with session_factory() as session:
        rows = (
            session.query(Heartbeat.component, func.max(Heartbeat.ts))
            .group_by(Heartbeat.component)
            .all()
        )
    return {component: ts for component, ts in rows}
