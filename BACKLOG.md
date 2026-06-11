# BACKLOG — TradeCouncil

アジャイル開発用のバックログ。タスク・アイデアはすべてここで一元管理する。

## 運用ルール

- 1アイテム = `BL-NNN`(連番・欠番再利用なし)+ ユーザーストーリー形式(「〜として〜したい。なぜなら〜」)+ 受け入れ条件
- 優先度は**並び順**で表現する(上が高い)。着手時に「今スプリント」へ移動し、完了時に「完了」へ移す(完了日付き)
- **アイデア / Icebox** は粒度・採否未定のメモ置き場。育ったらストーリー化してプロダクトバックログへ昇格する
- ポリシー決裁が必要なアイテムには **[要決裁]** タグを付け、会議アジェンダ(`docs/03_運営規程・第0回アジェンダ.md`)と連動させる
- REQUIREMENTS.md との棲み分け: REQUIREMENTS は**確定要件**の管理表、BACKLOG は**未確定の作業計画・アイデア**(実装が確定したら REQ 化して同期する)

---

## 今スプリント(Sprint 6: 未開始)

(次の作業開始時にプロダクトバックログから移動する)

## プロダクトバックログ(優先順)

| ID | ストーリー | 備考 |
|---|---|---|
| BL-007 | 運用者としてペーパーBOT 1体の24時間無人稼働試験を行いたい。なぜなら Phase 0 完了条件(設計書 §9)だから | BL-006 完了済み(fail-closed 解除済み)。bot + watchdog の2コンソール、全注文の根拠付きDB記録を確認。完了時に P-03/P-04 の実測 KPI 再評価(review 2026-07-10)へ繋ぐ |
| BL-008 | [要決裁] 決裁権者として Notion ミラー運用の採否を決め、採用なら初回 Notion DB を作成したい | docs/proposals/2026-06_notion-mirror-proposal.md を会議に付議 |
| BL-009 | 運用者として日次サマリ・週次レポートを Teams カードで受け取りたい。なぜなら FR-7.1 の通知種別のうち約定・損失警告・日次サマリは発火点が未実装だから | risk/executor 側の発火点実装が必要(core/risk・core/execution を触るため risk-auditor 審査対象) |
| BL-014 | 運用者として決裁イベントと KPI を専用チャネルで受け取りたい。なぜなら 📜governance・📊reports チャネルの発火点(`tc approve` 決裁時・`tc kpi` 集計時に `channel=` 指定で send)が未実装だから | scripts/cli 側のみで実装可(通知基盤は BL-013 で対応済み)。BL-009 と同時期に着手すると効率的 |
| BL-024 | 運用者として paper/live の適用範囲をポリシースキーマで分離し、live 移行前の P-02 再決裁を機械的に強制したい(再決裁なしの live 経路は fail-closed)。なぜなら P-02 決裁(2026-06-12 第0回会議)の veto 取り下げ条件(1)(2)だから | P-02 v1 の note 参照。live 実装(Phase 5 以降)前に必須。crypto_margin paper 拡張時の即時再上程(条件4)も連動 |
| BL-025 | 運用者として日次・週次境界の正準定義(JST 00:00 / JST 月曜 00:00 等)を system.yaml に明記し、bot_runner の week_peak_equity を週境界でリセットしたい。なぜなら P-03 決裁の前提条件(境界・DD起点の一意定義)であり、現実装はプロセス累積ピーク基準で境界リセットが無いから | 現状は安全側乖離(より厳しく停止)なので稼働ブロッカーではない。core/risk 関連のため risk-auditor 審査対象。テスト必須 |
| BL-026 | [要決裁] 決裁権者として、証拠金・引け概念を持つ資産クラス(IBKR・国内株・crypto_margin)の導入時に維持率(警告/縮小)と引け前レバ縮小のセーフガードを専用設計で決裁したい。なぜなら P-04 決裁(2026-06-12)で「Phase 0 非適用・導入決裁時に再上程」と記録されたから | P-04 v1 note 参照。執行点の実装(core/risk)+ ポリシー再上程のセット。建玉強制手仕舞いロジックの設計も同時に検討(P-04 開示事項) |
| BL-027 | 運用者として BOT 別 KPI 集計(週次実現損益ロールアップ / BOT別拒否率 = count(rejected)/count(total) / BOT別DD)を `tc kpi` に追加したい。なぜなら P-05 決裁(2026-06-12)の数値しきい値決裁トリガー「戦略KPI実装完了」の合格基準だから | P-05 v1 note 参照。P-03/P-04 の24h実測再評価でも同じ集計を使う。feedback/kpi.py 拡張 |
| BL-010 | 開発者として Alembic によるスキーマ移行を導入したい。なぜなら create_all はカラム追加を反映できないから(docs/04 §5) | Phase 1 以降。ADR 起票してから着手 |
| BL-016 | ~~Phase 1 のホスティング(A-5)を決定~~ → **AWS に決定済(2026-06-12、ADR-0006)**。残: 実構築は BL-021 | docs/01 A-5 確定済。構成は docs/setup/aws-architecture.md |
| BL-021 | 運用者として AWS インフラ(EC2/IAM/EBS/S3 + CloudWatch Agent + systemd)を構築したい。なぜなら paper 常駐の本番が必要だから | docs/setup/aws-architecture.md §2-3。SSH 鍵・git 一方向 pull デプロイ・`log_format: json`。BL-017(SSH 読取)と接続 |
| BL-022 | 運用者として取引ダッシュボードを Teams タブの Power BI で見たい。なぜならトランザクションを可視化したいから | 主要テーブル→Parquet エクスポート(systemd timer、tc snapshot 入力)→ S3 → Glue/Athena → Power BI(Teams タブ)。aws-architecture.md §4 |
| BL-023 | 運用者として CloudWatch アラートを Teams に流したい。なぜなら重大イベント(heartbeat 途絶等)を即時に知りたいから | CloudWatch Alarm → SNS → 既存 Teams 通知(notifier 連携)。aws-architecture.md §5 |
| BL-017 | 運用者としてサーバ上の Claude Code 運用(claude -p 定型ジョブ・SSH 障害調査)を整備したい。なぜなら AI が本番実態を直接観測できる必要があるから(docs/05 §5.3) | BL-016 の後。hooks 同梱・直接編集禁止ルールの確認手順を含む。**SSH ライブ読取(tc status/kpi/policy list)と tc snapshot の SharePoint/scp 配布**(docs/setup/remote-data-access.md)も整備。Phase 4 の週次レビューと接続 |

