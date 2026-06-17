# 開発用サブエージェント(並列開発)

このディレクトリ(リポジトリ root の `.claude/agents/`)の MD は **Claude Code ネイティブのサブエージェント**で、
Magi / TradeCouncil / Accounting / shared 横断で使う開発ヘルパー。`Task`/`Agent` ツールで**並列ディスパッチ**できる。

> 各プロジェクト配下(`<project>/.claude/agents/`)の人格(accountant・balthasar・risk_manager 等)は別系統の
> **共有ブリッジ人格**(`shared/ask_*.py` で召喚=合議/レビュー用)。本ディレクトリの dev-* とは目的が違う。

## ラインナップ

| エージェント | 役割 | 書込 | model |
|---|---|---|---|
| **dev-explorer** | コード探索・「どこで/どう」調査(read-only・file:line で返す) | × | sonnet |
| **dev-implementer** | 1プロジェクトの scoped な実装(規約準拠・テスト先行) | ○ | inherit |
| **dev-tester** | テスト実行と失敗の簡潔報告(read-only) | △(テスト実行のみ) | sonnet |
| **dev-reviewer** | 差分レビュー(正当性・ADR-0011・秘密・規約) read-only | × | inherit |

## 並列ディスパッチの基本

- **1メッセージで複数の Agent 呼び出し**を出すと同時並列に走る(設定不要)。独立な作業はまとめて投げる。
- 同時実行数はシステム上限(概ね `min(16, CPU数-2)`)で自動調整。超過分はキュー。
- 各サブエージェントは独立コンテキスト。**最終メッセージだけが呼び出し元に返る**(途中の探索ログは返らない)。

### 典型パターン

- **探索の扇形展開**: サブシステムごとに `dev-explorer` を並列 → 地図を集約してから実装方針を決める。
- **実装 ∥ レビュー/テスト**: `dev-implementer` で実装しつつ、別途 `dev-reviewer`/`dev-tester` を独立視点で走らせる。
- **横断修正**: 独立ファイル/プロジェクトごとに `dev-implementer` を並列。

### ⚠️ 並列で「書き込む」ときは worktree 隔離

複数の `dev-implementer` が**同じ作業ツリーを同時編集すると衝突**する。並列で書き込むなら、各エージェントを
`isolation: "worktree"` で起動して隔離コピー上で作業させる(変更が無ければ自動破棄)。
読み取り系(explorer/tester/reviewer)は隔離不要。

## 規約(全 dev-* が従う)

- **ADR-0011**: `<project>/core/` は stdlib + 自前のみ(他プロジェクト/`shared` を import しない)。`shared` は
  `scripts/`・`scenarios/` からのみ。`tests/test_decoupling.py` が検査。
- テストは共有 root `.venv`。プロジェクト dir から `..\.venv\Scripts\python.exe -m pytest`
  (TradeCouncil は `tc test`、Accounting は `..\.venv\Scripts\python.exe -m scripts.cli test` も可)。
- 秘密は env(root `.env`)から。コミット禁止。Conventional Commits(プロジェクト単位)。
- コミット/プッシュ・不可逆操作は明示指示があるときだけ。
