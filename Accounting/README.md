# Accounting — 会計経理支援システム

MoneyForward(クラウド経費 / クラウド会計 / クラウドBox)と連携し、**証憑の取り込み → 抽出
→ 検証ゲート → Teams 確認 → 経費登録 → 会計連携 → 仕訳調整** を半自動で支援するエージェント基盤。
利用者(代表者)が唯一の決裁者で、エージェントは抽出・検証・下準備まで。最終判断と不可逆操作は人間が行う。

**これはモノレポの1プロジェクト**(ADR-0011)。汎用シナリオ・LLM ブリッジ・SharePoint・Office 変換は
共通層 [`../shared/`](../shared/) にある。ルーターは [../CLAUDE.md](../CLAUDE.md)。会計ポリシー・会社特有論点・
注意点の **正本(source of truth)** は [docs/](docs/)(索引は [DOCS.md](DOCS.md))。

> **現在のフェーズ: Phase 0(足場)。** プロトタイプ由来の docs 移植とプロジェクト構造のみ。
> エージェント本体(`core/`)・API スパイク・検証ゲートは雛形([実装予定])。実装着手は [BACKLOG.md](BACKLOG.md) 参照。

## クイックスタート(Windows / 共有 .venv)

```powershell
cd Accounting
..\.venv\Scripts\python.exe -m scripts.cli --help     # CLI(test / hooks install / sync / mirror)
..\.venv\Scripts\python.exe -m scripts.cli test       # pytest(足場の健全性・削除可能性・docs lint)
```

- 正準起動は `python -m scripts.cli`(`ac` シムはブロックされる環境があるため。TradeCouncil と同じ)。
- シークレットはルート共有 [`../.env`](../.env.example)(`copy ..\.env.example ..\.env`)。コミット禁止。
- 会計バックエンドは **MoneyForward 前提**。API の正確なエンドポイントは製品ドメインの Swagger で確認(docs/caveats.md)。

## ドキュメント

| ファイル | 内容 |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Claude Code 起動時のルーター(モード判定・YOU MUST・遵守チェックの段取り) |
| [DEVELOPMENT.md](DEVELOPMENT.md) | 開発サイクル・テスト・コーディング規約 |
| [docs/accounting-policy.md](docs/accounting-policy.md) | 会計ポリシー(**正本**・適用開始日つき) |
| [docs/company-specific.md](docs/company-specific.md) | 会社特有の論点(一人法人・代表者海外在住・2割特例) |
| [docs/caveats.md](docs/caveats.md) | 注意点・落とし穴 |
| [docs/manual.md](docs/manual.md) | 運用マニュアル(日次フロー・月次レビュー) |
| [docs/compliance-checklist.md](docs/compliance-checklist.md) | 遵守チェック(タイミング別) |
| [docs/design.md](docs/design.md) | システム設計 |
| [docs/adr/0001-aws-hosting.md](docs/adr/0001-aws-hosting.md) | AWS ホスティング方針(将来・方針のみ) |
