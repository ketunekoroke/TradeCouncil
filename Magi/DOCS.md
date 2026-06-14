# DOCS — Magi(運用ガイド 概観)

Magi(汎用マルチエージェント基盤)の全体像。**一次資料は
[docs/07_シナリオ・人格基盤.md](docs/07_シナリオ・人格基盤.md)**(深い仕様)。進め方・作法は
[CLAUDE.md](CLAUDE.md)、編集は [DEVELOPMENT.md](DEVELOPMENT.md)、使い方は [README.md](README.md)。
本書は索引・概観で、詳細は docs/07 の各章へ繋ぐ(重複させない)。

## docs/07(一次資料)の章立て

| 章 | 内容 |
|---|---|
| 1. コンセプト | 価値観で分ける人格・意図的な弱み・好奇心の屈折 |
| 2. システム構成 | ファシリテーター + 人格サブエージェント + シナリオプロトコル + LLMブリッジ |
| 3. 人格(8人格体制) | MAGI 3人格 + TradeCouncil 5ペルソナの設計思想 |
| 4. シナリオとプロトコル | 合議/レビュー/ブレスト/人格テストの Round 構成・モード |
| 5. 成果物 | Markdown 常時 + Excel/Word/チャート任意 |
| 6. メディア入出力 | 画像/PDF/Office の渡し方(全人格に等しく) |
| 7. セットアップ | Claude Code・Python依存・.env のキー |
| 8. 使い方 | シナリオ別の発話例 |
| 9. ディレクトリ構成 | scenarios・agents・workspace・docs |
| 10. SharePoint 連携 | sync / mirror の要点 |
| 11. Git / 12. カスタマイズ / 13. 既知の制約 / 14. 今後の発展 | |

## シナリオ早見

| シナリオ | 使うとき | 出力先 |
|---|---|---|
| 合議(deliberation) | 賛否を聞いて考えを整理したい | `workspace/deliberations/` |
| 資料チェック&リバイス(document-review) | 資料を添削・改訂したい | `workspace/reviews/` |
| ブレスト(brainstorm) | アイデアを発散・評価したい | `workspace/brainstorms/` |
| 人格テスト(persona-test) | 人格の個性・回帰を確認したい | `workspace/persona-tests/` |

> council(意思決定会議)は売買固有 → [../TradeCouncil/](../TradeCouncil/CLAUDE.md)。

## LLMバックエンド

人格は claude / openai / gemini を frontmatter で選べる(混在可)。ブリッジは共通層
[../shared/](../shared/) にあり、リトライ・フォールバック・ファイル添付・履歴渡しに対応。
詳細は [../shared/README.md](../shared/README.md) と docs/07 §2/§12。

## SharePoint 連携

`sharepoint.config.json`(`env_prefix: MAGI`)の `enabled=true` で
`python ../shared/sharepoint.py sync --project .` が `workspace/` を双方向同期(追加型・
newer-wins・削除非伝播 — ADR-0009)。docs/管理表は git main → SharePoint `Magi/Docs/` へ
一方向ミラー(ADR-0010)。接続(site/client/secret)はプロジェクト別に設定可(ADR-0011)。
Azure 設定手順は [../TradeCouncil/docs/setup/sharepoint-azure-app-setup.md](../TradeCouncil/docs/setup/sharepoint-azure-app-setup.md)。

## 既知の制約(要点)

- シナリオ・人格は手動実行(自動テストはブリッジ部のみ — `../shared/tests`)
- openai/gemini 人格はステートレス(文脈は毎ラウンド渡す or `--history`)
- 詳細は docs/07 §13。
