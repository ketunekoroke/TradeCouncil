# BACKLOG — TradeCouncil

アジャイル開発用のバックログ。タスク・アイデアはすべてここで一元管理する。

## 運用ルール

- 1アイテム = `BL-NNN`(連番・欠番再利用なし)+ ユーザーストーリー形式(「〜として〜したい。なぜなら〜」)+ 受け入れ条件
- 優先度は**並び順**で表現する(上が高い)。着手時に「今スプリント」へ移動し、完了時に「完了」へ移す(完了日付き)
- **アイデア / Icebox** は粒度・採否未定のメモ置き場。育ったらストーリー化してプロダクトバックログへ昇格する
- ポリシー決裁が必要なアイテムには **[要決裁]** タグを付け、会議アジェンダ(`docs/03_運営規程・第0回アジェンダ.md`)と連動させる
- REQUIREMENTS.md との棲み分け: REQUIREMENTS は**確定要件**の管理表、BACKLOG は**未確定の作業計画・アイデア**(実装が確定したら REQ 化して同期する)

---

## 今スプリント(Sprint 2: 未開始)

(次の作業開始時にプロダクトバックログから移動する)

## プロダクトバックログ(優先順)

| ID | ストーリー | 備考 |
|---|---|---|
| BL-006 | [要決裁] 決裁権者として第0回意思決定会議を開催し ★P-01〜P-04 を決裁したい。なぜなら fail-closed 解除と Phase 0 完了の前提だから | 「第0回会議を開催」と発話 → scenarios/council.md。P-11(通知)・Notion ミラー採否も同会議の議題候補 |
| BL-007 | 運用者としてペーパーBOT 1体の24時間無人稼働試験を行いたい。なぜなら Phase 0 完了条件(設計書 §9)だから | BL-006 の後。bot + watchdog の2コンソール、全注文の根拠付きDB記録を確認 |
| BL-008 | [要決裁] 決裁権者として Notion ミラー運用の採否を決め、採用なら初回 Notion DB を作成したい | docs/proposals/2026-06_notion-mirror-proposal.md を会議に付議 |
| BL-009 | 運用者として日次サマリ・週次レポートを Teams カードで受け取りたい。なぜなら FR-7.1 の通知種別のうち約定・損失警告・日次サマリは発火点が未実装だから | risk/executor 側の発火点実装が必要(core/risk・core/execution を触るため risk-auditor 審査対象) |
| BL-010 | 開発者として Alembic によるスキーマ移行を導入したい。なぜなら create_all はカラム追加を反映できないから(docs/04 §5) | Phase 1 以降。ADR 起票してから着手 |

## アイデア / Icebox

- Teams タブ + Power BI で orders / pnl_daily のダッシュボード化(SQLite → CSV/Parquet エクスポート経由)
- Teams Bot コマンドからのキルスイッチ操作(FR-5.6 拡張。発注系ではないが要安全審査)
- Discord 併用(critical のみ二重通知)の要否 — P-11 決裁の論点
- Notion ↔ SharePoint の役割分担整理(ミラー二重化を避ける)— 会議論点
- bitFlyer 実費レート(fee_bps)の実測値反映
- IBKR アダプタ(設計書の実装順②、Phase 5)
- llm_usage テーブルへの記録実装(LLMコストメーター、Phase 2 のニュースパイプラインと同時)

## 完了

### Sprint 1(2026-06-11)
- BL-001 ✅ Teams 通知(Power Automate Workflows + Adaptive Card、backend 切替、tests/notify 17件)
- BL-002 ✅ docs/04_データベース設計書.md(ER図・23テーブル仕様・マイグレーション方針・ID規約)
- BL-003 ✅ docs/01〜03 を Teams 前提に直接改訂 + ADR-0002
- BL-004 ✅ Notion ミラー提案書(docs/proposals/2026-06_notion-mirror-proposal.md。採否は要決裁 → BL-008)
- BL-005 ✅ 管理表同期(DOCS/REQUIREMENTS/FEATURES/TESTCASES/README/CLAUDE/DEVELOPMENT)

### それ以前
- 2026-06-11 以前: Phase 0 基盤実装完了(market/paper/executor、runner/watchdog/notifier、tc CLI、council シナリオ移植、ドキュメントスイート)— 詳細は git log 参照
