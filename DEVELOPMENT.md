# TradeCouncil 開発ガイド

本体(Phase 0 基盤)の編集・改善・拡張のための作業ガイド。

> 安全規約(絶対ルール)は [CLAUDE.md](CLAUDE.md) の「開発モード」が正本。
> ここでは「どこを・どう変えるか」の実務を扱う。

---

## どこから Claude Code を起動するか

| 目的 | 起動場所 | 動き |
|---|---|---|
| **会議・シナリオを実行する** | リポジトリ直下で `claude` | ルーター(CLAUDE.md)がモード判定し、ファシリテーターとして動く |
| **開発作業をする** | 同じくリポジトリ直下 | 発言が開発系ならそのまま開発モード(「実装」「修正」等) |
| MAGI プロトタイプを使う | `cd prototype && claude` | 旧プロトタイプ(独立・編集禁止) |

## 環境構築・テスト

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m scripts.cli db init
.venv\Scripts\python.exe -m scripts.cli hooks install
.venv\Scripts\python.exe -m scripts.cli test          # 全テスト
.venv\Scripts\python.exe -m scripts.cli test --risk   # riskカバレッジ90%ゲート
```

- 編集後は hooks が自動で高速テストを回す(core/bots/tests の .py 編集時)
- `core/risk/`・`core/execution/` の変更は**テスト先行**(tests を先に書く)

## 編集対象ファイル

| ファイル | 内容 | 編集頻度 |
|---|---|---|
| `core/governance/` | ポリシーレジストリ・decision_gate | 低(慎重に。risk-auditor 必須) |
| `core/risk/` | リスクガード・キルスイッチ | 低(慎重に。テスト先行 + risk-auditor 必須) |
| `core/exchange/` | アダプタ・フィード(Phase 1 で実勢価格を追加) | 中 |
| `bots/` + `config/bots/` | 戦略(core.exchange への import 禁止) | 中 |
| `scenarios/council.md` | 会議プロトコル | 低(慎重に) |
| `.claude/agents/*.md` | 人格定義(8名) | 中 |
| `CLAUDE.md` | ルーター + 共通作法 + 開発規約 | 低(慎重に) |
| `config/system.yaml` | 技術設定(運用ポリシーは書かない) | 中 |
| `DOCS.md` / `REQUIREMENTS.md` / `FEATURES.md` / `TESTCASES.md` | 管理文書 | 高(変更を反映) |
| `docs/adr/` | 設計判断の記録 | 設計逸脱・大きな判断のたび |

**編集してはいけない**: `prototype/`(参照のみ)、`config/policies/*.yaml`・`config/generated/`
(`tc policy record` / `sync` 経由のみ)、`var/`、`local/`・`sharepoint/` の生成物。

## よくある変更パターン

### パターン1: ペルソナを微調整する
1. `.claude/agents/<name>.md` の本文を編集(frontmatter の name は変えない)
2. **「意図的な弱み」「偏り」のセクションは消さない**(設計思想。docs/02 §5.1)
3. persona-test シナリオで個性が出ているか確認(TC-104 相当)

### パターン2: リスクチェックを追加する
1. `tests/risk/` に境界値テスト(ちょうど=可 / +ε=拒否)とキー欠落テストを**先に**書く
2. `core/risk/guard.py` のチェック順序に追加(しきい値は必ず `self._value("P-XX", key)` で読む。
   **コード内デフォルト値・フォールバック禁止**)
3. `scenarios/council.md` の必須キー表と `tests/conftest.py` の TEST_POLICY_VALUES を更新
4. `test --risk`(90%ゲート)→ risk-auditor で審査

### パターン3: 戦略を追加する
1. `bots/<name>.py`(Strategy 継承。BarData → StrategyIntent のみ。取引所APIに触らない)
2. `bots/__init__.py` の STRATEGIES に登録、`config/bots/<bot_id>.yaml` を作成
3. テスト追加 → ペーパーで稼働確認。**実弾コードは書かない(Phase 5 まで存在しない)**

### パターン4: ポリシー項目を増やす(例: P-05 悪BOT判定)
1. ポリシーの中身は**コードで決めない**。会議の議題にする(docs/03 第5章参照)
2. コードが新ポリシーを読む場合は `registry.require_value("P-XX", key)` を使う(欠落=拒否)
3. 必須(★)に昇格させる場合は `REQUIRED_POLICY_IDS`(core/governance/schema.py)に追加
   — これは fail-closed の範囲を広げる変更なので risk-auditor + 利用者確認必須

### パターン5: シナリオを追加する
1. `scenarios/<name>.md` 新規作成(固有のラウンド・成果物だけ書く。共通作法は CLAUDE.md 参照)
2. `scenarios/README.md` の一覧・兆候表、`CLAUDE.md` のシナリオ選択表・出力先表に追記
3. 出力先を新設する場合は `local/`・`sharepoint/` にディレクトリ + `.gitkeep`
4. 管理文書(下記)を同期

## ドキュメント同期ルール(忘れがち)

| 変更内容 | 更新が必要なファイル |
|---|---|
| 仕様の変更 | `docs/`(一次資料)→ `DOCS.md` → `REQUIREMENTS.md` → `FEATURES.md` → `TESTCASES.md` |
| 設計書からの逸脱 | `docs/adr/`(新しい ADR を起票) |
| 人格を追加・編集 | `.claude/agents/` + `DOCS.md` 4章 + 会議で使うなら `scenarios/council.md` |
| ポリシーキー変更 | `scenarios/council.md` 必須キー表 + `tests/conftest.py` + `DOCS.md` 6章 |
| CLI コマンド追加 | `scripts/cli.py` + `README.md` 表 + `CLAUDE.md` コマンド表 |

迷ったら **docs/(一次資料)を正**とし、それ以外を追従させる。

## コミット規約

Conventional Commits + スコープ:

```
feat(core/risk): add margin maintenance check
feat(bots): add trend following strategy
docs(scenarios): clarify council round 2 veto rules
fix(cli): handle missing bot config
chore: update dependencies
```

- 動く単位ごとに1コミット。仕様変更と実装変更は同じコミットにまとめてよい
- pre-commit(`tc hooks install` 済み)が秘密情報・不正なポリシー変更を検査する

## Windows 運用メモ

- 実行は `.venv\Scripts\python.exe -m scripts.cli ...`(tc.exe シムはブロックされる環境がある)
- 24h試験前に `powercfg /change standby-timeout-ac 0`(スリープ無効化)
- 常駐はコンソール2枚(paper / watchdog)。停止は Ctrl+C または `kill`
- VPS(Linux + systemd)移行は Phase 1 以降(ADR-0001 §3)

## 困った時

- 仕様が不明 → `docs/01〜03` を読む。なければ利用者(決裁権者)に質問
- リスク・ガバナンスに触る → risk-auditor サブエージェントで審査
- 大きな設計判断 → プランモードで提案し、承認後に着手 + ADR 起票
- 「ポリシーの値を変えたい」→ 開発作業ではなく**会議の議題**(「臨時会議」と発話)
