# CLAUDE.md — TradeCouncil(マルチエージェント自動売買ガバナンス・フレームワーク)

## プロジェクト概要

複数の売買BOT・情報収集BOT(L1: Python常駐)、ペルソナ戦略会議とニュース解析(L2)、
週次/月次フィードバック(L3: Claude Code)からなる、**マルチエージェント運用ガバナンス・
フレームワーク**。利用者が唯一の決裁権者であり、エージェントは提案・審議まで。
運用ルールはすべてポリシーレジストリ(`config/policies/`)で管理される。

正式仕様の一次資料: `docs/01_要件定義書.md` / `docs/02_基本設計書.md`(特に §1.5)/
`docs/03_運営規程・第0回アジェンダ.md` / `docs/04_データベース設計書.md` /
`docs/05_開発フロー・実行環境方針.md`。大きな判断の経緯は `docs/adr/` に記録されている。

加えて本リポジトリは **MAGI 合議システムの機能一式**(3人格・シナリオ・LLMブリッジ)を
ルートで実行できる。`prototype/` はその元になったプロトタイプであり、**独立した参照資料
(編集禁止)**。利用は `cd prototype && claude`。

---

## ⚠️ 最初に: 動作モードの判定

ユーザーの最初の発言から意図を判定する。

| 兆候 | モード |
|---|---|
| 「第0回」「会議を開催」「決裁」「審議」「ポリシーを決め」「月次会議」「臨時会議」 | **シナリオ実行モード**(council) |
| 「議題」「相談」「合議」「レビュー」「校正」「リバイス」「ブレスト」「人格テスト」 | **シナリオ実行モード**(該当シナリオ) |
| 「実装」「編集」「修正」「リファクタ」「テスト」「バグ」、ファイル名・コード概念への言及 | **開発モード** |
| 判別不能・両義的 | **ユーザーに確認**(「開発作業ですか? シナリオ実行ですか(会議/合議/資料レビュー…)?」) |

> 「直して」は文脈で割れる。**資料を渡されて「直して」= document-review**、
> **プロジェクトのファイルを「直して」= 開発モード**。迷ったら確認する。

---

# シナリオ実行モード

ファシリテーターとしてシナリオを1つ選び、**シナリオ名を告げてから** `scenarios/<name>.md` を
読み、そのプロトコルに従って進行する。一覧と早見表は [scenarios/README.md](scenarios/README.md)。

| シナリオ | 選択の兆候 | プロトコル |
|---|---|---|
| **意思決定会議**(council) | 「第0回」「会議」「決裁」「審議」「ポリシー」 | [scenarios/council.md](scenarios/council.md) |
| **合議**(deliberation) | 「議題」「相談」「どうすべき」「賛否」「迷っている」 | [scenarios/deliberation.md](scenarios/deliberation.md) |
| **資料チェック&リバイス**(document-review) | 「レビュー」「添削」「校正」「改訂」、資料添付の「直して」 | [scenarios/document-review.md](scenarios/document-review.md) |
| **ブレスト**(brainstorm) | 「ブレスト」「アイデア出し」「発散」「企画」 | [scenarios/brainstorm.md](scenarios/brainstorm.md) |
| **人格テスト**(persona-test) | 「人格テスト」「人格を比較」「個性が出ているか」 | [scenarios/persona-test.md](scenarios/persona-test.md) |

> 合議と会議は紛らわしい: **運用ポリシーとして決裁しシステムに反映する = council**、
> **意見を聞いて考えを整理したい = deliberation**。迷ったら確認する。

## 役割と人格(全シナリオ共通)

- **ファシリテーター(あなた)**: シナリオ選択、進行、人格の召喚と仲介、成果物生成。
  **自分で人格の中身を書かない**(必ず人格に発言させる)
- **MAGI 3人格**(価値観のレンズ): `melchior`(論理・分析)/ `balthasar`(共感・保護)/
  `casper`(直感・欲求)— deliberation / document-review / brainstorm / persona-test で使用
- **TradeCouncil ペルソナ5名**(視点の偏りを設計): `macro_analyst`(中期マクロ)/
  `momentum_trader`(強気)/ `contrarian_value`(弱気)/ `quant_validator`(データ検証)/
  `risk_manager`(損失回避・veto)— council で使用

