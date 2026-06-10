"""`tc status` — システム状態の一覧(24h稼働試験の確認に使う)。"""

from __future__ import annotations

from datetime import UTC, datetime


def print_status() -> int:
    from core.config import get_config
    from core.db import get_session_factory, init_db
    from core.db.models import Order, Position
    from core.governance.errors import PolicyNotActiveError
    from core.governance.registry import default_registry
    from core.governance.schema import REQUIRED_POLICY_IDS
    from core.risk import kill_switch
    from core.runner.heartbeat import all_components

    cfg = get_config()
    init_db()
    session_factory = get_session_factory()

    print("=== TradeCouncil status ===")

    # キルスイッチ
    if kill_switch.is_active():
        print(f"[KILL]   有効(全BOT停止中): {cfg.kill_flag_path}")
    else:
        print("[KILL]   無効(通常運転)")

    # 必須ポリシー
    registry = default_registry()
    print("[POLICY] 必須ポリシー(★):")
    all_active = True
    for pid in REQUIRED_POLICY_IDS:
        try:
            doc = registry.require(pid)
            print(f"  {pid}: active v{doc.version} ({doc.title})")
        except PolicyNotActiveError as exc:
            all_active = False
            print(f"  {pid}: ✗ {exc.reason} → fail-closed(発注不可)")
    if not all_active:
        print("  → 第0回意思決定会議で P-01〜P-04 を決裁すると取引が解禁される")

    # heartbeat
    print("[HEART]  heartbeat:")
    beats = all_components(session_factory)
    if not beats:
        print("  (記録なし)")
    now = datetime.now(UTC).replace(tzinfo=None)
    for component, ts in sorted(beats.items()):
        age = (now - ts).total_seconds()
        marker = "OK" if age <= cfg.runtime.watchdog_stale_sec else "STALE"
        print(f"  {component}: {age:.0f}秒前 [{marker}]")

    # 建玉・注文サマリ
    with session_factory() as s:
        positions = s.query(Position).all()
        total = s.query(Order).count()
        filled = s.query(Order).filter(Order.status == "filled").count()
        rejected = s.query(Order).filter(Order.status == "rejected").count()
    print(f"[ORDERS] 合計 {total} 件(filled {filled} / rejected {rejected})")
    print("[POS]    建玉:")
    if not positions:
        print("  (なし)")
    for p in positions:
        print(f"  {p.bot_id} {p.instrument_id}: qty={p.qty} avg={p.avg_price:.0f}")
    return 0
