"""セッションカレンダー(FR-8.3)— Phase 0 は 24/7(always)のみの最小実装。

立会時間制(jpx 等)のカレンダーは Phase 6 以降で追加する。
未知のカレンダーは「閉場」とみなす(fail-closed: 場外時間の発注を抑止)。
"""

from __future__ import annotations

from datetime import datetime


def is_session_open(session_calendar: str, _now: datetime | None = None) -> bool:
    if session_calendar == "always":
        return True
    # 未実装カレンダーは閉場扱い(発注抑止)
    return False