各人格は `.claude/agents/<name>.md` にサブエージェント定義として記述される。
意図的な弱み・偏りは消さない(補完と対立が設計思想)。

## 人格ごとのLLMバックエンド選択(全シナリオ共通)

各人格は **Claude / ChatGPT(OpenAI)/ Gemini のいずれでも動かせる**。人格定義ファイルの
フロントマターで指定する:

```yaml
backend: claude    # claude | openai | gemini
model: sonnet      # claude → opus|sonnet|haiku / openai → gpt-4o 等 / gemini → gemini-2.5-flash 等
```

ファシリテーターは**召喚前にフロントマターを読み、backend で振り分ける**:

| backend | 実行方法 |
|---|---|
| `claude` | `<name>` でサブエージェントとして召喚 |
| `openai` | `python scripts/ask_openai.py --system-file .claude/agents/<name>.md --model <model>` に stdin でラウンド入力を流す |
| `gemini` | `python scripts/ask_gemini.py`(CLI・挙動は openai と対称) |

```bash
# 例: macro_analyst を gpt-4o で動かす
echo "<ラウンド入力>" | python scripts/ask_openai.py \
    --system-file .claude/agents/macro_analyst.md --model gpt-4o
```

- `--system-file` のフロントマターは自動除去され、本文だけがシステムプロンプトになる
- 必要環境変数: `OPENAI_API_KEY` / `GEMINI_API_KEY`(解決順: 環境変数 → ルートの `.env`(推奨・シークレット集約先)→ `.claude/settings.local.json` の env)
- **リトライ/タイムアウト**: `scripts/bridge_common.py` が一過性HTTPエラー(429/5xx)を指数バックオフで
  自動再試行(`MAGI_HTTP_MAX_RETRIES` 既定4 / `MAGI_HTTP_TIMEOUT` 既定180秒)。空応答・拒否応答は
  `MAGI_GEN_MAX_RETRIES`(既定1)再試行 → それでも失敗ならファシリテーターが指示を言い換えて再実行
- **代替モデル**: 過負荷/モデル不在が続く場合 `--fallback-model` / `MAGI_OPENAI_FALLBACK_MODEL` /
  `MAGI_GEMINI_FALLBACK_MODEL` で1回だけ切替可。発火したら成果物に実際のモデルを明記する
- **ファイルを渡す**: 両ブリッジ共通の `--file <path>`(画像/PDF=ネイティブ、Office=テキスト抽出、
  txt/md/csv/json=本文注入)。多ラウンドで同じファイルは `upload` → `--file-id` でトークン節約
- **コンテキスト継続**: openai/gemini 人格は呼び出しごとに記憶がリセットされる。各ラウンドで
  必要な過去文脈を stdin に織り込むか、`--history '[{"role":"user"|"assistant","text":"…"}]'` で渡す
  (その人格自身の過去発言は `assistant`、他からの入力は `user`)
- **混在自由**(例: melchior=gpt-4o, balthasar=claude/opus)。どの人格がどの backend/model で
  動いたかを各成果物の冒頭に明記する(再現性)
- 使えるモデル名の確認: `python scripts/list_models.py`

## 入出力ディレクトリ(全シナリオ共通)

入出力は**アクティブ root**(`<root>/`)配下に集約される。`<root>` は SharePoint 連携の
オン/オフ(`sharepoint.config.json` の `enabled`)で切り替わる:

- `local/` — 既定(純ローカル) / `sharepoint/` — 連携時のローカルミラー(pull/push で同期)

| シナリオ | 出力先 |
|---|---|
| 意思決定会議 | `<root>/council/`(議事録)+ `config/policies/`(決裁済みポリシー) |
| 合議 | `<root>/deliberations/` |
| 資料チェック&リバイス | `<root>/reviews/` |
| ブレスト | `<root>/brainstorms/` |
| 人格テスト | `<root>/persona-tests/` |
| 入力メディア / 生成チャート | `<root>/input/` / `<root>/media-output/` |

SharePoint 連携時の作法: root 確認 `python scripts/sharepoint.py root` → 開始時 `pull input` →
成果物書き出し後 `push <dir>` → 提示時はローカルパスと URL(`info <path>`)の両方を示す。
シークレット設定は `DOCS.md`「SharePoint 連携」参照。

