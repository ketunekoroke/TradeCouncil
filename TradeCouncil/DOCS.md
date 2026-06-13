# TradeCouncil — 仕様・運用ガイド(包括リファレンス)

マルチエージェント自動売買ガバナンス・フレームワークの実装・運用の包括ドキュメント。

> **このドキュメントの位置づけ**
> - 正式仕様の**一次資料は `docs/01〜07`**(要件定義書・基本設計書・運営規程・DB設計書・
>   開発フロー/実行環境方針・戦略開発ガイド・シナリオ/人格基盤)。本書は「実装された現在の姿」を
>   一望するためのガイドであり、docs/ と乖離させない
> - 戦略のノウハウ(仮説・パラメータ根拠・学び)は `docs/strategies/`(**戦略カタログ**。
>   1戦略=1カード、ADR-0007)に蓄積する。新規 BOT は `tc bot new` で雛形生成(docs/06)
> - `README.md` — クイックスタート / `CLAUDE.md` — AI が従うルーター+開発規約 /
>   `BACKLOG.md` — アジャイル開発のタスク・アイデア管理
> - `REQUIREMENTS.md` / `FEATURES.md` / `TESTCASES.md` — 管理表(要件↔機能↔検証)
> - 一次資料は**常に現状を映すよう直接改訂**し、意思決定の経緯は `docs/adr/` に記録する
>   (ADR-0001: Windows/CLI 等の初期判断 / ADR-0002: Teams 通知・Notion ミラー方針 /
>   ADR-0003: 専用 Team・マルチチャネル通知 / ADR-0004: 実行環境戦略 /
>   ADR-0005: 本番データ閲覧アーキテクチャ / ADR-0006: AWS ホスティング・可観測性 /
>   ADR-0007: 戦略ナレッジ管理 / ADR-0008: Bybit testnet 接続)

---

## 目次

