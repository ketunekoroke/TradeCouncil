# Magi — 汎用マルチエージェント・シナリオ基盤

価値観で分かれた MAGI 3人格(melchior=論理 / balthasar=共感 / casper=直感)で
**ブレスト・資料レビュー・合議・人格テスト**を行う汎用エージェント基盤。
モノレポの1プロジェクト([../README.md](../README.md) / ADR-0011)。

## 使い方

このディレクトリで `claude` を起動し、シナリオを起動する発話をする(例:「議題: ○○についてどう思う?」
「この資料をレビューして」)。進行は [CLAUDE.md](CLAUDE.md) と [scenarios/README.md](scenarios/README.md)。

OpenAI / Gemini 人格を使う場合はルート共有 `.env` に API キーを設定する。ブリッジは共通層
[../shared/](../shared/) にあり、`python ../shared/ask_openai.py ...` で呼ぶ。

## ドキュメント

| 知りたいこと | 読むファイル |
|---|---|
| シナリオの進め方・人格・バックエンド | [CLAUDE.md](CLAUDE.md) |
| 人格哲学・シナリオ詳細・ブリッジ内部仕様 | [docs/07_シナリオ・人格基盤.md](docs/07_シナリオ・人格基盤.md) |
| 要件・機能・テスト | [REQUIREMENTS.md](REQUIREMENTS.md) / [FEATURES.md](FEATURES.md) / [TESTCASES.md](TESTCASES.md) |
| 詳細テストケース | [docs/testing/scenario-bridge-testcases.md](docs/testing/scenario-bridge-testcases.md) |

## 構成

```
Magi/
├── CLAUDE.md            ルーター・人格・バックエンド・作法
├── .claude/agents/      melchior / balthasar / casper
├── scenarios/           deliberation / document-review / brainstorm / persona-test
├── docs/                07_シナリオ・人格基盤.md / testing/
├── workspace/           シナリオ入出力(SharePoint 同期対象)
└── REQUIREMENTS/FEATURES/TESTCASES/BACKLOG/DEVELOPMENT/DOCS.md
```
