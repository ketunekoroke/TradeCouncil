"""watchdog — heartbeat 監視(FR-7.2 の Phase 0 簡易版)。

途絶を検知したら通知 + incidents 記録(自動再起動は VPS 移行後に systemd で行う。
ADR-0001 §3)。`tc watchdog` で常駐起動する。停止は Ctrl+C。
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

logger = logging.getLogger("tradecouncil.watchdog")


def check_once(session_factory, stale_sec: int, notifier=None) -> list[str]:
    """途絶コンポーネントの一覧を返し、新規の途絶は incident + 通知する。"""
    from core.db.models import Incident
    from core.runner.heartbeat import all_components

    now = datetime.now(UTC).replace(tzinfo=None)
    stale: list[str] = []
    for component, ts in all_components(session_factory).items():
        age = (now - ts).total_seconds()
        if age > stale_sec:
            stale.append(component)
            with session_factory() as session:
                already = (
                    session.query(Incident)
                    .filter(
                        Incident.component == component,
                        Incident.summary == "heartbeat途絶",
                        Incident.resolved_at.is_(None),
                    )
                    .first()
                )
                if already is None:
                    session.add(
                        Incident(
                            severity="critical",
                            component=component,
                            summary="heartbeat途絶",
                            detail=f"最終heartbeatから {age:.0f}秒 経過(しきい値 {stale_sec}秒)",
                        )
                    )
                    session.commit()
                    if notifier is not None:
                        notifier.send(
                            f"watchdog: {component} のheartbeatが {age:.0f}秒 途絶",
                            severity="critical",
                        )
    return stale


def run_watchdog() -> int:
    """常駐監視ループ(`tc watchdog`)。"""
    from core.config import get_config
    from core.db import get_session_factory, init_db
    from core.notify import get_notifier
    from core.runner.heartbeat import beat

    cfg = get_config()
    init_db()
    session_factory = get_session_factory()
    notifier = get_notifier()
    interval = cfg.runtime.heartbeat_interval_sec
    stale_sec = cfg.runtime.watchdog_stale_sec

    from core.logsetup import configure_logging

    configure_logging()
    logger.info("watchdog 起動(間隔 %ss / 途絶しきい値 %ss)。停止は Ctrl+C", interval, stale_sec)
    try:
        while True:
            beat(session_factory, "watchdog")
            stale = check_once(session_factory, stale_sec, notifier)
            if stale:
                logger.warning("途絶中: %s", ", ".join(stale))
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("watchdog 停止")
        return 0
