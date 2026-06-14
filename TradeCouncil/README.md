# TradeCouncil — マルチエージェント自動売買ガバナンス・フレームワーク

複数の売買BOT(Python常駐)を、**ペルソナ・エージェント群が提案・審議し、利用者が
唯一の決裁権者として決定し、決定だけがシステムに反映される**ガバナンス構造で運用する
フレームワーク。モノレポの1プロジェクト([../README.md](../README.md) / ADR-0011)で、汎用
シナリオ・人格基盤は `../Magi/`、共通ツール(LLMブリッジ・SharePoint)は `../shared/` にある。

> 一次成果物は「特定の取引ルール」ではなくガバナンスの構造そのもの。
> 具体的な数値(リスク上限・レバレッジ等)はすべて**会議+決裁**で決まり、
> 決裁されるまでシステムは **fail-closed(発注拒否)** で動く。

## ドキュメントマップ

| 知りたいこと | 読むファイル |
|---|---|
| 最短で動かす | 本書(下のクイックスタート) |
| 全体仕様・運用ガイド | [DOCS.md](DOCS.md) |
| 正式仕様(一次資料) | [docs/01_要件定義書.md](docs/01_要件定義書.md) / [docs/02_基本設計書.md](docs/02_基本設計書.md) / [docs/03_運営規程・第0回アジェンダ.md](docs/03_運営規程・第0回アジェンダ.md) |
| 要件・機能・テストの管理表 | [REQUIREMENTS.md](REQUIREMENTS.md) / [FEATURES.md](FEATURES.md) / [TESTCASES.md](TESTCASES.md) |
| 開発の作法 | [DEVELOPMENT.md](DEVELOPMENT.md) / [CLAUDE.md](CLAUDE.md) |
| 会議・合議シナリオ | [scenarios/README.md](scenarios/README.md) |

## クイックスタート

### 1. セットアップ(Windows / Python 3.12)

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m scripts.cli db init
.venv\Scripts\python.exe -m scripts.cli hooks install   # git フック導入(秘密・ポリシー検査 + docs の SharePoint ミラー)
copy .env.example .env                                   # 通知(Teams/Discord)を使う場合は URL を記入(手順: DOCS.md §9)
.venv\Scripts\python.exe -m scripts.cli test             # 全テストが緑になることを確認
```

### 2. 第0回意思決定会議(取引解禁の鍵)

リポジトリ直下で `claude` を起動し、**「第0回会議を開催」** と発話する。
ペルソナ5名(マクロ/モメンタム/逆張り/クオンツ/リスク管理)が審議し、あなたの決裁で
必須ポリシー ★P-01〜P-04 が `config/policies/` に生成される。
これが決裁されるまで、システムは1件も発注しない(No Policy, No Trade)。

### 3. ペーパーBOT の24時間稼働試験(Phase 0 の完了条件)

```powershell
powercfg /change standby-timeout-ac 0    # スリープ無効化(24h試験のため)
# コンソール1:
.venv\Scripts\python.exe -m scripts.cli paper --bot dummy_rw
# コンソール2:
.venv\Scripts\python.exe -m scripts.cli watchdog
# 確認(随時):
.venv\Scripts\python.exe -m scripts.cli status
.venv\Scripts\python.exe -m scripts.cli kpi      # 全注文の根拠連鎖を検証
# 緊急停止:
.venv\Scripts\python.exe -m scripts.cli kill
```

### 4. MAGI シナリオ(合議・資料レビュー・ブレスト)

リポジトリ直下の `claude` でそのまま使える(例:「議題: ○○についてどう思う?」)。
OpenAI / Gemini 人格を使う場合は `.env` に API キーを設定する(シークレットは
通知 URL・SharePoint 認証も含め `.env` に集約。`.env.example` 参照)。詳細は [DOCS.md](DOCS.md)。

## CLI 一覧(`python -m scripts.cli ...`)

| コマンド | 内容 |
|---|---|
| `test [--fast\|--risk]` | テスト実行(--risk はカバレッジ90%ゲート) |
| `db init` | DB初期化(SQLite WAL) |
| `paper --bot <id>` | ペーパーBOT起動(常駐) |
| `bot new <bot_id> --strategy <key>` | 戦略雛形4ファイル一括生成(開発フロー: docs/06、カタログ: docs/strategies/) |
| `watchdog` | heartbeat 監視(常駐) |
| `status` / `kpi` | 状態一覧 / KPI+根拠連鎖検証 |
| `snapshot [--output <path>]` | DBの整合スナップショット(VACUUM INTO・バックアップ/本番閲覧用) |
| `kill [--close-positions]` / `resume` | キルスイッチ ON / 解除(resume は人間専用) |
| `policy list\|show\|sync\|record --file <yaml>` | ポリシーレジストリ操作(record が唯一の適用経路) |
| `approve\|reject\|defer <proposal_id>` | 決裁キューへの決裁 |
| `council log` / `hooks install` | 会議の開催記録 / git フック導入 |

## 安全設計(要点)

- **LLM非執行**: 発注経路は 戦略 → 根拠起票 → risk_guard → executor の決定的コードのみ
- **fail-closed**: 必須ポリシー未決裁の領域では発注を拒否(ポリシーのキー欠落でも拒否)
- **全注文に decision_id**: 注文 → 根拠 → 一次データまで遡及可能(`kpi` で機械検証)
- **キルスイッチ**: `kill` / `var/run/KILL` を置く / どちらでも全BOT即時停止

**免責**: 自動売買は元本を失うリスクがある。本システムは利益を保証しない(docs/01 §8 必読)。

## リポジトリ構成

```
TradeCouncil/
├── docs/          正式仕様(一次資料)+ ADR(main の内容が SharePoint Docs/ へ自動ミラー — ADR-0010)
├── config/        system.yaml / policies(レジストリ)/ generated / instruments / bots
├── core/          L1実行層: governance / risk / market / exchange / execution / runner / notify / db
├── bots/          戦略(core.exchange への直接アクセス禁止)
├── feedback/      KPI集計
├── scenarios/     council.md(意思決定会議)
├── scripts/       tc CLI(cli/cli_policy/cli_status)・scaffold_bot・Claude フック
├── tests/         risk はカバレッジ90%ゲート
├── workspace/     council 入出力(SharePoint 連携時は自動 sync — ADR-0009)
└── var/           実行時生成物(DB・キルフラグ・ログ。gitignore)

共通層・他プロジェクト(モノレポ — ADR-0011):
../shared/   LLMブリッジ・SharePoint・office変換・git フック
../Magi/     汎用シナリオ(合議/レビュー/ブレスト/人格テスト)・MAGI 3人格
```
