# 機能一覧 — Accounting(会計経理支援システム)

モノレポ全体の機能はルート [../FEATURES.md](../FEATURES.md)。本表は Accounting 固有。
状態: **実装済**(実装+テスト) / **雛形**([実装予定]の stub) / **仕様**(定義のみ)。

| ID | 機能 | 状態 | 実装/定義 | 関連要件 |
|---|---|---|---|---|
| FEAT-AC01 | プロジェクト足場(CLAUDE.md ルーター・docs 正本・管理表・workspace・config) | 実装済 | [CLAUDE.md](CLAUDE.md), [docs/](docs/) | REQ-AC01, REQ-AC03 |
| FEAT-AC02 | 運用 CLI(`python -m scripts.cli`: test / hooks install / sync / mirror) | 実装済 | [scripts/cli.py](scripts/cli.py) | REQ-AC01 |
| FEAT-AC03 | 削除可能性テスト(core が Magi/TradeCouncil 非依存)+ docs lint(適用開始日) | 実装済 | [tests/](tests/) | REQ-AC02, REQ-AC03 |
| FEAT-AC04 | Claude 安全フック(危険操作ブロック・正本/秘密の保護・編集後テスト) | 実装済 | [scripts/hooks/](scripts/hooks/) | REQ-EX05 |
| FEAT-AC05 | 月次レビュー シナリオ(LLM 召喚は `../shared` ブリッジ経由) | 雛形 | [scenarios/monthly-review.md](scenarios/monthly-review.md) | REQ-EX02 |
| FEAT-AC06 | MoneyForward API 疎通スパイク(設定を使い OAuth → offices。手動実行・実 creds 必要) | 雛形(設定連携済) | [scripts/spike_moneyforward.py](scripts/spike_moneyforward.py) | REQ-EX01, REQ-EX06 |
| FEAT-AC10 | MoneyForward API 設定の仕組み(非秘密 config + 秘密 env の解決・`ac mf config` 表示/検証) | 実装済 | [core/moneyforward.py](core/moneyforward.py), [core/config.py](core/config.py), [config/moneyforward.config.json](config/moneyforward.config.json) | REQ-EX06 |
| FEAT-AC07 | 検証ゲート(為替・税区分・証憑要件)/ ポリシー lint | 雛形 | [scripts/check_compliance.py](scripts/check_compliance.py) | REQ-EX02, REQ-TX01 |
| FEAT-AC08 | エージェント本体(取り込み・抽出・登録・会計連携・仕訳調整) | 仕様 | [core/](core/)(docstring に予定構成) | REQ-EX01〜04 |
| FEAT-AC09 | docs の SharePoint ミラー(git main → `Accounting/Docs/`・ADR-0010) | 実装済 | [sharepoint.config.json](sharepoint.config.json) + shared/hooks | REQ-AC03 |
