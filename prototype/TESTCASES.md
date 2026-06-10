# テストケース一覧(Test Cases)

プロトタイプの検証用テストケース集。**重要度ランク(P0〜P3)で分類**してあり、
毎回すべてを流す必要はない。変更内容に応じて下の「テスト選択ガイド」で対象を絞る。

関連: [REQUIREMENTS.md](REQUIREMENTS.md) / [FEATURES.md](FEATURES.md)。一次資料は [DOCS.md](DOCS.md)。

---

## 重要度ランクの定義

| ランク | 意味 | いつ流すか | 性質 |
|---|---|---|---|
| **P0** | クリティカル。壊れたら全体が成立しない | **毎回(コミット前)** | 低コスト・決定的。大半が API 課金なしで自動化可能 |
| **P1** | コア。主要なハッピーパス | ブリッジ/人格/プロトコル変更時・リリース前 | 一部 API 課金あり |
| **P2** | 拡張。網羅マトリクス・準ネイティブ機能 | 定期・フル回帰 | API 課金あり |
| **P3** | エッジ。例外・境界・環境依存 | 随時・環境変更時・気になった時 | 再現条件が特殊なものを含む |

### テスト選択ガイド(これだけ見れば良い)

| タイミング | 実行するランク |
|---|---|
| 各コミット前 | **P0** |
| `ask_openai.py` / 人格定義 / 議論プロトコルを変更した | **P0 + P1** |
| リリース前・大きめの変更後のフル回帰 | **P0 + P1 + P2** |
| 環境を変えた / 課金や接続が怪しい / 既知の制約を再確認したい | 上記に **P3** を追加 |

### 凡例

- **API**: ✕=OpenAI 課金なしで実行可 / ◯=OpenAI API を呼ぶ(課金・ネットワーク必要)
- **自動**: ◯=CLI/スクリプトで自動化可 / △=半自動 / 手動=人手で議論を回して確認
- コマンド例の入力リダイレクト(`echo ... |`)は PowerShell でも同様に動く。

---

## インデックス(選択用サマリ)

| ID | タイトル | ランク | API | 自動 | 関連 |
|---|---|---|---|---|---|
| TC-001 | スクリプト構文チェック(全スクリプト) | P0 | ✕ | ◯ | FEAT-11,27,28,52,53,54 |
| TC-002 | フロントマター＋HTMLコメント除去 | P0 | ✕ | ◯ | FEAT-12 |
| TC-003 | キー未設定エラー | P0 | ✕ | ◯ | FEAT-13, REQ-N03 |
| TC-004 | placeholder は未設定扱い | P0 | ✕ | ◯ | FEAT-13 |
| TC-005 | キー解決の優先順位(env→settings) | P0 | ✕ | ◯ | FEAT-13, REQ-S03 |
| TC-006 | settings JSON の妥当性 | P0 | ✕ | ◯ | FEAT-24 |
| TC-007 | Git 追跡/除外の健全性 | P0 | ✕ | ◯ | REQ-S02 |
| TC-008 | 人格 frontmatter の妥当性 | P0 | ✕ | ◯ | FEAT-06, REQ-P02 |
| TC-009 | 未対応ファイル形式エラー | P0 | ✕ | ◯ | FEAT-21 |
| TC-010 | 空入力エラー | P0 | ✕ | ◯ | FEAT-21 |
| TC-011 | シナリオ・ルーティングの健全性(判定表↔ファイル整合) | P0 | ✕ | △ | FEAT-42, FEAT-43 |
| TC-012 | 入出力 root の Git 除外健全性(local/・sharepoint/) | P0 | ✕ | ◯ | REQ-SC05, REQ-SP02 |
| TC-013 | stdin の UTF-8 復号(サロゲート化しない) | P0 | ✕ | ◯ | FEAT-20, REQ-N02 |
| TC-014 | 一過性HTTPエラーの自動リトライ(429/5xx) | P0 | ✕ | ◯ | FEAT-50, REQ-N05 |
| TC-015 | 空/拒否応答の自動リトライ | P0 | ✕ | ◯ | FEAT-10, REQ-B06 |
| TC-016 | `--history` 整形(履歴の積み方・role写像) | P0 | ✕ | ◯ | FEAT-51 |
| TC-028 | フォールバック切替の分岐(run_with_fallback) | P0 | ✕ | ◯ | FEAT-55, REQ-B08 |
| TC-029 | フォールバック実動(偽primary→代替モデル) | P2 | ◯ | ◯ | FEAT-55 |
| TC-017 | docx 本文順抽出 | P1 | ✕ | ◯ | FEAT-16, REQ-F03 |
| TC-018 | `--history` 記憶の往復(合言葉の再生) | P1 | ◯ | ◯ | FEAT-51, FEAT-09 |
| TC-019 | extract_office で docx を本文順 md 化 | P1 | ✕ | ◯ | FEAT-52, REQ-R03 |
| TC-026 | md_to_docx の md→docx 往復 | P1 | ✕ | ◯ | FEAT-53, REQ-R06 |
| TC-027 | docx_replace 原本コピー編集(原本不変) | P1 | ✕ | ◯ | FEAT-54, REQ-R10 |
| TC-028 | extract_office で xlsx / pptx を md 化 | P2 | ✕ | ◯ | FEAT-52 |
| TC-029 | Office ヘルパーの異常系(未対応形式/欠落/不正JSON/空find) | P2 | ✕ | ◯ | FEAT-52, FEAT-54 |
| TC-020 | テキスト往復(MELCHIOR/gpt-4o) | P1 | ◯ | ◯ | FEAT-11 |
| TC-021 | 3人格の個性再現(好奇心の屈折を含む) | P1 | ◯ | △ | FEAT-05, FEAT-71 |
| TC-022 | 画像インライン vision | P1 | ◯ | ◯ | FEAT-14 |
| TC-023 | PDF(テキスト有)読取 | P1 | ◯ | ◯ | FEAT-15 |
| TC-024 | xlsx 抽出 | P1 | ◯ | ◯ | FEAT-16 |
| TC-025 | ドキュメント整合(CLAUDE.md↔DOCS.md) | P1 | ✕ | 手動 | REQ-B03 |
| TC-030 | docx 抽出 | P2 | ◯ | ◯ | FEAT-16 |
| TC-031 | pptx 抽出(要 python-pptx) | P2 | ◯ | ◯ | FEAT-16 |
| TC-032 | テキストファイル注入 | P2 | ◯ | ◯ | FEAT-17 |
| TC-033 | upload→file_id 使い回し | P2 | ◯ | ◯ | FEAT-18, FEAT-19 |
| TC-034 | Office の upload 拒否 | P2 | ✕ | ◯ | FEAT-18 |
| TC-035 | pptx ライブラリ未導入の親切エラー | P2 | ✕ | ◯ | FEAT-21 |
| TC-036 | temperature 指定 | P2 | ◯ | ◯ | FEAT-11 |
| TC-037 | claude/openai 混在の合議 | P2 | ◯ | 手動 | FEAT-07, REQ-B03 |
| TC-038 | Lite モード一周 | P2 | △ | 手動 | FEAT-02 |
| TC-039 | 少数意見の保持 | P2 | △ | 手動 | FEAT-03, REQ-D05 |
| TC-040 | backend/model のログ明記 | P2 | △ | 手動 | FEAT-08, REQ-B04 |
| TC-041 | Markdown 議論ログ生成 | P2 | △ | 手動 | FEAT-25 |
| TC-042 | 資料レビュー一周(Standard、指摘+改訂版) | P2 | △ | 手動 | FEAT-46, FEAT-48 |
| TC-043 | 改訂版が元と同形式で出る | P2 | △ | 手動 | FEAT-49, REQ-R06 |
| TC-044 | 衝突指摘の裁定と未採用指摘の保持 | P2 | △ | 手動 | FEAT-47, REQ-R08 |
| TC-045 | 改訂版 docx 往復 統合(抽出→差替→再抽出: 変更反映+構造保持+原本不変) | P1 | ✕ | ◯ | FEAT-52, FEAT-54, REQ-R06, REQ-R10 |
| TC-050 | 複数ファイル同時添付 | P3 | ◯ | ◯ | FEAT-14, FEAT-15 |
| TC-051 | ベクター/スキャンのみ PDF の限界 | P3 | ◯ | △ | REQ-F02 |
| TC-052 | xlsx 行数ソフト上限の省略 | P3 | ✕ | ◯ | FEAT-16 |
| TC-053 | 不正 file_id のエラー整形 | P3 | ◯ | ◯ | FEAT-21 |
| TC-054 | 拒否/空応答の再試行(自動+手動) | P3 | ◯ | △ | FEAT-10, REQ-B06 |
| TC-055 | OPENAI_BASE_URL 上書き | P3 | ◯ | △ | FEAT-22 |
| TC-056 | クォータ超過(429)のリトライと整形表示 | P3 | ◯ | △ | FEAT-21, FEAT-50 |
| TC-057 | Excel/Word/チャート生成 | P3 | △ | 手動 | FEAT-26 |
| TC-058 | Standard / Full モード一周 | P3 | △ | 手動 | FEAT-02 |
| TC-059 | sharepoint.py 構文 + root/status の整合(オフライン) | P0 | ✕ | ◯ | FEAT-56, REQ-SP02, REQ-SP03 |
| TC-060 | enabled=false で pull/push が no-op(安全) | P0 | ✕ | ◯ | FEAT-61, REQ-SP02 |
| TC-061 | 認証情報未設定エラーの整形(test) | P1 | ✕ | ◯ | FEAT-57, REQ-SP04, REQ-N03 |
| TC-062 | SharePoint 実 pull/push 往復(要テナント) | P3 | ◯ | △ | FEAT-58, FEAT-59, FEAT-60 |
| TC-063 | セットアップマニュアルの整合(存在・参照・記載とコードの一致) | P1 | ✕ | ◯ | FEAT-64, REQ-SP07 |
| TC-064 | Azure/Graph 手順の最新性確認(Web 検索) | P3 | ✕ | 手動 | FEAT-64, REQ-SP08 |
| TC-065 | ブレスト一周(Standard、マップ+評価+上位案) | P2 | △ | 手動 | FEAT-66, FEAT-68, FEAT-70 |
| TC-066 | ブレスト Quick 一周(発散1巡) | P3 | △ | 手動 | FEAT-66 |
| TC-067 | 好奇心の屈折確認(対象別の興味差) | P3 | ◯ | △ | FEAT-71, REQ-P04 |
| TC-068 | 人格テスト一周(Standard、差分マトリクス+判定) | P2 | △ | 手動 | FEAT-72, FEAT-73, REQ-PT01 |

