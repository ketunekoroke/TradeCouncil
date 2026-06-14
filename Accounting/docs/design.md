# システム設計 — 会計経理支援システム

経理処理・ポリシー運用・API テストを行うエージェント基盤の設計。会計の判断方針は
[accounting-policy.md](accounting-policy.md)(正本)、会社特有論点は [company-specific.md](company-specific.md)、
落とし穴は [caveats.md](caveats.md)、運用は [manual.md](manual.md) を参照。

## このシステムの役割

- 会計ポリシー・会社特有の論点・注意点・運用マニュアルの **正本** を docs に持つ。
- 証憑の取り込み → 抽出 → 検証 → 経費登録 → 会計連携 → 仕訳調整を半自動で支援する。
- 利用者(代表者)が唯一の決裁者。エージェントは抽出・検証・下準備まで(提案止まり)。
- 運用フロー: **ローカルの Claude Code で改定 → コミット → GitHub へ push**。
  **自動処理サーバ(将来 AWS)は pull して最新ポリシーで動作** する。

## アーキテクチャ(データフロー)

```
取り込み  → 抽出      → 検証ゲート       → Teams 確認  → 経費登録      → 会計連携        → 仕訳調整
ingest      extract      gate               (人間)        register        reconcile         adjust
(紙/メール/  (構造化・     (為替・税区分・     (NG/低信頼     (MF 経費 API・   (相関キーで       (勘定科目・
 アップ)     確信度)       証憑3項目)         のみ提示)      摘要に相関キー)   仕訳突合 →        税区分・摘要)
                                                                         mf_journal_id)
```

- **検証ゲートは LLM 出力が直接 API に到達する経路を作らない**。抽出値は必ずゲートと人間確認を経る。
- 不可逆操作(送金・資金移動・削除・権限変更・認証情報入力)は系から排除し、人間が行う。

## コンポーネント(`core/` 予定構成 — Phase 1 以降)

| モジュール | 役割 |
|---|---|
| `core/ingest` | 取り込み・ステージング・重複検知 |
| `core/extract` | 証憑の構造化(日付・金額・通貨・取引先・取引内容 + 確信度) |
| `core/policy` | 適用開始日で版を選び、消費税(内外判定・税区分)・為替換算を当てる |
| `core/gate` | 検証ゲート(`scripts/check_compliance.py` と共有) |
| `core/register` | MoneyForward 経費 API への登録(摘要に相関キー)。不可逆操作はしない |
| `core/reconcile` | 相関キーで会計仕訳を突合し `mf_journal_id` を確定、仕訳調整 |

`core/` は **stdlib + 自前モジュールのみ**(ADR-0011 の削除可能性)。LLM 召喚・SharePoint・Office 変換は
`scripts/` / `scenarios/` 側で共通層 [`../../shared/`](../../shared/) を使う。

## MoneyForward 連携

- 対象: クラウド経費(証憑・経費登録・電帳法保存)/ クラウド会計(仕訳・勘定科目)/ クラウドBox(保存)。
- **正確なエンドポイント/パラメータは製品ドメインの Swagger で確認する**(archive されたドキュメントは使わない —
  [caveats.md](caveats.md))。

### API 設定の仕組み

接続設定は **非秘密と秘密を分離** して持つ(ADR-0011 / SharePoint と同じ作法)。

| 種別 | 置き場所 | 例 |
|---|---|---|
| 非秘密(OAuth/API の URL・scopes・client_id・enabled) | [`config/moneyforward.config.json`](../config/moneyforward.config.json) | `oauth.token_url`, `api.accounting_base` |
| 秘密(client_secret)・上書き | ルート共有 `.env`(`MONEYFORWARD_*`) | `MONEYFORWARD_CLIENT_SECRET` |

- ローダ: [`core/moneyforward.py`](../core/moneyforward.py) の `load_config()` → `MoneyForwardConfig`。
  各フィールドの解決順は **`MONEYFORWARD_<env_prefix>_<FIELD>`(env)→ config の値 → `MONEYFORWARD_<FIELD>`(env)**
  (`env_prefix=AC`)。env の解決は [`core/config.py`](../core/config.py)(環境変数 → ルート `.env` →
  `.claude/settings.local.json`。zero-dep)。
- 確認: `python -m scripts.cli mf config`(秘密はマスク表示)。`--check` で必須項目未設定なら exit 1(pre-flight / CI 用)。
- 疎通確認: `scripts/spike_moneyforward.py`(設定を使い OAuth → offices。最初に offices を開く。手動実行・実 creds 必要)。
- ドメイン別プレフィックス `MONEYFORWARD_*` は接続先で名付ける(プロジェクト名を使わない。`BYBIT_*` と同じ作法 — ADR-0011)。

## セキュリティ

- 秘匿情報(Client Secret / トークン)は環境変数(ルート共有 `.env`)から読む。コード・コミット・ログに残さない。
- 証憑の中身(口座番号・カード番号)をログに残さない。
- 海外アクセス経路の保護(VPN/IP 制限)。認証情報の入力はエージェントにさせない。

## 自動処理サーバ(将来)

- 将来 AWS に配置する。**Git は一方向**(開発 push → 本番 pull)。詳細は
  [adr/0001-aws-hosting.md](adr/0001-aws-hosting.md)(方針のみ・実装は別フェーズ)。

## 遵守の強制(重要)

CLAUDE.md と本 docs は **利言(強制ではない)**。絶対ルールは pre-commit / CI / PreToolUse フックで強制する。
タイミングと方法は [compliance-checklist.md](compliance-checklist.md) と [../CLAUDE.md](../CLAUDE.md) の遵守チェック表。
