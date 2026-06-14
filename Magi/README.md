# Magi — 汎用マルチエージェント・シナリオ基盤

価値観で分かれた MAGI 3人格(**melchior**=論理・分析 / **balthasar**=共感・保護 /
**casper**=直感・欲求)で **合議・資料レビュー・ブレスト・人格テスト**を行う汎用エージェント基盤。
モノレポの1プロジェクト([../README.md](../README.md) / ADR-0011)。

> 設計思想: 人格は専門分野ではなく**価値観・判断軸**で分ける。各人格の**意図的な弱み**は
> 消さない(補完と対立が面白さの源)。深い仕様は [docs/07_シナリオ・人格基盤.md](docs/07_シナリオ・人格基盤.md)。

## クイックスタート

```powershell
cd Magi
claude
```
起動して、シナリオを起こす発話をするだけ。OpenAI / Gemini 人格を使う場合はルート共有 `.env` に
`OPENAI_API_KEY` / `GEMINI_API_KEY` を設定(セットアップ詳細は [docs/07 §7](docs/07_シナリオ・人格基盤.md))。
ブリッジは共通層 [../shared/](../shared/) にあり `python ../shared/ask_openai.py ...` で呼ぶ。

## 使い方(シナリオ別の発話例)

ファシリテーターが最初の発言からシナリオを選ぶ(明示したいときはシナリオ名を伝えてよい)。

### 合議(deliberation) — 賛否を聞いて考えを整理する
```
これから合議を始める。議題:「30代後半で転職してスタートアップに行くべきか、大企業に残るべきか」
melchior, balthasar, casper の3人格で議論し、確信度を加味して合意形成してほしい。
成果物は Excel + レーダーチャートを希望。
```

### 資料チェック&リバイス(document-review) — 添削して改訂版も出す
事前に `workspace/input/` に資料を置く:
```
この資料をレビューして改訂版も作ってほしい。対象: workspace/input/提案書.docx
対象読者は社内役員、目的は予算承認、トーンは硬め。3レンズで Standard 深度のレビューを行い、
指摘レポートと改訂版(docx)を workspace/reviews/ に出してほしい。
```

### ブレスト(brainstorm) — アイデアを発散・評価する
```
社内勉強会の企画をブレストしたい。テーマ:「エンジニアの学びが続く社内勉強会のネタ」
制約: 月1回・1時間・登壇者は持ち回り。3レンズで Standard モードでアイデアマップ・評価・
上位案を workspace/brainstorms/ に出してほしい。
```

### 人格テスト(persona-test) — 人格を調整した後の回帰確認
```
人格テストを Standard で実行してほしい。CASPER に「好奇心・興味」の節を足したので、
新奇への食いつきが強まったか、3人格がちゃんと違う出力になるかを見たい。
固定プローブを同じ文面で独立投下し、差分マトリクスと人格別判定を workspace/persona-tests/ に。
```

### 画像を添付する(合議)
`workspace/input/` に画像を置いてから議題で参照する。**各人格が独立に画像を見る**のがポイント
(科学者の目・母の目・個としての目で見えるものが違う)。

## 操作のコツ

- 特定の人格に直接追加質問もできる
- 議論が長引きそうなら「チームメイトの完了を待ってから進めて」と指示
- openai/gemini 人格は呼び出しごとに記憶がリセットされる(文脈は毎ラウンド渡す or `--history`)。詳細は [../shared/README.md](../shared/README.md)
- どの人格がどの backend/model で動いたかは成果物の冒頭に明記される(再現性)

## カスタマイズ

- **人格の調整**: `.claude/agents/<name>.md` を編集 or 新規追加
- **backend を人格ごとに選ぶ**: frontmatter の `backend`(claude|openai|gemini)/ `model`。混在可。使えるモデルは `python ../shared/list_models.py`
- **シナリオを追加 / プロトコル変更**: `scenarios/<name>.md`(共通作法は [CLAUDE.md](CLAUDE.md) を参照)
- 詳しい手順は [DEVELOPMENT.md](DEVELOPMENT.md)

## ドキュメントマップ

| 知りたいこと | 読むファイル |
|---|---|
| 進め方・人格・バックエンド・作法 | [CLAUDE.md](CLAUDE.md) |
| 深い仕様(人格哲学・シナリオ詳細・ブリッジ内部) | [docs/07_シナリオ・人格基盤.md](docs/07_シナリオ・人格基盤.md) |
| 開発・編集の手順 | [DEVELOPMENT.md](DEVELOPMENT.md) |
| 運用ガイドの概観 | [DOCS.md](DOCS.md) |
| 要件・機能・テスト | [REQUIREMENTS.md](REQUIREMENTS.md) / [FEATURES.md](FEATURES.md) / [TESTCASES.md](TESTCASES.md) |
| 詳細テストケース | [docs/testing/scenario-bridge-testcases.md](docs/testing/scenario-bridge-testcases.md) |

## 構成

```
Magi/
├── CLAUDE.md            ルーター・人格・バックエンド・作法
├── .claude/agents/      melchior / balthasar / casper
├── scenarios/           deliberation / document-review / brainstorm / persona-test
├── docs/                07_シナリオ・人格基盤.md / testing/
├── workspace/           シナリオ入出力(SharePoint 同期対象。env_prefix=MAGI)
└── README / DEVELOPMENT / DOCS / REQUIREMENTS / FEATURES / TESTCASES / BACKLOG.md
```

> council(意思決定会議)と売買は別プロジェクト → [../TradeCouncil/](../TradeCouncil/README.md)。
> 共通ツール(LLMブリッジ・SharePoint・office・git フック)は [../shared/](../shared/README.md)。
