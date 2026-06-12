# BACKLOG — TradeCouncil

アジャイル開発用のバックログ。タスク・アイデアはすべてここで一元管理する。

## 運用ルール

- 1アイテム = `BL-NNN`(連番・欠番再利用なし)+ ユーザーストーリー形式(「〜として〜したい。なぜなら〜」)+ 受け入れ条件
- 優先度は**並び順**で表現する(上が高い)。着手時に「今スプリント」へ移動し、完了時に「完了」へ移す(完了日付き)
- **アイデア / Icebox** は粒度・採否未定のメモ置き場。育ったらストーリー化してプロダクトバックログへ昇格する
- ポリシー決裁が必要なアイテムには **[要決裁]** タグを付け、会議アジェンダ(`docs/03_運営規程・第0回アジェンダ.md`)と連動させる
- REQUIREMENTS.md との棲み分け: REQUIREMENTS は**確定要件**の管理表、BACKLOG は**未確定の作業計画・アイデア**(実装が確定したら REQ 化して同期する)

---

## 今スプリント(Sprint 11: 未開始)

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
| BL-032 | 運用者として TC-206(Bybit testnet 実発注検証)を実施したい。なぜなら接続実装(BL-031)の最終確認であり、公開データ取得は実測確認済み(2026-06-12 タイ AIS 回線で testnet/mainnet とも 200)だが実発注はまだだから | 前提: testnet API キー作成(docs/setup/bybit-testnet-setup.md §1-2)。注意: 米国等の制限国 IP は 403(初回 403 は NordVPN 米国出口が原因と判明・docs 訂正済)。BL-021 の AWS リージョン選定時もブロック対象でないか事前確認 |
| BL-034 | [要決裁] 決裁権者として市場データソースのスタックを決定したい(提案書 → 会議付議)。なぜなら全データ種(暗号資産/FX/日米株・指数/マクロ/カレンダー/先物)の取得経路と規約リスクの方針が未確定だから | 検討メモ(2026-06-12): 低リスク方針 = 公式一次ソース優先 + 公式 API アグリゲータ。暗号資産=取引所公式 WS / FX=Frankfurter(ECB・無料・キー不要)/ 国内株=J-Quants(JPX 公式。無料=日足12週遅延)/ 米株・指数=Twelve Data(無料800/日・WS)or Finnhub(60/分)+ Stooq(EOD 予備)/ マクロ=FRED(公式・無料)/ 先物=IBKR(Phase 5)までギャップ。**インジケータは取得せずローカル計算(pandas-ta → BL-037)**。TradingView は人間チャート専用 + 公式 Webhook のみ(スクレイピング・tvDatafeed ログイン・非公式 MCP は規約違反・Premium 停止リスクで不採用) |
| BL-035 | 運用者として market_collector(Bybit 公式 WS で1分足常時受信 → candles 保存、切断再接続・REST 補完・欠損検知)を実装したい。なぜなら FR-1.1 の本実装であり現行 REST ポーリング(BL-031)の上位互換だから | BybitFeed の置換でなく feed 実装の追加。FR-1.4 鮮度監視と接続 |
| BL-036 | 運用者として Frankfurter(ECB)から USDJPY を日次取得し fx_rates テーブルへ取り込みたい。なぜなら ADR-0008 の保守的固定レートを実勢参照で補完・点検できるから | リスク計算は引き続き保守側固定レート(fail-closed)。実勢は乖離監視と見直しの根拠に |
| BL-037 | 開発者として pandas-ta によるローカル指標計算基盤(bots/ から使える純関数群)を整備したい。なぜならインジケータは外部取得でなく OHLCV からの計算にすれば規約リスクゼロ・バックテスト再現性が確保できるから | BL-030(実戦略1本目)・BL-029(バックテスト)の前提部品 |
| BL-029 | 開発者として最小バックテストエンジン(CSV/合成データで Strategy を回し PF・最大DD・取引数を算出)を導入したい。なぜなら P-06 ゲート基準(PF>1.2 / DD<15% / 100取引)の証拠を作る場が無く、戦略カードの「検証結果」を埋められないから | docs/02 §フェーズ1。vectorbt/backtesting.py 採用判断は ADR 起票してから。BL-028 の戦略カードと接続 |
| BL-030 | 運用者として実戦略1本目(移動平均クロスのトレンドフォロー)を実装しペーパー稼働させたい。なぜなら docs/02 フェーズ1の中核であり、ダミー以外の戦略でノウハウ蓄積サイクルを実証したいから | `tc bot new` で雛形生成 → 戦略カード先行 → テスト先行(docs/06 のフロー実証)。検証は BL-029 のバックテスト or RandomWalk 試走 |
| BL-039 | 開発者として prototype/ の削除可否を判断したい(BL-038 の取り込み検収後)。なぜなら取り込み済みの旧仕様文書が残り続けると AI・人間双方の誤読リスクになるから | git 履歴には永久に残るためいつでも参照可。削除時は CLAUDE.md の prototype 言及(概要・絶対ルール8・ディレクトリ案内)と hooks の保護パターンも整理 |
| BL-017 | 運用者としてサーバ上の Claude Code 運用(claude -p 定型ジョブ・SSH 障害調査)を整備したい。なぜなら AI が本番実態を直接観測できる必要があるから(docs/05 §5.3) | BL-016 の後。hooks 同梱・直接編集禁止ルールの確認手順を含む。**SSH ライブ読取(tc status/kpi/policy list)と tc snapshot の SharePoint/scp 配布**(docs/setup/remote-data-access.md)も整備。Phase 4 の週次レビューと接続 |

