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
- **BL-AC-019(完了 2026-06-14)** — 経費の OAuth ログイン改善。経費は **localhost http を登録できない**
  (検証済)が、MF が **`urn:ietf:wg:oauth:2.0:oob`(CLI 向け)を公式提供**。config の `products.expense.oauth.redirect_uri`
  を OOB に更新し、`mf login` の手動経路を **対話ペースト式**へ作り替え(ブラウザ許可 → MF 表示の `code` を貼り付け
  → 即 `exchange_code`・保存。`--code <CODE>` で非対話・ヘッドレスは EOF で従来 .env+spike 案内にフォールバック)。
  `.env` 編集・spike 不要に。会計の `--no-listen` でも同じペースト式。`https://localhost` 自動受信は自己署名証明書+
  ブラウザ警告+依存追加が要るため不採用(zero-dep 方針)。CLI テスト追加(計84緑)。
  **実機 e2e 確認済**: 経費アプリに OOB を登録 → `mf login --product expense --code <code>` で交換・保存、
  **経費も `refresh_token` 発行**(expires は約3ヶ月と長寿命)、spike が保存トークンをブラウザ不要で再利用
  (`/api/external/v1/offices` 件数=1)、強制失効後の `mf refresh` が実 refresh グラントで更新。

- **BL-AC-020(完了 2026-06-14)** — **経費レシート取込パイプライン**(SharePoint master・Claude 抽出・
  前期実績ベース費目・下書き生成)。`ac expense refdata|pull|process|push|status|drafts`。SharePoint を
  マスタとし、inbox から pull → **Claude が画像/PDF を読んでサイドカー JSON**(項目 + 切出し枠)を生成 →
  日付_支払先でリネーム・画像トリミング(原本は `_original`)・重複排除(内容ハッシュ / 日付+支払先+金額。
  重複は承認の上で上書き・版履歴で復元可)・**前期のクラウド経費 `me/ex_transactions` から学習した費目/
  税区分**を当てた経費明細の下書き(JSON/CSV)を生成 → processed を master へ push。**実 API 書込はせず
  下書きのみ**(実登録はクラウド経費 REST `me/upload_receipt` / `me/ex_transactions`=`transaction:write` で後段)。
  会計の勘定科目は扱わない(経費承認 → 会計登録時に MF がマトリクスで自動変換)。core は zero-dep(extract/
  ingest/refdata/policy/gate/register)、I/O は scripts(SharePoint=shared・画像=Pillow・YAML=PyYAML)。
  ネットワーク非依存テスト 54 件追加(計 138 緑)。**BL-AC-011/012 を前進**。
  **未了(後続)**: 実 API 登録、ヘッドレス抽出(ビジョンブリッジ)+ Teams 確認(BL-AC-013)、電帳法/クラウドBOX、
  `me/ex_transactions` のページング/日付フィルタの実機調整、費目ラベルの id→名前 解決(必要なら office_setting:write)。

- **BL-AC-021(完了 2026-06-15。実装+dry-run確認済)** — **クラウド経費への API 登録(証憑添付=電帳法対応)
  + inbox 整理**。CSV 取込は証憑を添付できず電帳法に非対応のため、`POST me/ex_transactions` に **receipt_input**
  (証憑画像 base64)を同梱して **1コールで登録+証憑添付**(`ExTransactionCreateInput.receipt_input` を公式 Swagger
  で確認)。費目/税区分は **名前→ID** を前期実績(refdata)から解決(`ex_item_id`/`dr_excise_id`)。外貨は
  value=原通貨額 + jpyrate + use_custom_jpy_rate。接待人数は `ex_transaction_attendant_count_attributes`
  (サイドカー attendants)。`ac expense register`(既定ドライラン・`--confirm` で本番送信・ゲート error/費目ID未解決は
  skip)、登録後 `mf_status=registered`+MF明細ID を台帳に記録。`ac expense clean-inbox`(既定ドライラン・`--confirm`
  で SharePoint inbox から **登録済みの証憑のみ**削除=証憑が MF に入った後だけ消す・ごみ箱復元可)。ネットワーク
  非依存テスト追加(計154緑)。**dry-run 実機確認済**(sairee 領収書: 費目ID/税区分ID 解決・証憑添付=True・送信なし)。
  **未了**: 本番 `--confirm` 登録の実機実行(ユーザー確認後)、登録応答の MF明細ID 形の最終確認、接待人数の自動補完。

