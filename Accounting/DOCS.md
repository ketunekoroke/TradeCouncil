# DOCS — Accounting 一次資料の索引

会計に関わる作業時は、以下を必ず参照する(正本 = source of truth)。

| ドキュメント | 役割 | 強制レベル |
|---|---|---|
| [docs/accounting-policy.md](docs/accounting-policy.md) | 会計ポリシー(消費税・為替・証憑・勘定科目・経費の期間性)。**適用開始日つき** | 利言(フックで強制) |
| [docs/company-specific.md](docs/company-specific.md) | 会社特有の論点(一人法人・代表者海外在住・適格請求書発行事業者=売上側・2割特例) | 利言 |
| [docs/caveats.md](docs/caveats.md) | 注意点・落とし穴(経過措置の無関係性・strict_invoice_mode・API 可用性 等) | 利言 |
| [docs/manual.md](docs/manual.md) | 運用マニュアル(日次フロー・Teams 確認・月次レビュー・決算前・エラー対応) | 利言 |
| [docs/compliance-checklist.md](docs/compliance-checklist.md) | 遵守チェック(タイミング別・強制レベル別) | 自動/CI/フック |
| [docs/design.md](docs/design.md) | システム設計(役割・アーキテクチャ・MoneyForward 連携・セキュリティ) | 参考 |
| [docs/adr/0001-aws-hosting.md](docs/adr/0001-aws-hosting.md) | AWS ホスティング方針(将来フェーズ・方針のみ・実装なし) | 参考 |

> **重要(公式仕様)**: CLAUDE.md と参照ドキュメントは「利言(コンテキスト)」として読み込まれ、**強制ではない**
> (出典: https://code.claude.com/docs/en/memory )。絶対に破ってはならないルールは Git の pre-commit /
> GitHub Actions(CI)/ PreToolUse フックで強制する(→ compliance-checklist.md)。
