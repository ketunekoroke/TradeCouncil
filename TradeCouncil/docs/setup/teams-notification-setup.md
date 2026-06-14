# セットアップ手順書: Microsoft Teams 通知(Power Automate Workflows)

| 項目 | 内容 |
|---|---|
| 日付 | 2026-06-11(同日改訂: 専用 Team + 4チャネル構成 — ADR-0003) |
| 対象 | TradeCouncil の通知(FR-7.1)を専用 Team の複数チャネルで受信するためのセットアップ |
| 所要時間 | 約30分(Team 作成 + フロー4本。まず default 1本だけなら約10分) |
| 関連 | ADR-0002 / ADR-0003 / DOCS.md §9(要約版)/ core/notify/notifier.py(実装) |

> **重要(2025年末の仕様変更)**: 従来の「Incoming Webhook」コネクタ(チャネル設定から
> 追加するタイプ)は **Microsoft により廃止済み**で、新規作成できない。
> 本手順書の **Power Automate Workflows** 方式が現行の標準ルートである。

---

## 1. 前提条件

| 項目 | 要件 |
|---|---|
| Microsoft 365 アカウント | 組織アカウント(Teams が使えること)。個人用 Teams(無料版)は Workflows 非対応 |
| Power Automate ライセンス | ほとんどの M365 ビジネスプラン(Business Basic 以上 / E1 以上)に標準付属。今回使うのは標準コネクタのみで **Premium ライセンスは不要** |
| 投稿先 | 専用チーム「TradeCouncil」を新設する(下記 §1.1) |
| 権限 | 投稿先チャネルのメンバーであること(フロー作成者 = 投稿者として動作する)。チーム作成が組織で制限されている場合は IT 管理者に依頼 |
| ローカル | リポジトリのセットアップ済み(README クイックスタート)。`.env` ファイルが存在すること |

### 1.1 専用 Team とチャネルの作成

1. Teams → [チーム] → **[チームを作成]** → 種類は「その他」、名前 **`TradeCouncil`**、
   プライバシーは **プライベート** を推奨(取引データが流れるため)
2. 作成したチームに以下の **4チャネル** を追加する([…] → [チャネルを追加]):

| チャネル名(表示) | キー | 流すもの | severity 振り分け |
|---|---|---|---|
| 📢 運用通知 | `ops` | 約定・日次サマリ・info 全般 | info(routing) |
| 🚨 アラート | `alerts` | 損失警告・停止イベント・heartbeat 途絶 | warning / critical(routing) |
| 📜 ガバナンス | `governance` | 提案キュー・決裁結果・ポリシー変更・会議開催 | 発火側が明示指定 |
| 📊 レポート | `reports` | 週次 KPI・月次レビュー | 発火側が明示指定 |

> 🚨アラート はチャネル通知設定を「すべてのアクティビティ」にしておくと見逃しにくい。
> チャネル構成の正式決定は第0回会議の P-11 決裁(これはたたき台 — ADR-0003)。
> **全チャネル必須ではない**: URL 未設定のチャネル宛て通知は default(`TEAMS_TC_WORKFLOW_URL`)へ
> フォールバックするため、まず default 1本で始めて後から増やせる。

## 2. フローの作成(チャネルごとに1本、計4本 + 任意で default 用1本)

方法A(Teams 内で完結・推奨)と方法B(Power Automate ポータル)のどちらでもよい。
作成されるフローは同一。**以下の手順をチャネルごとに繰り返す**。

- フロー命名規約: **`TradeCouncil-<チャネルキー>`**(例 `TradeCouncil-alerts`)。
  Workflows アプリの一覧での識別と、障害時の実行履歴調査(§6)のために必須
- default 用(`TEAMS_TC_WORKFLOW_URL`)は 📢運用通知 チャネルのフローと兼用してよい
  (ops の URL を default にも設定する)

### 方法A: Teams の Workflows アプリから(推奨)

1. Teams 左サイドバーの **[…](その他のアプリ)** → **「Workflows」** を検索して開く
   (見つからない場合は [アプリ] → 検索「Workflows」→ 追加)
2. 右上の **[+ 新しいフロー]**(または [Create])をクリック
3. テンプレート検索欄に **「webhook」** と入力し、
   **「Webhook 要求を受信したらチャネルに投稿する」**
   (英語表示: *Post to a channel when a webhook request is received*)を選択
