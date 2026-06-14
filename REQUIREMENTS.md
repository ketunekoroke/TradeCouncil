# 要件一覧 — モノレポ全体

**モノレポ全体にかかわる事項だけ**を持つ薄い管理表(ADR-0011)。個別機能の要件は各プロジェクト:
[Magi/REQUIREMENTS.md](Magi/REQUIREMENTS.md) / [TradeCouncil/REQUIREMENTS.md](TradeCouncil/REQUIREMENTS.md) /
[shared/REQUIREMENTS.md](shared/REQUIREMENTS.md)。

## MR. モノレポ構造

| ID | 要件 | 優先度 | 状態 |
|---|---|---|---|
| REQ-MR01 | 疎結合の複数プロジェクトを1リポジトリ・1ブランチでディレクトリ単位に管理する。各プロジェクトは自前の CLAUDE.md・docs・管理表・workspace を持つ | 必須 | 実装済 |
| REQ-MR02 | `Magi` ⇎ `TradeCouncil` は相互非依存。一方のディレクトリを削除しても他方は動作する(疎結合の保証) | 必須 | 実装済 |
| REQ-MR03 | 共通ツール(LLMブリッジ・SharePoint・office・git フック)は `shared/` に集約し、両プロジェクトが path 起動で利用する | 必須 | 実装済 |
| REQ-MR04 | Python 実行環境はルート共有 `.venv`。シークレットはルート共有 `.env` に集約する | 必須 | 実装済 |
| REQ-MR05 | git フックはリポジトリ単位(`shared/hooks`)で、`tc hooks install` が pre-commit / post-commit / pre-push を導入する | 必須 | 実装済 |
| REQ-MR06 | 各プロジェクトの docs/管理表は SharePoint の `<Project>/Docs/` へ per-project でミラーされる(ADR-0010/0011) | 任意 | 実装済 |
