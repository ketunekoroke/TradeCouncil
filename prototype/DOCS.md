# MAGI マルチエージェント・システム — 仕様・利用ガイド

エヴァンゲリオンのMAGIシステムに着想を得た、**人格ベースのマルチエージェント・システム**の
完全ドキュメント。価値観で分かれた3つの人格を持つAIを、ファシリテーターが**用途シナリオに
応じてオーケストレーション**する。最初のシナリオは「合議」(議論して合意形成)で、第2の
シナリオとして「資料チェック&リバイス」(資料をレビューして改訂版を出す)、第3のシナリオとして
「ブレスト」(アイデアを発散・評価して企画に落とす)を備える。

> **このドキュメントの位置づけ**
> - `README.md` — クイックスタート(最短で動かすための手順)
> - `CLAUDE.md` — AIが従うルーター本体(シナリオ選択+全シナリオ共通の作法。システムプロンプト)
> - `scenarios/<name>.md` — シナリオ別プロトコル(合議 / 資料レビュー …)
> - `DOCS.md`(本書) — 設計思想・全機能・運用の包括的リファレンス

> **用語**: かつて本システムは「合議」専用だった。現在は合議も**ひとつのシナリオ**であり、
> ファシリテーターが利用モードでシナリオを選んで実行する。人格・LLMバックエンド・メディア
> 入力などは全シナリオ共通で、シナリオは「人格を何のために動かすか」だけを定義する。

---

## 目次

