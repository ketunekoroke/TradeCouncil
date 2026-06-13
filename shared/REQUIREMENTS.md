# 要件一覧 — shared(共通ツール層: LLMブリッジ・ファイル入力・SharePoint・非機能)

Magi / TradeCouncil の双方が利用する共通基盤の要件。**一次資料は
[Magi/docs/07_シナリオ・人格基盤.md](../Magi/docs/07_シナリオ・人格基盤.md)**(ブリッジ内部仕様)。
実装は [README.md](README.md)・[FEATURES.md](FEATURES.md)、検証は [TESTCASES.md](TESTCASES.md)。

## LB. LLM バックエンド選択

| ID | 要件 | 優先度 | 状態 |
|---|---|---|---|
| REQ-LB01 | 各人格ごとに Claude / ChatGPT(OpenAI)/ Gemini を frontmatter(`backend`/`model`)で選べる | 必須 | 実装済 |
| REQ-LB02 | `backend: claude` は通常召喚、`openai`/`gemini` は各ブリッジ経由で動かす | 必須 | 実装済 |
| REQ-LB03 | claude / openai / gemini 人格は混在でき、議論プロトコル(ラウンド/投票/採点)は不変 | 必須 | 仕様 |
| REQ-LB04 | openai/gemini 人格はステートレスなので、必要文脈を毎ラウンド渡して継続性を保つ(stdin/`--input` への織り込み、または `--history` での多ターン会話履歴) | 必須 | 実装済 |
| REQ-LB05 | openai/gemini 人格の拒否/空応答時は自動で再試行する(既定1回、`MAGI_GEN_MAX_RETRIES`)。続く場合はファシリテーターが人格定義を変えず指示を言い換えて再実行 | 推奨 | 実装済 |
| REQ-LB06 | プロバイダ間で共通する処理(キー解決/抽出/HTTP等)は共有モジュール(shared/bridge_common.py)に集約する | 推奨 | 実装済 |
| REQ-LB07 | 過負荷/モデル不在(429/5xx/404・model_not_found)で primary が失敗した場合、指定があれば代替モデルへ1回フォールバックできる(実際に使ったモデルを成果物に明記) | 推奨 | 実装済 |

## FI. ファイル入力

| ID | 要件 | 優先度 | 状態 |
|---|---|---|---|
| REQ-FI01 | 画像(jpg/png/gif/webp)を全 backend でネイティブに扱える | 必須 | 実装済 |
| REQ-FI02 | PDF を openai/gemini 人格でネイティブに扱える(テキストを持つ PDF) | 必須 | 実装済 |
| REQ-FI03 | Office(docx/xlsx/pptx)を準ネイティブに扱える(ローカルでテキスト抽出。docx は段落と表をドキュメント順に保つ) | 推奨 | 実装済 |
| REQ-FI04 | テキストファイル(txt/md/csv/json 等)を本文として注入できる | 推奨 | 実装済 |
| REQ-FI05 | 同一ファイルを全人格に等しく渡せる(claude/openai/gemini で挙動が対称) | 必須 | 実装済 |
| REQ-FI06 | 同じ画像/PDF を多ラウンドで使う場合、アップロードして file_id を使い回せる | 推奨 | 実装済 |

## SP. SharePoint 連携(任意)