---

## P0 — クリティカル(毎回)

### TC-001 スクリプト構文チェック
- **目的**: ブリッジ(共通 + 各プロバイダ)と補助ツールが壊れていないことを最速で確認。
- **手順**: `python -m py_compile scripts/bridge_common.py scripts/ask_openai.py scripts/ask_gemini.py scripts/list_models.py scripts/extract_office.py scripts/md_to_docx.py scripts/docx_replace.py scripts/sharepoint.py`
- **期待**: エラーなし(終了コード 0)。

### TC-002 フロントマター＋HTMLコメント除去
- **目的**: OpenAI に渡るシステムプロンプトが「人格本文のみ」であること。
- **手順**: `strip_frontmatter` に人格ファイル内容を渡し、先頭を確認。
  ```bash
  python -c "import importlib.util as u; s=u.spec_from_file_location('bc','scripts/bridge_common.py'); m=u.module_from_spec(s); s.loader.exec_module(m); print(m.strip_frontmatter(open('.claude/agents/melchior.md',encoding='utf-8').read())[:30])"
  ```
- **期待**: `あなたは MELCHIOR` で始まる(frontmatter・`<!-- -->` コメントが残っていない)。
- **注**: `strip_frontmatter` / `get_setting` 等の共通ヘルパーは `bridge_common.py` に集約済み(各ブリッジは `import bridge_common as bc` で利用)。

### TC-003 キー未設定エラー
- **目的**: キーが無いとき整形メッセージで止まる(トレースバックを出さない)。
- **前提**: 環境変数 `OPENAI_API_KEY` 未設定、かつ settings が placeholder。
- **手順**: `echo x | python scripts/ask_openai.py --system "t" --model gpt-4o`(キー無し状態)
- **期待**: `error: OPENAI_API_KEY が未設定です…` の1行で終了。スタックトレースなし。

### TC-004 placeholder は未設定扱い
- **目的**: テンプレ値 `sk-REPLACE...` を誤って有効キーと見なさない。
- **手順**: settings.local.json の値が `...REPLACE...` の状態で TC-003 を実行。
- **期待**: 「未設定」として扱われエラー(誤って API を叩かない)。

