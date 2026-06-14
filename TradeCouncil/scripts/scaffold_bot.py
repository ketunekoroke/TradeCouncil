"""BOT スキャフォールド(`tc bot new` の実体。ADR-0007 §3〜4)。

戦略の雛形4ファイル(bots/ 戦略クラス・config/bots/ 設定・tests/bots/ テスト・
docs/strategies/ 戦略カード)を一括生成する。

設計上の決まりごと:
  - 既存ファイルがあれば FileExistsError で「何も書かずに」拒否(部分生成しない)
  - 戦略カードは docs/strategies/_template.md から生成(テンプレート二重持ちしない)
  - STRATEGIES レジストリ(bots/__init__.py)は自動編集しない。生成されるテスト雛形の
    登録検査が red になることで、人間のレビューを伴う登録を誘導する
  - config は enabled: false 既定(生成しただけの BOT を意図せず走らせない)
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

# 小文字 snake_case(Python モジュール名 / bot_id 規約)
_IDENT_RE = re.compile(r"^[a-z][a-z0-9_]*$")

_STRATEGY_TEMPLATE = '''"""{strategy_key} 戦略。

詳細(仮説・パラメータ根拠・学び)は docs/strategies/{strategy_key}.md(戦略カード)。
注意(原則2: 権限分離): bots/ は core.exchange / core.execution を import しない。
戦略は BarData を受け取り StrategyIntent(意図)を返すだけ。発注経路は bot_runner が握る。
"""

from __future__ import annotations

from bots.base import BarData, Strategy, StrategyIntent


class {class_name}(Strategy):
    def __init__(self, bot_id: str, params: dict) -> None:
        super().__init__(bot_id, params)
        # パラメータは config/bots/{bot_id}.yaml の params から(ハードコード禁止)。
        # 例: self._lookback = int(params["lookback"])

    def on_bar(self, bar: BarData, position_qty: float) -> list[StrategyIntent]:
        # 全 Intent の rationale に判断材料を必ず入れる(trade_decisions に記録され
        # 週次レビューの一次資料になる)。
        rationale_base = {{
            "rule": "{strategy_key}",
            "bar_ts": bar.ts.isoformat(),
            "close": bar.c,
            "position_qty": position_qty,
        }}
        _ = rationale_base  # TODO: ロジック実装時に使用する
        # TODO: エントリー/イグジット条件を実装する(docs/06_戦略開発ガイド.md §2)。
        #   - est_max_loss_jpy はストップ幅等のロジックから導出する(固定率は不可)
        #   - 決定的に書く(乱数を使うなら seed を params で受ける)
        return []
'''

_CONFIG_TEMPLATE = """# {bot_id}(tc bot new で生成)
# 戦略カード: docs/strategies/{strategy_key}.md / パラメータの根拠もカードに書く
bot_id: {bot_id}
strategy: {strategy_key}
instrument_id: paper.btc_jpy.spot
enabled: false   # 実装・テスト完了まで起動させない(試走時に true へ)
params: {{}}
#  例:
#  lookback: 20
"""

_TEST_TEMPLATE = '''"""{strategy_key} 戦略のテスト(tc bot new で生成)。

テストファースト: on_bar の期待挙動を先に書いてから実装する(docs/06 §1-④)。
"""

from __future__ import annotations

from datetime import UTC, datetime

from bots import STRATEGIES
from bots.base import BarData
from bots.{strategy_key} import {class_name}


def _bar(close: float, ts: datetime | None = None) -> BarData:
    ts = ts or datetime(2026, 1, 1, tzinfo=UTC)
    return BarData(ts=ts, o=close, h=close, l=close, c=close, v=1.0)


def test_registered_in_strategies() -> None:
    """STRATEGIES レジストリに登録されていること(bots/__init__.py に手動追加する)。"""
    assert STRATEGIES.get("{strategy_key}") is {class_name}


def test_on_bar_returns_intent_list() -> None:
    strategy = {class_name}("{bot_id}", {{}})
    intents = strategy.on_bar(_bar(100.0), position_qty=0.0)
    assert isinstance(intents, list)


# TODO: 戦略ロジックの期待挙動をここに先に書く(red)→ 実装して green にする。
#   - エントリー条件を満たすバー列 → buy Intent(rationale・est_max_loss_jpy を検証)
#   - イグジット条件 → sell Intent(reduces_position=True)
#   - 条件を満たさないバー → 空リスト
'''


def _class_name(strategy_key: str) -> str:
    """snake_case の strategy_key から CamelCase のクラス名を作る。"""
    return "".join(part.capitalize() for part in strategy_key.split("_"))


def _validate(name: str, value: str) -> None:
    if not _IDENT_RE.match(value):
        raise ValueError(
            f"{name} が不正です: {value!r}(小文字 snake_case: ^[a-z][a-z0-9_]*$)"
        )


def scaffold_bot(bot_id: str, strategy_key: str, *, root: Path) -> list[Path]:
    """戦略の雛形4ファイルを生成し、生成したパスのリストを返す。

    Raises:
        ValueError: bot_id / strategy_key が規約(小文字 snake_case)に合わない
        FileNotFoundError: docs/strategies/_template.md が無い
        FileExistsError: 生成先のいずれかが既存(この場合は何も書かない)
    """
    _validate("bot_id", bot_id)
    _validate("strategy_key", strategy_key)

    template_path = root / "docs" / "strategies" / "_template.md"
    if not template_path.exists():
        raise FileNotFoundError(f"戦略カードテンプレートがありません: {template_path}")

    class_name = _class_name(strategy_key)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    card = (
        template_path.read_text(encoding="utf-8")
        .replace("{strategy_key}", strategy_key)
        .replace("{bot_id}", bot_id)
        .replace("{date}", today)
    )

    targets: dict[Path, str] = {
        root / "bots" / f"{strategy_key}.py": _STRATEGY_TEMPLATE.format(
            strategy_key=strategy_key, class_name=class_name, bot_id=bot_id
        ),
        root / "config" / "bots" / f"{bot_id}.yaml": _CONFIG_TEMPLATE.format(
            bot_id=bot_id, strategy_key=strategy_key
        ),
        root / "tests" / "bots" / f"test_{strategy_key}.py": _TEST_TEMPLATE.format(
            strategy_key=strategy_key, class_name=class_name, bot_id=bot_id
        ),
        root / "docs" / "strategies" / f"{strategy_key}.md": card,
    }

    # fail-closed: 1ファイルでも既存なら何も書かない(部分生成しない)
    existing = [p for p in targets if p.exists()]
    if existing:
        raise FileExistsError(
            "生成先が既存のため中止(何も書いていません): "
            + ", ".join(str(p) for p in existing)
        )

    for path, content in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    return list(targets)