| ID | 要件 | 優先度 | 状態 |
|---|---|---|---|
| REQ-SP01 | `workspace/` を SharePoint ドキュメントライブラリと同期できる(shared/sharepoint.py / Microsoft Graph) | 任意 | 実装済 |
| REQ-SP02 | `enabled` は**同期通信の有無のみ**を制御する(作業場所は常に workspace/ — ADR-0009)。設定は env(.env)→ sharepoint.config.json の順で解決 | 任意 | 実装済 |
| REQ-SP03 | `sync` は双方向・追加型・更新時刻の新しい方優先・**削除非伝播**・mtime 整合(再実行で skip) | 任意 | 実装済 |
| REQ-SP04 | 認証はアプリ(クライアントシークレット)。`MAGI_SHAREPOINT_*` を .env で解決しコミットしない | 任意 | 実装済 |
| REQ-SP05 | `sync` を主とし、`pull`/`push` は選択的リカバリ用に存続。`info` で SharePoint URL を提示できる | 任意 | 実装済 |
| REQ-SP06 | SharePoint 連携も標準ライブラリだけで動く(HTTP は bridge_common 経由、新規 pip 依存なし) | 推奨 | 実装済 |
| REQ-SP07 | Azure アプリ登録のセットアップ手順を docs/setup/ にマニュアル化し、記載内容(env 名・必要権限・コマンド)をコード/設定と一致させる | 推奨 | 実装済 |
| REQ-SP08 | セットアップ手順は外部仕様(Entra ID 画面・Microsoft Graph)に依存するため、定期的に最新の公式情報を確認し、変更があればマニュアルを更新する | 任意 | 仕様 |
| REQ-SP09 | 各プロジェクトの `docs/` と管理表を SharePoint `<Project>/Docs/` へ **git main から一方向ミラー**できる(`sharepoint.py mirror --project <p>`)。内容は作業ツリーでなく main コミットから読む(未コミット編集は流れない — ADR-0010) | 任意 | 実装済 |
| REQ-SP10 | docs ミラーは**完全ミラー**: main からの削除・リネームを反映する(workspace 双方向同期の削除非伝播とは別方針)。初回/`--full` は全 push + 遠隔余剰の削除(prune) | 任意 | 実装済 |
| REQ-SP11 | ミラーは差分ベース(前回ミラー済み sha を `<project>/var/` の状態ファイルに記録)。全アクション成功時のみ状態を進め、失敗時は次回実行が自動的に追いつく。main 不変なら通信しない | 任意 | 実装済 |
| REQ-SP12 | ミラーは git フック(post-commit=main 時のみ / pre-push)で**全プロジェクトを走査**して自動実行され、**fail-open**(失敗は warn のみ・コミット/プッシュを止めない)。enabled=false 時は何もしない | 任意 | 実装済 |

## NF. ブリッジ非機能

| ID | 要件 | 優先度 | 状態 |
|---|---|---|---|
| REQ-NF01 | ブリッジは標準ライブラリで動く(Office 抽出時のみ追加ライブラリを関数内 lazy import) | 推奨 | 実装済 |
| REQ-NF02 | クロス OS(Windows/macOS/Linux)で動作し、日本語を UTF-8 で入出力する(stdin 入力・stdout 出力とも) | 必須 | 実装済 |
| REQ-NF03 | エラーはトレースバックでなく整形メッセージで返す | 推奨 | 実装済 |
| REQ-NF04 | トークン消費が通常の数倍になる点をドキュメントで明示する | 任意 | 実装済 |
| REQ-NF05 | 一過性の HTTP エラー(429 / 5xx / 接続タイムアウト)は指数バックオフ + ジッタで自動リトライする(`Retry-After` 尊重、回数・タイムアウトは `MAGI_HTTP_*` で調整可) | 推奨 | 実装済 |

## SH. 共有層の構造(モノレポ — ADR-0011)

| ID | 要件 | 優先度 | 状態 |
|---|---|---|---|
| REQ-SH01 | shared は **path 起動**(`python shared/<tool>.py`)と `from shared import ...` の双方で使え、重い依存を持たない | 必須 | 実装済 |
| REQ-SH02 | シークレットは 環境変数 → リポジトリルート共有 `.env` → `.claude/settings.local.json` の3段で解決(placeholder/空は未設定扱い)。テンプレート(`.env.example`)のみ git 追跡する | 必須 | 実装済 |
| REQ-SH03 | git ライフサイクルフック(pre-commit 秘密/ポリシー検査・post-commit/pre-push の docs ミラー)はリポジトリ単位で shared/hooks に集約し、`tc hooks install` が3種を導入する | 必須 | 実装済 |