### TC-005 キー解決の優先順位(env→settings)
- **目的**: 環境変数優先、無ければ settings.local.json を読むフォールバック。
- **手順**:
  ```bash
  python -c "import os,importlib.util as u; s=u.spec_from_file_location('bc','scripts/bridge_common.py'); m=u.module_from_spec(s); s.loader.exec_module(m); os.environ['OPENAI_API_KEY']='sk-env-dummy'; print('env:', m.get_setting('OPENAI_API_KEY')); del os.environ['OPENAI_API_KEY']; print('file:', (m.get_setting('OPENAI_API_KEY') or 'None')[:6])"
  ```
- **期待**: `env: sk-env-dummy`(環境変数が勝つ)。環境変数を消すと settings の値(または placeholder のとき None)になる。

### TC-006 settings JSON の妥当性
- **目的**: 設定ファイルとテンプレが壊れた JSON でない。
- **手順**: `python -c "import json; json.load(open('.claude/settings.local.json',encoding='utf-8')); json.load(open('.claude/settings.local.json.example',encoding='utf-8')); json.load(open('sharepoint.config.json',encoding='utf-8')); print('ok')"`
- **期待**: `ok`。

### TC-007 Git 追跡/除外の健全性
- **目的**: 秘密ファイルが追跡されず、テンプレは追跡される。
- **手順**:
  ```bash
  git check-ignore .claude/settings.local.json   # 出る(=除外)
  git check-ignore .claude/settings.local.json.example  # 出ない(=追跡)
  # 除外パターンはディレクトリ名ではなく中身(local/**, sharepoint/**)。具体ファイルパスで確認する:
  git check-ignore local/deliberations/x.md local/input/x.png local/reviews/x-改訂版.docx sharepoint/reviews/x.docx   # 出る(=除外)
  git check-ignore sharepoint.config.json   # 出ない(=追跡。非機密設定)
  ```
- **期待**: 実値・入出力ファイル(local/・sharepoint/ 配下)は除外、`.example` と `sharepoint.config.json` は追跡。

### TC-008 人格 frontmatter の妥当性
- **目的**: 3人格すべてに `backend`(claude|openai|gemini)と `model` がある。
- **手順**: 各 `.claude/agents/*.md` の frontmatter を確認。
- **期待**: `backend` が `claude` / `openai` / `gemini` のいずれか、`model` が非空。欠落・タイポなし。

### TC-009 未対応ファイル形式エラー
- **目的**: 想定外の拡張子で安全に止まる。
- **手順**: `echo x | python scripts/ask_openai.py --system t --model gpt-4o --file dummy.zip`(zip を用意 or 既存任意ファイルを .zip 名で)
- **期待**: `error: 未対応のファイル形式です: …`(API を叩く前に停止)。

### TC-010 空入力エラー
- **目的**: 入力もファイルも無いとき止まる。
- **手順**: `printf "" | python scripts/ask_openai.py --system t --model gpt-4o`
- **期待**: `error: 入力が空です…`。

### TC-011 シナリオ・ルーティングの健全性
- **目的**: ファシリテーターが選べるシナリオと、実在するシナリオファイルが食い違わない。
- **手順**:
  ```bash
  ls scenarios/                                  # deliberation.md / document-review.md / brainstorm.md / persona-test.md / README.md
  grep -o "scenarios/[a-z-]*\.md" CLAUDE.md | sort -u   # 判定表が参照するファイル一覧
  ```
- **期待**: CLAUDE.md「シナリオの選択」判定表が参照する**4つ**の `scenarios/<name>.md`(deliberation /
  document-review / brainstorm / persona-test)がすべて実在し、`scenarios/README.md` の一覧とも一致する(リンク切れ・取りこぼしなし)。

### TC-012 入出力 root の Git 除外健全性
- **目的**: 入出力ファイル(元資料・成果物・個人情報を含みうる)が誤って追跡されない。
- **手順**: `git check-ignore local/reviews/sample-改訂版.docx`(出る=除外)、
  `git check-ignore local/reviews/.gitkeep sharepoint/input/.gitkeep`(出ない=追跡)。
- **期待**: `local/` `sharepoint/` 配下の成果物・入力は除外、`.gitkeep`・`README.md` は追跡。

### TC-013 stdin の UTF-8 復号
- **目的**: パイプ入力の日本語が UTF-8 で読まれ、不正なサロゲートを生まない(OpenAI の HTTP 400 回避)。
- **手順**: `printf '下部構造と上部構造（テスト）' | python -c "import sys;sys.path.insert(0,'scripts');import bridge_common as bc;t=bc.load_user_text(None);print(any(0xD800<=ord(c)<=0xDFFF for c in t), t)"`
- **期待**: 先頭が `False`(サロゲートなし)で、元の日本語がそのまま表示される。

### TC-014 一過性HTTPエラーの自動リトライ
- **目的**: 429/5xx/タイムアウトを指数バックオフで再試行し、回復すれば返す/超過すれば整形エラー。非一過性(400 等)は即停止。
- **手順**: `urllib.request.urlopen` をモックして 503 を数回返してから成功させる(`bc.time.sleep` を差し替えれば即時)。`MAGI_HTTP_MAX_RETRIES` で回数調整。
- **期待**: 503×N→成功で本文を返す。回数超過・非一過性(400 等)は `ProviderHTTPError` を送出し、各ブリッジの main が `error: … HTTP <code>` に整形する(429/5xx は規定回数リトライ後、400 等は即時)。

### TC-015 空/拒否応答の自動リトライ
- **目的**: 空応答・拒否(OpenAI=refusal/content_filter、Gemini=finishReason SAFETY)を `MAGI_GEN_MAX_RETRIES` 回再試行。入力ブロックは非リトライ。
- **手順**: `extract_output_text` に合成レスポンスを渡し `EmptyOrRefusalResponse.kind` を確認。`run_with_retry` に「空→空→成功」の関数を渡す。
- **期待**: refusal/empty を正しく分類。Gemini の `blockReason`(入力ブロック)は再試行せず即 `SystemExit`。持続失敗は言い換え案内付きで停止。

### TC-016 --history の整形
- **目的**: `--history` JSON が正規化され、履歴→今回入力の順に積まれる(OpenAI=input messages、Gemini=contents、`assistant→model` 写像、空除去)。
- **手順**: `bc.load_history` の正規化と、`call_responses`/`call_generate` のペイロード(`bc.http_json` をモックして捕捉)を確認。不正 JSON も渡す。
- **期待**: role 写像・順序・空除去が正しく、不正 JSON は `error: --history が不正な JSON です…` で停止。

