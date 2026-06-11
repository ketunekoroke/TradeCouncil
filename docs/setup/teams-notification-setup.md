# セットアップ手順書: Microsoft Teams 通知(Power Automate Workflows)

| 項目 | 内容 |
|---|---|
| 日付 | 2026-06-11 |
| 対象 | TradeCouncil の通知(FR-7.1)を Microsoft Teams で受信するためのセットアップ |
| 所要時間 | 約10分 |
| 関連 | ADR-0002 / DOCS.md §9(要約版)/ core/notify/notifier.py(実装) |

> **重要(2025年末の仕様変更)**: 従来の「Incoming Webhook」コネクタ(チャネル設定から
> 追加するタイプ)は **Microsoft により廃止済み**で、新規作成できない。
> 本手順書の **Power Automate Workflows** 方式が現行の標準ルートである。

---

## 1. 前提条件

| 項目 | 要件 |
|---|---|
| Microsoft 365 アカウント | 組織アカウント(Teams が使えること)。個人用 Teams(無料版)は Workflows 非対応 |
| Power Automate ライセンス | ほとんどの M365 ビジネスプラン(Business Basic 以上 / E1 以上)に標準付属。今回使うのは標準コネクタのみで **Premium ライセンスは不要** |
| 投稿先 | 通知を受け取るチーム/チャネルを事前に決めておく(例: チーム「TradeCouncil」> チャネル「運用通知」)。なければ先に Teams で作成する |
| 権限 | 投稿先チャネルのメンバーであること(フロー作成者 = 投稿者として動作する) |
| ローカル | リポジトリのセットアップ済み(README クイックスタート)。`.env` ファイルが存在すること |

## 2. フローの作成

方法A(Teams 内で完結・推奨)と方法B(Power Automate ポータル)のどちらでもよい。
作成されるフローは同一。

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

コピーした URL を、リポジトリ直下の `.env` に設定する:

```dotenv
TEAMS_WORKFLOW_URL=https://prod-XX.japaneast.logic.azure.com:443/workflows/...&sig=XXXX
```

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

# 2) キルスイッチを ON にする(warning 通知が発火する)
.venv\Scripts\python.exe -m scripts.cli kill
```

- 数秒以内に、指定したチャネルへ **黄色ヘッダの Adaptive Card**
  (`[WARNING] TradeCouncil` + メッセージ)が届けば成功
- 確認後、**人間の手で**解除する(エージェントからの resume は hooks がブロックする):

```powershell
.venv\Scripts\python.exe -m scripts.cli resume
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
| `notify(fallback)` がログに出る | `TEAMS_WORKFLOW_URL` が未設定(または空)。`.env` の記載とファイル位置(リポジトリ直下)を確認 |
| HTTP 401 / 403 | URL の `sig=` が欠落・改変されている。フローから URL を再コピーする(`&` を含む完全な URL であること。PowerShell で扱う際は引用符で囲む) |
| HTTP 404 | フローが削除されたか無効化されている。Workflows アプリでフローの状態(オン/オフ)を確認 |
| しばらく使っていたら止まった | ①フロー所有者の退職・ライセンス変更(→ §7)②90日間トリガーされなかったフローは自動で無効化されることがある → フローをオンに戻す |
| カードのレイアウトが崩れる | Adaptive Card v1.4 を使用(実装済み)。古い Teams クライアントの場合は更新する |

## 7. 運用上の注意

- **フローは作成者個人に紐づく**。作成者が組織を離れる・ライセンスを失うと停止する。
  長期運用では、フローの **[共有]** で共同所有者を追加しておくと安全
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
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

Discord はプレーンテキスト通知(Adaptive Card 非対応)。両方の URL を設定しておけば、
`backend` の1行を切り替えるだけで移行できる。
