"""キルスイッチのテスト(不変条項4)。"""

from __future__ import annotations

import pytest

from core.risk import kill_switch
from core.risk.errors import RiskRejection
from tests.conftest import activate_required_policies
from tests.risk.conftest import make_ctx, make_intent


class TestKillSwitchFile:
    def test_activate_creates_flag(self, kill_flag):
        assert not kill_switch.is_active(kill_flag)
        path = kill_switch.activate(path=kill_flag)
        assert path == kill_flag
        assert kill_switch.is_active(kill_flag)

    def test_activate_with_close_positions_writes_marker(self, kill_flag):
        kill_switch.activate(close_positions=True, path=kill_flag)
        assert "close_positions" in kill_flag.read_text(encoding="utf-8")
        assert kill_switch.close_positions_requested(kill_flag)

    def test_deactivate_removes_flag(self, kill_flag):
        kill_switch.activate(path=kill_flag)
        assert kill_switch.deactivate(kill_flag) is True
        assert not kill_switch.is_active(kill_flag)
        assert kill_switch.deactivate(kill_flag) is False  # 冪等

    def test_activate_is_idempotent(self, kill_flag):
        kill_switch.activate(path=kill_flag)
        kill_switch.activate(path=kill_flag)
        assert kill_switch.is_active(kill_flag)


class TestKillSwitchBlocksOrders:
    def test_kill_flag_rejects_immediately(self, guard, registry, kill_flag):
        """キルフラグはポリシーが揃っていても最優先で全注文を拒否する。"""
        activate_required_policies(registry)
        guard.check(make_intent(), make_ctx())  # 通る状態を確認
        kill_switch.activate(path=kill_flag)
        with pytest.raises(RiskRejection) as ei:
            guard.check(make_intent(), make_ctx())
        assert ei.value.reason_code == "KILL_SWITCH"

    def test_kill_checked_before_policies(self, guard, kill_flag):
        """ポリシー未決裁でもキルフラグの理由が先に返る(チェック順序1)。"""
        kill_switch.activate(path=kill_flag)
        with pytest.raises(RiskRejection) as ei:
            guard.check(make_intent(), make_ctx())
        assert ei.value.reason_code == "KILL_SWITCH"
