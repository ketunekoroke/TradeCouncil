# テストケース一覧(Test Cases)— Magi(シナリオ・人格)

シナリオ・人格の検証。**詳細手順の一次資料は
[docs/testing/scenario-bridge-testcases.md](docs/testing/scenario-bridge-testcases.md)**(独立 TC 名前空間)。
ブリッジ・SharePoint の自動テストは [../shared/TESTCASES.md](../shared/TESTCASES.md)。

## P0(自動・無課金)

| ID | タイトル | 実行方法 | 関連 |
|---|---|---|---|
| TC-016 | 人格 frontmatter の妥当性(name/description/backend/model が揃う) | grep(3人格 + 利用側ペルソナ)。詳細: [docs/testing/scenario-bridge-testcases.md](docs/testing/scenario-bridge-testcases.md) | REQ-SC03, REQ-PE02 |
| TC-027 | **シナリオ基盤 P0 一式**(frontmatter 除去・UTF-8 入出力・成果物テンプレート整合など — docs/testing §P0 のうちシナリオ分) | [docs/testing/scenario-bridge-testcases.md](docs/testing/scenario-bridge-testcases.md) §P0 | REQ-SC, REQ-PE |

## P1(手動・主要パス)

| ID | タイトル | 手順 | 関連 |
|---|---|---|---|
| TC-104 | 合議シナリオ(Lite)が完走し `workspace/deliberations/` に出力される | 「議題: <軽いお題>」 | REQ-DL01〜05 |
| TC-107 | **シナリオ基盤 P1 一式**(3人格の個性再現・各シナリオの一周・成果物整合 — 約16件) | [docs/testing/scenario-bridge-testcases.md](docs/testing/scenario-bridge-testcases.md) §P1 | REQ-DL, REQ-DR, REQ-BR, REQ-PT |

## P2(API課金・長時間)

| ID | タイトル | 手順 | 関連 |
|---|---|---|---|
| TC-203 | backend 混在の合議(1名を openai/gemini に切替)が完走し成果物に model 明記 | frontmatter 変更 → 合議 | REQ-SC03, REQ-SC08 |
| TC-207 | **シナリオ基盤 P2 一式**(各シナリオ一周〔合議/レビュー/ブレスト/人格テスト〕・backend 混在 — docs/testing §P2 のシナリオ分) | [docs/testing/scenario-bridge-testcases.md](docs/testing/scenario-bridge-testcases.md) §P2 | REQ-DL, REQ-DR, REQ-BR, REQ-PT |

## P3(エッジ・環境依存)

| ID | タイトル | 内容 | 関連 |
|---|---|---|---|
| TC-306 | **シナリオ基盤 P3 一式**(好奇心の屈折確認・人格の識別性・弱みの再現など — docs/testing §P3 のシナリオ分) | [docs/testing/scenario-bridge-testcases.md](docs/testing/scenario-bridge-testcases.md) §P3 | REQ-PE, REQ-PT |
