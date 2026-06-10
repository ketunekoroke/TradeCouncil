# MAGI風 マルチエージェント・システム プロトタイプ

エヴァンゲリオンのMAGIシステムを参考にした、人格ベースのマルチエージェント・システム。
Claude Code Agent Teamsを使い、ファシリテーター(リード)が3つの人格(チームメイト)を
**用途シナリオに応じて**動かす。

- **合議(deliberation)** — 議題に3人格が議論し、合意形成する
- **資料チェック&リバイス(document-review)** — 資料を3レンズでレビューし、指摘+改訂版を出す
- **ブレスト(brainstorm)** — テーマに3レンズでアイデアを発散・評価し、マップと上位案を出す
- **人格テスト(persona-test)** — 同一依頼への出力差で人格の個性・調整を検査する(QA/回帰テスト)

人格・LLMバックエンド・メディア入力は全シナリオ共通。ファシリテーターが最初の発言から
適用シナリオを選ぶ。シナリオは `scenarios/<name>.md` に1ファイルずつ定義され、追加もできる。

## 構成

- **MELCHIOR(科学者)** — 論理・分析・客観性を司る
- **BALTHASAR(母)** — 共感・保護・関係性を司る
- **CASPER(女性)** — 直感・欲求・自己実現を司る
- **ファシリテーター** — メインClaude Codeセッション。シナリオ選択・進行・合意形成/裁定・成果物生成

## ディレクトリ

```
magi-prototype/
├── CLAUDE.md                    # ルーター(シナリオ選択+共通作法)
├── scenarios/                   # シナリオ別プロトコル
│   ├── README.md                # シナリオ一覧・ルーティング早見表
│   ├── deliberation.md          # 合議
│   ├── document-review.md       # 資料チェック&リバイス
│   ├── brainstorm.md            # ブレスト
│   └── persona-test.md          # 人格テスト
├── .claude/agents/
│   ├── melchior.md
│   ├── balthasar.md
│   └── casper.md
├── scripts/
│   ├── bridge_common.py        # ブリッジ共通処理
│   ├── ask_openai.py           # ChatGPT(OpenAI)ブリッジ
│   ├── ask_gemini.py           # Gemini(Google)ブリッジ
│   ├── sharepoint.py           # SharePoint(Graph)同期ブリッジ(任意)
│   └── list_models.py          # 使えるモデル名の一覧取得
├── sharepoint.config.json       # SharePoint 連携設定(enabled でオンオフ)
├── local/                       # 入出力 root(SharePoint 不使用時。既定)
│   ├── input/                   # 添付画像・資料(渡したいファイルをここに置く)
│   ├── media-output/            # 生成チャート(レーダー・ヒートマップ等)
│   ├── reviews/                 # 資料レビューのレポート・改訂版
│   ├── deliberations/           # 合議のログ・Word・Excel
│   ├── brainstorms/             # ブレストのアイデア集・マップ・成果物
│   └── persona-tests/           # 人格テストの比較レポート
└── sharepoint/                  # 入出力 root(SharePoint 連携時。遠隔ミラー。同一構成)
    └── input/ media-output/ reviews/ deliberations/ brainstorms/ persona-tests/
```

> 入出力は2つのマウント root に集約され、`sharepoint.config.json` の `enabled` で切り替わる
> (`local/` ↔ `sharepoint/`)。詳細は下記「3.6 SharePoint連携」と `DOCS.md`「9.5 SharePoint 連携」。

## セットアップ

### 1. Claude Codeをインストール

```bash
npm install -g @anthropic-ai/claude-code
claude --version  # 2.1.32 以上であること
```

### 2. Agent Teams機能を有効化