- **BL-AC-022(完了 2026-06-15)** — **経費明細台帳の Excel 出力**(`ac expense xlsx [--push]`)。ledger+draft から
  **証憑サムネイル**(Pillow 縮小・埋込)+ **クラウド経費の明細番号** + サイドカー相当の内容(日付/支払先/費目/税区分/
  金額/通貨/レート/円換算/登録番号/内容/相関キー/状態/MF-ID)を 1行=1明細の xlsx(openpyxl)に。`--push` で
  SharePoint **ドキュメント/Expense/ 直下**へ単一ファイル upload。登録時に MF 明細番号(`number`)を ledger に保存
  (既存分は GET で backfill=946)。`PUT me/ex_transactions/{id}`(`update_ex_transaction`)で remark(店名先頭)/memo
  (為替レート適用)を更新可能に。**実機確認済**(ドキュメント/Expense/expense_明細台帳.xlsx)。
  **将来**: クラウド経費の**過去分**(`me/ex_transactions` 全件)を同じ行形式で取込(明細番号/相関キーで突合)。

- **BL-AC-023(完了 2026-06-15)** — **Teams 通知**(クラウド経費へ登録時に OPERATIONS チャネルへ詳細送信)。
  `scripts/notify.py`(stdlib urllib・Power Automate Workflows へ Adaptive Card v1.4 を POST。形式は TradeCouncil
  ADR-0002 を踏襲)。env は `TEAMS_AC_WORKFLOW_URL[_<CHANNEL>]`(system.yaml notify.env_prefix=AC)。`register --confirm`
  成功時に 明細番号/日付/支払先/費目/税区分/金額/円換算/証憑有無/相関キー/MF-ID を OPERATIONS へ自動送信(best-effort・
  失敗で本体を止めない)。`ac expense notify [--id]` で既存分の送信/再送も可。**実機送信確認済**(明細946 を OPERATIONS)。
  テスト追加(計167緑・URL/POST/notify 注入で無ネットワーク)。**将来**: EXPENSE チャネル通知、ヘッドレス時の
  Teams 確認カード(BL-AC-013)。

- **BL-AC-024(完了 2026-06-15)** — **複数レシート PDF の分割**(`ac expense split`)。1ファイルに複数の
  レシートが入った PDF を「1ファイル1レシート」へ分割する工程をパイプライン化(従来は pypdf を手作業で実行)。
  継ぎ目は他工程と同じく **Claude が書くサイドカー**: `var/expense/split/<name>.json`(`parts:[{pages,suffix,note}]`
  または `mode:"per_page"`)。**計画・検証は純粋な `core/pdfsplit`**(ページ番号1始まり・**範囲外(off-by-one)/
  空パート/suffix 重複・不正文字を実行前に弾く** → pypdf の不透明な `IndexError` を明確なエラーへ)、**実 pypdf
  操作は `scripts/pdfproc`**(`page_count`・部分集合書出し)。`pull` と `process` の間に位置づけ。既定ドライラン・
  `--confirm` で実分割。分割後のパートは raw/ に置き、**元 PDF は削除せず `var/expense/split_src/` へ退避**(SharePoint
  inbox にも原本が残る=復元可・不可逆操作なし)。**分割サイドカーが無いファイルは分割しない**(複数ページ≠複数
  レシート。Embassy の様な1レシート複数ページを誤分割しないため)。再実行は冪等(原本退避済み・既存出力は上書き
  せず skip)。`pyproject.toml` の optional-deps `pipeline` に `pypdf>=4` を追加、`test_decoupling` の zero-dep 検査に
  `pypdf` を追加。ネットワーク非依存テスト 19 件追加(`test_pdfsplit`=純粋・`test_pdfproc`=pypdf importorskip・
  `test_expense_cli`=注入。計186緑)。**実 pypdf でページ分割を検証済**。**未了/将来**: 1枚画像に複数レシートが
  写る場合の分割(現状は PDF のみ。画像は別レシートとして撮影 or crop で対応)、ヘッドレス時の分割サイドカー自動生成。

