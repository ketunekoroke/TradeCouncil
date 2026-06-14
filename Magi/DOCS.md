# DOCS — Magi(運用ガイド)

Magi の全体ガイド。一次資料は [docs/07_シナリオ・人格基盤.md](docs/07_シナリオ・人格基盤.md)。
進め方・人格・バックエンドは [CLAUDE.md](CLAUDE.md)。

## シナリオ早見

| シナリオ | 使うとき | 出力先 |
|---|---|---|
| 合議(deliberation) | 賛否を聞いて考えを整理したい | `workspace/deliberations/` |
| 資料チェック&リバイス(document-review) | 資料を添削・改訂したい | `workspace/reviews/` |
| ブレスト(brainstorm) | アイデアを発散・評価したい | `workspace/brainstorms/` |
| 人格テスト(persona-test) | 人格の個性・回帰を確認したい | `workspace/persona-tests/` |

## LLMバックエンド

人格は claude / openai / gemini を frontmatter で選べる(混在可)。ブリッジは共通層
[../shared/](../shared/) にあり、リトライ・フォールバック・ファイル添付・履歴渡しに対応。
詳細仕様は [../shared/README.md](../shared/README.md) と docs/07。

## SharePoint 連携

`sharepoint.config.json` の `enabled=true` で `python ../shared/sharepoint.py sync --project .` が
`workspace/` を双方向同期する(追加型・newer-wins・削除非伝播 — ADR-0009)。docs/管理表は
git main → SharePoint `Magi/Docs/` へ一方向ミラー(ADR-0010)。Azure 設定手順は
[../TradeCouncil/docs/setup/sharepoint-azure-app-setup.md](../TradeCouncil/docs/setup/sharepoint-azure-app-setup.md)。
