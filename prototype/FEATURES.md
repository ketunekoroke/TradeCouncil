# 機能一覧(Features)

プロトタイプに実装されている機能の棚卸し。各機能がどの要件([REQUIREMENTS.md](REQUIREMENTS.md))を
満たし、どこに実装されているかを対応づける。検証は [TESTCASES.md](TESTCASES.md)。

- 状態: **実装済**(動作確認済み) / **仕様**(プロトコルとして定義・ファシリテーターが手動実行) / **未**(未実装)
- 一次資料は [DOCS.md](DOCS.md)。機能を変更したら本ファイルも更新する。

---

## シナリオ・オーケストレーション(共通)

| ID | 機能 | 状態 | 実装/定義 | 関連要件 |
|---|---|---|---|---|
| FEAT-01 | モード判定(利用モード / 開発モード)と案内 | 仕様 | [CLAUDE.md](CLAUDE.md) | REQ-D02 |
| FEAT-04 | チームメイト召喚と人格間対話(claude は SendMessage、使えない環境はファシリテーター仲介=ダイジェスト/`--history` にフォールバック) | 仕様 | [CLAUDE.md](CLAUDE.md) | REQ-D07, REQ-SC04 |
| FEAT-42 | シナリオ選択(兆候語の判定表で適用シナリオを選ぶ/判別不能時は確認) | 仕様 | [CLAUDE.md](CLAUDE.md) §シナリオの選択, [scenarios/README.md](scenarios/README.md) | REQ-SC01, REQ-SC03 |
| FEAT-43 | シナリオの独立ファイル化と共通作法の単一出典化 | 仕様 | [scenarios/](scenarios/), [CLAUDE.md](CLAUDE.md) | REQ-SC02, REQ-SC04 |
| FEAT-44 | シナリオ別の出力先ディレクトリ分離(`<root>/deliberations/` / `<root>/reviews/` / `<root>/brainstorms/` / `<root>/persona-tests/`) | 仕様 | [CLAUDE.md](CLAUDE.md) §出力ディレクトリ, [.gitignore](.gitignore) | REQ-SC05 |

## 合議シナリオ(`scenarios/deliberation.md`)

| ID | 機能 | 状態 | 実装/定義 | 関連要件 |
|---|---|---|---|---|
| FEAT-02 | 3モード(Lite/Standard/Full)と Round 0〜9 の進行 | 仕様 | [scenarios/deliberation.md](scenarios/deliberation.md) | REQ-D03, REQ-D04 |
| FEAT-03 | 確信度加重の投票・少数意見の保持 | 仕様 | [scenarios/deliberation.md](scenarios/deliberation.md) | REQ-D05 |

## 資料チェック&リバイス シナリオ(`scenarios/document-review.md`)

| ID | 機能 | 状態 | 実装/定義 | 関連要件 |
|---|---|---|---|---|
| FEAT-45 | 価値観レンズをレビュー観点に投影(正確性/読者/訴求力の3レンズ) | 仕様 | [scenarios/document-review.md](scenarios/document-review.md) | REQ-R01 |
| FEAT-46 | 深度モード(Quick/Standard/Deep)と Round 0〜6 の進行 | 仕様 | [scenarios/document-review.md](scenarios/document-review.md) | REQ-R02, REQ-R03, REQ-R04 |
| FEAT-47 | 衝突指摘の裁定と must/should/nice/見送りの分類 | 仕様 | [scenarios/document-review.md](scenarios/document-review.md) | REQ-R05 |
| FEAT-48 | 指摘レポート + 改訂版(元と同形式)の両方生成・変更履歴・未採用指摘の保持 | 仕様 | [scenarios/document-review.md](scenarios/document-review.md) | REQ-R06, REQ-R07, REQ-R08, REQ-R09 |

## ブレストシナリオ(`scenarios/brainstorm.md`)