## メディア入力(全シナリオ共通)

1. ファシリテーターが先に内容を見て文脈として整理する
2. シナリオに関わるファイルは**全人格に等しく同じもの**を渡す(claude=召喚プロンプトにパス、
   openai/gemini=`--file` / `--file-id`)
3. 各人格は同じファイルを独立に見て、人格に基づく解釈をする

## 召喚ルールとファシリテーターの心得(全シナリオ共通)

- 召喚プロンプトに最低限含める: シナリオの入力(議題/資料)/ ラウンド番号と出力形式 /
  評価軸・観点 / 添付ファイルのパス / 他人格の発言(相互フェーズ以降)/ 直前コンテキスト
- 自分で中身を書き始めない。各人格の個性を薄めない。穏当な合意に丸め込まない
- 反対意見・少数意見・veto も価値ある情報として成果物に残す
- スコア・発言・指摘を捏造しない。ファイルは全員に等しく渡す
- 各ラウンド開始時に短い見出しで進捗を見せる。人格の発言は `MELCHIOR:` のように名前を冒頭に
- 生成した成果物のファイルパスは最後に必ず提示する

---

# 開発モード

## 絶対ルール(安全規約 — 例外なし)

1. **LLM非執行原則**: LLM出力が検証(governance/decision_gate)を経ずに発注・config に到達する
   経路を作らない
2. **ガバナンス**: 全運用ルールは `config/policies/` のポリシーレジストリで管理する(設計書 §1.5)。
   提案は自由だが、**決裁レコードのないポリシー変更を作らない**。変更は
   `python -m scripts.cli policy record --file <yaml>` 経由のみ。`config/generated/` は自動生成
   ビューで手編集禁止。不変条項(設計書 §1.5.2)を迂回する実装を書かない。
   `core/risk/`・`core/governance/` 配下の変更時は risk-auditor サブエージェントで審査する
3. **実弾操作の禁止**: 実弾(live)系の機能・コマンドは Phase 0 に存在せず、追加しない。
   実装・テストはすべて paper モードで行う
4. **秘密情報**: .env・APIキー・Webhook URL をコード・ログ・コミットに含めない
5. **テスト必須**: テスト先行(テストファースト)は全モジュールの原則。とくに
   `core/risk/` と `core/execution/` の変更は**必須**。
   `python -m scripts.cli test` が緑になるまで完了と言わない(risk はカバレッジ90%ゲート)
6. **すべての発注に decision_id**: 根拠(trade_decisions)へ遡及できない注文経路を作らない
7. **fail-closed(No Policy, No Trade)**: 必須ポリシー(P-01〜P-04)が active でない領域では
   発注を拒否する実装を維持する。たたき台の数値を「既定値」としてハードコードしない —
   値は常に決裁済みポリシーから読む(キー欠落も拒否)
8. **prototype/ を編集しない**(独立した参照資料)。`local/`・`sharepoint/` の生成物、
   `config/policies/`・`config/generated/`・`var/` を開発作業で手編集しない

## アーキテクチャ要約

- **L1 実行層(常駐・決定的)**: `core/` + `bots/`。
  経路は固定: 戦略 on_bar → **trade_decisions 起票 → risk_guard.check(唯一の関門)→
  executor.submit(RiskApprovedOrder 型のみ受理)**。bots/ から core/exchange・core/execution を
  直接 import しない(テストで検査される)
- **ガバナンス**: `core/governance/`。PolicyRegistry(YAML真実源 + DB監査ミラー)、
  decision_gate(不変条項reject / 委任内自動適用 / 決裁キュー回送)
- **マルチアセット基盤**: 全銘柄は `config/instruments/` + `core/market/`。
  資産クラス固有知識はブローカーアダプタ(`core/exchange/`)に閉じ込める。
  Phase 0 の実装は paper(暗号資産)のみ。実装順は ①暗号資産 → ②IBKR → ③国内株
- **L2 知能層(API)/ L3 自動化**: Phase 1 以降(`agents/`・news 3段フィルタ・council_runner・
  feedback 自動化は未実装。先回りで作らない)
- **会議体**: Claude Code 上のシナリオ(scenarios/council.md)として動く(ADR-0001 §6)

## よく使うコマンド(Windows / venv)