1. [コンセプト](#1-コンセプト)
2. [三層アーキテクチャと発注経路](#2-三層アーキテクチャと発注経路)
3. [ガバナンス(中核)](#3-ガバナンス中核)
4. [ペルソナ(8名)](#4-ペルソナ8名)
5. [シナリオ](#5-シナリオ)
6. [リスク管理と fail-closed](#6-リスク管理と-fail-closed)
7. [データ設計(遡及性)](#7-データ設計遡及性)
8. [CLI リファレンス](#8-cli-リファレンス)
9. [セットアップと運用手順](#9-セットアップと運用手順)
10. [LLMバックエンドと SharePoint](#10-llmバックエンドと-sharepoint)
11. [既知の制約](#11-既知の制約)
12. [ロードマップ](#12-ロードマップ)

---

## 1. コンセプト

### 何を解決するのか

自動売買の運用ルール(リスク上限・レバレッジ・戦略配分)は、誰かが恣意的に変えられる限り
安全ではない。本フレームワークは:

- **提案・審議はエージェント(ペルソナ会議)**、**決裁は利用者ただ一人**に分離する(三権分離)
- 決裁を経ない変更が**構造的に不可能**(コード上の経路が存在しない)
- すべての決定・注文が**監査ログ**として遡及可能
- ルールが決まっていない領域は**取引しない**(No Policy, No Trade)

### MAGI 基盤の利用(モノレポ — ADR-0011)

意思決定会議は MAGI 由来のオーケストレーション様式(ファシリテーター + 人格サブエージェント +
シナリオプロトコル)で動く。汎用シナリオ基盤・MAGI 3人格・4シナリオ(合議・資料レビュー・
ブレスト・人格テスト)は別プロジェクト `../Magi/`、LLMブリッジは共通層 `../shared/` にある。

## 2. 三層アーキテクチャと発注経路

| 層 | 内容 | 実装状態 |
|---|---|---|
| L1 実行層(常駐・決定的) | BOT・リスクガード・執行・DB・通知(Teams/Discord)・監視 | **Phase 0 実装済**(paper 2系統: ローカル模擬 + Bybit testnet 実接続 — ADR-0008。実弾なし) |
| L2 知能層(LLM API) | ニュース3段フィルタ、戦略会議の自動実行 | Phase 2〜3(未実装) |
| L3 改善層(Claude Code) | 週次/月次レビュー、改善提案、**意思決定会議** | 会議のみ実装済(シナリオとして) |

### 発注経路(これ以外の経路は存在しない)

```
戦略.on_bar() → StrategyIntent
  → trade_decisions 起票(根拠の記録 — 必須)
  → RiskGuard.check()(11段チェック・唯一の関門)→ RiskApprovedOrder(guard だけが生成可能)
  → Executor.submit()(RiskApprovedOrder 型のみ受理・冪等性キーで二重発注防止)
  → BrokerAdapter(paper)→ orders / fills / positions / pnl_daily に1トランザクションで記録
```

- bots/ は core.exchange / core.execution を import できない(テストで検査)
- 拒否も orders に status=rejected + reason_code で記録される(監査の一元化)

## 3. ガバナンス(中核)

### 三権分離(docs/02 §1.5.1)

| 権限 | 保有者 |
|---|---|
| 提案権 | エージェント・実績データ・利用者(何でも提案できる) |
| 審議権 | ペルソナ会議(risk_manager の veto は審議差し戻し) |
| **決裁権** | **利用者のみ**(`decided_by: owner` 以外をシステムが拒否する) |

### 不変条項(会議の議題にできない)

①決裁権は利用者のみ ②LLM非執行 ③全決定の監査ログ ④キルスイッチ ⑤fail-closed

### ポリシーレジストリ(`config/policies/`)

- 全運用ルールを `P-XX_<title>.yaml` で管理。ライフサイクル `draft→proposed→approved→active→retired`
- システムは **active かつ effective_from 到来**のものだけを読む
- 変更は `python -m scripts.cli policy record --file <決裁レコード>` のみ
  (手編集は hooks + pre-commit が検出)。決裁履歴は DB(policy_decisions)に**不滅**
- ロールバック = 旧値の再決裁(バージョンは進む。履歴は消えない)
- `config/generated/` は確認用の自動生成ビュー(`policy sync`)。システム本体はレジストリを直接読む

### decision_gate(提案の3分岐)

1. 不変条項に抵触 → **reject** + incident + 警告
2. P-01 の委任範囲内 → 検証して**自動適用** + 事後報告(初期値: 委任なし)
3. それ以外 → **決裁キュー**(proposals)へ回送 → `approve / reject / defer` で利用者が決裁

P-01 自体の変更は委任設定に関わらず常に決裁事項。

## 4. ペルソナ(8名)

定義は `.claude/agents/<name>.md`(frontmatter: name / description / backend / model)。
backend は claude / openai / gemini を人格ごとに選べる(→ §10)。
人格哲学(価値観レンズ・意図的な弱み・好奇心の屈折)の詳細は
[../Magi/docs/07_シナリオ・人格基盤.md](../Magi/docs/07_シナリオ・人格基盤.md)。

### TradeCouncil ペルソナ5名(意思決定会議用 — 偏りを設計)

| ペルソナ | 視点 | 役割上の偏り(意図的) |
|---|---|---|
| macro_analyst | 金利・規制・マクロ | 中期目線。相場観の土台 |
| momentum_trader | トレンド・出来高 | **強気バイアス**。機会の取りこぼし防止 |
| contrarian_value | 過熱感・乖離 | **弱気バイアス**。momentum への対抗軸 |
| quant_validator | データ・統計 | 「データで裏付くか」を全員に問う。数値の捏造禁止 |
| risk_manager | 損失回避 | **veto 保有**。唯一「儲け」を評価基準に持たない |

### MAGI 3人格(Magi プロジェクト)

MELCHIOR(論理・分析)/ BALTHASAR(共感・保護)/ CASPER(直感・欲求)。合議・レビュー・
ブレスト・人格テストで使い、定義は `../Magi/.claude/agents/`。詳細は
[../Magi/docs/07_シナリオ・人格基盤.md](../Magi/docs/07_シナリオ・人格基盤.md)。

## 5. シナリオ

このプロジェクトのシナリオは council のみ(`scenarios/council.md`)。汎用シナリオ
(合議・レビュー・ブレスト・人格テスト)は `../Magi/`。各シナリオの詳細仕様
(ラウンド・モード・成果物の設計意図)は
[../Magi/docs/07_シナリオ・人格基盤.md](../Magi/docs/07_シナリオ・人格基盤.md)、
詳細テストは [../Magi/docs/testing/scenario-bridge-testcases.md](../Magi/docs/testing/scenario-bridge-testcases.md)。

| シナリオ | 人格 | 何をするか |
|---|---|---|
| **council(意思決定会議)** | 5名 | ポリシーを審議 → 利用者の決裁 → `config/policies/` 生成。式次第は docs/03 第3章 |
| deliberation(合議) | MAGI 3 | 議題を議論し確信度加重で合意形成 |
| document-review | MAGI 3 | 資料を3レンズでレビュー、指摘+改訂版 |
| brainstorm | MAGI 3 | アイデア発散・評価・上位案磨き |
| persona-test | MAGI 3 | 人格の個性・調整の回帰検査 |

council の成果物: 議事録(`workspace/council/`)+ 決裁済みポリシー + council_sessions 記録
(`council log`)。決裁レコードの形式・必須キーは `scenarios/council.md` 参照。

## 6. リスク管理と fail-closed

RiskGuard のチェック順序(しきい値はすべて active ポリシーから。コード内デフォルト値なし):

1. キルスイッチ(`var/run/KILL`)
2. ★P-01〜P-04 が active(**No Policy, No Trade**)
3. 資産クラスが P-02 の per_asset_class で上限 > 0(未決裁クラス封鎖)
4. データ鮮度(P-04.stale_data_sec)
5. サーキットブレーカ(P-04: 1分変動率・スプレッド)
6. 1取引最大損失(P-03。損失見積りの無い注文は想定元本全額とみなす=保守的)
7. 日次損失 / 週次ドローダウン(P-03)
8. 総エクスポージャー / BOT別ポジション数(P-03)/ 実効レバレッジ(P-02)

**多層防御**: ポリシーのキー欠落でも拒否 / executor は RiskApprovedOrder 型のみ受理 /
初期状態(ポリシー0件)では clone 直後に起動しても1件も発注されない。

キルスイッチ: `kill` コマンド / `var/run/KILL` ファイルを置く。解除(`resume`)は人間専用
(エージェントからの実行は hooks がブロック)。

## 7. データ設計(遡及性)

SQLite(WAL、`var/tradecouncil.db`)、全23テーブル。概念設計は docs/02 §4、
**物理スキーマの詳細(ER図・全テーブル仕様・マイグレーション方針・ID規約)は
[docs/04_データベース設計書.md](docs/04_データベース設計書.md)** を参照
(`core/db/models.py` 変更時は docs/04 を併せて更新する)。

**遡及の背骨**: `orders.decision_id → trade_decisions(source_type / rationale_json / source_ref)
→ candles(一次データ)`。「この注文はなぜ出たか」が必ず一次情報まで遡れる。
`python -m scripts.cli kpi` が根拠のない注文(orphan)ゼロを機械検証する。

ガバナンス系: policies(現在値)/ policy_decisions(決裁履歴・append-only)/
proposals(決裁キュー)/ council_sessions(会議記録)。

## 8. CLI リファレンス

`README.md` の CLI 一覧参照。実行形式は `.venv\Scripts\python.exe -m scripts.cli <cmd>`
(`tc.exe` ランチャは環境によりブロックされるため)。

- `tc bot new <bot_id> --strategy <key>` — 戦略雛形4ファイル(bots/・config/bots/・
  tests/bots/・戦略カード)を一括生成(既存があれば何も書かず拒否)。開発フローは
  docs/06_戦略開発ガイド.md、ノウハウは docs/strategies/ に蓄積(ADR-0007)

## 9. セットアップと運用手順

1. **セットアップ**: README のクイックスタート(venv → install → db init → hooks install → test)
   - サンドボックス: `$env:TC_VAR_DIR="var-sandbox"` で DB・KILL・ログを別ディレクトリに
     差し替えてボットを並走できる(作って壊す検証環境。docs/05 §3.3・DEVELOPMENT.md)
   - 本番データの閲覧(Phase 1+): 議事録=git / DB=SSH ライブ読取・`tc snapshot` /
     ファイル=SharePoint / 可視化=Notion ミラー。git は一方向で本番は push しない
     (docs/setup/remote-data-access.md・ADR-0005)
   - クラウド = **AWS**(ADR-0006): EC2 1台 + SQLite on EBS + CloudWatch Logs +
     S3/Athena + Power BI(Teams タブ)。ログは `runtime.log_format: json` で構造化
     (docs/setup/aws-architecture.md)
2. **第0回会議**: 「第0回会議を開催」→ ★P-01〜P-04 決裁 → fail-closed 解除
3. **24h稼働試験**: コンソール2枚(paper / watchdog)+ `powercfg` でスリープ無効化。
   翌日 `status`(heartbeat OK・建玉)と `kpi`(根拠連鎖 OK)を確認
4. **日常運用**: 週次で `kpi` 確認 → 改善提案は proposals キュー → `approve/reject/defer`。
   review_after が到来したポリシーは月次会議で再上程(Phase 0 では手動確認: `policy list`)

### Teams 通知のセットアップ(ADR-0002 / ADR-0003)

通知は Microsoft Teams(Power Automate Workflows + Adaptive Card)が既定。
**専用 Team「TradeCouncil」+ 4チャネル**(📢ops=info / 🚨alerts=warning・critical /
📜governance=決裁 / 📊reports=KPI)で運用する。O365 Incoming Webhook コネクタは廃止済み。
**詳細手順(Team 作成・フロー4本・トラブルシューティング)は
[docs/setup/teams-notification-setup.md](docs/setup/teams-notification-setup.md) 参照。**以下は要約:

1. 専用チーム「TradeCouncil」を作成し、4チャネル(運用通知/アラート/ガバナンス/レポート)を追加
2. チャネルごとに Workflows テンプレート「**Webhook 要求を受信したらチャネルに投稿する**」で
   フローを作成(命名: `TradeCouncil-<key>`)し、発行された URL を `.env` の
   `TEAMS_WORKFLOW_URL_<KEY>`(OPS/ALERTS/GOVERNANCE/REPORTS)に設定。
   `TEAMS_WORKFLOW_URL`(default)は未設定チャネルのフォールバック先 — **まず1本でも運用可**
3. severity→チャネルの振り分けは `config/system.yaml` の `notify.routing`
   (info→ops / warning→alerts / critical→alerts)。発火側は `channel="governance"` 等で明示も可能
4. URL は `sig=` の SAS 署名を含む**秘密情報**(共有・コミット禁止 — pre-commit が検出)
5. 着信確認: `python -m scripts.cli kill` → 🚨アラート にカード →(人間が)`resume`。
   チャネル別疎通は手順書 §4 のワンライナー
6. 注意: フローは**作成者アカウントに紐づく**(4本とも共同所有者を追加推奨)。
   Workflows は 202 を返すためフロー内部の失敗は検知不能 — **通知はベストエフォート**。
   Discord へは `notify.backend: discord` + `DISCORD_WEBHOOK_URL(_<KEY>)` で切替可

## 10. LLMバックエンドと SharePoint

- 人格ごとに backend(claude / openai / gemini)を frontmatter で指定。openai/gemini は
  共通層 `../shared/ask_openai.py` / `ask_gemini.py` ブリッジ経由(リトライ・フォールバック・
  ファイル添付・履歴渡し対応)。詳細は `../shared/README.md`
- API キー等のシークレットは**ルート共有 `.env` に集約**(`.env.example` をコピー。通知 URL・
  OpenAI/Gemini キー・SharePoint 認証をすべてここに書ける)。解決順: 環境変数 → ルート `.env` →
  `.claude/settings.local.json` の env(後方互換)
- SharePoint 連携(任意): 入出力は単一の `workspace/`(ADR-0009)。
  `sharepoint.config.json` の `enabled=true` で `python ../shared/sharepoint.py sync --project .` が
  全フォルダ(council 含む)を**双方向・追加型・新しい方優先**で同期する(削除は伝播しない。
  シナリオ開始/終了時に自動実行)。`pull|push` は選択的リカバリ用。
  Azure アプリ登録は [docs/setup/sharepoint-azure-app-setup.md](docs/setup/sharepoint-azure-app-setup.md) 参照
- **docs ミラー(ADR-0010/0011)**: `docs/` 一式と管理表(README / DOCS / REQUIREMENTS /
  FEATURES / TESTCASES / BACKLOG / DEVELOPMENT)は SharePoint の `TradeCouncil/Docs/` へ
  **git main から一方向ミラー**される(`python ../shared/sharepoint.py mirror --project . [--full]`)。
  コミット(main 時)・プッシュで git フックが自動実行(失敗は warn のみ・次回追いつく)。
  workspace 同期と違い**削除も反映する完全ミラー**で、`Docs/` は読み取り専用
  (編集は git で。手動修復は `mirror --full`)
- Notion 可視化ミラー(**提案中・未決裁**): 議事録・ポリシー・KPI を Notion MCP で
  一方向ミラーする運用案。[docs/proposals/2026-06_notion-mirror-proposal.md](docs/proposals/2026-06_notion-mirror-proposal.md)
  参照(採否は P-11 決裁時の論点)

## 11. 既知の制約

- **Windows ローカル前提**(Phase 0)。systemd/cron なし — watchdog は通知のみで自動再起動しない。
  24h試験中の Windows Update 再起動・スリープに注意
- 価格フィードは RandomWalk(疑似価格)。実勢価格・実取引所接続は Phase 1 以降
- ペーパー約定は即時全量モデル(板・部分約定なし)
- L2(ニュース解析・会議の API 自動実行)・バックテスト・週次レビュー自動化は未実装
- `tc.exe` ランチャがセキュリティ設定でブロックされる環境がある(`python -m scripts.cli` を使う)
- 未知のセッションカレンダーは常に閉場扱い(fail-closed)。立会時間制市場は Phase 6

## 12. ロードマップ(docs/02 §9)

| Phase | スコープ | 状態 |
|---|---|---|
| **0. 基盤** | ガバナンス・risk_guard・paper executor・ダミーBOT・会議体 | **実装済 — 第0回会議と24h試験待ち** |
| 1. 単一戦略 | market_collector(実勢価格)、トレンドフォロー、バックテスト | 未着手 |
| 2. ニュース | RSS収集、3段フィルタ、news_drift BOT | 未着手 |
| 3. 戦略会議(API) | council_runner 自動実行、decision_gate 連携 | 未着手 |
| 4. フィードバック自動化 | 週次レビュー(claude -p)、悪BOT状態遷移 | 未着手 |
| 5. 少額実弾 | ゲート通過後に1BOTずつ | 未着手 |
| 6〜7. マルチアセット | IBKR → 国内株 | 未着手 |
