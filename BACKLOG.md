# BACKLOG — モノレポ全体

**モノレポ全体にかかわる項目だけ**。各プロジェクト固有のバックログは
[Magi/BACKLOG.md](Magi/BACKLOG.md) / [TradeCouncil/BACKLOG.md](TradeCouncil/BACKLOG.md) /
[shared/BACKLOG.md](shared/BACKLOG.md)(ID プレフィックス: 全体=`MR-` / 売買=`BL-` / MAGI=`MG-` / 共有=`SH-`)。

## 完了

### 2026-06-13
- MR-001 ✅ モノレポ3層再編(ADR-0011)。MAGI 汎用機能を `Magi/`、自動売買を `TradeCouncil/`、共通ツール(LLMブリッジ・SharePoint・office・git フック)を `shared/` に整理。`Magi` ⇎ `TradeCouncil` 相互非依存(削除可能)・ルート共有 .venv/.env・per-project workspace/sharepoint/docs ミラー・git フックはリポジトリ単位。prototype/ 削除。売買196件 + 共通35件緑

## プロダクトバックログ

| ID | ストーリー | 備考 |
|---|---|---|
| MR-002 | 開発者として `Magi` を別リポジトリへ切り出す(git subtree split)選択肢を持ちたい。なぜなら他プロジェクトで Magi だけを使う場面が出るかもしれないから | 現状はモノレポで足りる。需要が出たら検討(shared も同梱が必要) |
