"""リスク層の例外。"""

from __future__ import annotations


class RiskRejection(Exception):
    """risk_guard による注文拒否。reason_code で機械可読に分類する。

    主な reason_code:
      KILL_SWITCH / POLICY_MISSING:<id> / POLICY_KEY_MISSING:<id>.<key> /
      ASSET_CLASS_BLOCKED:<class> / STALE_DATA / CIRCUIT_BREAKER_PRICE_JUMP /
      CIRCUIT_BREAKER_SPREAD / PER_TRADE_LOSS / DAILY_LOSS_LIMIT /
      WEEKLY_DRAWDOWN / EXPOSURE_LIMIT / MAX_POSITIONS / LEVERAGE_LIMIT
    """

    def __init__(self, reason_code: str, message: str = "") -> None:
        self.reason_code = reason_code
        super().__init__(f"{reason_code}: {message}" if message else reason_code)
