# ADR-0003: TradeCouncil 専用 Team とマルチチャネル通知ルーティング

| 項目 | 内容 |
|---|---|
| 日付 | 2026-06-11 |
| ステータス | 承認済み(決裁権者の計画承認による) |
| 関連 | ADR-0002(Teams 移行)/ docs/03 P-11 / docs/setup/teams-notification-setup.md / core/notify/notifier.py |

## 背景

ADR-0002 で通知を Teams(Power Automate Workflows + Adaptive Card)に移行したが、
投稿先は単一チャネルだった。単一チャネルでは info(約定・日次サマリ)のノイズに
critical(停止・損失警告)が埋もれ、ガバナンス(決裁)やレポート(KPI)の閲覧動線も
作れない。決裁権者の要望により、**TradeCouncil 専用 Team を新設し複数チャネルで運用**する。

## 決定事項

### 1. 専用 Team「TradeCouncil」+ 4チャネル構成(P-11 たたき台)

| チャネル | キー | 流すもの |
|---|---|---|
| 📢 運用通知 | `ops` | info 全般(約定・日次サマリ・起動/停止の情報) |
| 🚨 アラート | `alerts` | warning・critical(損失警告・停止イベント・heartbeat 途絶) |
| 📜 ガバナンス | `governance` | 提案キュー・決裁結果・ポリシー変更・会議開催 |
| 📊 レポート | `reports` | 週次 KPI・月次レビュー |

チャネル構成と severity 運用の**正式決定は第0回会議の P-11 決裁**で行う(本 ADR は実装方式の決定)。

### 2. チャネルごとに Power Automate フロー(標準テンプレートのまま)

- チャネルごとに「Webhook 要求を受信したらチャネルに投稿する」フローを1本ずつ作成し、
  URL を `.env` に複数保持する。命名規約: `TradeCouncil-<チャネルキー>`(例 `TradeCouncil-alerts`)
- **却下案: 単一フロー + フロー内 Switch 分岐** — 振り分けロジックが Power Automate 側
  (Git 管理外・テスト不能)に移り、チャネル追加のたびにフロー編集が必要になるため。
  採用案はフローを無改造のテンプレートに保ち、ロジックを Python 側(テスト可能)に置く

### 3. ルーティングは Python 側(core/notify)で共通実装

- 環境変数命名規約: `TEAMS_WORKFLOW_URL_<チャネル名大文字>`(Discord は
  `DISCORD_WEBHOOK_URL_<チャネル名大文字>` で対称)。default は従来の
  `TEAMS_WORKFLOW_URL` / `DISCORD_WEBHOOK_URL`
- severity→チャネルの既定振り分けは `config/system.yaml` の `notify.routing`
  (たたき台: info→ops / warning→alerts / critical→alerts)。
  `governance` / `reports` は routing に載せず、発火側が `send(..., channel="governance")`
  を明示する用途専用とする
- **解決順**: 明示 `channel` → `routing[severity]` → default URL → ログ fallback。
  チャネルの URL が未設定でも通知を握りつぶさず、warning ログを残して default へ
  フォールバックする(通知ロスより誤チャネル配信を許容)
- **チャネル名は自由文字列**(`^[a-z][a-z0-9_]*$` を pydantic validator で強制)。
  Literal 固定にしない理由: チャネル追加が「Teams でチャネル+フロー作成 → .env に1行」
  で完結し、コード改訂が不要になるため。トレードオフとして routing の typo は
  default へフォールバックして「動いてしまう」— warning ログとテストで緩和する
- Teams カードのフッターに解決チャネル名(`#alerts` 等)を表示し、
  フローの投稿先誤配線をカード側から発見できるようにする

### 4. 既存挙動との互換

- `routing` 未記載・チャネル URL 未設定なら従来どおり全通知が default URL へ(完全後方互換)
- 既存の発火点3箇所(キルスイッチ warning / BOT 異常終了 critical / heartbeat 途絶 critical)は
  無変更のまま routing 経由で 🚨alerts に届く
- governance / reports への発火点(`tc approve` 時・`tc kpi` 時)は本 ADR のスコープ外
  (BACKLOG BL-014。通知基盤と独立に追加できる)

## 制約・既知のリスク

- **202 問題 ×4**: Workflows はフロー内部の失敗を送信側に返さない。監視対象フローが
  4本に増えるため、障害調査はフロー個別の実行履歴確認が必要(手順書 §6)
- **フロー作成者への紐づき ×4**: 4本すべて作成者アカウント依存。共同所有者の追加を
  4フロー分実施する(手順書 §7)
- min_severity はグローバル1本(チャネル別しきい値は将来 routing をオブジェクト化して
  後方互換で拡張可能)
