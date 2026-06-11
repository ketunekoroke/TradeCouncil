# ADR-0002: 通知の Microsoft Teams 移行と Notion 可視化ミラー方針

| 項目 | 内容 |
|---|---|
| 日付 | 2026-06-11 |
| ステータス | 承認済み(決裁権者の計画承認による) |
| 関連 | docs/01_要件定義書.md A-7, FR-5.6, FR-7.1 / docs/02_基本設計書.md §1.1, §1.2, §2, §4 / docs/03_運営規程・第0回アジェンダ.md P-11 / docs/04_データベース設計書.md / docs/proposals/2026-06_notion-mirror-proposal.md / ADR-0001 |

## 背景

要件定義書(v0.3 まで)は通知チャネルとして Discord Webhook を想定していた(FR-7.1。
A-7 で「Slack/LINE に変更可」と当初から変更を許容)。決裁権者の利用環境は Microsoft 365
であり、約定・損失・停止イベントなどトランザクションデータを**構造化された形で可視化**
したいという要望から、通知先を Microsoft Teams へ変更する。

なお Microsoft の O365 Incoming Webhook コネクタ(Teams コネクタ)は 2025 年末に廃止
されており新規作成できない。現行の標準的な受け口は **Power Automate Workflows**
(Teams の Workflows アプリ「Webhook 要求を受信したらチャネルに投稿する」フロー)である。

あわせて、ドキュメント系データ(議事録・ポリシー・KPI)の可視化手段として Notion の
利用可否を検討した。

## 決定事項

### 1. 通知の既定 backend を Microsoft Teams(Power Automate Workflows)とする
- Power Automate フローの HTTP URL へ **Adaptive Card(v1.4)** を POST する
  (`{"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", ...}]}`)
- severity(info/warning/critical)をカードの色(default/warning/attention)で表現し、
  キー値ペア(facts)を FactSet で構造化表示する — Discord のプレーンテキストでは
  不可能だった可視化要件に対応
- フロー URL は SAS 署名(`sig=`)を含む秘密情報。環境変数 `TEAMS_WORKFLOW_URL` で
  渡し、コミット前フック(scripts/hooks)の検出パターンに追加する
- 制約の明記: Workflows は受信時に 202 Accepted を返すため、フロー内部の失敗
  (チャネル削除等)は送信側から検知できない。通知は従来どおり**ベストエフォート**であり
  安全機構ではない(安全停止は kill フラグ・fail-closed が担う)

### 2. Discord backend はコードとして維持し、設定で切替可能とする
- `config/system.yaml` の `notify.backend: teams | discord` で切替(URL はそれぞれ
  `TEAMS_WORKFLOW_URL` / `DISCORD_WEBHOOK_URL`)
- FR-7.1 の趣旨(Webhook 型のプッシュ通知)は維持し、宛先のみ変更

### 3. 一次資料(docs/01〜03)は本文を直接改訂する(運用変更)
- ADR-0001 時点では「一次資料は遡及改訂せず、逸脱を ADR に記録」としていたが、
  決裁権者の指示(2026-06-11)により、**一次資料は常に現状を映すよう直接改訂**し、
  ADR は意思決定の経緯記録として併用する方式に変更する
- 本 ADR に伴い docs/01(A-7, FR-5.6, FR-7.1, §5)・docs/02(§1.1, §1.2, §2, §3, §4,
  §6.2)・docs/03(P-11 たたき台)を Teams 前提に改訂した

### 4. P-11(通知・エスカレーション)のたたき台を Teams 前提に更新
- P-11 は第0回会議で未決裁の「たたき台」であり、たたき台の修正に決裁は不要
  (docs/03 第5章冒頭の宣言どおり)。**正式決定は第0回会議の P-11 決裁**で行う

### 5. Notion はコード実装せず、MCP による一方向可視化ミラーを提案書として定義
- 議事録・ポリシー・KPI 等ドキュメント系データの可視化先として Notion を提案する
  (docs/proposals/2026-06_notion-mirror-proposal.md、採否は会議で決裁)
- 同期はファシリテーター(Claude Code)が接続済み Notion MCP でシナリオ事後処理として
  行う**一方向ミラー**のみ。真実の源泉は git(議事録・config/policies/)と
  SQLite(policy_decisions ほか)のまま動かさない
- Notion 上の編集はシステムに対し何の効力も持たない(Notion→リポジトリの逆流禁止)。
  決裁・発注経路に一切入らないため、LLM 非執行原則・不変条項3(監査ログ)に抵触しない
- Notion API のコード実装(常駐プロセスからの同期)は Phase 0 ではコード増・トークン
  管理増に見合わないため不採用。必要になれば別 ADR で再検討

### 6. データベース詳細仕様書(docs/04)を一次資料に追加
- docs/02 §4 は概念設計に留まるため、物理スキーマの詳細(ER図・全テーブル仕様・
  マイグレーション方針・ID 規約)を docs/04_データベース設計書.md として新設し、
  一次資料の一部とする。core/db/models.py 変更時は docs/04 を併せて更新する
