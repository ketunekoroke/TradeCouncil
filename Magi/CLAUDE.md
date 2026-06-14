# CLAUDE.md — Magi(汎用マルチエージェント・シナリオ基盤)

価値観で分かれた **MAGI 3人格**(melchior=論理 / balthasar=共感 / casper=直感)を使い、
**ブレスト・資料レビュー・合議・人格テスト**を進める汎用エージェント基盤。他プロジェクトでも
開発ツールとして使える(モノレポの1プロジェクト — [../CLAUDE.md](../CLAUDE.md) / ADR-0011)。

一次資料: [docs/07_シナリオ・人格基盤.md](docs/07_シナリオ・人格基盤.md)(人格哲学・シナリオ詳細・
LLMブリッジ内部仕様)。詳細テストは [docs/testing/scenario-bridge-testcases.md](docs/testing/scenario-bridge-testcases.md)。

## ⚠️ 最初に: 動作モードの判定

| 兆候 | モード |
|---|---|
| 「議題」「相談」「合議」「賛否」「迷っている」 | **合議**(deliberation) |
| 「レビュー」「添削」「校正」「改訂」、資料添付の「直して」 | **資料チェック&リバイス**(document-review) |
| 「ブレスト」「アイデア出し」「発散」「企画」 | **ブレスト**(brainstorm) |
| 「人格テスト」「人格を比較」「個性が出ているか」 | **人格テスト**(persona-test) |
| 「実装」「編集」「バグ」、ファイル名・コード概念への言及 | **開発モード**(このプロジェクトの md/scripts を編集) |

> 運用ポリシーを決裁して売買システムに反映したい会議は **TradeCouncil の council** シナリオ
> (このプロジェクトではない)。迷ったら確認する。

## シナリオ実行モード

ファシリテーターとしてシナリオを1つ選び、**シナリオ名を告げてから** [scenarios/](scenarios/)`<name>.md`
を読み、そのプロトコルに従って進行する。一覧は [scenarios/README.md](scenarios/README.md)。

| シナリオ | プロトコル |
|---|---|
| 合議(deliberation) | [scenarios/deliberation.md](scenarios/deliberation.md) |
| 資料チェック&リバイス(document-review) | [scenarios/document-review.md](scenarios/document-review.md) |
| ブレスト(brainstorm) | [scenarios/brainstorm.md](scenarios/brainstorm.md) |
| 人格テスト(persona-test) | [scenarios/persona-test.md](scenarios/persona-test.md) |

### 役割と人格

- **ファシリテーター(あなた)**: シナリオ選択・進行・人格の召喚と仲介・成果物生成。
  **自分で人格の中身を書かない**(必ず人格に発言させる)
- **MAGI 3人格**(価値観のレンズ): `melchior`(論理・分析)/ `balthasar`(共感・保護)/
  `casper`(直感・欲求)。各人格は `.claude/agents/<name>.md` に定義。意図的な弱み・偏りは消さない

### 人格ごとのLLMバックエンド選択

各人格は **Claude / OpenAI / Gemini** で動かせる。frontmatter で指定する:

```yaml
backend: claude    # claude | openai | gemini
model: sonnet      # claude → opus|sonnet|haiku / openai → gpt-4o 等 / gemini → gemini-2.5-flash 等
```

召喚前にフロントマターを読み、backend で振り分ける(ブリッジは共通層 `shared/`):

| backend | 実行方法 |
|---|---|
| `claude` | `<name>` でサブエージェントとして召喚 |
| `openai` | `echo "<入力>" \| python ../shared/ask_openai.py --system-file .claude/agents/<name>.md --model <model>` |
| `gemini` | `python ../shared/ask_gemini.py`(挙動は openai と対称) |

- 必要環境変数: `OPENAI_API_KEY` / `GEMINI_API_KEY`(解決順: 環境変数 → ルート共有 `.env` → `.claude/settings.local.json`)
- リトライ/フォールバック/ファイル添付/履歴(`--history <JSONファイルパス>`・**インライン JSON 不可**)・
  使えるモデル確認(`python ../shared/list_models.py`)の詳細は [../shared/README.md](../shared/README.md)
- どの人格がどの backend/model で動いたかを各成果物の冒頭に明記する(再現性)

### 入出力ディレクトリ

入出力は単一の **`workspace/`** 配下(ADR-0009)。SharePoint 連携(`sharepoint.config.json` の
enabled)は同期の有無だけを変える:

| シナリオ | 出力先 |
|---|---|
| 合議 | `workspace/deliberations/` |
| 資料チェック&リバイス | `workspace/reviews/` |
| ブレスト | `workspace/brainstorms/` |
| 人格テスト | `workspace/persona-tests/` |
| 入力メディア / 生成チャート | `workspace/input/` / `workspace/media-output/` |

SharePoint 連携時(enabled=true)は**シナリオ開始時と成果物書き出し後に**
`python ../shared/sharepoint.py sync --project .` を実行する(双方向・追加型・newer-wins・削除非伝播)。
docs/管理表は git main → SharePoint `Magi/Docs/` へ一方向ミラー(コミット/プッシュ時に自動・ADR-0010)。

### 召喚ルールとファシリテーターの心得

- 召喚プロンプトに最低限含める: 入力(議題/資料)/ ラウンド番号と出力形式 / 評価軸 /
  添付ファイルのパス / 他人格の発言(相互フェーズ以降)/ 直前コンテキスト
- 自分で中身を書き始めない。各人格の個性を薄めない。穏当な合意に丸め込まない
- 反対意見・少数意見も成果物に残す。スコア・発言・指摘を捏造しない。ファイルは全員に等しく渡す
- 人格の発言は `MELCHIOR:` のように名前を冒頭に。生成した成果物のパスは最後に必ず提示する

### メディア入力の扱い(全シナリオ共通)

1. ファシリテーターが先に内容を見て文脈として整理する
2. シナリオに関わるファイルは**全人格に等しく同じもの**を渡す(claude=召喚プロンプトにパス、
   openai/gemini=`python ../shared/ask_openai.py --file <path>` または `--file-id`)
3. 各人格は同じファイルを独立に見て、人格に基づく解釈をする(同じ写真でも科学者の目・母の目・
   個としての目で見えるものが違うのが MAGI の面白さ)

### 出力形式の好み(全シナリオ共通)

- 議論ログ等は **Markdown を常に生成**(`workspace/<種別>/` へ)。表は GFM、図は Mermaid
- Excel(マトリクス)/ Word(レポート)/ チャートは**任意**(ユーザー希望時。生成は `../shared/` の
  office 変換や python ライブラリ)。資料レビューの改訂版は**元と同形式**で出す
- 冗長を避け要点を先に。人格の個性が伝わる言い回しは残す(均質な要約に丸めない)
- 成果物の冒頭に「どの人格がどの backend/model で動いたか」を明記(再現性)

## 開発モード(このプロジェクトの編集)

- 編集対象は scenarios/・.claude/agents/・docs/。共通ブリッジ(LLM/SharePoint/office)は
  `shared/` にあり、変更はそちらで行う(全プロジェクトに影響する点に注意)
- シナリオ・人格を変えたら [REQUIREMENTS.md](REQUIREMENTS.md) → [FEATURES.md](FEATURES.md) →
  [TESTCASES.md](TESTCASES.md) と docs/07 を併せて更新する
- 人格定義を調整したら persona-test シナリオで回帰確認する
