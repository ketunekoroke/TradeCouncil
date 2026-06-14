# ADR-0001: Phase 0 の実行環境・設計書からの逸脱事項

| 項目 | 内容 |
|---|---|
| 日付 | 2026-06-11 |
| ステータス | 承認済み(決裁権者の計画承認による) |
| 関連 | docs/02_基本設計書.md §1.5, §3, §8 / docs/03_運営規程・第0回アジェンダ.md |

## 背景

基本設計書は VPS(Linux)+ systemd + cron + Makefile を想定しているが、Phase 0 は
Windows 11 ローカルで開発・稼働する(決裁権者の決定)。また、会議体の実装方式と
リポジトリ構成について、MAGI プロトタイプ(prototype/)の実績あるパターンを採用する。

## 決定事項

### 1. Makefile を廃止し Python CLI `tc` で代替
- 理由: Windows に make を導入する手間を避ける。設計書の `make xxx` はコマンドランナーで
  あり、`tc xxx`(scripts/cli.py、argparse)で同等機能を提供できる
- 対応: `make test` → `tc test` / `make paper` → `tc paper` / `make kill` → `tc kill` /
  `make approve` → `tc approve`。`make live` 相当(実弾)は Phase 0 では実装しない

### 2. キルスイッチ・実行時パスを `var/` 配下へ
- 設計書: `/var/run/tradecouncil/KILL` → 本実装: `<repo>/var/run/KILL`
- DB・ログも `<repo>/var/` 配下。パス解決は core/config.py に集約(pathlib・ルート相対)

### 3. systemd / cron を使わない(Phase 0)
- watchdog は通知のみ(自動再起動なし)。24h 稼働試験はコンソール2枚(bot / watchdog)+
  スリープ無効化(powercfg)で実施。VPS 移行(Phase 1 以降)で systemd 管理に切替

### 4. decision_gate を agents/council/ ではなく core/governance/ に配置
- 理由: decision_gate は L1 の決定的コードであり(設計書 §1.5.5)、Phase 0 には LLM 呼び出し
  コードを置かないため、ポリシーレジストリと同じ core/governance/ に集約する。
  Phase 3 で council_runner(API 版)を agents/council/ に実装する際も decision_gate は
  L1 側に留める

### 5. trade_decisions テーブルの新設
- 設計書 §4 では orders.decision_id が council_decisions / news_signals を多態参照するが、
  Phase 0 のダミー戦略には会議決議が存在しない。全注文の根拠を一元化する結合点として
  trade_decisions(decision_id, bot_id, source_type, source_ref, rationale_json)を導入。
  source_type: strategy_rule / council_decision / news_signal。FK 整合性も改善される

### 6. /council スラッシュコマンドを廃止し、プロトタイプ式のシナリオ会議を採用
- 設計書 §8.3 は .claude/commands/council を想定していたが、決裁権者の決定により
  MAGI プロトタイプの「ルーター(CLAUDE.md)+ シナリオ(scenarios/council.md)+
  ペルソナサブエージェント + ファシリテーター」方式を採用する
- 利点: 第0回だけでなく月次・臨時会議にも同一プロトコルで対応でき、既存シナリオ
  (合議・資料レビュー・ブレスト・人格テスト)と作法を共有できる
- 決裁レコードの適用経路は `tc policy record --file <yaml>` のみ(不変条項3の監査ログを担保)

### 7. ペーパーBOT の価格フィードは RandomWalkFeed を既定とする
- 理由: ①ネットワーク不要で「24時間無人稼働」の DoD が外部要因で落ちない
  ②シード固定で再現可能(テストと本稼働が同コード)③売り買い両経路を確実に通せる
- 公開 REST ticker フィード(キー不要)は config 切替のオプションとし、Phase 1 の
  market_collector への布石に留める

### 8. プロトタイプ資産のルートへの複製
- prototype/ は MAGI プロトタイプとして不変のまま残す(編集禁止)
- 3人格(melchior/balthasar/casper)・4シナリオ・LLM ブリッジ(OpenAI/Gemini)・
  メディア変換・SharePoint 同期・出力ルート(local/ sharepoint/)をルートへコピーし、
  TradeCouncil でも MAGI シナリオを実行可能にする(決裁権者の決定)
