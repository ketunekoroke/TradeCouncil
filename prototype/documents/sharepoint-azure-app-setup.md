# SharePoint 連携用 Azure アプリ作成マニュアル

MAGI プロトタイプの SharePoint 連携(`scripts/sharepoint.py`)を使うために必要な、
**Microsoft Entra ID(旧 Azure AD)へのアプリ登録**の手順書。非対話の
**クライアントシークレット認証(アプリケーション許可)**を前提とする。

> 関連: 連携の全体像は [`DOCS.md`「9.5 SharePoint 連携」](../DOCS.md)、ファシリテーターの
> 運用は [`CLAUDE.md`「SharePoint 連携」](../CLAUDE.md)、設定の入れ方は
> [`README.md`「3.6 SharePoint連携を使う場合」](../README.md) を参照。

---

## 0. 前提と所要時間

| 項目 | 内容 |
|---|---|
| 必要な権限 | Entra ID で**アプリを登録できる権限**、および `Sites.ReadWrite.All` に
**管理者の同意**を与えられる権限(グローバル管理者 / 特権ロール管理者 / クラウドアプリ管理者 等) |
| 認証方式 | クライアントシークレット(アプリケーション許可。委任ではない) |
| 所要時間 | 約10〜15分 |
| 取得するもの | テナントID / クライアントID / クライアントシークレット の3つ |

> **重要**: 始めるのは「**アプリの登録(App registrations)**」から。「エンタープライズ
> アプリケーション」から始めるとクライアントシークレットを発行する導線がない。アプリを
> 登録すると、対応するエンタープライズアプリ(サービスプリンシパル)は**自動で作成される**。

---

## 1. アプリを登録する