- **BL-AC-025(完了 2026-06-15)** — **過去分確認機能**(`ac expense import-past` / `revise-past`)。MF 内蔵
  OCR の精度が低いため、**新ポリシー追加時** などに **今期(未締め)** の既存クラウド経費明細を取込み、証憑を
  Claude が再読込 → **当期ポリシーを再適用** → MF 現値との差分を **変更フィールドのみ** `PUT` で補正。証憑の
  バイナリは `GET .../me/ex_transactions/{id}/mf_file`(公式 Swagger 確認)で `var/expense/past/<id>.<ext>` にDL
  (リサイズなし)、MF 現値スナップショット `<id>.mf.json` を基準に差分。**差分/PUTボディは純粋 `core/revise`**
  (`MFCurrent`・`FieldChange`・`diff_entry`=名前正規化/Decimal 比較・費目税区分は名前比較→ID送出・`build_update_body`
  =変更キーのみ・`applied`=補正後スナップショット更新で冪等)、**実 pypdf 同様に I/O は `scripts`**
  (`download_ex_transaction_receipt`・`import_past`/`revise_past`)。既定ドライラン・`--confirm`・`--id`・
  `--rewrite-remark`。**証憑は再アップロードしない(再 OCR 回避)・`receipt_input` 不付与**。**証憑なし(紙)明細は
  WEB 手動フラグ**(自動補正対象外)。冪等(`past_<id>`・DL は size 一致 skip・差分ゼロ skip で二重 PUT 防止)。台帳
  (xlsx)に過去分も記録(`past/` から証憑解決・**同一MF取引の registered 重複を排除**・draft が無い過去分は
  **snapshot から内容/レート/登録番号を補完**・**外貨は value×rate で円換算**)。`ac expense status` に過去分件数。
  **実機運用 2026-06-15: 今期50件を取込み37件の証憑を照合 → Loft ¥580→¥638・印紙 対象外→非課税・摩薄薄房 THB
  レート4.8→5.01(MUFG2月末仲値、ユーザ提供 `murc_2026.xls` で確定)を補正・検証。明細台帳50件を生成。** ネットワーク非依存テスト 20 件追加
  (`test_revise`=純粋・`test_mf_expense_api`=DL注入・`test_expense_cli`=list/download/update 注入。計205緑)。
  **ユーザー決定(2026-06-15)**: 今期分は新ポリシー全面再適用 / 台帳に記録(master push は任意) / 証憑なしは WEB 手動。
  **適用範囲**: 「過去取引を再計算しない」は締め済み期間の規定。本機能は **今期(未締め)限定**・過年度は対象外
  (manual.md・accounting-policy.md に明記)。**未了/将来**: 本番 `--confirm` の実機実行、過年度対応、日付キーの
  ポリシー版選択、過去分原本の master backfill、ヘッドレス時の証憑自動読取。

## Backlog(次に着手)
- **BL-AC-011** — 検証ゲート `scripts/check_compliance.py` 実装(為替換算・税区分・証憑検索3項目・適用開始日 lint)。
  pre-commit / CI から呼ぶ(compliance-checklist.md のタイミング表に従う)。**一部完了**: `core/gate.py` と
  `check_compliance.py --drafts`(下書きの error 級点検)を BL-AC-020 で実装。残: pre-commit/CI 連携・適用開始日版選択。
- **BL-AC-012** — エージェント本体 `core/` の最小実装(取り込み → 抽出 → 検証 → 登録の骨格)。**一部完了**:
  取込〜抽出〜検証〜下書きを BL-AC-020 で実装(`core/{ingest,extract,refdata,policy,gate,register}`)。残: 実登録・会計連携(reconcile)。
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