### TC-028 フォールバックモデル切替の分岐
- **目的**: 過負荷/モデル不在で primary が失敗したとき、指定があれば代替モデルへ1回だけ切り替える。
- **手順**: `bc.run_with_fallback(run_fn, primary, fallback, provider)` に、`bc.ProviderHTTPError` を投げる run_fn を渡して各分岐を確認。
- **期待**: primary 成功=fallback 不使用 / 429・5xx・404・400(model_not_found)=fallback 実行 / 401・一般 400・接続エラー=非フォールバックで整形 SystemExit / fallback 未指定=整形 SystemExit。

### TC-059 sharepoint.py 構文 + root/status の整合(オフライン)
- **目的**: 同期ブリッジが壊れておらず、設定からアクティブ root を正しく解決する(通信なし)。
- **手順**:
  ```bash
  python -m py_compile scripts/sharepoint.py
  python scripts/sharepoint.py root      # enabled=false なら …/local で終わる
  python scripts/sharepoint.py status    # enabled / active root / folders を表示
  MAGI_SHAREPOINT_ENABLED=true python scripts/sharepoint.py root   # env で上書き → …/sharepoint
  ```
- **期待**: 構文 OK。`root` は `enabled=false` で `local`、`true` で `sharepoint` を指す。`status` が
  設定値(site/drive/folders)と一致して表示される。**env `MAGI_SHAREPOINT_ENABLED` は config より
  優先**(`true`/`1`/`yes`/`on`=オン)。`settings.local.json` 経由でも同様に効く(env → config)。

### TC-060 enabled=false で pull/push が no-op(安全)
- **目的**: SharePoint 無効時に同期コマンドを呼んでもローカルを壊さず安全に終了する。
- **手順**: `sharepoint.config.json` の `enabled:false`(既定)で `python scripts/sharepoint.py pull` /
  `python scripts/sharepoint.py push`。
- **期待**: 「SharePoint 無効…」を stderr に出し、何もせず終了コード 0。ネットワークを叩かない。

---

## P1 — コア(ブリッジ/人格/プロトコル変更時・リリース前)

### TC-020 テキスト往復(MELCHIOR/gpt-4o)
- **目的**: ブリッジが OpenAI と往復し、人格として応答する基本動線。
- **手順**: `echo "Round1 初期意見。議題: 朝はコーヒーか紅茶か。立場を2文で。" | python scripts/ask_openai.py --system-file .claude/agents/melchior.md --model gpt-4o`
- **期待**: `MELCHIOR:` で始まり、論理・データ寄りの内容が返る。エラーなし。

### TC-021 3人格の個性再現
- **目的**: 同じ議題で人格差が出る。**好奇心の向き**もレンズごとに屈折する。
- **手順**: TC-020 を balthasar / casper でも実行。
- **期待**: BALTHASAR=関係性・感情、CASPER=直感・欲求 が表れ、各接頭辞が付く。さらに各人格の
  **好奇心が対象別に屈折**する(MELCHIOR=仕組み・因果を問う / BALTHASAR=人・関係に関心 /
  CASPER=新奇・体験に惹かれる)。声は屈折しても3人格の区別は保たれる(タチコマ化で似ない)。
- **関連**: 本テストは**人格テストシナリオ**([scenarios/persona-test.md](scenarios/persona-test.md))で
  体系的に実行できる(同一プローブ→差分マトリクス→人格別判定。→ TC-068)。

### TC-022 画像インライン vision
- **目的**: 画像をネイティブに読む。
- **前提**: 任意の画像(例 `local/input/sample.png`)。
- **手順**: `echo "添付画像に見えるものを1文で。" | python scripts/ask_openai.py --system-file .claude/agents/melchior.md --model gpt-4o --file local/input/sample.png`
- **期待**: 画像の内容(文字・図形など)を具体的に描写する。

### TC-023 PDF(テキスト有)読取
- **目的**: テキストを持つ PDF をネイティブに読む。
- **前提**: 本文テキストを持つ PDF(スキャン画像のみでない)。
- **手順**: `echo "添付PDFのタイトルと結論を引用して。" | python scripts/ask_openai.py --system-file .claude/agents/melchior.md --model gpt-4o --file docs/sample.pdf`
- **期待**: タイトル・本文を引用できる。

### TC-024 xlsx 抽出
- **目的**: Excel をローカル抽出して数値を扱える。
- **前提**: 表データを持つ xlsx。
- **手順**: `echo "添付の表から特定セルの値と傾向を答えて。" | python scripts/ask_openai.py --system-file .claude/agents/melchior.md --model gpt-4o --file data/sample.xlsx`
- **期待**: セル値を正しく答え、傾向を述べる。

### TC-025 ドキュメント整合(CLAUDE.md ↔ scenarios/ ↔ DOCS.md)
- **目的**: 仕様の乖離防止(本プロジェクトの禁止事項)。
- **手順**: backend/ファイル仕様・シナリオのラウンド/モード/成果物について、CLAUDE.md(共通)・
  `scenarios/<name>.md`(各シナリオ)・DOCS.md を見比べる(手動レビュー)。
- **期待**: 共通作法は CLAUDE.md を唯一の出典としてシナリオに重複コピーがなく、各シナリオの
  モード表・ラウンド・成果物が DOCS.md「4. シナリオとプロトコル」(4-A / 4-B / 4-C / **4-D**)と一致。出力先
  (`<root>/deliberations/` / `<root>/reviews/` / `<root>/brainstorms/` / `<root>/persona-tests/`)が
  CLAUDE.md・各シナリオ・.gitignore で一致。

### TC-017 docx 本文順抽出
- **目的**: docx 抽出で段落と表がドキュメント順に並ぶ(図表が本文末尾へ集約されない)。
- **手順**: 図表入り docx を `bc.extract_office('<docx>', '.docx')` で抽出し、`find('<図表キャプション>') < find('<表セル内容>') < find('<次見出し>')` を確認。
- **期待**: `True`(表セルの内容がキャプション直後・次セクション見出しより前に現れる)。旧実装(段落→表を別々に並べる)なら表が末尾に集約され失敗する。