1. [Azure Portal](https://portal.azure.com) または
   [Entra 管理センター](https://entra.microsoft.com) にサインイン。
2. **「Microsoft Entra ID」→「アプリの登録」→「＋ 新規登録」** を開く。
3. 次を入力する:
   - **名前**: 例 `MAGI-SharePoint-Sync`(任意。後から変更可)
   - **サポートされているアカウントの種類**:
     **「この組織ディレクトリのみに含まれるアカウント(単一テナント)」** を選ぶ
   - **リダイレクト URI**: **空欄のままでよい**(クライアントクレデンシャルフローでは不要)
4. **「登録」** をクリック。

登録後の「概要」ページで、次の2つを控える:

| 値 | 概要ページの表示名 | 後で使う環境変数 |
|---|---|---|
| テナントID | **ディレクトリ (テナント) ID** | `MAGI_SHAREPOINT_TENANT_ID` |
| クライアントID | **アプリケーション (クライアント) ID** | `MAGI_SHAREPOINT_CLIENT_ID` |

---

## 2. クライアントシークレットを発行する

1. 作成したアプリの **「証明書とシークレット」→「クライアント シークレット」→
   「＋ 新しいクライアント シークレット」** を開く。
2. **説明**(例 `magi-secret`)と**有効期限**(例 6か月 / 12か月。組織のポリシーに従う)を設定し、
   **「追加」** をクリック。
3. 表示された **「値(Value)」をすぐにコピーする**。

> ⚠️ シークレットの**「値」は作成直後の一度しか全文表示されない**。ページを離れると二度と
> 見られない(再発行が必要になる)。**「シークレット ID」ではなく「値」**の方をコピーすること。

| 値 | 後で使う環境変数 |
|---|---|
| クライアントシークレットの**値** | `MAGI_SHAREPOINT_CLIENT_SECRET` |

> 有効期限が切れると認証に失敗する。期限管理(更新リマインダ)をしておくとよい。

---

## 3. API のアクセス許可を付与する(アプリケーション許可 + 管理者同意)

1. アプリの **「API のアクセス許可」→「＋ アクセス許可の追加」** を開く。
2. **「Microsoft Graph」** を選ぶ。
3. **「アプリケーションの許可(Application permissions)」** を選ぶ
   (**「委任されたアクセス許可」ではない**点に注意)。
4. 検索ボックスに `Sites` と入力し、**`Sites.ReadWrite.All`** にチェック → **「アクセス許可の追加」**。
5. 一覧に戻ったら、**「<テナント名> に管理者の同意を与えます」** をクリックし、確認する。
6. `Sites.ReadWrite.All` の**状態**列が **緑のチェック「付与済み」** になれば完了。

| 許可 | 種別 | 用途 |
|---|---|---|
| `Sites.ReadWrite.All` | アプリケーション | SharePoint ドキュメントライブラリの読み書き(pull / push) |

> **より厳格にしたい場合**: `Sites.ReadWrite.All` はテナント**全サイト**の読み書きに及ぶ。
> 特定サイトだけに絞りたいときは `Sites.Selected`(アプリケーション)を使う。まずは動作確認を
> `Sites.ReadWrite.All` で行い、本番で絞るのが分かりやすい。手順は次の **「3.5 Sites.Selected で
> 対象サイトだけに絞る」** を参照。

---

## 3.5 Sites.Selected で対象サイトだけに絞る(推奨・本番運用)

`Sites.ReadWrite.All` は**テナント内の全サイト**を読み書きできてしまう。MAGI が触るのは
1つ(数個)のサイトだけなので、本番では `Sites.Selected` に絞るのが安全(最小権限)。

### しくみ

`Sites.Selected`(アプリケーション)を付与しただけでは、アプリは**どのサイトにもアクセスできない**。
そのうえで、**サイトごとに**「このアプリに読み/書きを許可する」と明示的にグラント(付与)して
初めてアクセスできる。これにより、許可したサイト以外には一切触れない。

> MAGI 側のコード・設定は変更不要。`sharepoint.py` は同じクライアントシークレット認証のまま動き、
> アクセスできる範囲が絞られるだけ。

### 手順 A: アプリの許可を `Sites.Selected` にする

3章の `Sites.ReadWrite.All` の代わりに(または差し替えて):

1. アプリの **「API のアクセス許可」→「＋ アクセス許可の追加」→ Microsoft Graph →
   アプリケーションの許可** で `Sites.Selected` を追加。
2. **「管理者の同意を与えます」** を実行(状態が「付与済み」になる)。
3. すでに `Sites.ReadWrite.All` を付与済みなら、絞り込むために**それを削除**しておく
   (残すと全サイトアクセスのまま)。

### 手順 B: 対象サイトにアプリの権限をグラントする

この操作には **テナント全体管理者**、または **`Sites.FullControl.All`(アプリケーション)を持つ
別アプリ** が必要(`Sites.Selected` を付与されたアプリ自身では自分にグラントできない)。
ロールは用途に応じて選ぶ:

| ロール | できること | MAGI での用途 |
|---|---|---|
| `read` | 読み取りのみ | `pull` だけ(入力取得専用)なら可 |
| `write` | 読み取り + 書き込み | **`pull` + `push` 両方。MAGI の既定はこれ** |
| `fullcontrol` | フルコントロール | 通常は不要(過剰) |

**方法1: PnP PowerShell(手軽・おすすめ)**

> ⚠️ **初回準備が2つ必要**(下記)。ここで登録する「PnP ログイン用アプリ」は、MAGI が使う
> アプリ(`MAGI-SharePoint-Sync`)とは**別のアプリ登録**。混同しないこと。

**初回準備①: PowerShell 7 を入れる(必須)**

PnP.PowerShell v3 は **PowerShell 7.4 以上**が必須で、**Windows PowerShell 5.1 / ISE では動かない**
(.NET 8 ベース)。未導入なら入れる:

```powershell
winget install --id Microsoft.PowerShell --source winget   # または https://aka.ms/powershell から
```

以降のコマンドは **`pwsh`(PowerShell 7)** のウィンドウで実行する(`pwsh` で起動)。

**初回準備②: PnP のログイン用 Entra アプリを登録する(初回のみ)**

旧来の共有アプリ「PnP Management Shell」は廃止されたため、対話ログイン用に**自分のテナントへ
アプリを登録**しておく(初回1回だけ)。これにより以後 `-ClientId` で接続できる:

```powershell
Install-Module PnP.PowerShell -Scope CurrentUser    # 初回のみ(pwsh 7 で)

# 対話ログイン用アプリを登録(ブラウザで同意。完了後に表示される ClientId を控える)
Register-PnPEntraIDAppForInteractiveLogin `
  -ApplicationName "MAGI-PnP-Admin" `
  -Tenant "<tenant>.onmicrosoft.com"
```

> `-ApplicationName` と `-Tenant`(例 `contoso.onmicrosoft.com`)は必須。既定で対話(ブラウザ)
> ログイン。ブラウザが使えない環境は `-DeviceLogin` を付ける。返ってきた **ClientId** が次の接続で要る。

**本処理: 対象サイトへ接続して、MAGI アプリに権限を付与**

```powershell
# ① 上で登録した PnP ログイン用アプリの ClientId で、管理者として対象サイトへ接続
Connect-PnPOnline -Url "https://<tenant>.sharepoint.com/sites/<site>" `
  -Interactive -ClientId "<① で登録した PnP ログイン用アプリの ClientId>"

# ② MAGI アプリ(MAGI-SharePoint-Sync)に write を付与
#    -AppId は MAGI アプリのクライアント ID(PnP ログイン用アプリの ClientId ではない)
Grant-PnPAzureADAppSitePermission `
  -AppId "<MAGI アプリのクライアント ID>" `
  -DisplayName "MAGI-SharePoint-Sync" `
  -Site "https://<tenant>.sharepoint.com/sites/<site>" `
  -Permissions Write

# ③ 付与状況の確認
Get-PnPAzureADAppSitePermission -Site "https://<tenant>.sharepoint.com/sites/<site>"
```

> `Grant-PnPAzureADAppSitePermission` は `Grant-PnPEntraIDAppSitePermission` の別名で、
> 実行には Graph の `Sites.FullControl.All` 相当の権限(全体管理者など)が要る。
> **2つの ClientId を取り違えない**こと: 接続(`-ClientId`)= PnP ログイン用アプリ、
> 権限付与(`-AppId`)= MAGI アプリ。

**方法2: Microsoft Graph を直接呼ぶ**

サイト ID を取得してから、そのサイトの `permissions` にアプリ ID とロールを POST する
(Graph Explorer を管理者で使う、または `Sites.FullControl.All` を持つトークンで実行):

```http
# 1) サイト ID を得る
GET https://graph.microsoft.com/v1.0/sites/<tenant>.sharepoint.com:/sites/<site>

# 2) そのサイトにアプリの write を付与
POST https://graph.microsoft.com/v1.0/sites/{siteId}/permissions
Content-Type: application/json

{
  "roles": ["write"],
  "grantedToIdentities": [
    { "application": { "id": "<クライアント ID>", "displayName": "MAGI-SharePoint-Sync" } }
  ]
}
```

確認・変更・取り消し:

```http
GET    https://graph.microsoft.com/v1.0/sites/{siteId}/permissions                 # 一覧
PATCH  https://graph.microsoft.com/v1.0/sites/{siteId}/permissions/{permId}        # ロール変更 {"roles":["read"]}
DELETE https://graph.microsoft.com/v1.0/sites/{siteId}/permissions/{permId}        # 取り消し
```

### 注意点

- **付与するまではアクセス不可**。`Sites.Selected` だけの状態で `sharepoint.py test` を実行すると
  サイト解決で 403 になる。手順 B を済ませてから確認する。
- **`pull` だけでなく `push` も使うなら `write`** が必要(`read` では push が 403 になる)。
- アプリに**どのサイトが付与されているかを一覧する API は無い**(列挙は非対応)。権限は各サイトの
  `permissions` で個別に確認する。付与したサイトはこちらで記録しておくとよい。
- 複数サイトを使うなら、サイトごとに手順 B を繰り返す。

---

## 4. 取得した値を MAGI に設定する

### 4.1 シークレットと設定(Git 追跡外)

`prototype/.claude/settings.local.json` の `env` に設定する(API キーと同じ作法)。
テンプレートからコピーして埋める:

```bash
cp .claude/settings.local.json.example .claude/settings.local.json
```

```json
{
  "env": {
    "MAGI_SHAREPOINT_ENABLED": "true",
    "MAGI_SHAREPOINT_SITE_URL": "https://<tenant>.sharepoint.com/sites/<site>",
    "MAGI_SHAREPOINT_TENANT_ID": "<ディレクトリ (テナント) ID>",
    "MAGI_SHAREPOINT_CLIENT_ID": "<アプリケーション (クライアント) ID>",
    "MAGI_SHAREPOINT_CLIENT_SECRET": "<クライアント シークレットの値>"
  }
}
```

> `settings.local.json` は `.gitignore` 済み。**シークレットは絶対にコミットしないこと。**
> 環境変数(`$env:MAGI_SHAREPOINT_CLIENT_SECRET = "..."` 等)で渡してもよい(環境変数が優先)。
>
> **設定の優先順位**: `enabled` / `site_url` / `drive` / `root` は **env(settings.local.json)→
> sharepoint.config.json** の順で解決される。オンオフやテナント URL を**コミットせず**ローカルで
> 管理したい場合は、ここ(settings.local.json)に書くのがよい。`REPLACE` を含む値は未設定扱い。

### 4.2 接続先(非機密・追跡)

`prototype/sharepoint.config.json` を編集して有効化する:

```json
{
  "enabled": true,
  "site_url": "https://<tenant>.sharepoint.com/sites/<site>",
  "drive": "Documents",
  "root": "MAGI",
  "folders": {
    "input": "input",
    "media-output": "media-output",
    "reviews": "reviews",
    "deliberations": "deliberations",
    "brainstorms": "brainstorms",
    "persona-tests": "persona-tests"
  }
}
```

> 4.1 で `MAGI_SHAREPOINT_ENABLED` 等を設定した場合は、そちらが config より優先される。
> `sharepoint.config.json` は主に `folders` 構造の保持と既定値の置き場として使う。

| キー | 説明 |
|---|---|
| `enabled` | `true` で連携オン(アクティブ root が `sharepoint/` になる)。`false` で純ローカル(`local/`)。env `MAGI_SHAREPOINT_ENABLED` が優先 |
| `site_url` | 対象 SharePoint サイトの URL(ブラウザのアドレスバーの `…/sites/<site>` まで) |
| `drive` | ドキュメントライブラリ名(既定の「ドキュメント」は通常 `Documents`)。見つからなければ既定ライブラリにフォールバック |
| `root` | ライブラリ直下のミラー基点フォルダ。`sharepoint/<key>` ↔ 遠隔 `<root>/<value>` |
| `folders` | ローカルのサブフォルダ名 ↔ 遠隔フォルダ名の対応 |

---

## 5. 動作確認

`prototype/` ディレクトリで実行する:

```bash
python scripts/sharepoint.py status   # 設定とアクティブ root を表示(通信なし)
python scripts/sharepoint.py test     # トークン取得 → サイト/ドライブ解決を検証
python scripts/sharepoint.py pull input   # 遠隔 input → sharepoint/input/ に取得
```

期待される結果:

- `status` … `enabled: True`、`active root: …/sharepoint` と設定値が表示される
- `test` … `token: OK` / `site id: …` / `drive id: …` / 「認証・サイト・ドライブの解決に成功しました。」
- `pull input` … 遠隔の入力ファイルが `sharepoint/input/` にダウンロードされる

成果物を上げるときは、`sharepoint/reviews/` 等に書き出してから:

```bash
python scripts/sharepoint.py push reviews          # sharepoint/reviews/ → 遠隔
python scripts/sharepoint.py info sharepoint/reviews/<file>   # SharePoint の Web URL を表示
```

---

## 6. トラブルシューティング

| 症状 / エラー | 主な原因 | 対処 |
|---|---|---|
| `error: SharePoint の認証情報が未設定です: …` | env / settings.local.json に値が無い、または `REPLACE` のまま | 4.1 の3つの値を実値で設定する |
| HTTP 401 / `invalid_client` | クライアントシークレットの誤り・期限切れ、テナントID違い | シークレットを再発行(2章)、テナントID/クライアントIDを再確認 |
| `token: OK` の直後に site 解決で **HTTP 401 / `generalException` / `General exception while processing`** | 認証は通っているが、**アプリに API 権限が未同意**(アクセストークンに `roles` が無い) | 3章で `Sites.ReadWrite.All`(または 3.5 の `Sites.Selected`)を追加し**管理者の同意**を付与。数分待って再実行。確認: `sharepoint.py test` のトークンに `roles` が入るか(無ければ未同意) |
| HTTP 403 / `Access denied` / `Authorization_RequestDenied` | `Sites.ReadWrite.All` 未付与、または**管理者同意が未実施**。`Sites.Selected` 運用なら**対象サイトへの個別グラント未実施**(または `read` のみで `push` した) | 3章の「管理者の同意を与えます」を確認。`Sites.Selected` の場合は 3.5 の手順 B(`push` には `write`)を実施 |
| HTTP 404(site 解決時) | `site_url` の誤り(パスやサイト名が違う) | ブラウザで開ける正しい `…/sites/<site>` URL を設定 |
| drive 名の警告 `drive '…' が見つからない` | `drive` 名がライブラリ表示名と不一致 | 既定ライブラリにフォールバックされる。明示したい場合は正しい表示名(例 `Documents`)を設定 |
| `SharePoint 無効(enabled=false)…` | `enabled` が `false` | 4.2 で `enabled: true` にする |
| PnP: `Connect-PnPOnline は認識されない` / モジュールが読み込めない | **Windows PowerShell 5.1 / ISE で実行**している | **PowerShell 7.4+(`pwsh`)** で実行する(3.5 初回準備①) |
| PnP: 接続時に `ClientId` を求められる / 既定アプリで失敗 | PnP ログイン用アプリ未登録(旧共有アプリ廃止) | `Register-PnPEntraIDAppForInteractiveLogin` を初回実行し、得た ClientId を `-ClientId` に渡す(3.5 初回準備②) |
| PnP: `Register-PnPEntraIDAppForInteractiveLogin` が見つからない | モジュールが古い | `Update-Module PnP.PowerShell`(pwsh 7 で)。最新 v3 系にする |

> 同意が反映されるまで数分かかることがある。403 が続く場合は少し待って再試行する。

---

## 7. セキュリティ上の注意

- **シークレットをコミットしない**。`settings.local.json` は `.gitignore` 済みだが、`git add -f`
  などで誤って追加していないか公開前に確認する。
- シークレットには**有効期限**を設定し、期限管理する(無期限にしない)。
- 権限は必要最小限に。広すぎる場合は `Sites.Selected` での絞り込みを検討する(3章の補足)。
- 退職・委譲などでアプリが不要になったら、**アプリの登録を削除**する(エンタープライズ
  アプリ側のサービスプリンシパルも併せて整理する)。

---

## 付録: 用語(アプリの登録 vs エンタープライズアプリケーション)

| | アプリの登録(App registration) | エンタープライズアプリケーション |
|---|---|---|
| 実体 | Application オブジェクト(アプリの定義) | サービスプリンシパル(テナント内の実体) |
| 持つもの | クライアントID / シークレット / API 許可 | 同意の記録 / サインインログ / ユーザー割り当て |
| 作り方 | **自分で新規登録**(本マニュアルの起点) | アプリ登録時に**自動生成** |

今回は「アプリの登録」で設定し、「エンタープライズアプリケーション」で同意状況などを確認する、
という関係になる。