## アイデア / Icebox

- [要決裁] `fx.usdjpy_rate`(JPY 換算係数)のポリシー化 — 値次第で実効的に全リスク上限をスケールさせるため決裁事項に近い(risk-auditor 指摘)。次回会議で P-02/P-03 と併せて扱う
- マルチ通貨 KPI 統合(pnl_daily/fills が instrument 通貨建てで bot 間混在 — ADR-0008 既知の制約1。REQ-M04 Phase 6 の前倒し検討)
- Teams Bot コマンドからのキルスイッチ操作(FR-5.6 拡張。発注系ではないが要安全審査)
- Discord 併用(critical のみ二重通知)の要否 — P-11 決裁の論点
- Notion ↔ SharePoint の役割分担整理(ミラー二重化を避ける)— 会議論点
- bitFlyer 実費レート(fee_bps)の実測値反映
- IBKR アダプタ(設計書の実装順②、Phase 5)
- llm_usage テーブルへの記録実装(LLMコストメーター、Phase 2 のニュースパイプラインと同時)

## 完了

### Sprint 10(2026-06-13)
- BL-038 ✅ prototype 開発ドキュメントの完全マージ(docs/07_シナリオ・人格基盤.md=49KB を現行仕様に更新して一次資料化〔1,079行〕、docs/testing/scenario-bridge-testcases.md=73件の詳細テストを現行仕様化、REQUIREMENTS に DL/DR/BR/PT/PE/LB/FI/SP/NF 節〔56件・旧→新対応表付き〕、FEATURES に FEAT-60〜97 詳細節、TESTCASES に索引行 TC-027/107/207/306。コードは移植済みのため変更なし。実 .env 由来のテスト分離バグ1件を修正し 211件緑)。prototype/ は無改変・削除判断は BL-039

### Sprint 9(2026-06-12)
- BL-033 ✅ シナリオ入出力を単一 `workspace/` に統合(ADR-0009。local/・sharepoint/ 二重ツリー廃止、enabled は同期通信の有無のみ)+ `sharepoint.py sync` 新設(双方向・追加型・newer-wins・mtime 整合・削除非伝播。council も同期対象に追加 = Teams から議事録が見える)。シナリオ開始/終了時の自動 sync を CLAUDE.md の作法に明文化。議事録は git mv で履歴維持、DB minutes_path 更新済。tests/scripts 10件、211件緑

### Sprint 8(2026-06-12)
- BL-031 ✅ Bybit testnet 接続実装(ADR-0008・docs/setup/bybit-testnet-setup.md。BybitAdapter=testnet 強制/mainnet 発注経路なし/実約定・実手数料解決、BybitFeed=確定 kline+data_age 実測で P-04 が実質動作、OrderIntent.fx_rate_jpy+FxConfig 保守的固定レートで JPY 換算。risk-auditor 審査合格・risk カバレッジ 93.86%、tests 39件追加で 201件緑)。公開データの実接続はタイ AIS 回線で確認済(初回 403 は NordVPN 米国出口が原因 — 米国は Bybit 制限国)。実発注検証(TC-206)は BL-032(要 testnet API キー)

### Sprint 7(2026-06-12)
- BL-028 ✅ 戦略ナレッジ基盤(ADR-0007・docs/06_戦略開発ガイド・docs/strategies/ 戦略カタログ=1戦略1カード・学び append-only・数値は DB 真実源)+ `tc bot new` スキャフォールド(雛形4ファイル一括生成・既存拒否・enabled:false 既定・レジストリ登録はテスト駆動誘導。tests/bots 12件、162件緑、手動検証済み)。バックテストは BL-029、実戦略1本目は BL-030 に分離

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
