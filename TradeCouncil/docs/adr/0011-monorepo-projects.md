# ADR-0011: モノレポ3層再編(Magi / TradeCouncil / shared)

| 項目 | 内容 |
|---|---|
| 日付 | 2026-06-13 |
| ステータス | 承認済み(決裁権者の計画承認による) |
| 関連 | ADR-0001(Phase0 構成)/ ADR-0009(workspace 同期)/ ADR-0010(docs ミラー)/ ルート CLAUDE.md |

## 背景

MAGI 由来の汎用機能(ブレスト・資料レビュー・合議・人格テスト)は他プロジェクトでも開発
ツールとして使いたい。一方、プロジェクトごとにリポジトリを分けるのは煩雑。単一リポジトリの
ルートに売買(core/bots/config)と MAGI(scenarios/personas/bridges)が混在しており、
どちらが汎用でどちらが売買固有かが曖昧だった。

要望: **1リポジトリ・1ブランチ内でディレクトリ単位の疎結合プロジェクトとして管理**し、
各プロジェクトに CLAUDE.md を置いてそのディレクトリ単位で開発する。**あるプロジェクトの
ディレクトリを消しても他は動く**ことを保証する。

調査で判明した土台: TradeCouncil の `core/`(売買の実行時コード)は `scripts/`(MAGI ブリッジ)を
**一切 import していない** — 実行時の結合は元から無く、MAGI ブリッジを使うのは Claude 駆動の
council シナリオだけ。全パス解決が「ファイルの2階層上 = リポジトリルート」前提のため、
サブディレクトリへ移すと各 dir が自然に新しいプロジェクトルートになる。

## 決定事項

### 1. 3層構成

| 層 | 役割 |
|---|---|
| `Magi/` | 汎用マルチエージェント基盤(3人格・4シナリオ・docs・workspace) |
| `TradeCouncil/` | 自動売買(core/bots/config/feedback・5ペルソナ・council シナリオ) |
| `Accounting/` | 会計経理支援(core/config・2ペルソナ・monthly-review シナリオ・MoneyForward 連携)。2026-06-14 追加 |
| `shared/` | 共通ツール(LLMブリッジ・SharePoint・office変換・git ライフサイクルフック)。path 起動・pip 不要 |

第一階層(ルート)は**全プロジェクトに共通する事項だけ**を持つ(共有 .venv/.env、ルーター
CLAUDE、薄い全体管理表、ruff/pytest 集約)。各プロジェクトは自前の CLAUDE.md・docs・
管理表・workspace を持つ。

### 2. 依存グラフと疎結合の保証

- `Magi` → `shared` のみ。`TradeCouncil`(実行時 core)→ 依存なし。council シナリオ → `shared`。
  `Accounting`(実行時 core)→ 依存なし。monthly-review シナリオ → `shared`
- **各プロジェクト(`Magi` / `TradeCouncil` / `Accounting`)は相互非依存**。`Magi/` を削除しても
  売買・会計は `tc test`・`ac test` 緑のまま(MAGI への実行時依存ゼロ)。`TradeCouncil/` や
  `Accounting/` を削除しても他は無傷。各 `core/` の import グラフに他プロジェクト参照なし
- `shared/` は全プロジェクトの土台。削除すると外部 LLM/SharePoint 連携が縮退するが、各プロジェクト
  固有ロジックは生存する
- 注: `Accounting` と `TradeCouncil` は同名のトップレベル package(`core`/`scripts`)を持つため、
  共有 `.venv` への editable install はしない。各プロジェクト dir を cwd にして `python -m ...` で
  実行する(ルート `conftest.py` も Accounting を sys.path に足さない — TradeCouncil の `core` を隠さない)

### 3. パス解決(共有ルートとプロジェクトルートの分離)

- シークレットはルート共有 `.env`。`core/config.py` は `.git` を上方向探索してルート `.env` を
  読む。`shared/bridge_common.py` は shared がルート直下のため従来どおりルート `.env` に一致
- `shared/sharepoint.py` は git/差分の基点をリポジトリルートに保ちつつ、config/workspace/var/
  mirror 状態を `--project <dir>`(既定 cwd)で受ける。`git_mirror.paths` はリポジトリ相対
  (例 `TradeCouncil/docs`)、`remote` は `<Project>/Docs`

### 4. git フックはリポジトリ単位

git は1リポジトリ1組のフックしか持てないため、ライフサイクルフックは `shared/hooks` に集約。
`post-commit`/`pre-push` は**全プロジェクトを走査**して各 docs を per-project でミラーする
(ADR-0010・fail-open)。`pre-commit` の秘密スキャンは repo 全域、ポリシー/generated 検査は
`config/policies`・`config/generated` をパスに含むファイル(どのプロジェクト配下でも)。
Claude ツールフック(block_live / protect_paths / post_edit_test)は売買開発の保護として
`TradeCouncil/.claude` に置く。`hook_common` は安全フックが shared 削除で壊れないよう両側コピー。

## 却下した代替案

| 代替案 | 却下理由 |
|---|---|
| プロジェクトごとに別リポジトリ | 要望どおり「煩雑」。共通ツールの版ずれ・横断変更が重い |
| ブリッジを各プロジェクトに複製 | 二重メンテ。単一ソースの shared が保守容易 |
| workspace/sharepoint をルートで共有 | per-project 化で疎結合を徹底(一方を消しても他方の入出力が無傷)。決定どおり分離 |
| プロジェクト別 .venv | 依存は分かれるが Windows で環境構築が2重。共有 .venv が単純で既存 settings と整合 |

## 影響・注記

- `prototype/` は削除(取り込み済み・新 Magi が正本。git 履歴に残る。旧 BL-039 クローズ)
- 移動は `git mv` 主体で履歴を保持(`git log --follow` で継続)
- 売買196件 + 共通35件のテストが緑。`core` の import グラフに `shared`/`Magi` 参照なし
- 将来 `Magi` を別リポジトリへ切り出す場合は `git subtree split`(shared 同梱が必要)— MR-002
