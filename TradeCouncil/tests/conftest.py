"""共通フィクスチャ。

注意: テスト用ポリシー値は「テストであることが明白な値」(99 / 999 等)を使う。
設計書のたたき台数値をテストに混入させない(第0回会議の議論を汚染しないため)。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session, sessionmaker

from core.db.engine import create_db_engine
from core.db.models import Base
from core.governance.registry import PolicyRegistry
from core.governance.schema import DecisionAction, DecisionRecord

TEST_DECIDED_AT = "2026-01-01T00:00:00+09:00"

# キー名は本番と同一・値はテスト用(明白に緩い値 = 既定で注文が通る)
TEST_POLICY_VALUES: dict[str, dict[str, Any]] = {
    "P-01": {"delegation": {"enabled": False}},
    "P-02": {
        "account_max_effective": 1.0,
        "per_asset_class": {"crypto_spot": 1.0},
        "hard_ceiling": 1.0,
    },
    "P-03": {
        "max_daily_loss_pct": 99.0,
        "max_weekly_drawdown_pct": 99.0,
        "per_trade_max_loss_pct": 99.0,
        "max_total_exposure_pct": 999.0,
        "per_bot_max_positions": 999,
    },
    "P-04": {
        "stale_data_sec": 999999,
        "cb_price_jump_pct_1m": 999.0,
        "cb_max_spread_bps": 99999,
    },
}

TEST_POLICY_TITLES: dict[str, str] = {
    "P-01": "決裁・委任規程(テスト)",
    "P-02": "レバレッジ規程(テスト)",
    "P-03": "口座リスク上限(テスト)",
    "P-04": "セーフガード運用(テスト)",
}


@pytest.fixture(autouse=True)
def _isolate_var_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """開発者シェルの TC_VAR_DIR 残留からテストを隔離する(ADR-0004)。"""
    monkeypatch.delenv("TC_VAR_DIR", raising=False)


@pytest.fixture
def db_session_factory(tmp_path: Path) -> sessionmaker[Session]:
    engine = create_db_engine(tmp_path / "test.db")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def registry(tmp_path: Path, db_session_factory: sessionmaker[Session]) -> PolicyRegistry:
    return PolicyRegistry(
        policies_dir=tmp_path / "policies",
        generated_dir=tmp_path / "generated",
        session_factory=db_session_factory,
    )


def make_decision(
    policy_id: str,
    value: dict[str, Any] | None = None,
    action: DecisionAction = DecisionAction.APPROVE,
    **overrides: Any,
) -> DecisionRecord:
    """テスト用の決裁レコードを作る(レジストリAPI経由で正規の決裁フローを通す)。"""
    kwargs: dict[str, Any] = dict(
        policy_id=policy_id,
        title=TEST_POLICY_TITLES.get(policy_id, f"{policy_id}(テスト)"),
        action=action,
        value=value,
        decided_by="owner",
        channel="sync_council",
        session_ref="council-test",
        basis_refs=["tests/conftest.py"],
        decided_at=TEST_DECIDED_AT,
    )
    kwargs.update(overrides)
    return DecisionRecord(**kwargs)


def activate_required_policies(
    registry: PolicyRegistry,
    overrides: dict[str, dict[str, Any]] | None = None,
) -> None:
    """P-01〜P-04 を正規の決裁フロー(record_decision)で active 化する。

    overrides で特定ポリシーの value を差し替えられる(境界値テスト用)。
    """
    for policy_id, value in TEST_POLICY_VALUES.items():
        merged = dict(value)
        if overrides and policy_id in overrides:
            merged = overrides[policy_id]
        registry.record_decision(make_decision(policy_id, merged))
