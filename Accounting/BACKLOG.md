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
  紐づくため、事業者の取得は `/v2/tenant` が正(= 会計側の疎通はこれで完結)。
- **BL-AC-017(完了 2026-06-14)** — クラウド経費(expense)の **実 API 疎通を確認**。経費の開発者向けアプリで
  client_id/secret を登録 → OAuth 認可コードフロー → token 交換成功 → `GET /api/external/v1/offices` が
  **所属事業者一覧(件数=1)** を返すことを実機検証。接続情報は公式 Swagger
  (`https://expense.moneyforward.com/api/index.json`)から確認: 必須 scope `user_setting:write`、全6スコープ。
  config の `products.expense` に offices_url・最小スコープを記入済。会計の単一 tenant と異なり offices は**リスト**。
- **BL-AC-018(完了 2026-06-14)** — **公式リモート MCP サーバ(クラウド会計)を接続・疎通確認**。
  `https://beta.mcp.developers.biz.moneyforward.com/mcp/ca/v3`(HTTP・OAuth2、`www-authenticate` で要求 scope
  `mfc/accounting/*` 群を提示)。Claude Desktop の claude.ai コネクタとして接続(`/mcp` で OAuth)。`currentOffice` で
  CloudBloom合同会社・FY2023〜2025 を取得して連携確認。公開ツール19(読み15: currentOffice/getTermSettings/
  getAccounts/getSubAccounts/getDepartments/getTaxes/getTradePartners/getConnectedAccounts/getJournals/
  getJournalById/試算表 PL・BS/推移表 PL・BS/en_ja_dictionary、書込4: postJournals/putJournals/postTransactions/
  postTradePartners。削除系なし)。**自作 `core/moneyforward.py`(OAuth 疎通)とは別の連携経路** — 採用方針は
  Icebox BL-AC-106 で検討。GA 正式 URL は ot10.html で要確認(現状 beta)。書込ツールは明示確認を経てのみ実行。
- **BL-AC-016(完了 2026-06-14。実 API e2e 確認済)** — 認可コードフローの補助。
  共通 OAuth ロジックを `core/oauth.py`(zero-dep)へ集約(build_token_request 移設・build_refresh_request・
  parse_token_response・parse_callback・TokenBundle・get_access_token)。`core/token_store.py` で access/refresh を
  gitignore の `var/moneyforward/`(`MONEYFORWARD_TOKEN_DIR` で可変)に保存。`scripts/oauth_listener.py` が
  **会計の loopback(127.0.0.1:8765)で `code` を単回自動受信**(state を hmac 照合・無ログ)。CLI に
  `mf login`(会計=自動・経費/--no-listen=手動)/`mf refresh`/`mf token` を追加。spike は保存トークンを再利用し
  失効時 refresh で自動更新。経費は redirect が HTTPS 限定のため手動継続。ネットワーク非依存テスト39件追加(計81緑)。
  **実機 e2e 確認済**: `mf login --product accounting` がリスナで code 自動取得 → token 保存、**`refresh_token`
  発行を確認**(MoneyForward は refresh あり)、spike が保存トークンをブラウザ不要で再利用、強制失効後の
  `mf refresh` が実 refresh グラントで access token を更新(expires_at 更新)。

## Backlog(次に着手)
- **BL-AC-011** — 検証ゲート `scripts/check_compliance.py` 実装(為替換算・税区分・証憑検索3項目・適用開始日 lint)。
  pre-commit / CI から呼ぶ(compliance-checklist.md のタイミング表に従う)。
- **BL-AC-012** — エージェント本体 `core/` の最小実装(取り込み → 抽出 → 検証 → 登録の骨格)。
- **BL-AC-013** — Teams 確認カード(NG/低信頼項目の提示 → 承認 → 確定値返却)。通知は Teams(ADR-0002 系)。

## Icebox(将来アイデア)

- **BL-AC-106** — 会計連携の**経路選定**: 公式リモート MCP(BL-AC-018)と自作 `core/moneyforward.py`(REST 直叩き)の
  使い分け。MCP は仕訳/帳票/マスタを即利用でき保守も MF 側だが、対話 UI 前提・自動パイプライン/CI には組み込みにくい。
  REST 直叩きは検証ゲート・無人実行・監査ログに向く。**案: 対話的な確認/閲覧は MCP、無人の検証・登録パイプラインは core**。
  GA 正式 URL 確定(ot10.html)と書込ガバナンス(誰が postJournals を承認するか)も併せて決める。
- **BL-AC-100** — 会計バックエンドのアダプタ抽象化(将来 freee 等へ拡張可能に)。今は MoneyForward 前提。
- **BL-AC-101** — クラウドBox 連携(電帳法保存)。トライアル API のため本番依存に置かず、手動アップロードを
  フォールバックに用意(→ docs/caveats.md)。
- **BL-AC-102 [要確認:税理士]** — 簡易課税への移行(2割特例の期間後)。移行日を accounting-policy の適用開始日に反映。
- **BL-AC-103** — 自動処理サーバの AWS 構築(EC2 pull 専用・CloudWatch)。IaC を別プラン化(→ docs/adr/0001-aws-hosting.md)。
- **BL-AC-104** — 決算前ワークフロー(外貨建資産・負債の評価替え、要確認事項の整理、税理士連携)。