## アイデア / Icebox

- Teams Bot コマンドからのキルスイッチ操作(FR-5.6 拡張。発注系ではないが要安全審査)
- Discord 併用(critical のみ二重通知)の要否 — P-11 決裁の論点
- Notion ↔ SharePoint の役割分担整理(ミラー二重化を避ける)— 会議論点
- bitFlyer 実費レート(fee_bps)の実測値反映
- IBKR アダプタ(設計書の実装順②、Phase 5)
- llm_usage テーブルへの記録実装(LLMコストメーター、Phase 2 のニュースパイプラインと同時)

## 完了

### Sprint 6(2026-06-12)
- BL-006 ✅ 第0回意思決定会議を開催(P-01〜P-05 を決裁・active 化、**fail-closed 解除**。P-02 はレバ枠5.0の paper テスト条件付き修正承認、P-03 は緩和値修正承認、P-05 は骨格承認+しきい値条件付き保留。P-06〜P-12 は次回会議へ持ち越し。議事録: local/council/2026-06-12-第0回意思決定会議.md。派生起票: BL-024〜BL-027)

### Sprint 5(2026-06-12)
- BL-018 ✅ `tc status` の cp932 コンソール対応(真因は PolicyNotActiveError 未捕捉ではなく、捕捉済み except 節の「✗」U+2717 print が cp932 で UnicodeEncodeError。CLI エントリポイントで stdout/stderr を `reconfigure(errors="replace")` + ✗→×(cp932 対応)に置換。encoding は不変でパイプ互換維持。tests/scripts 5件、150件緑)

### Sprint 4(2026-06-12)
- BL-020 ✅ AWS ホスティング・可観測性アーキテクチャ(ADR-0006・docs/setup/aws-architecture.md。A-5=AWS 確定、コア DB は SQLite 維持・DynamoDB 不採用)+ 中央集権的な構造化ログ実装(core/logsetup.py、tests/log 8件、既定 plain で後方互換、145件緑)

### Sprint 3(2026-06-12)
- BL-019 ✅ 本番データ閲覧アーキテクチャ(ADR-0005・docs/05 §3.5.1・docs/setup/remote-data-access.md。git 一方向・本番 push なし)+ `tc snapshot`(VACUUM INTO、tests/db 5件)+ 議事録の git 追跡 + Notion 採用(閲覧専用)

### Sprint 2(2026-06-12)
- BL-015 ✅ 開発フロー・実行環境方針(docs/05 + ADR-0004)+ TC_VAR_DIR サンドボックス実装(tests/config 8件、既存テスト無修正で132件緑、手動検証済み)

### Sprint 1(2026-06-11)
- BL-013 ✅ 専用 Team + 4チャネル通知ルーティング(ops/alerts/governance/reports、notify.routing、チャネル別 URL とフォールバック連鎖、ADR-0003、手順書改訂、テスト 19件)
- BL-012 ✅ シークレットをルート .env に集約(bridge_common に .env フォールバック追加。解決順: 環境変数 → .env → settings.local.json。tests/scripts 5件)
- BL-011 ✅ Teams 通知の詳細セットアップ手順書(docs/setup/teams-notification-setup.md。DOCS.md §9 からリンク)
- BL-001 ✅ Teams 通知(Power Automate Workflows + Adaptive Card、backend 切替、tests/notify 17件)
- BL-002 ✅ docs/04_データベース設計書.md(ER図・23テーブル仕様・マイグレーション方針・ID規約)
- BL-003 ✅ docs/01〜03 を Teams 前提に直接改訂 + ADR-0002
- BL-004 ✅ Notion ミラー提案書(docs/proposals/2026-06_notion-mirror-proposal.md。採否は要決裁 → BL-008)
- BL-005 ✅ 管理表同期(DOCS/REQUIREMENTS/FEATURES/TESTCASES/README/CLAUDE/DEVELOPMENT)

### それ以前
- 2026-06-11 以前: Phase 0 基盤実装完了(market/paper/executor、runner/watchdog/notifier、tc CLI、council シナリオ移植、ドキュメントスイート)— 詳細は git log 参照