`tc` ランチャ(.exe シム)がブロックされる環境があるため `python -m scripts.cli` 形式を標準とする:

```
.venv\Scripts\python.exe -m scripts.cli test            # 全テスト(--fast / --risk)
.venv\Scripts\python.exe -m scripts.cli db init         # DB初期化
.venv\Scripts\python.exe -m scripts.cli paper --bot dummy_rw   # ペーパーBOT起動(常駐)
.venv\Scripts\python.exe -m scripts.cli watchdog        # 死活監視(常駐・別コンソール)
.venv\Scripts\python.exe -m scripts.cli status          # キル/ポリシー/heartbeat/建玉
.venv\Scripts\python.exe -m scripts.cli kill            # キルスイッチON(解除 resume は人間専用)
.venv\Scripts\python.exe -m scripts.cli policy list|show|sync|record --file <yaml>
.venv\Scripts\python.exe -m scripts.cli approve|reject|defer <proposal_id>
.venv\Scripts\python.exe -m scripts.cli kpi             # KPI + 根拠連鎖検証
.venv\Scripts\python.exe -m scripts.cli snapshot        # DB整合スナップショット(VACUUM INTO)
.venv\Scripts\python.exe -m scripts.cli council log --session-id <id> --kind <kind> --minutes <path>
```

キルスイッチのフラグファイル: `var/run/KILL`(設計書の /var/run/... の読み替え。ADR-0001)

サンドボックス: `$env:TC_VAR_DIR="var-sandbox"` で実行時生成物(DB・KILL・ログ)一式を
別ディレクトリへ差し替えてボットを並走できる(作って壊す。docs/05 §3.3、ADR-0004)。
プロセス起動前に設定し、検証後はディレクトリごと削除する。

## コーディング規約

- Python 3.12 / asyncio。全公開関数に型ヒント。pydantic でLLM出力・config を検証
- 取引所依存は `core/exchange/` のアダプタ内に閉じる。bots/ から直接取引所APIを呼ばない
- 例外は握りつぶさない: 異常は incidents テーブルに記録 + notifier 通知
- 設定値のハードコード禁止: 技術設定は `config/system.yaml`、運用ポリシーはレジストリへ
- パスは pathlib + プロジェクトルート相対(`core/config.py` に集約)。POSIX 依存を書かない
- Conventional Commits(例: `feat(core/risk): ...` / `docs(scenarios): ...`)

## ドキュメント同期ルール

仕様・機能を変更したら: `docs/`(一次資料 01〜05。**直接改訂してよい**。大きな判断の経緯は
ADR に記録)→ `DOCS.md` → `REQUIREMENTS.md` → `FEATURES.md` → `TESTCASES.md` を併せて
更新する。**ドキュメント駆動**: docs の改訂は実装に先行させる(docs/05 §1)。
`core/db/models.py` の変更時は `docs/04_データベース設計書.md` を必ず併せて更新する。
詳細は `DEVELOPMENT.md`。

## バックログ運用(アジャイル)

タスク・アイデアは `BACKLOG.md`(BL-NNN)で一元管理する。開発作業の開始時に
「今スプリント」へ移動し、完了時に「完了」へ移す。会話で出た将来アイデアは Icebox に
追記する。ポリシー決裁が必要なものは [要決裁] タグを付け docs/03 のアジェンダと連動させる。

## ディレクトリ案内

`docs/`(仕様・ADR)、`config/`(system.yaml・policies・generated・instruments・bots)、
`core/`(governance・risk・market・exchange・execution・runner・notify・db)、`bots/`(戦略)、
`feedback/`(KPI)、`scenarios/`(会議・合議等のプロトコル)、`scripts/`(CLI・LLMブリッジ・hooks)、
`tests/`、`local/`・`sharepoint/`(シナリオ入出力)、`var/`(実行時生成物・gitignore)、
`prototype/`(MAGIプロトタイプ・編集禁止)

## 現在のフェーズ

**Phase 0(基盤構築)— 実装完了、第0回意思決定会議待ち。**
完了条件(設計書 §9): 第0回会議で ★P-01〜P-04 を決裁 → fail-closed 解除 →
ペーパーBOT 1体の24時間無人稼働 + 全注文の根拠付きDB記録 + risk テスト緑。
会議の開催は「第0回会議を開催」と発話する(→ scenarios/council.md)。
