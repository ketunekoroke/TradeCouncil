from bots.base import BarData, Strategy, StrategyIntent
from bots.dummy_random_walk import DummyRandomWalk

# 戦略レジストリ(config/bots/*.yaml の strategy フィールドで参照)
STRATEGIES: dict[str, type[Strategy]] = {
    "dummy_random_walk": DummyRandomWalk,
}

__all__ = ["STRATEGIES", "BarData", "Strategy", "StrategyIntent"]