4. 接続確認画面で自分のアカウントにチェックが付いていることを確認 → **[次へ]**
5. 投稿先の **チーム** と **チャネル** を選択 → **[フローを作成]**
6. 完成画面に **HTTP POST の URL** が表示される → **このタイミングで必ずコピーする**
   (例: `https://prod-XX.japaneast.logic.azure.com:443/workflows/.../triggers/manual/paths/invoke?...&sig=XXXX`)

> URL をコピーし損ねた場合: Workflows アプリ → 対象フロー → [編集] →
> トリガー「When a Teams webhook request is received」を展開すると HTTP URL を再表示できる。

### 方法B: Power Automate ポータルから

1. <https://make.powerautomate.com> にサインイン
2. 左メニュー **[テンプレート]** → 検索「webhook」→
   **「Webhook 要求を受信したらチャネルに投稿する」** を選択
3. 以降は方法A の手順 4〜6 と同じ

### 任意: 投稿者表示の調整

テンプレート既定では「フロー作成者のユーザー名」として投稿される。
ボット風に分けたい場合は、フロー編集画面で投稿アクションの **Post as** を
**Flow bot** に変更する(機能上の差はない。見た目の好みで選んでよい)。

## 3. URL の設定(シークレットの取り扱い)

コピーした各フローの URL を、リポジトリ直下の `.env` に設定する:

> env 名は**プロジェクト別プレフィックス**(TradeCouncil = `TC`。system.yaml の `notify.env_prefix`)。
> `TEAMS_TC_WORKFLOW_URL` のように「どのプロジェクトの通知か」が名前で分かる。無印の
> `TEAMS_WORKFLOW_URL[...]` も後方互換で読まれる(ADR-0011)。

```dotenv
# default(必須推奨。未設定チャネルのフォールバック先。ops と兼用可)
TEAMS_TC_WORKFLOW_URL=https://prod-XX.japaneast.logic.azure.com:443/workflows/...&sig=XXXX
# チャネル別(設定したものだけ有効。未設定分は default へフォールバック)
TEAMS_TC_WORKFLOW_URL_OPS=https://...
TEAMS_TC_WORKFLOW_URL_ALERTS=https://...
TEAMS_TC_WORKFLOW_URL_GOVERNANCE=https://...
TEAMS_TC_WORKFLOW_URL_REPORTS=https://...
```

severity からチャネルへの振り分けは `config/system.yaml` の `notify.routing`
(既定: info→ops / warning→alerts / critical→alerts)。

**取り扱い注意 — この URL は秘密情報である:**

- URL 末尾の `sig=...` は **SAS 署名**であり、知っている者は誰でもこのチャネルに
  投稿できてしまう。チャット・ドキュメント・コミットに貼らない
- `.env` は gitignore 済み。万一コードやドキュメントに書いた場合は
  pre-commit フック(`scripts/hooks/hook_common.py` の検出パターン)がコミットをブロックする
- 漏えいした(疑いがある)場合: フローを開いて **トリガーの [URL の再生成]**
  (なければフローを削除して再作成)→ `.env` を新 URL に差し替える

`config/system.yaml` 側は既定で `notify.backend: teams` になっていることを確認する:

```yaml
notify:
  backend: teams            # teams | discord
  min_severity: info        # info | warning | critical
```

## 4. 動作確認

```powershell
# 1) 設定の読み込み確認を兼ねてテストを実行(全緑であること)
.venv\Scripts\python.exe -m scripts.cli test

# 2) キルスイッチを ON にする(warning 通知 → routing 経由で 🚨アラート へ)
.venv\Scripts\python.exe -m scripts.cli kill
```

- 数秒以内に、🚨アラート チャネルへ **黄色ヘッダの Adaptive Card**
  (`[WARNING] TradeCouncil` + メッセージ、フッターに `#alerts`)が届けば成功
- 確認後、**人間の手で**解除する(エージェントからの resume は hooks がブロックする):

```powershell
.venv\Scripts\python.exe -m scripts.cli resume
```

各チャネルの個別疎通はワンライナーで確認できる(カードのフッターの `#<チャネル名>` が
期待どおりのチャネルに届いているかも併せて見る — フローの投稿先誤配線の検出):

