# DEVELOPMENT — Magi

Magi(シナリオ・人格)の編集作法。共通ブリッジ(LLM/SharePoint/office)は [../shared/](../shared/)
にあり、その変更は全プロジェクトに影響する点に注意。

## 編集パターン

| やること | 手順 |
|---|---|
| シナリオのプロトコル変更 | `scenarios/<name>.md` を編集 → [docs/07](docs/07_シナリオ・人格基盤.md) と FEATURES/TESTCASES を同期 → persona-test/該当シナリオで挙動確認 |
| 人格の調整 | `.claude/agents/<name>.md` の本文(=システムプロンプト)を編集 → **persona-test シナリオで回帰**(識別性・弱みの再現を確認) |
| 新シナリオ追加 | `scenarios/<name>.md` を1ファイルで作成 → `scenarios/README.md` と CLAUDE.md のモード判定表に追記 → REQUIREMENTS/FEATURES/TESTCASES |
| ブリッジの不具合 | `../shared/` で修正(ask_openai/ask_gemini/bridge_common)→ `shared/tests` と docs/testing |

## ドキュメント同期

シナリオ・人格を変えたら: [docs/07_シナリオ・人格基盤.md](docs/07_シナリオ・人格基盤.md)(一次資料・直接改訂可)→
[DOCS.md](DOCS.md) → [REQUIREMENTS.md](REQUIREMENTS.md) → [FEATURES.md](FEATURES.md) →
[TESTCASES.md](TESTCASES.md) を併せて更新する。

## テスト

ブリッジの自動テストはルートで `.venv\Scripts\python.exe -m pytest shared/tests`。
シナリオ・人格は手動(実機 LLM)で [docs/testing/scenario-bridge-testcases.md](docs/testing/scenario-bridge-testcases.md) に従う。