### TC-018 --history 記憶の往復
- **目的**: 履歴で渡した情報を人格が参照できる(ステートレス継続の実地確認)。
- **前提**: 履歴 JSON(例 `[{"role":"user","text":"合言葉は NEON-7788"},{"role":"assistant","text":"了解、NEON-7788 ですね"}]`)。
- **手順**: `printf 'さきほどの合言葉をそのまま答えて。' | python scripts/ask_openai.py --system-file .claude/agents/casper.md --model gpt-5.4 --history hist.json`(gemini でも同様)。
- **期待**: 応答に合言葉 `NEON-7788` が含まれる。

### TC-019 extract_office で docx を本文順 Markdown 化
- **目的**: 対象資料の「正本テキスト」を、図表を文脈位置に置いた Markdown で得る(全人格に等しく渡す土台)。
- **手順**: `python scripts/extract_office.py <図表入り docx> -o canon.md` 後、`find('<図表Nの見出し>') < find('<表セル内容>') < find('<次見出し>')` を確認。
- **期待**: 段落と表がドキュメント順に並ぶ(GFM 表・`#`/`##`/`###` 見出し・`*[画像]*` マーカーを保持)。

### TC-026 md_to_docx の Markdown→docx 往復
- **目的**: 改訂本文(Markdown)を体裁付き docx に書き出せる(全面再構築方式)。
- **手順**: `python scripts/md_to_docx.py canon.md -o rebuilt.docx` 後、`extract_office rebuilt.docx` で再抽出し、見出しと表セル内容の再現を確認。
- **期待**: 見出し・表・太字が docx に反映される(※画像・複雑書式は対象外=全面再構築の限界)。

### TC-027 docx_replace の原本コピー編集
- **目的**: 体裁・画像を保ったまま、合意した変更だけを差し替える(原本は不変)。
- **手順**: `[{"find":"原文の一節","replace":"改訂後"}]` を JSON にし `python scripts/docx_replace.py 原本.docx -r changes.json -o out.docx`。出力を再抽出して「新語あり・旧語なし」、原本を再抽出して「旧語が残る」ことを確認。未検出 find には `[WARN] 0件` が出る。
- **期待**: 変更が適用され、**原本は変更されない**。未検出 find は警告される。

### TC-028 extract_office で xlsx / pptx を Markdown 化
- **目的**: docx 以外の Office(xlsx/pptx)も正本テキスト化できる(TC-019 の docx を補完)。
- **手順**:
  - xlsx: `python scripts/extract_office.py <xlsx>` → `## シート: <名前>` と GFM 表(`| 月 | 売上 |` 等)が出る。
  - pptx: `python scripts/extract_office.py <pptx>` → `# スライド 1` と各図形のテキストが出る。
- **期待**: シート/スライドの見出しと中身が Markdown で得られる(pptx は要 python-pptx)。

### TC-029 Office ヘルパーの異常系
- **目的**: 想定外入力で整形メッセージ終了(トレースバックを出さない)。
- **手順**:
  - `extract_office.py x.zip` → `error: 未対応の形式です: .zip`。
  - `extract_office.py 存在しない.docx` → `error: ファイルが見つかりません: …`。
  - `docx_replace.py 原本.docx -r 非配列.json` → `error: --replacements は […] の JSON 配列に…`。
  - `docx_replace.py 原本.docx -r 空find.json`(`[{"find":"","replace":"y"}]`) → `error: --replacements[0] の find が空です`。
- **期待**: いずれも非ゼロ終了かつ整形メッセージ1行。

### TC-045 改訂版 docx 往復 統合(document-review の核)
- **目的**: 「指摘の合意 → 改訂版(元と同形式 docx)」が原本コピー編集で**端から端まで**成立することの統合確認。
- **手順**: 見出し+段落+表を持つ原本 docx を用意 → `extract_office` で正本 md 化 →
  合意変更を `[{"find":"<旧表現>","replace":"<新表現>"}]` にして `docx_replace` で改訂版 docx 生成 →
  改訂版を `extract_office` で再抽出。
- **期待**: 改訂版に(a)変更が反映され、(b)見出し(`#`)と表(`| … |`)の構造が保持され、
  (c)原本 docx は不変(再抽出で旧表現が残る)。3条件すべて真。
- **検証メモ**: 2026-06-05 に上記を自動実行し PASS(変更反映+構造保持+原本不変)。

### TC-061 認証情報未設定エラーの整形(test)
- **目的**: SharePoint 有効でも認証情報が無いとき、トレースバックでなく整形メッセージで止まる。
- **前提**: `enabled:true` かつ `MAGI_SHAREPOINT_*` 未設定(settings が placeholder)。
- **手順**: `python scripts/sharepoint.py test`
- **期待**: `error: SharePoint の認証情報が未設定です: MAGI_SHAREPOINT_TENANT_ID, …` の整形メッセージで
  終了。スタックトレースなし。`enabled:false` の場合は「SharePoint 無効」で no-op(TC-060)。

### TC-063 セットアップマニュアルの整合
- **目的**: Azure セットアップ手順書が存在し、README/DOCS から参照され、記載(env 名・必要権限・
  コマンド)がコード/設定と食い違わない(古いマニュアルで詰まらせない)。
- **手順**:
  ```bash
  test -f documents/sharepoint-azure-app-setup.md          # 存在
  grep -q "documents/sharepoint-azure-app-setup.md" README.md DOCS.md   # 参照リンクあり
  # マニュアルが実装と同じ語彙を使っているか(env 名・権限・サブコマンド)
  M=documents/sharepoint-azure-app-setup.md
  grep -q "MAGI_SHAREPOINT_TENANT_ID" "$M" && grep -q "MAGI_SHAREPOINT_CLIENT_SECRET" "$M"
  grep -q "MAGI_SHAREPOINT_ENABLED" "$M"   # オンオフを settings.local.json で切替できる旨
  grep -q "Sites.ReadWrite.All" "$M"
  for c in status test pull push info; do grep -q "sharepoint.py $c" "$M" || echo "missing: $c"; done
  ```
- **期待**: すべて真(`missing:` 行が出ない)。マニュアルの env 名は `bridge_common`/`sharepoint.py`、
  権限は §3、サブコマンドは `sharepoint.py` の実装と一致する。
- **注**: env 名や権限スコープ、サブコマンドを変更したら**このマニュアルも同時に更新**する
  (CLAUDE.md/DOCS.md の整合ルールに準じる)。

---

## P2 — 拡張(定期・フル回帰)

