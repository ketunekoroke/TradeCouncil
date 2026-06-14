# BACKLOG — Accounting(会計経理支援システム)

アジャイル運用。タスク・アイデアは BL-AC-NNN で一元管理する。開発開始時に「今スプリント」へ移動し、
完了時に「完了」へ移す。会話で出た将来アイデアは Icebox に追記する。会計ポリシー決裁が必要なものは
[要確認:税理士] タグを付ける。モノレポ全体に関わるものはルート [../BACKLOG.md](../BACKLOG.md)。

## 今スプリント

(なし — Phase 0 足場の取り込みが完了したら次を計画)

## 完了

- **BL-AC-001** — ADR-0011 準拠の `Accounting/` 足場を新設(CLAUDE.md・docs 移植・管理表・.claude・
  scripts・tests)。プロトタイプ由来 docs(会計ポリシー/会社特有/注意点/運用マニュアル/遵守チェック/設計)を
  UTF-8 で移植。AWS 方針を ADR-0001 に記録。

## 完了(追補)

- **BL-AC-014** — MoneyForward API 設定の仕組み。非秘密 config(`config/moneyforward.config.json`)+ 秘密 env
  (`MONEYFORWARD_*`)を `core/moneyforward.py` で解決(per-project env → config → 共有 env)。`ac mf config [--check]`
  で表示・検証。`scripts/spike_moneyforward.py` を設定連携(OAuth → offices)。`.env.example` に MONEYFORWARD_* 追加。

## Backlog(次に着手)

- **BL-AC-010** — MoneyForward 実エンドポイントの確定と疎通(`config/moneyforward.config.json` の URL/scopes を
  製品ドメインの Swagger で確認して記入 → 実アカウントで `scripts/spike_moneyforward.py` 疎通)。
  スモールビジネスプランで開発者向け API が有効化できるか実アカウント確認(→ docs/caveats.md)。
  **archive された expense-api-doc リポジトリは使わない**。grant_type / offices URL は env で調整可。
- **BL-AC-011** — 検証ゲート `scripts/check_compliance.py` 実装(為替換算・税区分・証憑検索3項目・適用開始日 lint)。
  pre-commit / CI から呼ぶ(compliance-checklist.md のタイミング表に従う)。
- **BL-AC-012** — エージェント本体 `core/` の最小実装(取り込み → 抽出 → 検証 → 登録の骨格)。
- **BL-AC-013** — Teams 確認カード(NG/低信頼項目の提示 → 承認 → 確定値返却)。通知は Teams(ADR-0002 系)。

## Icebox(将来アイデア)

- **BL-AC-100** — 会計バックエンドのアダプタ抽象化(将来 freee 等へ拡張可能に)。今は MoneyForward 前提。
- **BL-AC-101** — クラウドBox 連携(電帳法保存)。トライアル API のため本番依存に置かず、手動アップロードを
  フォールバックに用意(→ docs/caveats.md)。
- **BL-AC-102 [要確認:税理士]** — 簡易課税への移行(2割特例の期間後)。移行日を accounting-policy の適用開始日に反映。
- **BL-AC-103** — 自動処理サーバの AWS 構築(EC2 pull 専用・CloudWatch)。IaC を別プラン化(→ docs/adr/0001-aws-hosting.md)。
- **BL-AC-104** — 決算前ワークフロー(外貨建資産・負債の評価替え、要確認事項の整理、税理士連携)。