| ID | 機能 | 状態 | 実装/定義 | 関連要件 |
|---|---|---|---|---|
| FEAT-65 | 価値観レンズを発散と評価に投影(実現/人/独創の3レンズ) | 仕様 | [scenarios/brainstorm.md](scenarios/brainstorm.md) | REQ-BR01 |
| FEAT-66 | モード(Quick/Standard/Deep)と Round 0〜8 の進行(発散巡数モード固定・早期収束) | 仕様 | [scenarios/brainstorm.md](scenarios/brainstorm.md) | REQ-BR03 |
| FEAT-67 | 独立大量発散 → アイデアマップ化(クラスタ・白地)→ build-on/掛け合わせ/空白埋めの二次発散 | 仕様 | [scenarios/brainstorm.md](scenarios/brainstorm.md) | REQ-BR02, REQ-BR04 |
| FEAT-68 | 各レンズでの 0〜10 評価とレンズ別内訳を保持した上位選定・割れた尖り案の保持 | 仕様 | [scenarios/brainstorm.md](scenarios/brainstorm.md) | REQ-BR05, REQ-BR06 |
| FEAT-69 | 上位案の3レンズ協働ブラッシュアップ(+Deep のプレモーテム) | 仕様 | [scenarios/brainstorm.md](scenarios/brainstorm.md) | REQ-BR07 |
| FEAT-70 | 成果物: アイデア集 + アイデアマップ(Mermaid) + 評価マトリクス + 上位案 | 仕様 | [scenarios/brainstorm.md](scenarios/brainstorm.md) §成果物 | REQ-BR08 |

## 人格テストシナリオ(`scenarios/persona-test.md`)

| ID | 機能 | 状態 | 実装/定義 | 関連要件 |
|---|---|---|---|---|
| FEAT-72 | 人格テスト(固定プローブ・バッテリを全人格に独立投下、差分マトリクスと人格別判定。Round 0〜4・Quick/Standard/Deep) | 仕様 | [scenarios/persona-test.md](scenarios/persona-test.md) | REQ-PT01, REQ-PT02, REQ-PT03, REQ-PT06 |
| FEAT-73 | 識別性チェック(似すぎ警告)とベースライン回帰比較(任意・Deep)。backend は既定=設定どおり・任意で同一に揃える | 仕様 | [scenarios/persona-test.md](scenarios/persona-test.md) | REQ-PT04, REQ-PT05, REQ-PT07 |

## 人格定義

| ID | 機能 | 状態 | 実装/定義 | 関連要件 |
|---|---|---|---|---|
| FEAT-05 | 3人格(価値観ベース・意図的な弱み付き) | 実装済 | [.claude/agents/](.claude/agents/) | REQ-D01, REQ-D06, REQ-P01 |
| FEAT-06 | frontmatter スキーマ(name/description/backend/model) | 実装済 | `.claude/agents/*.md` | REQ-P02 |
| FEAT-71 | 好奇心・興味の共通駆動(レンズ別に対象・強度が屈折、向きにくい対象が弱みと呼応) | 実装済 | [.claude/agents/](.claude/agents/)「好奇心・興味」節, [DOCS.md](DOCS.md) §3 | REQ-P04, REQ-D06 |

## LLM バックエンド振り分け

| ID | 機能 | 状態 | 実装/定義 | 関連要件 |
|---|---|---|---|---|
| FEAT-07 | `backend` による claude / openai の振り分け | 実装済 | [CLAUDE.md](CLAUDE.md) §人格ごとのLLMバックエンド選択 | REQ-B01, REQ-B02 |
| FEAT-08 | claude/openai 混在と再現性のためのログ明記 | 仕様 | [CLAUDE.md](CLAUDE.md) | REQ-B03, REQ-B04 |
| FEAT-09 | openai/gemini 人格のステートレス継続(毎ラウンド文脈付与。`--history` で多ターン履歴も渡せる) | 仕様 | [CLAUDE.md](CLAUDE.md), FEAT-51 | REQ-B05 |
| FEAT-10 | 拒否/空応答時の自動再試行(既定1回 `MAGI_GEN_MAX_RETRIES`)+ 継続時はファシリテーターが言い換え再実行 | 実装済 | `run_with_retry` / `extract_output_text` | REQ-B06 |

## ブリッジ共通(`scripts/bridge_common.py`)

| ID | 機能 | 状態 | 実装 | 関連要件 |
|---|---|---|---|---|
| FEAT-27 | プロバイダ非依存の共有処理(キー解決/フロントマター除去/Office抽出/ファイル判定/HTTP リトライ/生成リトライ/履歴/UTF-8) | 実装済 | `bridge_common.py` | REQ-B07 |
| FEAT-50 | 一過性 HTTP エラー(429/5xx/接続タイムアウト)の指数バックオフ自動リトライ(`Retry-After` 尊重、`MAGI_HTTP_MAX_RETRIES`/`MAGI_HTTP_TIMEOUT`) | 実装済 | `_urlopen_retrying` | REQ-N05 |
| FEAT-51 | `--history` による多ターン会話履歴の注入(ステートレス人格の継続。`assistant→model` 写像) | 実装済 | `load_history` + `call_responses`/`call_generate` | REQ-B05 |
| FEAT-55 | 過負荷/モデル不在時のフォールバックモデル切替(`--fallback-model` / `MAGI_*_FALLBACK_MODEL`、使用モデルを stderr 明記) | 実装済 | `run_with_fallback` / `ProviderHTTPError` | REQ-B08 |

