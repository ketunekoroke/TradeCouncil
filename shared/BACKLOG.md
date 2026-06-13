# BACKLOG — shared(共通ツール層)

共通基盤の作業・アイデア。ID プレフィックス `SH-`。モノレポ全体は [../BACKLOG.md](../BACKLOG.md)。

## アイデア / Icebox

- SH-001 `find_secret`(秘密スキャン)を shared と TradeCouncil の両 hook_common で共有する仕組み(現状は同一コピー2つ。テストで一致を保証する案)
- SH-002 ブリッジに Anthropic 直叩き backend を追加(現状 claude はサブエージェント召喚のみ)
- SH-003 sharepoint mirror の dry-run(`--plan` で push/delete 予定だけ表示)