`~/.claude/settings.json`:

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  },
  "teammateMode": "in-process"
}
```

`teammateMode` は好みで:
- `"in-process"` — 1つのターミナル内、Shift+↓で切替
- `"tmux"` — ペイン分割(macOS推奨、議論を並列で見たい時)

### 3. Python依存ライブラリをインストール(成果物が必要な場合)

```bash
pip install python-docx openpyxl matplotlib pillow
```

日本語チャートを生成するなら、日本語フォント(Linuxなら Noto Sans CJK JP 等)も
入っていることを確認してください。

### 3.5 ChatGPT / Gemini バックエンドを使う場合(任意)

人格を `backend: openai` / `backend: gemini` で動かすときだけ必要。ブリッジ
(`scripts/ask_openai.py` / `scripts/ask_gemini.py`)は標準ライブラリだけで動く
(画像・PDF・テキスト添付は追加インストール不要。Office=docx/xlsx/pptx の添付を
使う場合のみ `pip install python-docx openpyxl python-pptx`)。APIキーは**環境変数**で渡す:

- openai: `OPENAI_API_KEY`(任意で `OPENAI_BASE_URL`)
- gemini: `GEMINI_API_KEY`(または `GOOGLE_API_KEY`、任意で `GEMINI_BASE_URL`)

**おすすめ: テンプレートをコピーして使う**(Git追跡外の `settings.local.json` に書く)

```bash
cp .claude/settings.local.json.example .claude/settings.local.json
# コピーした settings.local.json の OPENAI_API_KEY / GEMINI_API_KEY を実キーに差し替える(使う方だけ)
```

`.claude/settings.local.json.example` は Git 管理されるテンプレート。実キーを書いた
`.claude/settings.local.json` は `.gitignore` 済みなのでコミットされない。Claude Code が
ツール実行時の環境変数に自動で渡す。

その場限りでよいなら環境変数を直接設定してもよい:

```bash
# macOS / Linux
export OPENAI_API_KEY="sk-..."
# Windows PowerShell(セッション一時) / 永続化は setx
$env:OPENAI_API_KEY = "sk-..."
```

全人格を Claude のままにするなら、この設定は不要。**APIキーは絶対にコミットしないこと。**

### 3.6 SharePoint連携を使う場合(任意)

入出力ファイル(入力資料・成果物)を SharePoint で共有したいときだけ必要。同期ブリッジ
`scripts/sharepoint.py` は標準ライブラリだけで動く(追加 pip 不要)。**使わない場合は何もしなくてよい**
(既定 `enabled:false` で `local/` を使い、従来どおり動く)。

**(1) Azure でアプリを登録**(管理者作業):

- Azure Portal → 「アプリの登録」で新規アプリを作成し、**テナント ID / クライアント ID** を控える
- 「証明書とシークレット」で**クライアントシークレット**を発行して控える
- 「API のアクセス許可」→ Microsoft Graph → **アプリケーションの許可** `Sites.ReadWrite.All` を追加し、
  **管理者の同意を付与**(委任ではなくアプリケーション許可)

> 画面操作つきの詳しい手順は
> [documents/sharepoint-azure-app-setup.md](documents/sharepoint-azure-app-setup.md) を参照。

**(2) シークレットと設定を `settings.local.json` に書く**(API キーと同じ作法・Git 追跡外)。
`enabled` / `site_url` / `drive` / `root` はここに書くと `sharepoint.config.json` より優先される
(env → config)。**オンオフやテナント URL をコミットしたくない場合はこちらに置くのが便利**:

```json
{
  "env": {
    "MAGI_SHAREPOINT_ENABLED": "true",
    "MAGI_SHAREPOINT_SITE_URL": "https://<tenant>.sharepoint.com/sites/<site>",
    "MAGI_SHAREPOINT_TENANT_ID": "<tenant-id>",
    "MAGI_SHAREPOINT_CLIENT_ID": "<client-id>",
    "MAGI_SHAREPOINT_CLIENT_SECRET": "<client-secret>"
  }
}
```

**(3) `folders` 構造などは `sharepoint.config.json`(追跡)で管理**。オンオフを config 側で
切り替えたい場合は `"enabled": true` にしてもよい(`settings.local.json` の env があればそちらが優先):

```json
{ "enabled": false, "site_url": "https://<tenant>.sharepoint.com/sites/<site>",
  "drive": "Documents", "root": "MAGI", "folders": { ... } }
