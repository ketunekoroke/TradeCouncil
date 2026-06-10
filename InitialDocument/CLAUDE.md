# CLAUDE.md — TradeCouncil(マルチエージェント自動売買システム)

## プロジェクト概要
複数の売買BOT・情報収集BOT(L1: Python常駐)、ペルソナ戦略会議とニュース解析(L2: Anthropic API)、
週次/月次フィードバック(L3: Claude Code)からなる、**マルチエージェント運用ガバナンス・フレームワーク**。
利用者が唯一の決裁権者であり、エージェントは提案・審議まで。運用ルールはすべてポリシーレジストリで管理される。
詳細は docs/01_要件定義書.md、docs/02_基本設計書.md(特に §1.5)、docs/03_運営規程・第0回アジェンダ.md を必ず先に読むこと。

## 絶対ルール(安全規約 — 例外なし)
1. **LLM非執行原則**: LLM出力が検証(agents/council/decision_gate)を経ずに発注・config に到達する経路を作らない
2. **ガバナンス**: 全運用ルールは config/policies/ のポリシーレジストリで管理する(設計書 §1.5)。
   提案は自由だが、**決裁レコードのないポリシー変更・実行用config(risk_limits.yaml 等)の手編集をコミットしない**。
   不変条項(設計書 §1.5.2)を迂回する実装を書かない。risk/ 配下の変更時は必ず risk-auditor サブエージェントで審査する
3. **実弾操作の禁止**: `make live` 等の実弾系コマンドを実行しない(hooks でもブロックされている)。
   実装・テストはすべて paper モードで行う
4. **秘密情報**: .env・APIキー・Webhook URL をコード・ログ・コミットに含めない
5. **テスト必須**: core/risk/ と core/execution/ の変更はテスト先行。`make test` 緑になるまで完了と言わない
6. **すべての発注に decision_id**: 根拠(シグナル/決議)へ遡及できない注文経路を作らない
7. **fail-closed(No Policy, No Trade)**: 必須ポリシー(P-01〜P-04)が active でない資産クラス・領域では
   発注を拒否する実装とする。数値のたたき台を「既定値」としてハードコードしない — 値は常に決裁済みポリシーから読む

## アーキテクチャ要約
- **マルチアセット基盤**: 全銘柄は統一インストゥルメントモデル(config/instruments/ + core/market/)で定義。
  資産クラス固有の知識はブローカーアダプタ(core/exchange/)と margin_rule に閉じ込める。
  実装順は ①暗号資産 → ②IBKR(海外株・先物・債券ETF) → ③国内株(設計書 §2.5)
- L1 実行層(常駐): core/ + bots/。決定的コードのみ。LLM障害時も「最後に検証済みのconfig」で稼働継続。
  BOTはバー駆動型(短期)とスケジュール駆動型(中長期リバランス)の2系統
- L2 知能層(API): agents/。ニュース3段フィルタ(Stage1ルール → Stage2軽量モデル → Stage3上位モデル)、
  ペルソナ5名の戦略会議 → 短期/中期/長期スリーブへ配分 → decision_gate 検証 → config 差分適用
- L3 改善層(Claude Code): feedback/。週次 = KPI集計 → レビューレポート + 改善提案(diff) → 人間承認。
  悪BOT(成績不振BOT)は ACTIVE → REDUCED → PAPER → RETIRED へ機械的に降格(評価期間はスリーブ別)

## よく使うコマンド
- `make test` / `make test-fast` … 全テスト / 高速サブセット(編集後フックで自動実行)
- `make paper BOT=<bot_id>` … 指定BOTをペーパーモードで起動
- `make backtest BOT=<bot_id>` … バックテスト実行(合格基準: 手数料込み PF>1.2, 最大DD<15%, 取引≥100)
- `make kpi` … 週次KPI集計を手動実行
- `make approve PROPOSAL=<path>` … 承認済み提案の適用(人間専用)
- `make kill` … キルスイッチ(人間専用)

## コーディング規約
- Python 3.12 / asyncio。全公開関数に型ヒント。pydantic でLLM出力・config を検証
- 取引所依存は core/exchange/ のアダプタ内に閉じる(ccxt)。bots/ から直接取引所APIを呼ばない
- 例外は握りつぶさない: 異常は incidents テーブルに記録 + notifier 通知
- 設定値のハードコード禁止(config/*.yaml へ)

## ディレクトリ案内
docs/(仕様)、config/(設定・ペルソナ)、core/(基盤)、bots/(戦略)、agents/(L2)、
feedback/(L3)、backtest/、scripts/(cronエントリ)、tests/、reports/(生成物)

## 現在のフェーズ
**Phase 0(基盤構築)** — docs/02_基本設計書.md §9 参照。
ポリシーレジストリと決裁フロー(§1.5)、統一インストゥルメントモデルとブローカーアダプタ共通IFは **Phase 0 から導入**する
(実装は暗号資産アダプタのみ。他クラスのアダプタを先回りで実装しない — インターフェースだけ多資産対応にしておく)。
完了条件: **第0回意思決定会議(/council)で必須ポリシー P-01〜P-04 を決裁**し、未決裁領域の発注拒否(fail-closed)をテストで確認。
ペーパーBOT1体が24時間無人稼働し、全注文がDBに根拠付きで記録され、risk テストが緑。
着手前に必ず計画(plan)を提示し、決裁権者の承認を得てから実装すること。