## OpenAI ブリッジ(`scripts/ask_openai.py`)

| ID | 機能 | 状態 | 実装 | 関連要件 |
|---|---|---|---|---|
| FEAT-11 | Responses API でのテキスト往復(instructions=人格本文) | 実装済 | `call_responses` / `extract_output_text` | REQ-B02 |
| FEAT-12 | frontmatter + 先頭 HTML コメントの自動除去 | 実装済 | `strip_frontmatter` | REQ-P03 |
| FEAT-13 | API キー解決(env 優先 → settings.local.json、placeholder 除外) | 実装済 | `_get_setting` / `_settings_env` | REQ-S01, REQ-S03 |
| FEAT-14 | 画像のネイティブ vision(`--file` inline base64) | 実装済 | `build_content_parts`(input_image) | REQ-F01 |
| FEAT-15 | PDF のネイティブ処理(`--file` inline base64) | 実装済 | `build_content_parts`(input_file) | REQ-F02 |
| FEAT-16 | Office 抽出(docx/xlsx/pptx をテキスト化して注入。docx は段落と表を本文順、xlsx 上限は `MAGI_XLSX_MAX_ROWS`) | 実装済 | `extract_office` | REQ-F03 |
| FEAT-17 | テキストファイルの注入(txt/md/csv/json 等) | 実装済 | `build_content_parts` | REQ-F04 |
| FEAT-18 | `upload` サブコマンド(Files API へ multipart アップロード) | 実装済 | `cmd_upload` / `upload_file` | REQ-F06 |
| FEAT-19 | `--file-id` 参照(メタ情報で画像/PDF を判定) | 実装済 | `build_content_parts` / `file_meta` | REQ-F06 |
| FEAT-20 | 日本語の UTF-8 入出力固定(Windows のパイプ/コンソール対応) | 実装済 | stdin/stdout/stderr reconfigure + stdin buffer 復号 | REQ-N02 |
| FEAT-21 | 整形エラーハンドリング(HTTP/URL/未設定/空/未対応形式/lib 未導入) | 実装済 | `_http_json` ほか | REQ-N03 |
| FEAT-22 | `OPENAI_BASE_URL` 上書き(Azure / 互換プロキシ) | 実装済 | `_base_url` | REQ-S01 |
| FEAT-23 | 標準ライブラリのみで動作(Office 時だけ追加 lib) | 実装済 | 全体 | REQ-N01 |

## Gemini ブリッジ(`scripts/ask_gemini.py`)

ask_openai.py と CLI・挙動を対称に揃え、共通処理は bridge_common を利用。

| ID | 機能 | 状態 | 実装 | 関連要件 |
|---|---|---|---|---|
| FEAT-28 | generateContent でのテキスト往復(system_instruction=人格本文) | 実装済 | `call_generate` / `extract_output_text` | REQ-B02 |
| FEAT-29 | 画像・PDF のネイティブ処理(inline_data)/ Office 抽出 / テキスト注入 | 実装済 | `build_parts` | REQ-F01, REQ-F02, REQ-F03, REQ-F04 |
| FEAT-30 | Files API(resumable upload + ACTIVE 待ち)と `--file-id`(files/xxx)参照 | 実装済 | `upload_file` / `file_meta` / `_wait_active` | REQ-F06 |
| FEAT-31 | キー解決(GEMINI_API_KEY / GOOGLE_API_KEY)と `GEMINI_BASE_URL` 上書き | 実装済 | `_require_key` / `_base_url` | REQ-S01 |
| FEAT-32 | ブロック/空応答の整形エラー(promptFeedback/finishReason) | 実装済 | `extract_output_text` | REQ-N03 |

## 補助ツール

