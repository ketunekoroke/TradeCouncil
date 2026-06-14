# 機能一覧(Features)— shared(共通ツール層)

LLMブリッジ・SharePoint・office 変換・git フックの実装機能。要件は [REQUIREMENTS.md](REQUIREMENTS.md)、
検証は [TESTCASES.md](TESTCASES.md)。利用側のシナリオ機能は
[../Magi/FEATURES.md](../Magi/FEATURES.md)、売買機能は [../TradeCouncil/FEATURES.md](../TradeCouncil/FEATURES.md)。

---

## ブリッジ実装

| ID | 機能 | 状態 | 実装/定義 | 関連要件 |
|---|---|---|---|---|
| FEAT-54 | LLMブリッジ(OpenAI/Gemini。リトライ・フォールバック・ファイル添付・履歴) | 実装済 | [ask_openai.py](ask_openai.py), [ask_gemini.py](ask_gemini.py), [bridge_common.py](bridge_common.py) | REQ-LB02 |
| FEAT-55 | メディア変換(Office抽出・md→docx・docx置換) | 実装済 | [extract_office.py](extract_office.py) ほか | REQ-FI03 |
| FEAT-82 | bridge_common: プロバイダ非依存の共有処理(キー3段解決/フロントマター除去/Office抽出/HTTP/履歴/UTF-8) | 実装済 | [bridge_common.py](bridge_common.py) | REQ-LB06, REQ-SH02 |
| FEAT-83 | 一過性 HTTP エラーの指数バックオフ自動リトライ(`Retry-After` 尊重・`BRIDGE_HTTP_*`) | 実装済 | `_urlopen_retrying` | REQ-NF05 |
| FEAT-84 | 過負荷/モデル不在時のフォールバックモデル切替(`--fallback-model` / `MAGI_*_FALLBACK_MODEL`) | 実装済 | `run_with_fallback` | REQ-LB07 |
| FEAT-85 | OpenAI ブリッジ: Responses API 往復(instructions=人格本文・frontmatter 自動除去) | 実装済 | [ask_openai.py](ask_openai.py) | REQ-LB02, REQ-PE03 |
| FEAT-86 | ファイル入力: 画像/PDF ネイティブ・Office 抽出注入・テキスト注入(両ブリッジ対称) | 実装済 | `build_content_parts` / `build_parts` | REQ-FI01〜05 |
| FEAT-87 | `upload` + `--file-id` 参照(OpenAI Files API / Gemini Files API・ACTIVE 待ち) | 実装済 | `upload_file` / `file_meta` | REQ-FI06 |
| FEAT-88 | UTF-8 入出力固定(Windows パイプ/コンソール)・整形エラー・`*_BASE_URL` 上書き | 実装済 | 両ブリッジ共通 | REQ-NF02, REQ-NF03 |
| FEAT-89 | Gemini ブリッジ: generateContent 往復・ブロック/空応答の整形(promptFeedback/finishReason) | 実装済 | [ask_gemini.py](ask_gemini.py) | REQ-LB02, REQ-NF03 |
| FEAT-90 | モデル一覧取得(openai/gemini を議論向けに抽出・`--all`) | 実装済 | [list_models.py](list_models.py) | REQ-LB01 |
| FEAT-91 | Office→Markdown 抽出 CLI(docx/pptx/xlsx・本文順・GFM表) | 実装済 | [extract_office.py](extract_office.py) | REQ-FI03, REQ-DR03 |
| FEAT-92 | Markdown→docx 変換 CLI(見出し/表/太字・日本語フォント・全面再構築) | 実装済 | [md_to_docx.py](md_to_docx.py) | REQ-DR06 |
| FEAT-93 | docx 原本コピー編集 CLI(find→replace・体裁/画像保持・原本不変) | 実装済 | [docx_replace.py](docx_replace.py) | REQ-DR06, REQ-DR10 |

## SharePoint 連携 + git フック

| ID | 機能 | 状態 | 実装/定義 | 関連要件 |
|---|---|---|---|---|
| FEAT-56 | SharePoint 同期(`sync` 双方向・追加型・newer-wins・mtime 整合。削除非伝播。pull/push はリカバリ用 — ADR-0009)。`--project` でプロジェクト dir を基点に解決 | 実装済 | [sharepoint.py](sharepoint.py) | REQ-SP03 |
| FEAT-94 | Graph クライアントシークレット認証・サイト/ドライブ解決・`test` 検証(日本語テナントの既定ライブラリへフォールバック) | 実装済 | [sharepoint.py](sharepoint.py) | REQ-SP01, REQ-SP04 |
| FEAT-95 | `pull`/`push`(再帰・4MB 超はアップロードセッション分割)+ `info`(SharePoint URL) | 実装済 | `pull_folder` / `push_folder` / `cmd_info` | REQ-SP05 |
| FEAT-96 | 設定解決(env(.env)→ `<project>/sharepoint.config.json`)+ 非機密設定ファイル | 実装済 | `load_config`, `set_project` | REQ-SP02 |
| FEAT-96b | **プロジェクト別の接続**(site_url/tenant_id/client_id を config に持てる・client_secret は env)。解決順 = プロジェクト別 env `SHAREPOINT_<env_prefix>_*` → config → 共有 env。異なるサイト/アプリ登録を per-project に切替可(ADR-0011) | 実装済 | `_conn_value` / `client_secret` / `env_prefix` | REQ-SP13 |
| FEAT-97 | Azure アプリ登録セットアップマニュアル(登録→シークレット→権限+同意→Sites.Selected→確認→トラブルシュート) | 実装済 | [../TradeCouncil/docs/setup/sharepoint-azure-app-setup.md](../TradeCouncil/docs/setup/sharepoint-azure-app-setup.md) | REQ-SP07, REQ-SP08 |
| FEAT-98 | docs ミラー `mirror [--full] --project <p>`(git main → SharePoint `<Project>/Docs/` 一方向・差分ベース・削除反映・sha 状態ファイル・失敗時は状態を進めず次回追いつく — ADR-0010) | 実装済 | `cmd_mirror` / `plan_mirror`([sharepoint.py](sharepoint.py)) | REQ-SP09〜SP11 |
| FEAT-99 | ミラーの git フック自動実行(post-commit=main 時のみ / pre-push。**全プロジェクト走査**・fail-open=warn のみ。`tc hooks install` が3フック一括導入) | 実装済 | [hooks/post_commit.py](hooks/post_commit.py) / [hooks/pre_push.py](hooks/pre_push.py) / [hooks/__init__.py](hooks/__init__.py) | REQ-SP12, REQ-SH03 |
| FEAT-100 | git pre-commit(秘密・決裁レコードなしポリシー・generated 手編集の検出。per-project パス対応) | 実装済 | [hooks/pre_commit.py](hooks/pre_commit.py) | REQ-SH03 |