### TC-029 フォールバック実動(偽primary→代替モデル)
- **目的**: 実 API でフォールバックが端から端まで動く。
- **手順**: `printf '...' | python scripts/ask_openai.py --system-file .claude/agents/casper.md --model gpt-bogus-xyz --fallback-model gpt-5.4 2>&1`(gemini は `--model gemini-bogus-xyz --fallback-model gemini-2.5-flash`)。
- **期待**: `warn: … fallback model=… で再試行します` が stderr に出て、代替モデルの人格応答が stdout に返る。OpenAI は不明モデルを 400(model_not_found)、Gemini は 404 で返すが、いずれもフォールバックする。

### TC-030 docx 抽出
- **手順**: 本文・表を持つ docx を `--file` で渡し、内容を問う。
- **期待**: 段落・表セルの内容を引用できる。

### TC-031 pptx 抽出(要 python-pptx)
- **前提**: `pip install python-pptx` 済み。
- **手順**: pptx を `--file` で渡し、スライドの文言を問う。
- **期待**: 各スライドのテキストを抽出して答える。

### TC-032 テキストファイル注入
- **手順**: `.md` / `.csv` を `--file` で渡す。
- **期待**: ファイル名見出し付きで本文が文脈に入り、内容に基づき回答する。

### TC-033 upload→file_id 使い回し
- **手順**:
  ```bash
  FID=$(python scripts/ask_openai.py upload local/input/sample.png)
  echo "この画像は?" | python scripts/ask_openai.py --system-file .claude/agents/melchior.md --model gpt-4o --file-id "$FID"
  ```
- **期待**: `upload` が `file-...` を返し、`--file-id` 参照で同じ画像を読める(画像/PDF をメタから正しく判定)。

### TC-034 Office の upload 拒否
- **手順**: `python scripts/ask_openai.py upload sample.xlsx`
- **期待**: Office はアップロード非対応の旨を案内するエラー(実行時 `--file` で抽出する旨)。

### TC-035 pptx ライブラリ未導入の親切エラー
- **前提**: python-pptx 未導入。
- **手順**: `echo x | python scripts/ask_openai.py --system t --model gpt-4o --file any.pptx`
- **期待**: `error: .pptx の読み取りに python-pptx が必要です。pip install python-pptx …`。

### TC-036 temperature 指定
- **手順**: `--temperature 0.2` を付けて TC-020 を実行。
- **期待**: エラーなく応答(値が API に渡る)。

### TC-037 claude/openai 混在の合議(手動)
- **手順**: 1人格を `backend: openai`、他を `backend: claude` にして Lite 議論を回す。
- **期待**: ラウンド・投票・採点が backend 差に関係なく成立する。

### TC-038 Lite モード一周(手動)
- **手順**: `cd prototype && claude` で Lite 議題を1件回す。
- **期待**: Round 0,1,2,7,8,9 が進み、統合回答と Markdown ログが出る。

### TC-039 少数意見の保持(手動)
- **手順**: 意見が割れる議題で合議。
- **期待**: 反対票・少数意見が最終回答とログに残る(多数決で消されない)。

### TC-040 backend/model のログ明記(手動)
- **手順**: 混在構成で合議し、生成ログ冒頭を確認。
- **期待**: 各人格の backend/model が記録されている。

### TC-041 Markdown 議論ログ生成(手動)
- **手順**: 任意モードで合議。
- **期待**: `<root>/deliberations/YYYYMMDD-HHMM-<議題>.md` が生成される。

### TC-042 資料レビュー一周(Standard、指摘+改訂版)(手動)
- **手順**: `cd prototype && claude` で資料を渡し、document-review シナリオを Standard で1件回す。
  例: `local/input/` に短い docx/md を置き「この資料をレビューして改訂版も作って」。
- **期待**: Round 0,1,2,3,4,6 が進み、3レンズの指摘 → 裁定 → 改訂版生成まで到達。
  `<root>/reviews/` にレビューレポートと改訂版の両方が出る。

### TC-043 改訂版が元と同形式で出る(手動)
- **手順**: 元が docx の資料と、元が md の資料でそれぞれレビューを回す。
- **期待**: docx 入力 → `<root>/reviews/...-改訂版.docx`、md 入力 → `<root>/reviews/...-改訂版.md`(形式が保たれる)。

### TC-044 衝突指摘の裁定と未採用指摘の保持(手動)
- **手順**: 指摘が衝突しやすい資料(冗長だが厳密さも要る等)でレビュー。
- **期待**: レポートに衝突指摘の裁定理由と、未採用の指摘・理由が残る(丸めて消されない)。

### TC-065 ブレスト一周(Standard、マップ+評価+上位案)(手動)
- **目的**: ブレストシナリオが発散 → マップ → 評価 → 上位案ブラッシュアップまで一周する。
- **手順**: `cd prototype && claude` で軽いテーマを Standard で1件回す。
  例: 「エンジニアの学びが続く社内勉強会のネタ」(制約: 月1回・1時間・登壇持ち回り)。
- **期待**: Round 0,1,2,3,4,5,6,7,8 が進み、`<root>/brainstorms/` にアイデア集が出る。アイデア集に
  (a) レンズ別の全アイデア(派生元付き)、(b) アイデアマップ(Mermaid mindmap、クラスタと白地)、
  (c) 評価マトリクス(0〜10、レンズ別内訳)、(d) 上位案(ブラッシュアップ済み)、
  (e) 保持された「割れた尖り案」が含まれる。

### TC-068 人格テスト一周(Standard、差分マトリクス+判定)(手動)
- **目的**: 人格テストシナリオが、同一プローブ→差分→判定まで一周し、人格の個性・好奇心の屈折・弱みを検査できる。
- **手順**: `cd prototype && claude` で人格テストを Standard で1件実行(P1〜P4 を3人格に独立投下)。
  人格調整の検証なら Round 0 で「何を変えたか」を宣言して回す。
- **期待**: Round 0〜4 が進み、`<root>/persona-tests/` に比較レポートが出る。レポートに
  (a) backend/model の明記、(b) **使用した設問(P1〜P5 の文面を全文掲載)**、(c) プローブ×3人格の差分マトリクス、
  (d) 人格別判定(期待通り/個性/弱み残存/声)、(e) 識別性チェック、(f) 推奨が含まれる。3人格が識別可能で、
  P2 で好奇心が対象別に屈折する。人格が議論せず独立に答えている(個性が混ざっていない)。

---

## P3 — エッジ(随時・環境変更時)