| ID | 機能 | 状態 | 実装 | 関連要件 |
|---|---|---|---|---|
| FEAT-33 | 使えるモデル名の一覧取得(openai/gemini を議論向けに抽出、`--all` で全件) | 実装済 | [scripts/list_models.py](scripts/list_models.py) | REQ-B01 |
| FEAT-52 | Office→Markdown 抽出 CLI(docx/pptx/xlsx、本文順、見出し/GFM表/画像マーカー) | 実装済 | [scripts/extract_office.py](scripts/extract_office.py) | REQ-F03, REQ-R03 |
| FEAT-53 | Markdown→docx 変換 CLI(見出し/表/太字、日本語フォント。全面再構築) | 実装済 | [scripts/md_to_docx.py](scripts/md_to_docx.py) | REQ-R06, REQ-R07 |
| FEAT-54 | docx 原本コピー編集 CLI(find→replace、体裁・画像保持、原本不変) | 実装済 | [scripts/docx_replace.py](scripts/docx_replace.py) | REQ-R06, REQ-R10 |

## SharePoint 連携(`scripts/sharepoint.py`)

| ID | 機能 | 状態 | 実装 | 関連要件 |
|---|---|---|---|---|
| FEAT-56 | 2つのマウント root と `enabled` トグル(`local/` ↔ `sharepoint/`)。`enabled`/`site_url`/`drive`/`root` は env(settings.local.json)→ config の順で解決。`root`/`status` で確認 | 実装済 | `load_config` / `_parse_bool` / `cmd_root` / `cmd_status` | REQ-SP02, REQ-SP03 |
| FEAT-57 | クライアントシークレット認証(Graph トークン取得)とキー解決(env → settings.local.json) | 実装済 | `get_token`(`bridge_common.get_setting` 再利用) | REQ-SP04 |
| FEAT-58 | サイト/ドライブ解決と認証検証(`test`) | 実装済 | `resolve_site` / `resolve_drive` / `cmd_test` | REQ-SP01 |
| FEAT-59 | `pull`(遠隔→ローカル、再帰・downloadUrl)/`push`(ローカル→遠隔、4MB 超はアップロードセッション分割) | 実装済 | `pull_folder` / `push_folder` / `_upload_large` | REQ-SP01, REQ-SP05 |
| FEAT-60 | `info`(ローカルミラーパス→SharePoint Web URL) | 実装済 | `cmd_info` | REQ-SP05 |
| FEAT-61 | ファシリテーター運用(開始時 pull / 提示時 push / URL 併記、無効時は no-op) | 仕様 | [CLAUDE.md](CLAUDE.md) §SharePoint 連携 | REQ-SP02, REQ-SP05 |
| FEAT-62 | 標準ライブラリのみ(HTTP は `bridge_common` 経由、新規 pip 依存なし) | 実装済 | `sharepoint.py`(`bridge_common.http_json`/`http_raw` 再利用) | REQ-SP06, REQ-N01 |
| FEAT-64 | Azure アプリ登録セットアップマニュアル(登録→シークレット→権限+同意→設定→確認→トラブルシュート) | 実装済 | [documents/sharepoint-azure-app-setup.md](documents/sharepoint-azure-app-setup.md) | REQ-SP07, REQ-SP08 |

## 設定 / シークレット管理

| ID | 機能 | 状態 | 実装 | 関連要件 |
|---|---|---|---|---|
| FEAT-24 | 設定テンプレート `.example`(Git 追跡)と実値ファイル(Git 除外)。OPENAI/GEMINI 両キー対応 | 実装済 | [.claude/settings.local.json.example](.claude/settings.local.json.example) | REQ-S02 |
| FEAT-63 | SharePoint 連携設定ファイル(非機密・追跡。`enabled`/site/drive/folders) | 実装済 | [sharepoint.config.json](sharepoint.config.json) | REQ-SP02 |

## 成果物生成

| ID | 機能 | 状態 | 実装/定義 | 関連要件 |
|---|---|---|---|---|
| FEAT-25 | Markdown ログの生成(合議=議論ログ / 資料レビュー=指摘レポート) | 仕様 | [scenarios/deliberation.md](scenarios/deliberation.md) §成果物, [scenarios/document-review.md](scenarios/document-review.md) §成果物 | REQ-O01 |
| FEAT-26 | Excel / Word / チャートの生成(python-docx, openpyxl, matplotlib, pillow) | 仕様 | [scenarios/deliberation.md](scenarios/deliberation.md) §成果物 | REQ-O02 |
| FEAT-49 | 改訂版ドキュメントの生成(元と同形式: md/docx/txt 等) | 仕様 | [scenarios/document-review.md](scenarios/document-review.md) §成果物 | REQ-R06, REQ-R07 |