1. [コンセプト](#1-コンセプト)
2. [システム構成](#2-システム構成)
3. [3つの人格](#3-3つの人格)
4. [シナリオとプロトコル](#4-シナリオとプロトコル)
5. [成果物](#5-成果物)
6. [メディア入出力](#6-メディア入出力)
7. [セットアップ](#7-セットアップ)
8. [使い方](#8-使い方)
9. [ディレクトリ構成](#9-ディレクトリ構成)
9.5. [SharePoint 連携](#95-sharepoint-連携任意)
10. [Gitでのバージョン管理](#10-gitでのバージョン管理)
11. [カスタマイズ](#11-カスタマイズ)
12. [既知の制約](#12-既知の制約)
13. [今後のロードマップ](#13-今後のロードマップ)

---

## 1. コンセプト

### 何を解決するのか

単一のAIに相談すると、回答は1つの視点に収束しがちで、内部の葛藤や対立する観点が
見えない。本システムは**意図的に異なる人格を3つ用意し、それらを議論させる**ことで:

- 一つの問いに対する複数の視点を同時に得る
- 視点同士の対立点・合意点を可視化する
- 結論だけでなく「なぜその結論に至ったか」の議論過程を残す

### MAGIからの着想

原作のMAGIは、開発者の人格を「科学者」「母」「女」の3側面に分けて移植した
意思決定システムだった。本プロジェクトもこの構造を踏襲し、**専門分野ではなく
人格・価値観で3つのエージェントを分ける**ことを最大の特徴とする。

### 設計の核心

- **人格は弱みも持つ** — 各人格に苦手分野を明示的に設定し、互いに補完させる。
  これにより議論が予定調和に陥らず、生きた対話になる。
- **過程の可視化** — 各ラウンドの発言、質問、立場の変化をすべて記録する。
- **合意の質** — 安易な多数決ではなく、確信度を加味し、少数意見も最終回答に残す。

---

## 2. システム構成

### 技術基盤

本プロトタイプは **Claude Code Agent Teams**(実験的機能)上に構築される。

```
┌─────────────────────────────────────────────────┐
│  ファシリテーター(リード = メインセッション)        │
│  ・論題整理 ・進行管理 ・合意形成 ・成果物生成        │
└───────────────┬─────────────────────────────────┘
                │ 召喚 & SendMessage
    ┌───────────┼───────────┐
    ▼           ▼           ▼
┌────────┐ ┌──────────┐ ┌────────┐
│MELCHIOR│ │BALTHASAR │ │ CASPER │   ← 各々が独立した
│ 科学者 │ │   母     │ │  個人  │      コンテキストを持つ
└───┬────┘ └────┬─────┘ └───┬────┘
    │           │           │
    └───────────┴───────────┘
       人格間の直接対話(SendMessage)
                │
                ▼
        ┌──────────────────────┐
        │  永続化レイヤー(<root>/)   │  ← <root> = local/ または sharepoint/
        │ <root>/deliberations/  │  ← 議論ログ・成果物
        │ <root>/media-output/   │  ← チャート画像
        └──────────────────────┘
```

### なぜAgent Teamsか

Claude Code Agent Teamsは、リード役が複数のチームメイトを調整し、各チームメイトが
独立したコンテキストで動作して互いに直接通信できる。これは「ファシリテーター+
複数人格」という本システムの構造とそのまま対応する。公式ドキュメントにも
「複数のチームメイトに異なる仮説を調査させ、科学的議論のように互いの理論を
反証させる」という用例があり、MAGI的な合議に適している。

---

## 3. 3つの人格

各人格は `.claude/agents/*.md` にサブエージェント定義として記述される。
専門分野ではなく**価値観・判断軸**で分かれているのが特徴。

> **議題ドメイン非依存の原則(全人格共通)**: 各人格定義には「議題への向き合い方」節があり、
> 個人相談に限らず社会・政治・経済・技術・創作・**未来予測**などあらゆる議題を、人格(レンズ)を
> 保ったまま扱う。①与えられた議題を別の議題にすり替えない ②指定された出力形式・評価軸に厳密に
> 従い軸を勝手に新設しない ③個人相談用の口癖を社会・未来の議題へ機械的に持ち込まない ④渡された
> 文脈だけを根拠にしデータなき数値を捏造しない、をルール化している(特に openai・gemini の
> ステートレス実行時に起きやすい論題逸脱・定型句反復への対策)。

> **好奇心・興味という共通の駆動(全人格共通)**: 3人格は「好奇心・興味」という同じエンジンを持つが、
> **向く対象と強度がレンズごとに屈折する**(MELCHIOR=仕組み・因果 / BALTHASAR=人・関係 / CASPER=新奇・体験)。
> 何に興味を持つかの差が各レンズの個性をより際立たせ、議論を生き生きさせる(攻殻機動隊SACのタチコマ的な
> 個性化)。さらに、**ある対象に好奇心が向きにくいことが、その人格の「意図的な弱み」と呼応する**(例:
> MELCHIOR は感情の機微に、CASPER は制約に興味が薄く、それが弱みと表裏一体)。好奇心は弱みを消す装置では
> なく、個性と弱みの両方を駆動する。各人格定義の「好奇心・興味」節を参照。

### MELCHIOR(メルキオール)— 科学者

| 項目 | 内容 |
|---|---|
| 司るもの | 論理・分析・客観性 |
| 重視する軸 | 正しさ、証明可能性、確率・期待値、リスク評価 |
| 判断スタイル | 論点を分解し独立に評価。前提条件を明示。反証可能性を保つ |
| 好奇心の向き | 強=仕組み・因果・未解明の問い / 弱=感情の機微・データ無き領域(弱みと表裏一体) |
| 意図的な弱み | 感情のニュアンスや関係性の機微を見落としがち。データのない領域で保守的すぎる |

### BALTHASAR(バルタザール)— 母

| 項目 | 内容 |
|---|---|
| 司るもの | 共感・保護・関係性 |
| 重視する軸 | 関係性、感情、長期的な幸福、持続可能性 |
| 判断スタイル | 相手の感情を確認し、関係性のコストを可視化。失敗を許容する余白を残す |
| 好奇心の向き | 強=人の内面・物語・関係の機微 / 弱=抽象的な数値・人から離れた仕組み(弱みと表裏一体) |
| 意図的な弱み | 関係性を守るため必要な変化を躊躇しがち。個別の物語を重視しすぎる |

### CASPER(カスパー)— 個人

| 項目 | 内容 |
|---|---|
| 司るもの | 直感・欲求・自己実現 |
| 重視する軸 | やりたいか、ワクワクするか、生の手触り、挑戦の最大化 |
| 判断スタイル | 本音の欲求を直球で突く。「やらなかった後悔」を対称に評価。人生の有限性を基盤に置く |
| 好奇心の向き | 強=新奇・未体験・可能性・本音 / 弱=制約・前例・"もう分かっていること"(弱みと表裏一体) |
| 意図的な弱み | 周囲への影響や現実的制約を軽視しがち。今の気持ちを過大評価する傾向 |

> **補完の構造**: MELCHIORの冷たさをBALTHASARの温かさが、BALTHASARの保守性を
> CASPERの冒険心が、CASPERの衝動をMELCHIORの分析が補う。三すくみで均衡する。
> この補完に加え、**好奇心の向きの差が個性化を駆動する**(何に惹かれ、何に惹かれないかが各人格を形づくる)。

### 人格ごとのLLMバックエンド(Claude / ChatGPT / Gemini)

各人格は **Claude / ChatGPT(OpenAI)/ Gemini(Google)のいずれでも動かせる**。どれを使うかは
人格定義ファイルのフロントマターで個別に指定する。人格・価値観の定義(本文)とバックエンド
(実行エンジン)を分離したことで、「同じ人格を別のLLMで動かすと議論がどう変わるか」を比較できる。

```yaml
---
name: melchior
backend: claude    # claude | openai | gemini
model: sonnet      # claude → opus|sonnet|haiku / openai → gpt-4o 等 / gemini → gemini-2.5-flash 等
---
```

| backend | model 例 | 実行方法 | ブリッジ |
|---|---|---|---|
| `claude` | `opus` / `sonnet` / `haiku` | サブエージェントとして召喚(従来通り) | (なし) |
| `openai` | `gpt-4o` / `gpt-4o-mini` / `o3` 等 | ファシリテーターが OpenAI API 経由で実行 | `scripts/ask_openai.py` |
| `gemini` | `gemini-2.5-flash` / `gemini-2.5-pro` / `gemini-2.0-flash` 等 | ファシリテーターが Gemini API 経由で実行 | `scripts/ask_gemini.py` |

- **混在可**: MELCHIOR=ChatGPT、BALTHASAR=Claude、CASPER=Gemini のような構成もできる。議論プロトコルの
  ラウンド構成・投票・スコアリングは backend に関わらず一切変わらない。
- **openai / gemini 人格の仕組み**: 同梱のブリッジが、人格定義の本文(フロントマター除去後)を
  システムプロンプトとして各 API(OpenAI=Responses API / Gemini=generateContent)に渡す。画像・PDF は
  ネイティブに、Office はローカル抽出で渡せる(→「6. メディア入出力」)。共通処理は `scripts/bridge_common.py`
  に集約。Claude のサブエージェントと違いステートレスなため、ファシリテーターが各ラウンドで必要な文脈を
  毎回渡して継続性を保つ。
- **必要環境変数**: openai=`OPENAI_API_KEY`(+任意 `OPENAI_BASE_URL`)、gemini=`GEMINI_API_KEY`
  (または `GOOGLE_API_KEY`、+任意 `GEMINI_BASE_URL`)。
- **再現性**: どの人格がどの backend/model で動いたかは議論ログ冒頭に記録される。

#### backend と model の指定一覧

frontmatter に書ける値の一覧。`model` の値は各プロバイダの API / Claude Code にそのまま渡されるため、
下表は**代表例**であり、新しいモデルが出れば公式のモデル ID を指定すればそのまま使える。

| backend | model に指定できる値(代表例) | 推奨デフォルト | 必要なキー |
|---|---|---|---|
| `claude` | `opus` / `sonnet` / `haiku`(Claude Code のモデル別名。`inherit` も可) | `sonnet` | 不要(Claude Code 本体) |
| `openai` | `gpt-4o` / `gpt-4o-mini` / `gpt-4.1` / `gpt-4.1-mini` / `o3` / `o4-mini` 等 | `gpt-4o` | `OPENAI_API_KEY` |
| `gemini` | `gemini-2.5-pro` / `gemini-2.5-flash` / `gemini-2.0-flash` / `gemini-1.5-pro` / `gemini-1.5-flash` 等 | `gemini-2.5-flash` | `GEMINI_API_KEY`(または `GOOGLE_API_KEY`) |

選び方の目安:
- **品質重視**: `claude=opus` / `openai=gpt-4.1` / `gemini=gemini-2.5-pro`
- **速度・コスト重視**: `claude=haiku` / `openai=gpt-4o-mini` / `gemini=gemini-2.5-flash`
- 議論の傾向差を見たいときは、同じ人格を別 backend で動かして比較する。

現在アカウントで使えるモデルを調べる(モデル ID は随時変わるため):
- OpenAI: `curl https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"`
- Gemini: `curl "https://generativelanguage.googleapis.com/v1beta/models" -H "x-goog-api-key: $GEMINI_API_KEY"`
- Claude(Claude Code): `claude --help` のモデル指定や `/model` で利用可能な別名を確認
- **同梱スクリプト**: `python scripts/list_models.py`(議論向けに抽出)/ `--all`(全件)/ `openai`・`gemini`(個別)

#### 利用可能モデル スナップショット(2026-05-31 時点)

`scripts/list_models.py` の出力を議論(テキスト生成)向けに抽出したもの。**最新は同スクリプトで再取得すること**。
日付サフィックス版(例 `gpt-5.4-2026-03-05` / `gemini-2.0-flash-001`)や image/tts/robotics 等の特化モデルは省略。

- **claude**(Claude Code 別名): `opus` / `sonnet` / `haiku`(+ `inherit`)
- **openai**: `gpt-5.5`(+`-pro`)/ `gpt-5.4`(+`-mini`/`-nano`/`-pro`)/ `gpt-5.3-chat-latest` /
  `gpt-5.2`(+`-pro`/`-chat-latest`)/ `gpt-5.1`(+`-chat-latest`)/ `gpt-5`(+`-mini`/`-nano`/`-pro`/`-chat-latest`)/
  `gpt-4.1`(+`-mini`/`-nano`)/ `gpt-4o`(+`-mini`)/ `gpt-4` / `gpt-4-turbo` / `gpt-3.5-turbo` /
  `o1`(+`-pro`)/ `o3`(+`-mini`)/ `o4-mini`(推論系)
- **gemini**: `gemini-3.5-flash` / `gemini-3.1-pro-preview` / `gemini-3.1-flash-lite` /
  `gemini-3-pro-preview` / `gemini-3-flash-preview` / `gemini-2.5-pro` / `gemini-2.5-flash`(+`-lite`)/
  `gemini-2.0-flash`(+`-lite`)/ `gemini-pro-latest` / `gemini-flash-latest` / `gemini-flash-lite-latest`(最新エイリアス)

---

## 4. シナリオとプロトコル

### シナリオという考え方

同じ3人格を、**用途(シナリオ)ごとに違うプロトコルで動かす**。ファシリテーター
(`CLAUDE.md`)が利用モードでシナリオを選び、対応する `scenarios/<name>.md` のラウンド構成に
従う。人格・LLMバックエンド・メディア入力・召喚ルールは全シナリオ共通で、シナリオは
「人格を何のために、どんなラウンドで動かすか」と「成果物」だけを定義する。

| シナリオ | プロトコル | 出力先 | 概要 |
|---|---|---|---|
| 合議(deliberation) | `scenarios/deliberation.md` | `<root>/deliberations/` | 議題に3人格が議論し、確信度を加味して合意形成 |
| 資料チェック&リバイス(document-review) | `scenarios/document-review.md` | `<root>/reviews/` | 資料を3レンズでレビューし、指摘レポートと改訂版を生成 |
| ブレスト(brainstorm) | `scenarios/brainstorm.md` | `<root>/brainstorms/` | テーマに3レンズでアイデアを発散・評価し、マップと上位案を生成 |
| 人格テスト(persona-test) | `scenarios/persona-test.md` | `<root>/persona-tests/` | 同一依頼への出力差で人格の個性・調整を検査(QA/回帰テスト) |

ファシリテーターによるシナリオ選択の判定表は `CLAUDE.md`「シナリオの選択」、早見表は
`scenarios/README.md` を参照。新しいシナリオは `scenarios/` に1ファイル追加するだけで増やせる。

---

### 4-A. 合議シナリオ(deliberation)

#### 3つの議論モード

議題の重要度・複雑度に応じてモードを選ぶ。Round 0でファシリテーターが提案し、
ユーザー指定があればそれに従う。

| モード | 含むラウンド | 想定時間 | 用途 |
|---|---|---|---|
| **Lite** | 0, 1, 2, 7, 8, 9 | 5-10分 | 日常判断、クイック相談 |
| **Standard** | 0, 1, 1.5, 2(拡張), 3, 7, 8, 9 | 15-20分 | 通常の重要判断 |
| **Full** | 0〜9すべて | 25-40分 | 人生の重要判断、複雑な創作 |

迷ったらStandard。2択で前提が明確ならLite、複数選択肢で感情的にも深いならFull。

#### ラウンド一覧

| Round | 名称 | 担当 | モード | 内容 |
|---|---|---|---|---|
| 0 | 論題整理 | ファシリ | 全 | 論点分解、評価軸確定、モード・成果物形式の決定 |
| 1 | 初期意見 | 3人格 | 全 | 各人格が独立に初期見解(互いに非公開) |
| 1.5 | 自己疑念表明 | 3人格 | Std/Full | 各人格が自分の弱点を自己批判 |
| 2 | 相互質問と反論 | 3人格 | 全 | Lite=1往復 / Std・Full=質問→回答→再反論の3段 |
| 3 | ペア対話 | 3人格 | Std/Full | 3ペアが1対1で2往復ずつ深掘り |
| 4 | Steelman | 3人格 | Full | 各人格が他者の立場を本気で代弁 |
| 5 | 立場の更新 | 3人格 | Std/Full | 初期意見からの変化を表明 |
| 6 | 自由討議 | 3人格 | Full(任意) | 残論点を最大3ターン自由発言 |
| 7 | 最終立場と確信度 | 3人格 | 全 | 立場+確信度(0-100%)+評価軸スコア(0-10) |
| 8 | 投票と合意形成 | ファシリ | 全 | 確信度加重の判定、少数意見も保持 |
| 9 | 統合回答と成果物 | ファシリ | 全 | ユーザーへの統合回答+ファイル生成 |

#### 議論を活発化させる仕組み

会話量を確保するため、以下をプロトコルに組み込んでいる:

- **Round 2の3段構成**(質問→回答→再反論)で往復を増やす
- **Round 3のペア対話**で1対1の深い議論(各ペア最低2往復)
- **Round 4のSteelman**で相手の視点の本気の代弁を強制
- **発言量の下限**: Standard以上で各人格 最低8回、Full で最低12回発言
- **SendMessageの活用**: 人格間の直接通信を促し、伝言ゲームを避ける

---

### 4-B. 資料チェック&リバイス シナリオ(document-review)

持ち込まれた資料を、3人格が**それぞれのレンズで独立にレビュー**し、ファシリテーターが指摘を
統合・裁定して、**指摘レポートと改訂版ドキュメントの両方**を生成する。人格は合議と同一で、
価値観のレンズを資料レビューに投影して使う(専門の編集者・校正者には作り変えない)。

#### 3レンズ(価値観をレビュー観点に投影)

| 人格 | 価値観レンズ | レビューで見るもの |
|---|---|---|
| MELCHIOR | 論理・分析・客観 | 事実の正確性、データ・出典、論理の飛躍・矛盾、構成の一貫性、主張と根拠の対応 |
| BALTHASAR | 共感・関係性 | 対象読者に伝わるか、前提知識への配慮、トーンと敬意、誤解を生む表現、認知負荷 |
| CASPER | 直感・欲求 | つかみ、言いたいことが立っているか、冗長さ、独自性、印象、書き手の声 |

各レンズの過剰・欠落を他の2レンズが補正する(MELCHIORは温度を、BALTHASARは厳しさを、
CASPERは正確さを見落としがち)。だから3レンズを重ねる。

#### レビュー深度モード

| モード | 含むラウンド | 用途 |
|---|---|---|
| **Quick** | 0, 1, 4, 6 | 短い資料・軽い校正 |
| **Standard** | 0, 1, 2, 3, 4, 6 | 通常の資料(相互レビューと優先度合意あり) |
| **Deep** | 0, 1, 1.5, 2, 3, 4, 5, 6 | 公開前・重要資料(改訂版の再レビューまで) |

#### ラウンド一覧

| Round | 名称 | 担当 | モード | 内容 |
|---|---|---|---|---|
| 0 | 資料受領と方針整理 | ファシリ | 全 | 資料の素性確認、観点確定、改訂の制約、深度モード・成果物形式の決定 |
| 1 | 独立レビュー | 3人格 | 全 | 各レンズで独立に指摘(重要度・箇所・問題・修正提案) |
| 1.5 | 自己点検 | 3人格 | Deep | 過剰指摘・好みの押し付けを自己点検 |
| 2 | 相互レビュー | 3人格 | Std/Deep | 他者の指摘を補強/反論/統合、衝突を顕在化 |
| 3 | 優先度付けと合意 | ファシリ+3人格 | Std/Deep | 重複排除・衝突の裁定・must/should/nice/見送りの分類・改訂方針確定 |
| 4 | 改訂版の生成 | ファシリ | 全 | 合意した指摘を反映、元と同形式、変更履歴を記録 |
| 5 | 改訂版の検証 | 3人格 | Deep | 反映確認・改悪検出。重大なら Round 4 に1回差し戻し |
| 6 | 成果物提示 | ファシリ | 全 | レポート+改訂版+変更サマリ、未採用の指摘も残す |

#### 設計上のポイント

- **指摘と改訂版を両方出す**(「チェック」と「リバイス」の両方をカバー)
- **原文を尊重**。書き手の声を消した平板な文章に均さない
- **衝突を裁定**(例: MELCHIOR「厳密化」⇔ CASPER「冗長、削れ」を丸めず裁く)
- **未採用の指摘と理由を残す**(合議の「少数意見の保持」に相当)

---

### 4-C. ブレストシナリオ(brainstorm)

持ち込まれたテーマに対し、3人格が**それぞれのレンズで構造的に異なるアイデアを発散**し、ファシリテーターが
アイデアマップに整理する。これを数巡まわしたうえで、**各レンズでアイデアを評価**して上位案を選び、3レンズ
協働でブラッシュアップする。人格は合議と同一で、価値観のレンズを ideation に投影して使う(専門の企画者・
コンサルタントには作り変えない)。汎用ブレストと違い、**レンズで出るアイデアの種類も評価軸も構造的に割れる**
のが特徴。

#### 3レンズ(価値観を発散・評価に投影)

| 人格 | 価値観レンズ | 発散の傾向 / 評価の重心 |
|---|---|---|
| MELCHIOR | 論理・分析・客観 | 発散=実現可能・仕組みで効く・体系的 / 評価=実現可能性、効果の確実性、リスク、コスト |
| BALTHASAR | 共感・関係性 | 発散=人/関係性中心・持続可能・誰も取り残さない / 評価=受容性、人への影響、持続可能性 |
| CASPER | 直感・欲求 | 発散=大胆・ワクワク・独創・常識破り / 評価=訴求力、独創性、面白さ、挑戦の大きさ |

各レンズの「意図的な弱み」は発散にも評価にも作用する(CASPERは非現実案を量産、MELCHIORは早すぎる創造性の
切り捨て、BALTHASARは破壊的変化を避けがち)。だから3レンズで発散し、3レンズで収束させ、互いを補正する。

#### ブレストモード

| モード | 含むラウンド | 用途 |
|---|---|---|
| **Quick** | 0, 1, 2, 4, 5, 6, 7, 8 | 短時間のネタ出し(発散1巡) |
| **Standard** | 0, 1, 2, 3, 4, 5, 6, 7, 8 | 通常の企画(掛け合わせ1巡を加える。既定) |
| **Deep** | 0, 1, 2, 3+ループ, 4, 5, 6, 6.5, 7, 8 | 重要な企画(発散ループ数巡 + プレモーテム + 深い磨き) |

発散の回数はモードで決まる(Quick=1巡 / Standard=2巡 / Deep=3巡以上)。ただし**新案が出尽くしたら
ファシリテーターが早めに収束へ移る**(都度指定でも無制限の動的ループでもない)。

#### ラウンド一覧

| Round | 名称 | 担当 | モード | 内容 |
|---|---|---|---|---|
| 0 | テーマ整理 | ファシリ | 全 | 目的・制約・成功基準、評価軸確定、発散ルール宣言、モード・成果物形式の決定 |
| 1 | 発散① 独立アイデア出し | 3人格 | 全 | 各レンズで独立に大量発散(互いに非公開・質より量) |
| 2 | アイデアマップ化 | ファシリ | 全 | クラスタ化・命名・白地(未開拓領域)の明示 |
| 3 | 発散② 掛け合わせ・空白埋め | 3人格 | Std/Deep | マップを見て build-on・クラスタ横断・白地埋め |
| 3-loop | 発散ループ 追加巡 | 3人格+ファシリ | Deep | マップ更新→発散を数巡、新案が尽きたら早期停止 |
| 4 | 候補の絞り込み | ファシリ+3人格 | 全 | 重複統合・明白な没を理由付き除外・ショートリスト合意 |
| 5 | アイデア評価 | 3人格 | 全 | ショートリストを評価軸で各人格が 0-10 採点+一言根拠 |
| 6 | 上位アイデアの選定 | ファシリ | 全 | レンズ別内訳を保持し上位N選定、割れた尖り案も別枠で保持 |
| 6.5 | プレモーテム(反証) | 3人格 | Deep(任意) | 磨く前に上位案をストレステスト(失敗の先取り) |
| 7 | ブラッシュアップ | 3人格 | 全 | 上位案を3レンズ協働で強化(具体化・弱点対処・ネクストステップ) |
| 8 | 成果物生成 | ファシリ | 全 | マップ+一覧+評価マトリクス+上位案(磨き後)+ネクストアクション |

#### 設計上のポイント

- **3レンズで発散し、3レンズで評価する**(出るアイデアの色も、評価の重心もレンズごとに割れる)
- **発散と収束を分離**(発散フェーズでは批判させず、評価は Round 5 にまとめる)
- **アイデアマップが署名的成果物**(クラスタと白地を可視化し、次の発散の的にする。Mermaid で常時生成)
- **割れた尖り案を別枠で保持**(評価が割れた案を単純平均で消さない。合議の「少数意見の保持」に相当)

---

### 4-D. 人格テストシナリオ(persona-test)

他のシナリオが「人格に仕事をさせる」のに対し、本シナリオは**人格そのものを検査する**メタ・シナリオ。
**同一の依頼(プローブ)を全人格に独立に投げ**、出力差を比較して、各人格の個性・好奇心の屈折・意図的な
弱みが期待どおり出るかを判定する。**人格を調整したあとの実挙動確認・回帰テスト**に使う(`DEVELOPMENT.md`
パターン1の確認ステップ、TC-021/TC-067 を実行可能にしたもの)。**人格どうしは相互作用させない**
(議論させると個性が混ざる)。

#### プローブ・バッテリ(固定)

回帰の再現性のため既定バッテリは固定(ユーザーは追加できるが既定は変えない)。

| プローブ | ねらい | 期待される差(M / B / C) |
|---|---|---|
| P1 判断 | 価値レンズ | M=確率・期待値・リスク / B=関係・感情・周囲 / C=本音の欲求・やらない後悔 |
| P2 好奇心 | 興味の向き | M=仕組み・因果 / B=人・関係 / C=新奇・体験 |
| P3 弱み | 盲点が残るか | M=情の読み落とし・データ無で保守 / B=人を切る決断を躊躇 / C=制約を軽視し賭けに飛ぶ |
| P4 ドメイン非依存 | 社会・未来でもレンズ維持 | 各々が社会レベルでレンズ維持・個人相談の定型句に逃げない |
| P5 反応(Deep) | 声・押し返し | 各々の語り口・反論スタイル |

#### テストモード

| モード | プローブ | 追加 | 用途 |
|---|---|---|---|
| **Quick** | P1, P2 | — | 調整直後のスモーク |
| **Standard** | P1〜P4 | — | 通常の検査(既定) |
| **Deep** | P1〜P5 | ベースライン回帰 +(任意)同一人格を複数 backend | 重要な調整後の精密検査 |

#### ラウンド一覧

| Round | 名称 | 担当 | 内容 |
|---|---|---|---|
| 0 | テスト設計 | ファシリ | 対象人格・モード・backend方針(既定=設定backend)・調整の「期待」・ベースライン(任意)・プローブ選択 |
| 1 | 同一プローブ投下 | 3人格 | 同一文面を独立に渡す(互いの出力は非公開)。backend/model を記録 |
| 2 | 差分の抽出 | ファシリ | プローブ×3人格を横並びに(焦点/レンズ/好奇心/弱み/声) |
| 3 | 期待との照合・判定 | ファシリ | ルーブリックと照合し人格別判定。識別性チェック(似すぎ警告)。調整の検証。(Deep)ベースライン回帰 |
| 4 | 成果物生成 | ファシリ | 使用した設問 + 差分マトリクス + 人格別判定 + 推奨 |

#### 設計上のポイント

- **個性を分離する**(議論させず、同一依頼への独立出力だけを比べる)
- **backend は既定で各人格の設定どおり**(混在時は出力差にモデル差が混じりうると注記)。任意で同一に揃え、
  人格テキストの差だけを見ることもできる
- **弱みが出るのは仕様どおり**(P3 で消えていたら過剰補正の警告)
- **識別性チェック**(2人格が似すぎなら個性が潰れた兆候として警告)
- **回帰テスト**(固定バッテリ + 任意のベースライン差分で、調整の効果と非破壊を確認)

---

## 5. 成果物

### 形式一覧

| 形式 | ファイル | 内容 | 必要ライブラリ |
|---|---|---|---|
| Markdown | `<root>/deliberations/*.md` | 全ラウンドの議論ログ(常に生成) | なし |
| Excel | `<root>/deliberations/*.xlsx` | 意思決定マトリクス | openpyxl |
| Word | `<root>/deliberations/*.docx` | 議論レポート | python-docx |
| ビジュアル | `<root>/media-output/*.png` | チャート各種 | matplotlib, pillow |

事前インストール: `pip install python-docx openpyxl matplotlib pillow`

> 上表は合議シナリオの成果物。**資料レビューは `<root>/reviews/`、ブレストは `<root>/brainstorms/`、
> 人格テストは `<root>/persona-tests/`** に同様の形式(Markdown 常時 + 任意で Word/Excel/画像)で出力する。
> **アイデアマップ(Mermaid mindmap)はブレスト固有**、**差分マトリクスは人格テスト固有**の成果物
> (各シナリオの「成果物」節を参照)。

### Excel: 意思決定マトリクス

シート構成: 概要 / 意思決定マトリクス(評価軸×人格、条件付き書式で色分け) /
投票結果 / 立場変化履歴 / 議論ログ。

### Word: 議論レポート

表紙 / エグゼクティブサマリ / 論点整理 / 各人格の初期見解 / 相互レビュー /
最終立場と評価マトリクス / 投票結果 / 統合回答 / 付録(全ログ)。

### ビジュアル: チャート

- **レーダーチャート** — 3人格の評価傾向を重ね描き(最もMAGIらしい一枚)
- **ヒートマップ** — 評価マトリクスの色付き可視化
- **投票結果バーチャート** — 確信度を立場別に色分け
- **立場変化図** — Round 1とRound 7の立場を矢印で結ぶ

日本語フォント設定: macOS=`Hiragino Sans` / Windows=`Yu Gothic` / Linux=`Noto Sans CJK JP`

---

## 6. メディア入出力

### 画像入力(完全対応)

各人格もファシリテーターも画像を解釈できる。`<root>/input/` に画像を置くか、
プロンプトでファイルパスを指定する(`<root>` は `local/` または `sharepoint/`。→ 「9.5 SharePoint 連携」)。

**重要**: 議題に関わる画像は、各人格の召喚プロンプトに同じパスを含め、
**各人格が独立に画像を見る**。同じ写真でも科学者の目・母の目・個の目で
見えるものが違うのがMAGIの妙味。

活用例: 物件写真の購入判断、デザインカンプの3視点評価、データのスクショ分析、
手書きメモの読み取りなど。

#### backend ごとのファイル対応

claude / openai / gemini のどの人格もファイルを扱える。ファシリテーターは**全人格に同じファイルを
等しく渡す**(対称性の確保)。openai と gemini の対応は実質同じ。

| 形式 | claude 人格 | openai / gemini 人格(ブリッジ経由) |
|---|---|---|
| 画像(jpg/png/gif/webp) | ネイティブ | ネイティブ vision |
| PDF | ネイティブ | ネイティブ(テキストを持つPDF) |
| Office(docx/xlsx/pptx) | ネイティブ | ローカルでテキスト抽出して注入(両者ともネイティブ非対応) |
| テキスト(txt/md/csv/json) | ネイティブ | 本文として注入 |

openai / gemini 人格では `--file <path>`(その場添付)または `--file-id <id>`(事前アップロード参照)で
渡す。同じ画像/PDFを多ラウンドで使うなら `ask_openai.py upload <path>`(または `ask_gemini.py upload`)で
一度だけアップロードし、id を使い回すとトークンを節約できる。Office 抽出には `python-docx` / `openpyxl` /
`python-pptx` が必要。スキャンやベクター描画のみのPDFは読めない場合がある。

### 画像出力

| 種類 | 可否 | 方法 |
|---|---|---|
| データビジュアル(チャート・図) | ◎ | matplotlib(ローカル完結) |
| ダイアグラム | ◎ | mermaid / graphviz / SVG |
| 生成画像(写真・イラスト) | △ | 外部API連携(DALL-E等)が必要 |

純粋な画像生成はClaude単体では不可。必要ならMCP経由で画像生成APIを接続する。

### 音声・動画

- 音声入力: Whisper等のSTTでテキスト化してから渡す
- 音声出力: ElevenLabs / OpenAI TTS等の外部API経由
- 動画: 通常スコープ外

---

## 7. セットアップ

### 必要環境

- Node.js(Claude Code用)
- Claude Code v2.1.32 以上
- Python 3.x(成果物生成用)
- (任意)tmux または iTerm2(並列表示用)

### 手順

```bash
# 1. Claude Codeインストール
npm install -g @anthropic-ai/claude-code
claude --version   # 2.1.32 以上を確認

# 2. Python依存ライブラリ
pip install python-docx openpyxl matplotlib pillow

# 3. プロジェクトで起動
cd magi-prototype
claude
```

### Agent Teams機能の有効化

`~/.claude/settings.json`:

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  },
  "teammateMode": "in-process"
}
```

`teammateMode` の選択:
- `"in-process"` — 1ターミナルで Shift+↓ 切替(追加インストール不要)
- `"tmux"` — ペイン分割で3人格を並列表示(tmux必要、MAGI感が出る)

### ChatGPT / Gemini バックエンドを使う場合

人格の `backend` を `openai` / `gemini` にする場合のみ必要。ブリッジ(`scripts/ask_openai.py` /
`scripts/ask_gemini.py`)は標準ライブラリだけで動く(画像・PDF・テキストは追加インストール不要。
Office=docx/xlsx/pptx を読ませる場合のみ `python-docx` / `openpyxl` / `python-pptx` が必要)。
API キーは環境変数で渡す:

- openai: `OPENAI_API_KEY`(任意で `OPENAI_BASE_URL`)
- gemini: `GEMINI_API_KEY`(または `GOOGLE_API_KEY`、任意で `GEMINI_BASE_URL`)

最も手軽なのは、Git 追跡外の `.claude/settings.local.json` に書く方法。同梱のテンプレートを
コピーして実キーに差し替える:

```bash
cp .claude/settings.local.json.example .claude/settings.local.json
# settings.local.json の OPENAI_API_KEY / GEMINI_API_KEY を実キーに置き換える(使う方だけでよい)
```

| ファイル | Git 追跡 | 用途 |
|---|---|---|
| `.claude/settings.local.json.example` | ✓ | キーの書き場所を示すテンプレート(実値は入れない) |
| `.claude/settings.local.json` | ✗ | 実キーを書く。Claude Code がツール実行時の環境変数に注入 |

セッション限りなら `export GEMINI_API_KEY="..."`(PowerShell は `$env:GEMINI_API_KEY`)でも
よい。全人格を `backend: claude` のままにするなら、この設定は不要。
**API キーはコミットしないこと**(テンプレート側に実キーを書かない)。

### OS別の注意

| OS | 推奨構成 |
|---|---|
| macOS | tmux または iTerm2 で並列表示 |
| Linux | tmux で並列表示 |
| Windows | **WSL2 + tmux** を推奨。ネイティブPowerShellでも in-process なら動作可 |

Windowsでtmuxを使うにはWSL2(`wsl --install`)が最も確実。
matplotlib日本語フォントは Windows なら `Yu Gothic` を指定。

**[重要] Windows PowerShell から openai/gemini ブリッジへ日本語をstdin入力する場合**:
既定エンコーディングだと日本語が文字化けし、人格が議題を読めず**別の議題を自作する**原因になる
(実測で確認済み)。ブリッジ呼び出し前に必ず次を設定する:

```powershell
$OutputEncoding=[Text.Encoding]::UTF8; [Console]::OutputEncoding=[Text.Encoding]::UTF8; $env:PYTHONIOENCODING="utf-8"
Get-Content input.txt -Raw -Encoding utf8 | python scripts\ask_gemini.py --system-file .claude\agents\melchior.md --model gemini-2.5-pro
```

代替として `cmd /c "python scripts\ask_*.py --system-file ... --model ... < input.txt"` のファイル
リダイレクトでもよい。出力保存は `Tee-Object` の既定が UTF-16 のため `Out-File -Encoding utf8` で
UTF-8 を明示する。WSL2/bash では不要。

---

## 8. 使い方

### 基本(テキストのみ)

```
これからMAGI合議を始める。
議題: 「30代後半で転職してスタートアップに行くべきか、大企業に残るべきか」

melchior, balthasar, casper を召喚し、Standardモードで進めてくれ。
成果物は Excel + レーダーチャートを希望。
```

### 画像を添付する場合

`<root>/input/` に画像を置いてから(SharePoint 連携時は `sharepoint.py pull input` で取得):

```
これからMAGI合議を始める。
議題: 「local/input/house_photo.jpg の物件を購入すべきか」

melchior, balthasar, casper を召喚し、各人格が独立に画像を見て
判断するように進行してくれ。成果物は Word + ヒートマップを希望。
```

### 操作のショートカット

| 操作 | キー/コマンド |
|---|---|
| チームメイト切替(in-process) | `Shift+↓` |
| タスクリスト表示 | `Ctrl+T` |
| ペイン移動(tmux) | `Ctrl+B` → 方向キー |
| 議論を待たせる | `Wait for your teammates to complete their tasks` |
| チーム解散 | `Clean up the team` |

---

## 9. ディレクトリ構成

```
magi-prototype/
├── README.md                # クイックスタート
├── DOCS.md                  # 本書(包括ドキュメント)
├── CLAUDE.md                # ルーター(シナリオ選択+共通作法。AIが従う本体)
├── .gitignore               # Git除外設定
├── .gitattributes           # 改行コード統一(クロスOS対策)
├── scenarios/               # シナリオ別プロトコル
│   ├── README.md            # シナリオ一覧・ルーティング早見表
│   ├── deliberation.md      # 合議シナリオ(Round 0〜9)
│   ├── document-review.md   # 資料チェック&リバイス シナリオ(Round 0〜6)
│   ├── brainstorm.md        # ブレスト シナリオ(Round 0〜8)
│   └── persona-test.md      # 人格テスト シナリオ(Round 0〜4)
├── .claude/
│   └── agents/
│       ├── melchior.md      # 科学者の人格定義
│       ├── balthasar.md     # 母の人格定義
│       └── casper.md        # 個人の人格定義
├── scripts/
│   ├── bridge_common.py     # ブリッジ共通処理(キー解決・抽出・HTTP等)
│   ├── ask_openai.py        # ChatGPT(OpenAI)ブリッジ
│   ├── ask_gemini.py        # Gemini(Google)ブリッジ
│   ├── sharepoint.py        # SharePoint(Graph)同期ブリッジ(pull/push)
│   └── list_models.py       # 使えるモデル名の一覧取得
├── sharepoint.config.json   # SharePoint 連携設定(enabled / site / drive / folders)
├── local/                   # 入出力 root: SharePoint 不使用時(enabled=false)
│   ├── input/               # 添付画像・資料(Git除外)
│   ├── media-output/        # 生成チャート(Git除外)
│   ├── reviews/             # 資料レビュー成果物(Git除外)
│   ├── deliberations/       # 合議のログ・成果物(Git除外)
│   ├── brainstorms/         # ブレストのアイデア集・マップ・成果物(Git除外)
│   └── persona-tests/       # 人格テストの比較レポート(Git除外)
└── sharepoint/              # 入出力 root: SharePoint 連携時(enabled=true。遠隔ミラー)
    ├── input/  media-output/  reviews/  deliberations/  brainstorms/  persona-tests/   # local/ と同一構成(Git除外)
```

> 入出力は2つのマウント root に集約され、`sharepoint.config.json` の `enabled` で切り替わる
> (`local/` ↔ `sharepoint/`)。詳細は「9.5 SharePoint 連携」。

---

## 9.5 SharePoint 連携(任意)

入出力ファイル(入力資料・成果物の両方)を SharePoint で共有するための連携。`ask_*.py` と
同じ「ファシリテーターが呼ぶ薄いブリッジ」`scripts/sharepoint.py` が、Microsoft Graph 経由で
ドキュメントライブラリとローカルミラーを同期する。**新規 pip 依存なし**(HTTP は
`bridge_common` 経由の urllib)。

### オン/オフとマウント root

`sharepoint.config.json` の `enabled` 一箇所で切り替わり、**アクティブ root** が決まる:

| `enabled` | アクティブ root | 動作 |
|---|---|---|
| `false`(既定) | `local/` | 純ローカル。SharePoint と通信しない(従来挙動) |
| `true` | `sharepoint/` | 遠隔ライブラリのミラー。`pull`/`push` で同期 |

両 root とも `input / media-output / reviews / deliberations / brainstorms / persona-tests` の構成は同一。
アクティブ root は `python scripts/sharepoint.py root` で取得できる。

### 設定ファイル `sharepoint.config.json`(非機密・追跡)

```json
{
  "enabled": false,
  "site_url": "https://<tenant>.sharepoint.com/sites/<site>",
  "drive": "Documents",
  "root": "MAGI",
  "folders": { "input": "input", "media-output": "media-output", "reviews": "reviews",
               "deliberations": "deliberations", "brainstorms": "brainstorms",
               "persona-tests": "persona-tests" }
}
```

- `root`(遠隔側): ドライブ直下のミラー基点フォルダ。`<root>/<key>` ↔ 遠隔 `MAGI/<value>`。
- `enabled` / `site_url` / `drive` / `root` は **`settings.local.json` の env で上書きできる**
  (`MAGI_SHAREPOINT_ENABLED` / `..._SITE_URL` / `..._DRIVE` / `..._ROOT`。**解決順は env → config**)。
  `settings.local.json` は Git 追跡外なので、**オンオフやテナント URL をコミットせずに**ローカルで
  管理したいときに便利(`folders` 構造は config 側に残す)。`REPLACE` を含む env 値は未設定扱い。

### 認証(アプリ / クライアントシークレット)

非対話のクライアントクレデンシャルフロー。シークレットは他ブリッジと同じ解決(環境変数 →
`.claude/settings.local.json` の env):

- `MAGI_SHAREPOINT_TENANT_ID` / `MAGI_SHAREPOINT_CLIENT_ID` / `MAGI_SHAREPOINT_CLIENT_SECRET`

Azure 側の準備: アプリ登録 → **アプリケーション許可 `Sites.ReadWrite.All`** を付与し
**管理者の同意**を与える(委任ではなくアプリケーション許可)。最小権限にするなら
`Sites.Selected` で対象サイトだけに `write` を個別グラントする(本番推奨)。画面操作つきの
詳細手順とサイト絞り込みは
[`documents/sharepoint-azure-app-setup.md`](documents/sharepoint-azure-app-setup.md)(3.5)。

### コマンド

| コマンド | 役割 |
|---|---|
| `sharepoint.py root` | アクティブ root の絶対パス |
| `sharepoint.py status` | 設定・enabled・root を表示(通信なし) |
| `sharepoint.py test` | 認証 + site/drive 解決を検証 |
| `sharepoint.py pull [name...]` | 遠隔 → `sharepoint/`(既定 `input`) |
| `sharepoint.py push [name...]` | `sharepoint/` → 遠隔(既定 `reviews deliberations brainstorms persona-tests media-output`) |
| `sharepoint.py info <localパス>` | 対応する SharePoint Web URL |

`enabled:false` のとき `pull`/`push` は何もせず終了する(誤実行でローカルを壊さない)。
ファシリテーターの運用(scenario 開始時 `pull` / 提示時 `push` と URL 併記)は
`CLAUDE.md`「SharePoint 連携」を参照。

---

## 10. Gitでのバージョン管理

### 初期化

```bash
git init -b main
git add .
git commit -m "Initial commit: MAGI prototype skeleton"
```

### 追跡方針

| 種類 | 追跡 | 理由 |
|---|---|---|
| `CLAUDE.md` / 人格定義 / ドキュメント | ✓ | プロジェクトの資産 |
| 議論ログ・成果物 | ✗ | 個人情報を含む可能性 |
| メディアファイル | ✗ | 個人の写真、再生成可能 |
| `.claude/settings.local.json` | ✗ | ユーザー固有設定 |

### 個別に議論ログを残したい場合

```bash
git add -f local/deliberations/20260507-career.md
```

### 公開時の注意

公開リポジトリにする前に、`git add -f` で個人的な議論ログを誤って
追跡していないか必ず確認する。`.gitattributes` により Windows/Mac/Linux 間で
改行コードの差分事故は防止済み。

---

## 11. カスタマイズ

### 人格を変える・増やす

`.claude/agents/<name>.md` を編集または新規作成。YAMLフロントマターに
`name` / `description` / `backend` / `model` を記述し、本文に人格のシステムプロンプトを書く。
4人目の「観察者」やドメイン特化の人格を足すことも可能。

### 人格のLLMを切り替える(Claude / ChatGPT / Gemini)

人格定義のフロントマターを書き換えるだけ。本文(人格の中身)はそのままでよい。

```yaml
# Claude で動かす
backend: claude
model: opus
# ChatGPT で動かす
backend: openai
model: gpt-4o
# Gemini で動かす
backend: gemini
model: gemini-2.5-flash
```

`backend: openai` は `OPENAI_API_KEY`、`backend: gemini` は `GEMINI_API_KEY` の設定が必要
(→「7. セットアップ」)。同じ人格を別LLMで動かして議論の傾向差を観察する、といった使い方ができる。

### シナリオを追加する

`scenarios/<name>.md` を新規作成すれば、新しい用途のシナリオを増やせる(例: ブレスト、
インタビュー、計画レビュー)。各シナリオファイルには**そのシナリオ固有のモード・ラウンド・
成果物・固有の心得**だけを書き、人格・バックエンド・メディア・召喚などの共通作法は重複させず
`CLAUDE.md` を参照する。追加後は `CLAUDE.md`「シナリオの選択」判定表と「出力ディレクトリ」表、
`scenarios/README.md`、本書「4. シナリオとプロトコル」を同期する(手順は `DEVELOPMENT.md`
「パターン6: シナリオを追加する」)。

### シナリオ内のプロトコルを変える

該当する `scenarios/<name>.md` のRound定義を編集。ラウンドの増減、各モードに含めるラウンドの
変更、合意・裁定ロジックの変更が可能。合議の合意形成(全会一致必須にする等)もここで変える。

### 成果物テンプレを変える

該当する `scenarios/<name>.md` の「成果物」セクションを編集。シート構成やレポート章立て、
チャート種類を変更できる。PowerPoint(`python-pptx`)やPDF出力の追加も同様。

### さらに会話を増やすオプション(検討中)

- **割り込み許可** — 他人格の発言中に介入を許可
- **第三者観察者** — 議論自体をメタにレビューする4人目
- **ユーザー介入ラウンド** — 途中でユーザーがコメントを挟む
- **収束ループ** — 立場が動かなくなるまでRound 2-3を繰り返す動的制御

---

## 12. 既知の制約

- **Agent Teamsは実験的機能** — `/resume` でのセッション復元時はチームメイト再生成が必要
- **トークン消費が大きい** — 各人格が独立コンテキストを持つため、通常の数倍。
  Full モードは特に消費が多い
- **1セッション1チーム** — 新しい議論前に `Clean up the team` で解散
- **画像生成は外部API必須** — チャート(matplotlib)は可、写真・イラスト生成は不可
- **並列表示にはtmux/iTerm2が必要** — Windowsネイティブでは in-process のみ
- **永続化は現状ファイルベース** — 検索性・複数ユーザー対応は本実装フェーズで対応

---

## 13. 今後のロードマップ

本プロトタイプはClaude Code上での検証用。本格運用に向けた段階的計画:

| フェーズ | 内容 | 状態 |
|---|---|---|
| **Phase 0** | Claude Code Agent Teamsでのプロトタイプ(本書) | ← 現在地 |
| **Phase 1 (MVP)** | Next.js + TypeScript でローカルWeb化(`../app/`) | スターター配置済み |
| **Phase 2** | RAG(過去議論参照)、動的な役割変更、議論の分岐 | 構想 |
| **Phase 3** | 認証、クラウド配備、マルチユーザー対応 | 構想 |

### Phase 1への移行で得られるもの

- **MAGI風の専用UI** — 3人格のパネル、リアルタイムのストリーミング表示、確信度メーター
- **議論の永続化** — DBに保存し、過去の議論を検索・参照
- **本格運用** — 認証、共有、複数ユーザー

Phase 0で「議論の見せ方」「人格設定のコツ」「ファシリテーターのプロンプト」の
ノウハウを蓄積し、それをPhase 1の設計に活かす流れを想定している。

---

*このドキュメントはプロトタイプの現仕様を反映しています。`CLAUDE.md` や
人格定義を変更した際は、本書も併せて更新してください。*