```

**(4) 動作確認**:

```bash
python scripts/sharepoint.py status   # 設定とアクティブ root を表示(通信なし)
python scripts/sharepoint.py test     # 認証 + サイト/ドライブ解決を検証
python scripts/sharepoint.py pull input   # 遠隔の入力を sharepoint/input/ に取得
```

有効化すると入出力 root が `sharepoint/` に切り替わる。ファシリテーターはシナリオ開始時に
`pull`、成果物提示時に `push` を行い、ローカルパスと SharePoint URL の両方を提示する
(詳細は `DOCS.md`「9.5 SharePoint 連携」/ `CLAUDE.md`「SharePoint 連携」)。
**シークレットは絶対にコミットしないこと。**

### 4. プロジェクトディレクトリで起動

```bash
cd magi-prototype
claude
```

## 使い方

ファシリテーターが最初の発言からシナリオを選ぶ。明示したい場合はシナリオ名を伝えてもよい。

### 合議シナリオ(テキストのみの議題)

```
これからMAGI合議を始める。
議題: 「30代後半で転職してスタートアップに行くべきか、大企業に残るべきか」

melchior, balthasar, casper の3人格をチームメイトとして召喚し、
合議シナリオ(scenarios/deliberation.md)の議論プロトコルに従って進めてくれ。
成果物形式は Excel + ビジュアル(レーダーチャート)を希望。
```

### 資料チェック&リバイス シナリオ

事前に `local/input/` に資料を置いてから(SharePoint 連携時は `sharepoint/input/`):

```
この資料をレビューして改訂版も作ってほしい。
対象: local/input/提案書.docx
対象読者は社内の役員、目的は予算承認。トーンは硬めで。

melchior, balthasar, casper の3レンズで Standard 深度のレビューを行い、
資料チェック&リバイス シナリオ(scenarios/document-review.md)に従って、
指摘レポートと改訂版(docx)を local/reviews/ に出してくれ。
```

3人格が同じ資料を独立にレビューし、指摘の衝突をファシリテーターが裁定して、
指摘レポート + 改訂版ドキュメントを生成する。

### ブレストシナリオ

```
新しい社内勉強会の企画をブレストしたい。
テーマ: 「エンジニアの学びが続く社内勉強会のネタ」
制約: 月1回・1時間・登壇者は持ち回り。

melchior, balthasar, casper の3レンズで Standard モードのブレストを行い、
ブレストシナリオ(scenarios/brainstorm.md)に従って、アイデアマップ・評価・
上位案を local/brainstorms/ に出してくれ。
```

3レンズが構造的に異なるアイデアを発散し、ファシリテーターがマップ化・評価して、
上位案を3つの価値で磨く。評価が割れた「尖り案」も別枠で残る。

### 人格テストシナリオ(調整後の確認)

人格定義を編集したあと、実挙動がどう変わったかを確認したいとき:

```
人格テストを Standard で実行してほしい。
さっき CASPER に「好奇心・興味」の節を足したので、新奇への食いつきが
強まっているか、3人格がちゃんと違う出力になるかを見たい。

melchior, balthasar, casper に固定プローブ(判断/好奇心/弱み/ドメイン非依存)を
同じ文面で独立に投げ、persona-test シナリオ(scenarios/persona-test.md)に従って、
差分マトリクスと人格別判定を local/persona-tests/ に出してくれ。
```

同じ依頼を全人格に独立に投げ(議論させない)、出力差をマトリクス化して、各人格の
個性・好奇心の向き・弱みが期待どおり出るかを判定する。2人格が似すぎていれば警告が出る。
**人格を調整するたびの回帰テスト**として使える。

### 画像を添付するパターン(合議)

事前に `local/input/` に画像を置いてから(SharePoint 連携時は `sharepoint/input/`):

```
これからMAGI合議を始める。
議題: 「local/input/house_photo.jpg の物件を購入すべきか」
予算と立地、家族構成は前回伝えた条件。

