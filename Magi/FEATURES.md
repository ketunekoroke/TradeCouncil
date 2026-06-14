# 機能一覧(Features)— Magi(シナリオ・人格基盤)

汎用シナリオと人格の機能の棚卸し。要件は [REQUIREMENTS.md](REQUIREMENTS.md)、検証は
[TESTCASES.md](TESTCASES.md)、一次資料は [docs/07_シナリオ・人格基盤.md](docs/07_シナリオ・人格基盤.md)。
LLMブリッジ実装(FEAT-82〜99)は [../shared/FEATURES.md](../shared/FEATURES.md)。

- 状態: **実装済** / **仕様**(プロトコルとして定義・ファシリテーターが手動実行)

---

## ルーター・シナリオ

| ID | 機能 | 状態 | 実装/定義 | 関連要件 |
|---|---|---|---|---|
| FEAT-50 | モード判定ルーター + シナリオ選択 | 仕様 | [CLAUDE.md](CLAUDE.md) | REQ-SC01 |
| FEAT-53 | MAGI 3人格 + 4シナリオ(合議/資料レビュー/ブレスト/人格テスト) | 仕様 | [scenarios/](scenarios/), [.claude/agents/](.claude/agents/) | REQ-SC04 |
| FEAT-60 | チームメイト召喚と人格間対話(claude は SendMessage、使えない環境はファシリテーター仲介=ダイジェスト/`--history` フォールバック) | 仕様 | [CLAUDE.md](CLAUDE.md) | REQ-DL07, REQ-SC02 |
| FEAT-61 | シナリオ別出力先の分離(workspace/deliberations 等 — ADR-0009) | 実装済 | [CLAUDE.md](CLAUDE.md) | REQ-SC05 |
| FEAT-62 | 合議: 3モード(Lite/Standard/Full)と Round 0〜9 の進行 | 仕様 | [scenarios/deliberation.md](scenarios/deliberation.md) | REQ-DL03, REQ-DL04 |
| FEAT-63 | 合議: 確信度加重の投票・少数意見の保持 | 仕様 | [scenarios/deliberation.md](scenarios/deliberation.md) | REQ-DL05 |
| FEAT-64 | レビュー: 価値観レンズの投影(正確性/読者/訴求力) | 仕様 | [scenarios/document-review.md](scenarios/document-review.md) | REQ-DR01 |
| FEAT-65 | レビュー: 深度モード(Quick/Standard/Deep)と Round 0〜6 | 仕様 | [scenarios/document-review.md](scenarios/document-review.md) | REQ-DR02〜04 |
| FEAT-66 | レビュー: 衝突指摘の裁定と must/should/nice/見送り分類 | 仕様 | [scenarios/document-review.md](scenarios/document-review.md) | REQ-DR05 |
| FEAT-67 | レビュー: 指摘レポート+同形式改訂版+変更履歴+未採用指摘の保持 | 仕様 | [scenarios/document-review.md](scenarios/document-review.md) | REQ-DR06〜09 |
| FEAT-68 | ブレスト: レンズを発散と評価の両方に投影(実現/人/独創) | 仕様 | [scenarios/brainstorm.md](scenarios/brainstorm.md) | REQ-BR01 |
| FEAT-69 | ブレスト: モードと Round 0〜8(発散巡数固定・早期収束) | 仕様 | [scenarios/brainstorm.md](scenarios/brainstorm.md) | REQ-BR03 |
| FEAT-70 | ブレスト: 独立大量発散 → マップ化(クラスタ・白地)→ build-on/掛け合わせ二次発散 | 仕様 | [scenarios/brainstorm.md](scenarios/brainstorm.md) | REQ-BR02, REQ-BR04 |
| FEAT-71 | ブレスト: レンズ別 0〜10 採点(内訳保持)・割れた尖り案の別枠保持 | 仕様 | [scenarios/brainstorm.md](scenarios/brainstorm.md) | REQ-BR05, REQ-BR06 |
| FEAT-72 | ブレスト: 上位案の3レンズ協働ブラッシュアップ+Deep プレモーテム | 仕様 | [scenarios/brainstorm.md](scenarios/brainstorm.md) | REQ-BR07 |
| FEAT-73 | ブレスト: 成果物一式(アイデア集・Mermaid マップ・評価マトリクス・上位案) | 仕様 | [scenarios/brainstorm.md](scenarios/brainstorm.md) | REQ-BR08 |
| FEAT-74 | 人格テスト: 固定プローブ・バッテリの独立投下・差分マトリクス・人格別判定(Round 0〜4・3モード) | 仕様 | [scenarios/persona-test.md](scenarios/persona-test.md) | REQ-PT01〜03, REQ-PT06 |
| FEAT-75 | 人格テスト: 識別性チェック(似すぎ警告)+ベースライン回帰比較(Deep)・backend 揃え | 仕様 | [scenarios/persona-test.md](scenarios/persona-test.md) | REQ-PT04, REQ-PT05, REQ-PT07 |
| FEAT-76 | 成果物生成: Markdown ログ常時 + Excel/Word/チャート任意 + 同形式改訂版 | 仕様 | scenarios/ 各「成果物」節 | REQ-SC07, REQ-DR06 |

## 人格・バックエンド

| ID | 機能 | 状態 | 実装/定義 | 関連要件 |
|---|---|---|---|---|
| FEAT-77 | 価値観ベース人格 + frontmatter スキーマ(name/description/backend/model) | 実装済 | [.claude/agents/](.claude/agents/) | REQ-PE01〜03 |
| FEAT-78 | 好奇心・興味の共通駆動(レンズ別に対象・強度が屈折、向きにくい対象が弱みと呼応) | 実装済 | [.claude/agents/](.claude/agents/), [docs/07](docs/07_シナリオ・人格基盤.md) | REQ-PE04 |
| FEAT-79 | backend 振り分け(claude/openai/gemini)・混在・使用モデルのログ明記 | 仕様 | [CLAUDE.md](CLAUDE.md) | REQ-LB01〜03, REQ-SC08 |
| FEAT-80 | ステートレス人格の継続(毎ラウンド文脈付与・`--history` 多ターン履歴) | 実装済 | [../shared/bridge_common.py](../shared/bridge_common.py) `load_history` | REQ-LB04 |
| FEAT-81 | 拒否/空応答の自動再試行(`BRIDGE_GEN_MAX_RETRIES`)+言い換え再実行の作法 | 実装済 | `run_with_retry` / `extract_output_text` | REQ-LB05 |