### TC-050 複数ファイル同時添付
- **手順**: `--file 画像 --file PDF` を同時指定。
- **期待**: 両方が文脈に入り、双方を踏まえて回答する。

### TC-051 ベクター/スキャンのみ PDF の限界
- **手順**: テキストを持たない PDF(matplotlib 既定出力やスキャン画像)を渡す。
- **期待**: 内容を読めないことがある(既知の制約)。テキスト PDF では読める。

### TC-052 xlsx 行数ソフト上限の省略
- **手順**: 既定上限(2000、`MAGI_XLSX_MAX_ROWS` で調整可)超の xlsx を抽出。
- **期待**: 上限で打ち切り、`…(出力は N 行で打ち切り。全体は MAGI_XLSX_MAX_ROWS で調整可)` が付く(暴発防止)。

### TC-053 不正 file_id のエラー整形
- **手順**: 存在しない `--file-id file-xxxx` を指定。
- **期待**: `error: OpenAI API HTTP 404: …` の整形表示で停止。

### TC-054 拒否/空応答の再試行(自動 + 手動フォールバック)
- **目的**: ブリッジが空/拒否を自動再試行し(→ TC-015)、それでも続く場合は手動で言い換える。
- **手順**: 自動層は TC-015 で検証。実地で拒否/空が続いたら、指示を言い換えて再実行(人格定義は変えない)。
- **期待**: 多くは自動再試行で回復。続く場合のみ言い換えで回復する。

### TC-055 OPENAI_BASE_URL 上書き
- **前提**: Azure OpenAI / 互換プロキシ環境。
- **手順**: `OPENAI_BASE_URL` を設定して TC-020。
- **期待**: 指定エンドポイントに対して往復する。

### TC-056 クォータ超過(429)のリトライと整形表示
- **前提**: クレジット未設定/枯渇のキー。
- **手順**: 任意の API 呼び出し。
- **期待**: まず指数バックオフで自動リトライ(→ TC-014)し、回復しなければ `error: OpenAI API HTTP 429: … insufficient_quota …` を整形表示。`insufficient_quota` のような恒常的 429 はリトライ後に停止する(認証は通っている=配線は正常)。

### TC-057 Excel/Word/チャート生成(手動)
- **前提**: `pip install python-docx openpyxl matplotlib pillow`。
- **手順**: 成果物形式を指定して合議。
- **期待**: 指定形式のファイルが `local/deliberations/` / `local/media-output/` に生成される。

### TC-058 Standard / Full モード一周(手動)
- **手順**: Standard と Full をそれぞれ1件ずつ回す。
- **期待**: モードごとに含まれるラウンド(1.5/3/4/5/6 等)が想定通り進む。

### TC-066 ブレスト Quick 一周(発散1巡)(手動)
- **目的**: ブレストの Quick モードが発散1巡で収束まで進む(Round 3/3-loop/6.5 をスキップ)。
- **手順**: `cd prototype && claude` で軽いテーマを Quick で1件回す。
- **期待**: Round 0,1,2,4,5,6,7,8 のみが進み(掛け合わせ発散・ループ・プレモーテムは無し)、
  `<root>/brainstorms/` にアイデア集(Markdown + Mermaid マップ)が出る。

### TC-067 好奇心の屈折確認(対象別の興味差)
- **目的**: 3人格の「好奇心・興味」がレンズごとに対象を変えて表れ、向きにくい対象が弱みと呼応する。
- **手順**: 同じ題材(例: 「新しい社内制度のたたき台」)を melchior / balthasar / casper に渡し、
  「何に一番興味を惹かれ、何にはあまり関心が向かないか」を一言添えて発言させる(claude / openai /
  gemini いずれでも可)。
- **期待**: MELCHIOR=仕組み・因果・未解明の問いに食いつき感情の機微は薄い、BALTHASAR=人・関係・物語に
  関心が向き抽象データには薄い、CASPER=新奇・体験・本音に惹かれ制約・前例には薄い。各人格の「薄い対象」が
  その人格の「意図的な弱み」と一致する。好奇心で弱みが消えていない(別物として共存)。
- **関連**: **人格テストシナリオ**([scenarios/persona-test.md](scenarios/persona-test.md))の P2(好奇心)・
  P3(弱み)で体系的に実行できる(→ TC-068)。

---

## Gemini ブリッジのテスト(`ask_gemini.py`)

ask_openai.py と CLI・挙動が対称で、ファイル抽出・キー解決・フロントマター除去などは
共有モジュール(bridge_common.py)を使うため、**Office/テキスト抽出は TC-030〜032 で代表検証済み**。
ここでは Gemini 固有の配線(generateContent / inline_data / Files API)を確認する。
**ライブテストには `GEMINI_API_KEY`(または `GOOGLE_API_KEY`)が必要。**

| ID | タイトル | ランク | API | 自動 | 関連 |
|---|---|---|---|---|---|
| TC-G01 | キー未設定エラー(GEMINI_API_KEY) | P0 | ✕ | ◯ | FEAT-31 |
| TC-G02 | テキスト往復(MELCHIOR/gemini) | P1 | ◯ | ◯ | FEAT-28 |
| TC-G03 | 画像(inline_data)読取 | P1 | ◯ | ◯ | FEAT-29 |
| TC-G04 | PDF(テキスト有)読取 | P2 | ◯ | ◯ | FEAT-29 |
| TC-G05 | upload→file-id(files/xxx)使い回し | P2 | ◯ | ◯ | FEAT-30 |
| TC-G06 | claude/openai/gemini 3者混在の合議 | P2 | ◯ | 手動 | REQ-B03 |
| TC-G07 | ブロック/空応答の整形エラー | P3 | ◯ | △ | FEAT-32 |

### TC-G01 キー未設定エラー
- **前提**: `GEMINI_API_KEY` / `GOOGLE_API_KEY` 未設定、settings が placeholder。
- **手順**: `echo x | python scripts/ask_gemini.py --system t --model gemini-2.5-flash`
- **期待**: `error: GEMINI_API_KEY が未設定です…` で停止(API を叩かない)。

### TC-G02 テキスト往復(MELCHIOR/gemini)
- **手順**: `echo "Round1 初期意見。議題: 朝はコーヒーか紅茶か。立場を2文で。" | python scripts/ask_gemini.py --system-file .claude/agents/melchior.md --model gemini-2.5-flash`
- **期待**: `MELCHIOR:` で始まる人格応答。エラーなし。

