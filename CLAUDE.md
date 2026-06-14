# CLAUDE.md — モノレポ・ルーター(Magi / TradeCouncil / shared)

このリポジトリは**疎結合の複数プロジェクトを1リポジトリ・1ブランチで管理するモノレポ**
(ADR-0011)。**開発は各プロジェクトのディレクトリへ `cd` してから行う** — そのディレクトリの
`CLAUDE.md`・`.claude/`・`docs/`・テストが適用される。第一階層(ここ)は**全プロジェクトに
共通する事項だけ**を持つ。

## プロジェクト一覧

| ディレクトリ | 役割 | 入口 |
|---|---|---|
| **[Magi/](Magi/CLAUDE.md)** | 汎用マルチエージェント基盤(ブレスト・資料レビュー・合議・人格テスト。MAGI 3人格) | `cd Magi` |
| **[TradeCouncil/](TradeCouncil/CLAUDE.md)** | 自動売買ガバナンス・フレームワーク(売買BOT・リスク・会議体) | `cd TradeCouncil` |
| **shared/** | 共通ツール層(LLMブリッジ・SharePoint・office変換・git フック)。path 起動・pip 不要 | 直接編集可 |

## 依存と疎結合(削除可能性の保証 — ADR-0011)

- `Magi` → `shared` のみ。`TradeCouncil`(売買の実行時 `core/`)→ **依存なし**。
  `TradeCouncil` の council シナリオ → `shared`(LLM 召喚)
- **`Magi` ⇎ `TradeCouncil` は相互非依存**。一方のディレクトリを削除しても他方は動作する
  (`Magi/` を消しても `tc test` は緑。`TradeCouncil/` を消しても Magi の4シナリオは無傷)
- `shared/` は両者の土台。消すと両者の外部 LLM/SharePoint 連携が縮退するが、各プロジェクト
  固有のロジック(売買 core・シナリオ md)は生存する

## 共通の決まり(全プロジェクト)

- **Python 実行環境はルート共有 `.venv`**。各プロジェクトのテストはそのプロジェクト dir から
  `..\.venv\Scripts\python.exe -m pytest`(TradeCouncil は `tc test` も可)。共通スイートは
  ルートで `.venv\Scripts\python.exe -m pytest shared/tests`
- **シークレットはルート共有 `.env` に集約**(`.env.example` をコピー)。解決順:
  環境変数 → ルート `.env` → `.claude/settings.local.json` の env。コミット禁止
- **git フックはリポジトリ単位**(`shared/hooks`)。`tc hooks install` で pre-commit(秘密/
  ポリシー検査)+ post-commit / pre-push(各プロジェクトの docs を SharePoint へミラー — ADR-0010)を導入
- **環境変数の命名規約**(コーディング規約・ADR-0011): 環境変数は**共有層(shared)の設定にのみ**
  使い、**ドメイン別プレフィックス**で名付ける(プロジェクト名は使わない)。
  - `SHAREPOINT_*`(SharePoint 接続)/ `BRIDGE_*`(LLMブリッジ実行設定)/ `OFFICE_*`(Office 変換)/
    プロバイダ標準キー `OPENAI_API_KEY`・`GEMINI_API_KEY`
  - **プロジェクトごとに異なる設定は env で分けない** — 各プロジェクトの config
    (例 `*/sharepoint.config.json` の `root`・`folders`)で表現する。env は全プロジェクト共通の
    接続・実行設定だけに使う
  - 旧 `MAGI_*` は非推奨エイリアス(`shared/bridge_common.py` の `setting()` が後方互換で読む)。
    新規コードは正準名のみを使う
- **Conventional Commits**。コミットは原則あるプロジェクトに閉じる(`refactor(TradeCouncil): ...`)
- ルートの管理表([REQUIREMENTS](REQUIREMENTS.md) / [FEATURES](FEATURES.md) /
  [TESTCASES](TESTCASES.md) / [BACKLOG](BACKLOG.md))は**モノレポ全体にかかわる事項だけ**。
  個別機能は各プロジェクトの管理表が持つ

## ルートで起動した場合

各プロジェクトの `.claude/agents` が混ざる。人格を召喚する作業や開発は、必ず対象プロジェクトへ
`cd` してから行うこと(モード判定・人格セット・フックが正しく効く)。
