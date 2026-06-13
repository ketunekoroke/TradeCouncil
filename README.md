# モノレポ — Magi / TradeCouncil / shared

疎結合の複数プロジェクトを**1リポジトリ・1ブランチ**でディレクトリ単位に管理する
モノレポ(ADR-0011)。開発は各プロジェクトの dir へ `cd` して行う。

| ディレクトリ | 役割 | 詳細 |
|---|---|---|
| **[Magi/](Magi/README.md)** | 汎用マルチエージェント基盤(ブレスト・資料レビュー・合議・人格テスト) | [Magi/CLAUDE.md](Magi/CLAUDE.md) |
| **[TradeCouncil/](TradeCouncil/README.md)** | 自動売買ガバナンス・フレームワーク | [TradeCouncil/CLAUDE.md](TradeCouncil/CLAUDE.md) |
| **[shared/](shared/README.md)** | 共通ツール層(LLMブリッジ・SharePoint・office変換・git フック) | — |

## セットアップ(Windows / Python 3.12)

```powershell
python -m venv .venv                                     # ルート共有の venv
.venv\Scripts\python.exe -m pip install -e TradeCouncil[dev]
copy .env.example .env                                   # シークレットを記入(全プロジェクト共有)
cd TradeCouncil; ..\.venv\Scripts\python.exe -m scripts.cli hooks install   # git フック(リポジトリ単位)
```

## 疎結合(削除可能性)

`Magi` ⇎ `TradeCouncil` は相互非依存で、片方のディレクトリを削除しても他方は動作する。
両者は `shared/` を共通の土台として参照する。詳細は [CLAUDE.md](CLAUDE.md) と
[TradeCouncil/docs/adr/0011-monorepo-projects.md](TradeCouncil/docs/adr/0011-monorepo-projects.md)。

## テスト

```powershell
cd TradeCouncil; ..\.venv\Scripts\python.exe -m scripts.cli test   # 売買スイート
.venv\Scripts\python.exe -m pytest shared/tests                   # 共通スイート(ルートから)
```