```powershell
.venv\Scripts\python.exe -c "from core.notify import get_notifier; get_notifier().send('チャネル疎通テスト', 'info', channel='governance')"
# channel= を ops / alerts / reports に変えて繰り返す
```

届かない場合は §6 トラブルシューティングへ。

## 5. 送信ペイロード仕様(参考)

`core/notify/notifier.py` の `TeamsNotifier` が送る JSON の構造:

```json
{
  "type": "message",
  "attachments": [
    {
      "contentType": "application/vnd.microsoft.card.adaptive",
      "content": {
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
          { "type": "Container", "style": "attention",
            "items": [{ "type": "TextBlock", "text": "[CRITICAL] TradeCouncil" }] },
          { "type": "TextBlock", "text": "<本文>" },
          { "type": "FactSet", "facts": [{ "title": "component", "value": "bot:dummy_rw" }] },
          { "type": "TextBlock", "isSubtle": true, "text": "TradeCouncil Phase 0 (paper) | <UTC時刻>" }
        ]
      }
    }
  ]
}
```

| severity | ヘッダ色(Container.style) |
|---|---|
| info | default(無色) |
| warning | warning(黄) |
| critical | attention(赤) |

curl 等で手動テストしたい場合は上記 JSON をそのまま POST すればよい
(成功時の応答は **202 Accepted**)。

## 6. トラブルシューティング

| 症状 | 原因と対処 |
|---|---|
| カードが届かないが、ログにエラーもない | Workflows は受信時に必ず 202 を返すため、**フロー内部の失敗は送信側から見えない**。Workflows アプリ → 対象フロー → **[実行履歴(28日分)]** で失敗の有無と理由を確認する |
| 実行履歴が「失敗」: チャネルが見つからない | 投稿先チャネルが削除/改名された。フローを編集して投稿先を選び直す |
| `notify(fallback)` がログに出る | `TEAMS_TC_WORKFLOW_URL` が未設定(または空)。`.env` の記載とファイル位置(リポジトリ直下)を確認 |
| HTTP 401 / 403 | URL の `sig=` が欠落・改変されている。フローから URL を再コピーする(`&` を含む完全な URL であること。PowerShell で扱う際は引用符で囲む) |
| HTTP 404 | フローが削除されたか無効化されている。Workflows アプリでフローの状態(オン/オフ)を確認 |
| しばらく使っていたら止まった | ①フロー所有者の退職・ライセンス変更(→ §7)②90日間トリガーされなかったフローは自動で無効化されることがある → フローをオンに戻す |
| カードのレイアウトが崩れる | Adaptive Card v1.4 を使用(実装済み)。古い Teams クライアントの場合は更新する |
| **特定チャネルだけ届かない** | ①`.env` の変数名 typo(`_OPS` / `_ALERTS` 等の綴り)を確認 — URL 未設定チャネルは default へフォールバックするためログに「URL 未設定 → default へフォールバック」の warning が出る ②該当フロー(`TradeCouncil-<key>`)の実行履歴を**フロー個別に**確認 ③カードのフッター `#<チャネル名>` と実際の着信チャネルが食い違う場合はフローの投稿先チャネル設定が誤配線 |

## 7. 運用上の注意

- **フローは作成者個人に紐づく**。作成者が組織を離れる・ライセンスを失うと停止する。
  長期運用では、フローの **[共有]** で共同所有者を追加しておくと安全(**4フローすべてに**実施)
- 通知は**ベストエフォート**であり安全機構ではない(ADR-0002)。
  停止の安全性はキルスイッチ(`var/run/KILL`)と fail-closed が担っており、
  通知が死んでいても取引の安全性は損なわれない
- 通知量を抑えたい場合は `config/system.yaml` の `min_severity` を `warning` 等に上げる
- severity 別の運用ルール(何を即時通知にするか)は **P-11 として第0回会議で決裁**する
  (docs/03 第5章)

## 8. Discord に切り替える場合(予備チャネル)

```yaml
# config/system.yaml
notify:
  backend: discord
```

```dotenv
# .env
DISCORD_TC_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

Discord はプレーンテキスト通知(Adaptive Card 非対応)。両方の URL を設定しておけば、
`backend` の1行を切り替えるだけで移行できる。
