# DEVELOPMENT — Accounting 開発ガイド

モノレポ規約は [../CLAUDE.md](../CLAUDE.md)、本プロジェクトのルール・モードは [CLAUDE.md](CLAUDE.md) を参照。
ここでは開発サイクル・テスト・コーディング規約をまとめる。

## 環境

- Python 実行環境は **ルート共有 `.venv`**。本プロジェクトのテストは Accounting dir から:
  ```powershell
  cd Accounting
  ..\.venv\Scripts\python.exe -m pytest -q          # 直接
  ..\.venv\Scripts\python.exe -m scripts.cli test   # CLI 経由(同じ)
  ```
- **editable install はしない**。Accounting と TradeCouncil は同名のトップレベル package
  (`core` / `scripts`)を持つため、共有 `.venv` に両方を editable で入れると衝突する。
  各プロジェクト dir を cwd にして実行すれば cwd 解決で正しく import される(ルート `conftest.py` も
  Accounting を sys.path に足さない — TradeCouncil の `core` を隠さないため)。
- シークレットはルート共有 [`../.env`](../.env.example)。解決順: 環境変数 → ルート `.env` →
  `.claude/settings.local.json` の env。

## 開発サイクル(ドキュメント駆動)

仕様・機能を変えたら、まず docs を直すこと(実装に先行 — 一次資料は [docs/](docs/))。

1. `docs/`(accounting-policy ほか。**直接改訂してよい**。会計ポリシー改定は適用開始日・理由を明記)
2. `DOCS.md` → `REQUIREMENTS.md` → `FEATURES.md` → `TESTCASES.md` を併せて更新
3. テスト先行で実装(`tests/` に先に書く)→ `python -m scripts.cli test` 全緑で完了
4. コミット(Conventional Commits。例 `feat(Accounting): ...` / `docs(Accounting): ...`。
   会計ポリシー改定時は本文に `policy: <変更点>(適用開始日: YYYY-MM-DD, 理由: ...)`)

## テスト

足場(Phase 0)のテスト:

| ファイル | 検証 |
|---|---|
| `tests/test_smoke.py` | パッケージ import の健全性 |
| `tests/test_decoupling.py` | `core/` が `Magi`/`TradeCouncil` を import しない(削除可能性 — ADR-0011) |
| `tests/test_docs_lint.py` | `docs/accounting-policy.md` に「適用開始日」が存在し、相互矛盾の自明な記述が無い |

## コーディング規約

- Python 3.12 / 全公開関数に型ヒント。
- **依存規約(ADR-0011)**: `core/` は **stdlib + 自前モジュールのみ**(`Magi`/`TradeCouncil` を import しない)。
  `shared/` への依存は `scripts/`・`scenarios/` のみ許可(LLM 召喚・SharePoint・Office 変換)。
- 設定値のハードコード禁止: 技術設定は `config/system.yaml`、勘定科目マッピングは `config/accounts.yaml`、
  会計の判断方針は `docs/accounting-policy.md`(正本)。
- 環境変数はドメイン別プレフィックス(`SHAREPOINT_*` / `BRIDGE_*` / `OFFICE_*` ・プロバイダ標準キー)。
  プロジェクト名を env に入れない。プロジェクト別の値は config(`sharepoint.config.json` 等)で分ける。
- パスは pathlib + プロジェクトルート相対。POSIX 依存を書かない(Windows 開発)。
- **秘匿情報**(client secret・口座/カード番号・トークン)はコード・ログ・コミットに残さない。
- 例外を握りつぶさない。不可逆操作(送金・資金移動・削除・権限変更・認証情報入力)は実装に持たせない。

## ディレクトリ案内

`docs/`(一次資料・ADR)、`config/`(system.yaml・accounts.yaml)、`core/`(ドメインロジック雛形・zero-dep)、
`scripts/`(CLI・API スパイク・検証ゲート・Claude フック)、`scenarios/`(monthly-review)、
`tests/`、`workspace/`(シナリオ入出力・SharePoint 同期対象・gitignore)、`var/`(実行時生成物・gitignore)。
共通層は [`../shared/`](../shared/)。
