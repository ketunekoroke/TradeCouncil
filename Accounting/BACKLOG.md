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
  を `core/moneyforward.py` で解決。`ac mf config` で表示・検証。`scripts/spike_moneyforward.py` を設定連携。
- **BL-AC-015** — MoneyForward 会計 + 経費の **2系統同時対応**(完了)。`config/moneyforward.config.json` を
  `products.{accounting,expense}` 構造に、env を `MONEYFORWARD_<PRODUCT>_*`(ACCOUNTING/EXPENSE)へ。
  `ac mf config [--product]` で両系統を表示・検証。OAuth 既定エンドポイントを公式値で記入。手順は
  docs/setup/moneyforward-api-setup.md。
- **BL-AC-010(会計分・完了 2026-06-14)** — クラウド会計の **実 API 疎通を確認**。OAuth 認可コードフロー
  (ブラウザ認可 → token 交換 `client_secret_basic`)が成功し、認証付き REST `GET /v2/tenant` で事業者情報
  (`{tenant_code, tenant_name}`)を取得。`/v2/tenant` は scope **`mfc/admin/tenant.read`** が必須(会計ドメインの
  `mfc/accounting/*` とは別の admin 名前空間)。config に offices_url・scope を記入済(`api.offices_url`)。
  **判明(開発者サイト確認)**: 会計には「事業者一覧」エンドポイントは無い。OAuth トークンが事業者(tenant)に
  紐づくため、事業者の取得は `/v2/tenant` が正(= 会計側の疎通はこれで完結)。残: 経費(expense)系統 → **BL-AC-017**。

## Backlog(次に着手)

- **BL-AC-017** — クラウド経費(expense)の実エンドポイント確定と疎通: 経費の開発者向けアプリで
  client_id/secret を登録 → 疎通。offices 一覧候補は `GET https://expense.moneyforward.com/api/external/v1/offices`
  (所属組織の一覧。**Swagger https://expense.moneyforward.com/api/index.html で要確認**)。経費はユーザーが複数組織に
  所属しうるため一覧が存在する(会計と異なる)。**archive された expense-api-doc / api-doc リポジトリは使わない**
  (docs/caveats.md)。offices URL は config の `products.expense.api.offices_url`(または env
  `MONEYFORWARD_EXPENSE_OFFICES_URL`)で指定。
- **BL-AC-011** — 検証ゲート `scripts/check_compliance.py` 実装(為替換算・税区分・証憑検索3項目・適用開始日 lint)。
  pre-commit / CI から呼ぶ(compliance-checklist.md のタイミング表に従う)。
- **BL-AC-016** — 認可コードフローの補助(ローカルで `redirect_uri` を受けて `code` を取得する簡易リスナ、
  リフレッシュトークン更新)。現状は手動で `MONEYFORWARD_<PRODUCT>_AUTH_CODE` を設定する運用。
- **BL-AC-012** — エージェント本体 `core/` の最小実装(取り込み → 抽出 → 検証 → 登録の骨格)。
- **BL-AC-013** — Teams 確認カード(NG/低信頼項目の提示 → 承認 → 確定値返却)。通知は Teams(ADR-0002 系)。

## Icebox(将来アイデア)

- **BL-AC-100** — 会計バックエンドのアダプタ抽象化(将来 freee 等へ拡張可能に)。今は MoneyForward 前提。
- **BL-AC-101** — クラウドBox 連携(電帳法保存)。トライアル API のため本番依存に置かず、手動アップロードを
  フォールバックに用意(→ docs/caveats.md)。
- **BL-AC-102 [要確認:税理士]** — 簡易課税への移行(2割特例の期間後)。移行日を accounting-policy の適用開始日に反映。
- **BL-AC-103** — 自動処理サーバの AWS 構築(EC2 pull 専用・CloudWatch)。IaC を別プラン化(→ docs/adr/0001-aws-hosting.md)。
- **BL-AC-104** — 決算前ワークフロー(外貨建資産・負債の評価替え、要確認事項の整理、税理士連携)。
