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
| 汎用シナリオ・MAGI 人格を使う/編集 | `cd ../Magi && claude` | 別プロジェクト(モノレポ — ADR-0011) |
| LLMブリッジ・SharePoint・office を編集 | `../shared/` を編集 | 共通層(全プロジェクトに影響) |

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
- テスト先行(テストファースト)は全モジュールの原則。`core/risk/`・`core/execution/` は**必須**

## 開発サイクル(1 BACKLOG アイテム = 6ステップ — docs/05 §1)

| # | ステップ | 内容 |
|---|---|---|
| ① | BL 選択 | BACKLOG.md のアイテムを「今スプリント」へ |
| ② | docs 先行更新 | 仕様・設計の改訂を実装に先行(ドキュメント駆動)。大きな判断は ADR |
| ③ | テスト先行 | 受け入れ条件をテストに翻訳(red 確認) |
| ④ | 実装 | `python -m scripts.cli test` 全緑まで |
| ⑤ | 管理表同期 | DOCS → REQUIREMENTS → FEATURES → TESTCASES |
| ⑥ | コミット | Conventional Commits。BL を「完了」へ |

作業単位は **1 BL = 1 モジュール境界**を原則とし、超えるなら BL を分割する(LLM コスト統制 — docs/05 §2)。

## サンドボックス(TC_VAR_DIR — docs/05 §3.3)

実行時生成物一式(DB・KILL・ログ)を別ディレクトリに差し替えて「作って壊す」検証環境を作れる。
config/(ポリシー)と .env は本体と共有(fail-closed 状態が本番と一致したまま検証できる)。

```powershell
$env:TC_VAR_DIR = "var-sandbox"          # プロセス起動前に設定(相対= repo 直下。絶対パス可)
.venv\Scripts\python.exe -m scripts.cli db init
.venv\Scripts\python.exe -m scripts.cli paper --bot dummy_rw
# 検証後の後片付け(ディレクトリごと破棄)
Remove-Item Env:TC_VAR_DIR
Remove-Item -Recurse -Force var-sandbox
```

- 命名規約は `var-<name>`(gitignore・hooks 保護の対象)
- シェルに TC_VAR_DIR が残ると以後の CLI が別環境を向く — `status` のパス表示で確認。テストは conftest が自動隔離

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
| `BACKLOG.md` | タスク・アイデアのバックログ(アジャイル運用) | 高(作業の開始/完了時・アイデアが出るたび) |
| `docs/adr/` | 設計判断の記録 | 大きな判断のたび(一次資料 docs/01〜04 は直接改訂し、経緯を ADR に残す) |
| `docs/04_データベース設計書.md` | DB物理スキーマ仕様 | `core/db/models.py` 変更時に**必ず**併せて更新 |

**編集してはいけない**: `config/policies/*.yaml`・`config/generated/`
(`tc policy record` / `sync` 経由のみ)、`var/`、`workspace/` の生成物。共通層 `../shared/` の
変更は全プロジェクトに影響する点に注意(売買固有の変更は TradeCouncil 内に閉じる)。

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
1. `scenarios/<name>.md` 新規作成(固有のモード・ラウンド・成果物・心得だけ書く。
   共通作法〔人格・backend 振り分け・メディア・召喚〕は CLAUDE.md を唯一の出典とし
   **重複コピーしない**=乖離防止)
2. `scenarios/README.md` の一覧・兆候表、`CLAUDE.md` のシナリオ選択表・出力先表に追記
3. 出力先を新設する場合は `workspace/` にディレクトリ + `.gitkeep`、
   `sharepoint.config.json` の folders にも追加(同期対象になる — ADR-0009)
4. `docs/07_シナリオ・人格基盤.md` にシナリオ節を追加 → 管理文書(下記)を同期
5. 軽いお題で1〜2件実走し、ラウンド進行と成果物を確認

### パターン6: 人格を追加する(4人目の MAGI / 6人目のペルソナ)
1. 既存ファイル(`.claude/agents/melchior.md` 等)の節構成(人格 / 好奇心・興味 /
   議論スタイル / 苦手なこと / 発言時の注意)を踏襲して新規作成。
   **既存人格と被らない「意図的な弱み」を必ず設定**(補完と対立が設計思想)
2. `CLAUDE.md` の役割・召喚ルールに追記。**参加人数が変わると投票・スコア集計式が
   変わる**ため、各シナリオのラウンド定義(集計・採点)を見直す
3. `docs/07_シナリオ・人格基盤.md` の人格表(council ペルソナなら docs/02 §5 も)を更新
4. persona-test シナリオで動作確認(個性が出ているか・既存人格と似すぎないか)

### パターン7: シナリオのラウンド・成果物形式を変更する
1. 該当 `scenarios/<name>.md` のラウンド定義を編集し、**モード別の含まれるラウンド表
   (ファイル冒頭)との整合**を確認(時間目安が変わればそれも)
2. 成果物形式の追加(例: PowerPoint)は「成果物」節に仕様を書き、必要ライブラリを
   README のセットアップに追記
3. `docs/07_シナリオ・人格基盤.md` の該当節を**同一コミットで**更新(乖離防止)
4. 軽いお題で実走確認。プロトコルの大きな変更は性質の違う3議題
   (2択判断 / 複数候補の比較 / 創作系)× モードで挙動を見る

> シナリオ・人格編集の共通禁止事項: 生成済みの議論ログ(`workspace/` 配下)を編集しない /
> 人格に専門分野を持たせない(価値観で分ける) / 予定調和に丸める変更をしない
> (「意図的な弱み」を消さない・「最終的にみな同意する」プロトコルにしない)

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

- 仕様が不明 → `docs/01〜05` を読む。なければ利用者(決裁権者)に質問
- リスク・ガバナンスに触る → risk-auditor サブエージェントで審査
- 大きな設計判断 → プランモードで提案し、承認後に着手 + ADR 起票
- 「ポリシーの値を変えたい」→ 開発作業ではなく**会議の議題**(「臨時会議」と発話)
