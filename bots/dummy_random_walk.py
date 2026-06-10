"""ダミー戦略(Phase 0 の24h稼働試験用 — 収益を狙わない固定ルール)。

ルール(決定的):
  - ポジションが無ければ hold_bars ごとの周期で order_qty を買う
  - ポジションを hold_bars 保有したら全量売る
目的は「発注 → risk_guard → 執行 → 記録」のループを常時回すことだけ。
"""

from __future__ import annotations

from bots.base import BarData, Strategy, StrategyIntent


class DummyRandomWalk(Strategy):
    def __init__(self, bot_id: str, params: dict) -> None:
        super().__init__(bot_id, params)
        self._order_qty = float(params["order_qty"])
        self._hold_bars = int(params.get("hold_bars", 3))
        self._bar_count = 0
        self._bars_held = 0

    def on_bar(self, bar: BarData, position_qty: float) -> list[StrategyIntent]:
        self._bar_count += 1
        rationale_base = {
            "rule": "dummy_fixed_cycle",
            "bar_ts": bar.ts.isoformat(),
            "close": bar.c,
            "position_qty": position_qty,
            "bar_count": self._bar_count,
        }

        if position_qty > 0:
            self._bars_held += 1
            if self._bars_held >= self._hold_bars:
                self._bars_held = 0
                return [
                    StrategyIntent(
                        side="sell",
                        qty=position_qty,
                        reduces_position=True,
                        est_max_loss_jpy=0.0,
                        rationale={**rationale_base, "action": "exit_after_hold"},
                    )
                ]
            return []

        self._bars_held = 0
        if self._bar_count % self._hold_bars == 1:
            notional = self._order_qty * bar.c
            return [
                StrategyIntent(
                    side="buy",
                    qty=self._order_qty,
                    # 固定ルールの想定最大損失: 想定元本の1%(ダミー用の控えめな見積り)
                    est_max_loss_jpy=notional * 0.01,
                    rationale={**rationale_base, "action": "enter_cycle"},
                )
            ]
        return []
