# シナリオ — Accounting

Claude Code 上で動く半自動ワークフロー。LLM 召喚は共通層ブリッジ([`../../shared/`](../../shared/))経由
(`python ../shared/ask_openai.py --system-file .claude/agents/<name>.md`)。人格は
[`.claude/agents/`](../.claude/agents/)(`accountant` / `tax-reviewer`)。

| シナリオ | 役割 | 状態 |
|---|---|---|
| [monthly-review.md](monthly-review.md) | 月次レビュー / 経費登録合議(取り込み→抽出→検証→Teams確認→登録→会計連携→調整) | 雛形(Phase 0) |

> Phase 0(足場)では、シナリオは設計(docs/manual.md・design.md)に沿った手順の案内に留め、
> API への書き込み・不可逆操作は自動実行しない。