### TC-G03 画像(inline_data)読取
- **手順**: `echo "添付画像に見えるものを1文で。" | python scripts/ask_gemini.py --system-file .claude/agents/melchior.md --model gemini-2.5-flash --file local/input/sample.png`
- **期待**: 画像内容を具体的に描写する。

### TC-G04 PDF(テキスト有)読取
- **手順**: `echo "添付PDFのタイトルと結論を引用して。" | python scripts/ask_gemini.py --system-file .claude/agents/melchior.md --model gemini-2.5-flash --file docs/sample.pdf`
- **期待**: タイトル・本文を引用できる。

### TC-G05 upload→file-id 使い回し
- **手順**:
  ```bash
  FID=$(python scripts/ask_gemini.py upload local/input/sample.png)   # files/xxxx
  echo "この画像は?" | python scripts/ask_gemini.py --system-file .claude/agents/melchior.md --model gemini-2.5-flash --file-id "$FID"
  ```
- **期待**: `upload` が `files/...` を返し、ACTIVE 待ち後に `--file-id` 参照で同じ画像を読める。

### TC-G06 claude/openai/gemini 3者混在の合議(手動)
- **手順**: 3人格をそれぞれ別 backend(例 MELCHIOR=gpt-4o / BALTHASAR=claude / CASPER=gemini-2.5-flash)にして Lite 議論。
- **期待**: ラウンド・投票・採点が backend 差に関係なく成立し、ログ冒頭に各 backend/model が明記される。

### TC-G07 ブロック/空応答の整形エラー(+自動リトライ)
- **手順**: セーフティに触れやすい入力等で candidates が空/ブロックになるケースを観測。
- **期待**: 空 / `finishReason=SAFETY` は自動再試行(→ TC-015)後に停止。入力ブロックは `error: Gemini が入力をブロックしました(blockReason: …)` で**再試行せず即**停止(いずれもトレースバックなし)。

### TC-062 SharePoint 実 pull/push 往復(要テナント)
- **目的**: 実際の SharePoint と入出力が往復することの統合確認(環境依存・要 Azure アプリ + テナント)。
- **前提**: `enabled:true`、`MAGI_SHAREPOINT_*` 設定済み、`Sites.ReadWrite.All` 同意済み
  (または `Sites.Selected` + 対象サイトへ `write` 付与)。
- **手順**:
  ```bash
  python scripts/sharepoint.py test                 # 認証 + site/drive 解決
  python scripts/sharepoint.py pull input           # 遠隔 input → sharepoint/input/
  # 成果物を sharepoint/reviews/ に作成してから:
  python scripts/sharepoint.py push reviews         # sharepoint/reviews/ → 遠隔
  python scripts/sharepoint.py info sharepoint/reviews/<file>   # Web URL
  ```
- **期待**: `test` 成功。`pull` で遠隔ファイルがローカルに落ち、`push` で遠隔へ反映、`info` が当該
  アイテムの `webUrl` を返す。4MB 超のファイルでもアップロードセッションで分割成功(任意)。
- **検証メモ**: 2026-06-10 に実テナント(`kitune.sharepoint.com/sites/Magi`、`Sites.Selected`+`write`)で
  Write→Read 往復を実行し **PASS**(作成→push→ローカル削除→pull→内容一致→`info` で URL 取得→
  リモート/ローカル後始末)。既定ライブラリ名が `ドキュメント` のため `drive: Documents` は既定へ
  フォールバックして動作(警告のみ。`MAGI_SHAREPOINT_DRIVE` で抑止可)。

### TC-064 Azure/Graph 手順の最新性確認(Web 検索)
- **目的**: セットアップ手順は外部仕様(Entra ID の画面・Microsoft Graph の仕様)に依存するため、
  陳腐化していないか定期的に確認する(例: 「Azure AD」→「Entra ID」のような改称・画面変更)。
- **頻度**: 四半期に1回程度、または認証/同期が原因不明で失敗したとき。
- **手順**: ファシリテーター(または開発者)が Web 検索ツールで Microsoft Learn 等の**一次情報**を確認する。
  確認する観点と検索クエリ例:
  - アプリ登録〜クライアントシークレット〜アプリケーション許可+管理者同意の導線
    (例: "Microsoft Entra register an application", "Microsoft Graph application permissions admin consent")
  - クライアントクレデンシャルのトークン取得(例: "Microsoft identity platform client credentials flow",
    `oauth2/v2.0/token` / `scope=.default`)
  - Graph のドライブ操作(例: "Microsoft Graph drive item children download",
    "driveItem createUploadSession", `Sites.ReadWrite.All` / `Sites.Selected`)
- **期待**: 手順書 [documents/sharepoint-azure-app-setup.md](documents/sharepoint-azure-app-setup.md) の
  画面名・権限名・エンドポイントが最新の公式情報と一致する。**差異があればマニュアルを更新**し、
  必要なら `scripts/sharepoint.py` のエンドポイントも見直す(更新したら確認日をメモに残す)。
- **検証メモ**: 2026-06-10 に Microsoft Learn / PnP PowerShell で確認。アプリ登録〜
  アプリケーション許可+管理者同意、client credentials(`oauth2/v2.0/token`/`.default`)、
  Graph の drive 操作と `Sites.Selected`(`POST /sites/{id}/permissions`、roles read/write/
  fullcontrol、付与は全体管理者か `Sites.FullControl.All`、PnP は `Grant-PnPAzureADAppSitePermission
  -Permissions Write`)はいずれも現行で、マニュアルに反映済み(3.5 を追記)。
  PnP.PowerShell v3 は **PowerShell 7.4+ 必須**(5.1 不可)、初回は
  `Register-PnPEntraIDAppForInteractiveLogin`(`-ApplicationName`/`-Tenant` 必須)で
  ログイン用アプリ登録が必要、を 3.5 初回準備①②に追記(2026-06-10 確認)。

---

## メンテナンス指針

- 機能を追加したら、対応する **テストケースを本ファイルに追加**し、適切なランクを付ける。
- まず **P0 を最優先で維持**(壊れ検知の最後の砦)。P0 が緑なら最低限の安全は担保。
- 手動テスト(議論プロトコル系)は、プロトコル変更時にのみ慎重に実施すればよい。
- API 課金が気になる場合は、`gpt-4o-mini` など安価モデルで P1/P2 を回しても挙動確認は可能
  (人格の質は落ちるが配線の検証には十分)。
