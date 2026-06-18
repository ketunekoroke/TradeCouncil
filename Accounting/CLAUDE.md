# CLAUDE.md — Accounting(会計経理支援システム)

> このファイルは Claude Code 起動時にコンテキストとして読み込まれるプロジェクト指示。
> 経理処理・ポリシー改定・API テストを行う際の動作モード・参照先・遵守事項をまとめる。

**重要(公式仕様)**: CLAUDE.md と参照ドキュメントは「利言(コンテキスト)」として読み込まれ、**強制ではありません**
(出典: https://code.claude.com/docs/en/memory )。**絶対に破ってはいけないルールは、自然言語の指示ではなく、
Git の pre-commit フック / GitHub Actions(CI)/ PreToolUse フックで強制してください**(→ 遵守チェックの節)。

**これはモノレポの1プロジェクト**(ADR-0011)。汎用シナリオ・LLM ブリッジ・SharePoint・Office 変換は
共通層 [`../shared/`](../shared/) にある。Accounting の `core/`(将来の実行時コード)は `shared` に依存しない
(シナリオの LLM 召喚のみ `../shared/` を使う)。ルーターは [../CLAUDE.md](../CLAUDE.md)。

正式仕様の一次資料(正本): [docs/accounting-policy.md](docs/accounting-policy.md) /
[docs/company-specific.md](docs/company-specific.md) / [docs/caveats.md](docs/caveats.md) /
[docs/manual.md](docs/manual.md) / [docs/runbook-expense.md](docs/runbook-expense.md)(Claude への依頼文言・
認可フロー)/ [docs/compliance-checklist.md](docs/compliance-checklist.md) /
[docs/design.md](docs/design.md)。AWS 方針は [docs/adr/0001-aws-hosting.md](docs/adr/0001-aws-hosting.md)。

---

## ⚠️ 最初に: 動作モードの判定

ユーザーの最初の発言から意図を判定する。

| 兆候 | モード |
|---|---|
| 「経費を登録」「証憑」「仕訳」「月次レビュー」「決算」「税区分」「為替換算」 | **経理処理モード**(monthly-review 等) |
| 「ポリシーを改定」「適用開始日」「会計方針を変更」 | **ポリシー改定モード** |
| 「実装」「編集」「修正」「リファクタ」「テスト」「バグ」、ファイル名・コード概念への言及 | **開発モード** |
| 判別不能・両義的 | **ユーザーに確認** |

> **現在のフェーズ: Phase 0(足場)。** エージェント本体(`core/`)・API スパイク・検証ゲートは雛形([実装予定])。
> 経理処理モードは設計(docs/manual.md・design.md)に沿って手順を案内するに留め、自動実行はしない。

---

## YOU MUST(経理作業時の前提)

- 仕訳・経費登録・抽出・調整に関する判断は、**[docs/accounting-policy.md](docs/accounting-policy.md) に従う**。
  ポリシーと矛盾する指示を受けたら **停止して確認** する。
- ポリシーは **適用開始日** を持つ。**取引日(または処理日)時点で有効なバージョン** のルールを適用する。
  過去取引を新ルールで再計算しない。
- **不可逆操作(送金・資金移動・権限/共有設定の変更・データ削除・認証情報の入力)は実行しない**。人間に促す。
- 税務の最終判断は税理士。エージェントは一次チェック(フラグ)まで。国際課税(居住者/非居住者・PE・
  役員報酬等)は扱わず注意喚起のみ([docs/company-specific.md](docs/company-specific.md))。
- **秘匿情報**(Client Secret / トークン / .env / 口座番号・カード番号)は **コミットしない**。コードに書かず、
  環境変数から読む。ログに証憑の中身を残さない。

---

## 経理処理モード(monthly-review)

**ユーザーからの依頼文言(定型文)と Claude が回す手順・役割分担(認可コード・フロー含む)は
[docs/runbook-expense.md](docs/runbook-expense.md) が正本。** 主な依頼文言: 「Inbox から経費を登録して」
(取込→登録)/「クラウド経費の認証を更新して」(トークン再認可)/「FY20XX(…)を別フォルダで取り込んで」
(過年度取込)/「定期支払いを一覧化して」/「過去分の OCR 誤りを補正して」。**不可逆操作は必ずドライラン
提示 → ユーザー承認の後に `--confirm`**。

[scenarios/monthly-review.md](scenarios/monthly-review.md) のプロトコルに従う。証憑の取り込み → 抽出 →
検証ゲート → Teams 確認 → 経費登録 → 会計連携 → 仕訳調整。LLM 召喚は共通層ブリッジ経由:

```bash
# 例: 人格を gpt-4o で動かす(Accounting/ から。ブリッジは共通層 ../shared)
echo "<入力>" | python ../shared/ask_openai.py \
    --system-file .claude/agents/accountant.md --model gpt-4o
```

人格は `.claude/agents/<name>.md`(`accountant` = 抽出・仕訳ドラフト / `tax-reviewer` = 税務観点のフラグ)。
フロントマターの `backend`(claude|openai|gemini)で振り分ける。詳細は [../shared/README.md](../shared/README.md)。

SharePoint 連携(`sharepoint.config.json` の `enabled`)時は、シナリオ開始時と成果物書き出し後に
`python ../shared/sharepoint.py sync --project .`。`docs/` と管理表は git main → `Accounting/Docs/` の
**一方向ミラー**(コミット/プッシュ時に git フックが自動 — ADR-0010)。

---

## ポリシー改定モード

1. ローカルの Claude Code で `docs/` を改定(**適用開始日・理由** を明記)。
2. 差分レビュー → コミット。要約: `policy: <変更点>(適用開始日: YYYY-MM-DD, 理由: ...)`。
3. push → 自動処理サーバ(将来 AWS)が pull で最新化。
4. 過去取引は取引日基準で旧ルールを維持(再計算しない)。

---

## 開発モード

- **依存規約(ADR-0011)**: `core/` は stdlib + 自前モジュールのみ(`Magi`/`TradeCouncil` を import しない)。
  `shared/` への依存は `scripts/`・`scenarios/` のみ。`tests/test_decoupling.py` が検査する。
- テスト先行。`cd Accounting; ..\.venv\Scripts\python.exe -m scripts.cli test` が緑になるまで完了と言わない。
- 設定値のハードコード禁止: 技術設定は `config/system.yaml`、勘定科目は `config/accounts.yaml`、
  会計の判断方針は `docs/accounting-policy.md`(正本)。
- editable install しない(TradeCouncil と同名 package の衝突回避 — [DEVELOPMENT.md](DEVELOPMENT.md))。
- Conventional Commits(例 `feat(Accounting): ...` / `docs(Accounting): ...`)。
- 詳細は [DEVELOPMENT.md](DEVELOPMENT.md)。

---

## 遵守チェックのタイミングと方法

詳細は [docs/compliance-checklist.md](docs/compliance-checklist.md)。強制レベルを分けて運用する。

| タイミング | 方法 | 強制レベル |
| --- | --- | --- |
| セッション開始時 | 本ファイル(ポリシー)をコンテキスト読込 | 利言 |
| 抽出時 / 経費登録前 / 仕訳調整時 | `scripts/check_compliance.py` の検証ゲート(為替・税区分・証憑)[実装予定] | 自動 |
| コミット時 | pre-commit フックで秘密スキャン + ポリシー文書 lint(適用開始日・矛盾)+ check_compliance | 強制 |
| GitHub push / PR 時 | GitHub Actions(CI)で同等チェック [実装予定]。失敗ならマージ不可 | 強制 |
| 月次 / 決算 | checklist に沿って Claude がサンプル監査 → 税理士確認 | 人 / Claude |
| 危険操作の発生時 | PreToolUse フックで送金・削除・権限変更・鍵入力系をブロック | 強制 |

---

## 現在のフェーズ

**Phase 0(足場)— プロトタイプ由来 docs の移植とプロジェクト構造のみ完了。**
次の着手は [BACKLOG.md](BACKLOG.md)(BL-AC-010 MoneyForward 疎通スパイク → BL-AC-011 検証ゲート → BL-AC-012 core)。