melchior, balthasar, casper を召喚し、各人格が独立に画像を見て
判断を下すように進行してくれ。成果物は Word + ヒートマップを希望。
```

各人格が**独立に**画像を見るのが重要なポイント。同じ写真でも、
科学者の目・母の目・個としての目で見えるものが違うのがMAGIの面白さ。

## 操作のコツ

- **`Shift+↓`** — チームメイト間を切り替え(in-processモード)
- **`Ctrl+T`** — タスクリスト表示
- **直接話しかける** — 特定の人格に追加質問もできる
- 議論が長引きそうなら `Wait for your teammates to complete their tasks before proceeding`
- 議論を終えたら `Clean up the team` で次回のためにリソース解放

## カスタマイズ

- **人格の調整**: `.claude/agents/*.md` を編集または新規追加
- **人格ごとにClaude/ChatGPT/Geminiを選ぶ**: 各人格の frontmatter で `backend`(claude | openai | gemini)と
  `model`(opus/sonnet/haiku / gpt-4o 等 / gemini-2.5-flash 等)を指定。混在可。`openai` は `OPENAI_API_KEY`、
  `gemini` は `GEMINI_API_KEY` が必要。**指定できる値の一覧は `DOCS.md`「backend と model の指定一覧」**
- **シナリオを追加する**: `scenarios/<name>.md` を新規作成(共通作法は `CLAUDE.md` を参照)
- **シナリオ内のプロトコル変更**: `scenarios/<name>.md` のRound定義を編集
- **成果物テンプレ変更**: `scenarios/<name>.md` の「成果物」セクションを編集
- **ファシリテーターに個性を与える**: `CLAUDE.md` の冒頭に人格セクション追加

## Gitでのバージョン管理

このプロジェクトには `.gitignore` と `.gitattributes` が同梱されており、
そのままGit管理を始められます。

### 初期化

```bash
cd magi-prototype
git init -b main
git add .
git commit -m "Initial commit: MAGI prototype skeleton"
```

### 何が追跡され、何が無視されるか

| 種類 | 追跡対象 | 理由 |
|---|---|---|
| `CLAUDE.md` | ✓ | プロジェクトの設定(ルーター) |
| `scenarios/*.md` | ✓ | シナリオ別プロトコル(プロジェクトの資産) |
| `.claude/agents/*.md` | ✓ | 人格定義(プロジェクトの資産) |
| `README.md` | ✓ | ドキュメント |
| `.gitignore` / `.gitattributes` | ✓ | Git設定 |
| `sharepoint.config.json` | ✓ | 連携設定(非機密。site URL 等) |
| `local/**`, `sharepoint/**`(入出力ファイル) | ✗ | 元資料・成果物・個人情報を含む可能性 |
| `.claude/settings.local.json` | ✗ | ユーザー固有のローカル設定・シークレット |
| `__pycache__/`, `venv/` 等 | ✗ | Python一般 |

### 議論ログを共有したい場合

特定の議論ログだけGit追跡したいときは強制追加:

```bash
git add -f local/deliberations/20260507-1200-career-decision.md
git commit -m "Add career deliberation log"
```

または、入出力全体を追跡したいなら `.gitignore` の `local/**` / `sharepoint/**` の
除外行を調整する(個人情報の混入に注意)。

### おすすめのコミット粒度

- **人格を調整したとき**: `feat(personas): refine MELCHIOR's argumentation style`
- **議論プロトコルを変えたとき**: `feat(protocol): add steelman round to Standard mode`
- **新しい人格を追加したとき**: `feat(personas): add 4th persona OBSERVER`
- **CLAUDE.mdの構成変更**: `refactor(claude.md): reorganize round descriptions`

### リモートに公開する場合の注意

- **公開リポジトリにする前に必ず `local/` / `sharepoint/` の内容を確認** —
  `.gitignore` で守られているはずだが、`git add -f` で強制追加した履歴が残っていないかチェック
- **シークレット系も再確認** — `.claude/settings.local.json`(API キー・`MAGI_SHAREPOINT_*`)、`.env` 等
- 公開する場合はライセンス(MIT等)の追加も検討

### 履歴から個人情報を削除したくなった場合

うっかり議論ログをコミットしてしまった等の場合:

```bash
# 履歴から完全削除(リスキーなので慎重に)
git filter-repo --path local/deliberations/sensitive-file.md --invert-paths
```

(`git-filter-repo` の事前インストールが必要)

## 既知の制約

- Agent Teamsは実験的機能。`/resume` でセッション復元時にチームメイトは再生成が必要
- トークン消費は通常セッションの数倍(各人格が独立コンテキストを持つため)
- 1セッションに1チームのみ
- 画像生成(写真・イラスト)は外部APIが必要(MCP経由でDALL-E等を繋ぐ)
- Split-paneモードは tmux または iTerm2 が必要
