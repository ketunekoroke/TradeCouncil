# テストケース一覧 — Accounting(会計経理支援システム)

モノレポ構造の検証はルート [../TESTCASES.md](../TESTCASES.md)。本表は Accounting 固有。
優先度: P0(必須・回帰の核)/ P1 / P2 / P3。

| ID | タイトル | 実行方法 | 優先 | 関連 |
|---|---|---|---|---|
| TC-AC01 | 足場スイートが緑(Accounting/ 内) | `cd Accounting; ..\.venv\Scripts\python.exe -m scripts.cli test` | P0 | REQ-AC01 |
| TC-AC02 | import 健全性(scripts.cli / core が読める) | `tests/test_smoke.py` | P0 | REQ-AC01 |
| TC-AC03 | **削除可能性**: `core/` に `import Magi` / `import TradeCouncil` が無い | `tests/test_decoupling.py` | P0 | REQ-AC02 |
| TC-AC04 | docs lint: `accounting-policy.md` に「適用開始日」が存在し矛盾が無い | `tests/test_docs_lint.py` | P0 | REQ-AC03 |
| TC-AC05 | sharepoint.config.json が有効な JSON で env_prefix/git_mirror が ADR-0010 形 | `tests/test_smoke.py`(config 読込) | P1 | REQ-AC03 |
| TC-AC06 | Accounting/ を一時退避しても TradeCouncil/Magi のスイートが緑(相互非依存) | Accounting を mv → 各 `test` → 戻す | P1 | REQ-AC02 |
| TC-AC07 | 検証ゲート(為替・税区分・証憑要件)の単体検証 | `scripts/check_compliance.py`(実装後) | P1 | REQ-EX02(将来) |
| TC-AC08 | MoneyForward 疎通スパイク(offices 取得まで) | `scripts/spike_moneyforward.py`(手動・実 creds・最小データ)。**会計・経費とも 2026-06-14 確認済**(会計→`/v2/tenant`・経費→`/api/external/v1/offices` 件数=1) | P2 | REQ-EX01 |
| TC-AC11 | 疎通スパイクの純粋ロジック単体検証(token リクエスト組立=認可コード grant・basic/post 認証・auth_code 欠落で SystemExit、offices URL 解決、offices 件数抽出=応答形状の差を吸収) | `tests/test_spike_moneyforward.py`(ネットワーク・実 creds 不要) | P1 | REQ-EX01 |
| TC-AC09 | MoneyForward 設定の解決(`MONEYFORWARD_<PRODUCT>_<FIELD>` env → config)・会計/経費の独立性・プレースホルダ除外・秘密マスク | `tests/test_moneyforward_config.py` | P0 | REQ-EX06 |
| TC-AC10 | `ac mf config [--product] --check` が未設定で exit 1、いずれか系統 ready で exit 0。両系統を表示 | `tests/test_moneyforward_config.py`(CLI 経由) | P1 | REQ-EX06 |
| TC-AC13 | 経費 core の純粋単体(抽出 parse/検証・台帳/重複(完全/近接)・前期実績集計とサジェスト・ポリシー(費目/税区分・内外判定・外貨換算・相関キー)・ゲート・下書き生成) | `tests/test_{extract,ingest,refdata,policy,gate,register}.py`(ネットワーク非依存) | P1 | REQ-EX01〜04 |
| TC-AC14 | 経費パイプライン(process: サイドカー→リネーム/トリミング/重複上書き・版履歴/下書き・refdata 集計・`ac expense` dispatch・画像切出し・`me/ex_transactions` ページング/日付フィルタ) | `tests/test_expense_cli.py` `tests/test_imageproc.py` `tests/test_mf_expense_api.py`(SharePoint/HTTP/PIL 注入・無ネットワーク) | P1 | REQ-EX01〜03 |
| TC-AC15 | core の zero-dep 強化: `core/` が `yaml`/`PIL`/`shared` を import しない | `tests/test_decoupling.py::test_core_is_stdlib_only` | P0 | REQ-AC02 |
| TC-AC16 | API 登録(`register`)+ inbox 整理(`clean-inbox`): 費目/税区分の名前→ID 解決・`receipt_input`(証憑)同梱・摘要店名先頭/メモ為替・ドライラン/`--confirm`・ゲートerror/ID未解決で skip・登録後 mf_status=registered・PUT 更新・登録済みのみ inbox 削除 | `tests/test_register.py` `tests/test_mf_expense_api.py` `tests/test_expense_cli.py`(create/put/delete 注入・無ネットワーク) | P1 | REQ-EX01, REQ-EX03 |
| TC-AC17 | 明細台帳 xlsx 生成: ヘッダ・明細番号/支払先等の値・証憑サムネイル埋込・ledger からの行構築 | `tests/test_expense_xlsx.py` `tests/test_expense_cli.py::test_export_xlsx_from_ledger`(openpyxl/PIL・無ネットワーク) | P2 | REQ-EX03 |
| TC-AC18 | Teams 通知: URL 解決(チャネル別→既定)・Adaptive Card 構造・送信 best-effort(URL無/失敗で False)・register 成功時に OPERATIONS へ明細詳細送信 | `tests/test_notify.py` `tests/test_expense_cli.py::test_register_notifies_operations`(URL/POST/notify 注入・無ネットワーク) | P2 | REQ-EX02 |
| TC-AC19 | 複数レシート PDF 分割: 純粋計画(parse/expand=per_page・**範囲外 off-by-one を弾く**・suffix 重複/空・output_name・unused_pages)+ パイプライン(分割サイドカーのみ対象・dry-run/`--confirm`・原本を split_src へ退避・冪等再実行・既存出力は上書きせず skip・分割→各パート process)+ 実 pypdf(page_count・部分集合書出し・範囲外で ValueError) | `tests/test_pdfsplit.py`(純粋・無 pypdf)`tests/test_pdfproc.py`(pypdf importorskip)`tests/test_expense_cli.py`(page_count/split_fn 注入) | P1 | REQ-EX01 |
| TC-AC20 | core の zero-dep に **pypdf** を追加(`core/` が `pypdf` を import しない) | `tests/test_decoupling.py::test_core_is_stdlib_only` | P0 | REQ-AC02 |
