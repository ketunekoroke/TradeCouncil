# 機能一覧 — モノレポ全体

**モノレポ全体にかかわる機能だけ**。個別機能は各プロジェクト:
[Magi/FEATURES.md](Magi/FEATURES.md) / [TradeCouncil/FEATURES.md](TradeCouncil/FEATURES.md) /
[shared/FEATURES.md](shared/FEATURES.md)。

| ID | 機能 | 状態 | 実装/定義 | 関連要件 |
|---|---|---|---|---|
| FEAT-MR01 | 3層プロジェクト構成(Magi / TradeCouncil / shared)とルーター CLAUDE | 実装済 | [CLAUDE.md](CLAUDE.md) | REQ-MR01 |
| FEAT-MR02 | ルート共有 .venv + .env、per-project pyproject/テスト | 実装済 | [pyproject.toml](pyproject.toml), 各 `*/pyproject.toml` | REQ-MR04 |
| FEAT-MR03 | リポジトリ単位の git フックと全プロジェクト走査の docs ミラー | 実装済 | [shared/hooks/](shared/hooks/) | REQ-MR05, REQ-MR06 |
