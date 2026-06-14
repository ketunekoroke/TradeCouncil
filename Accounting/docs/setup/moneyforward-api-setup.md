# MoneyForward API キー取得マニュアル(クラウド会計 / クラウド経費)

会計経理支援システムが MoneyForward と連携するために必要な、**OAuth アプリ登録と
client_id / client_secret の取得手順**。会計バックエンドは **クラウド会計** と **クラウド経費** の
2系統で、**登録窓口・OAuth サーバ・client_id/secret がそれぞれ別**(片方の資格情報はもう片方では使えない)。

> 関連: 設定の仕組みは [docs/design.md「API 設定の仕組み」](../design.md)、注意点は
> [docs/caveats.md](../caveats.md)、プロジェクトへの反映は [../../CLAUDE.md](../../CLAUDE.md)。
> 取得した値の置き場所(`MONEYFORWARD_*` env / `config/moneyforward.config.json`)は本書「C. 反映」。

> ⚠️ **正確な最新仕様は公式で確認すること**(本書のエンドポイント/スコープも下記公式の写し)。
> archive されたリポジトリ(`moneyforward/expense-api-doc`・`moneyforward/api-doc`)は使わない
> ([caveats.md](../caveats.md) — 2026-05-22 アーカイブ済み)。一次情報は **開発者サイト** と **Swagger**:
> - 開発者サイト(会計ほか): https://developers.biz.moneyforward.com/docs/
> - クラウド経費 API ドキュメント(Swagger): https://expense.moneyforward.com/api/index.html

---

## 0. 前提と全体像

| 項目 | 内容 |
|---|---|
| 認証方式 | **OAuth 2.0 認可コードフロー**(RFC6749)。**API キー単体では不可**(会計)。`grant_type=authorization_code` |
| 取得するもの | **client_id** と **client_secret**(会計・経費で**別々に**取得) |
| 必要なもの | 対象プランの契約と、アプリ登録できる権限(会計=アプリ開発権限 / 経費=各ユーザーの開発者向け設定) |
| 所要時間 | 各 10〜15 分(+ プラン/API 有効化の確認) |

> **重要(可用性の確認 — [caveats.md](../caveats.md))**: スモールビジネスプランで開発者向け API が
> 有効化できるかを、**実アカウントで最初に確認** する(プランにより API 連携メニューが出ないことがある)。

2系統の違い(どちらを使うかで窓口が変わる):

| | クラウド会計(+ 請求書 / 債務支払 等) | クラウド経費 |
|---|---|---|
| 登録窓口 | **アプリポータル**(共通) | クラウド経費の **個人設定 > API連携（開発者向け）** |
| 認可サーバ | `https://api.biz.moneyforward.com`(認可サーバー API v2) | `https://expense.moneyforward.com/oauth` |
| API ドメイン | 各プロダクトの API(開発者サイト参照) | `https://expense.moneyforward.com/api` |
| client_id/secret | アプリポータルのアプリ | 経費の開発者向けアプリ(**会計とは別**) |

---

## A. クラウド会計 の API 連携(アプリポータル + 認可サーバー v2)

### A-1. 前提の権限・設定

- 操作するユーザーに **「アプリ開発」権限** が必要(アプリポータルで新規登録できる権限)。
- 連携を受けるユーザー側で、**ユーザー設定 →「編集」→「アプリ連携権限」** の
  **「アプリ連携」** と **「クラウド会計・確定申告」** にチェックを入れて保存する
  (これが無いと認可しても会計 API を呼べない)。

### A-2. アプリを登録して client_id / client_secret を取得

1. **マネーフォワード クラウド アプリポータル**にサインインする。
2. **「アプリ開発」→「新規登録」**(連携用アプリの登録)を開く。
3. 次を入力する:
   - **アプリ名称**(任意)
   - **リダイレクト URI**(認可後に認可コードを受け取る URL。**HTTPS 推奨**。ローカル検証は後述)
   - **クライアント認証方式**(token エンドポイントでの client_secret の渡し方)
4. 登録すると **client_id** と **client_secret** が発行される。**client_secret は控える**
   (再表示されない場合があるため、その場でコピー)。

| 取得値 | 後で使う env(本プロジェクト) |
|---|---|
| client_id | `MONEYFORWARD_CLIENT_ID`(または config に記入) |
| client_secret | `MONEYFORWARD_CLIENT_SECRET`(**秘密**。env のみ) |

### A-3. OAuth エンドポイント(認可サーバー API v2)

| 用途 | メソッド・URL |
|---|---|
| 認可エンドポイント | `GET https://api.biz.moneyforward.com/authorize` |
| トークンエンドポイント | `POST https://api.biz.moneyforward.com/token` |

- RFC6749 準拠の **認可コードフロー**: 認可エンドポイントへリダイレクト(必要 **スコープ** を指定)
  → ユーザーが許可 → リダイレクト URI に **認可コード** → トークンエンドポイントで **アクセストークン** に交換。
- **スコープは「使う API」ごとに異なる**。使用する API のリファレンス(開発者サイト)で必要スコープを確認する。

### A-4. クラウド会計の利用可能スコープ(`mfc/accounting/*`)

| scope | 用途 | 種別 |
|---|---|---|
| `mfc/accounting/offices.read` | 事業者情報の取得(**最初に offices を開く**前提) | read |
| `mfc/accounting/accounts.read` | 勘定科目・補助科目の参照 | read |
| `mfc/accounting/taxes.read` | 税(税区分)の参照 | read |
| `mfc/accounting/trade_partners.read` | 取引先の参照 | read |
| `mfc/accounting/trade_partners.write` | 取引先の登録 | write |
| `mfc/accounting/departments.read` | 部門の参照 | read |
| `mfc/accounting/journal.read` | 仕訳の参照(相関キーでの突合) | read |
| `mfc/accounting/journal.write` | 仕訳の登録・更新・削除(**仕訳調整**) | write |
| `mfc/accounting/voucher.write` | 証憑の登録・削除 | write |
| `mfc/accounting/report.read` | 帳票(試算表・推移表等)の参照 | read |
| `mfc/accounting/connected_account.read` | 連携サービスの参照 | read |
| `mfc/accounting/transaction.write` | 入出金明細の作成・更新 | write |

> 本プロジェクトの既定(`config/moneyforward.config.json` の `products.accounting.oauth.scopes`)は、
> 会計連携・仕訳調整に必要な実用セット(`offices.read` / `accounts.read` / `taxes.read` /
> `trade_partners.read` / `journal.read` / `journal.write`)。用途に応じて増減する(**最小権限**)。
>
> ⚠️ **アプリポータル側の有効化**: 認可リクエストで指定する scope は、**アプリ登録(アプリポータル)で
> 有効化されているもの**でなければならない。`invalid_scope` 等のエラーが出たら、アプリポータルの当該
> アプリでそのスコープを有効化するか、config の scopes を有効化済みのものに合わせる。一覧は出典が
> サードパーティ記事(下記参照)のため、**最新・正確はアプリポータルの権限設計画面で確認**すること。

---

## B. クラウド経費 の API 連携(開発者向け)

### B-1. アプリを作成して client_id / client_secret を取得

1. **クラウド経費**(または クラウド債務支払)にログインする。
2. **個人設定 →「基本設定」→「API連携（開発者向け）」** を開く。
3. **「アプリケーションの作成」** をクリックし、フォームに入力 → 利用規約に同意 → 作成。
4. **client_id** と **client_secret** が発行される(控える)。

> **経費と債務支払は別アプリ**: 両方使うなら**それぞれ**アプリを登録する。一方の client_id/secret は
> もう一方では使えない。

### B-2. リダイレクト URI(HTTPS 必須)

- リダイレクト URI は **HTTPS のみ**(http は不可)。
- API ドキュメント上でお試し実行する場合のリダイレクト URI は
  `https://expense.moneyforward.com/api/oauth2-redirect.html` を指定する。

### B-3. OAuth エンドポイント(クラウド経費)

| 用途 | URL |
|---|---|
| 認可エンドポイント | `GET https://expense.moneyforward.com/oauth/authorize?client_id=<ID>&redirect_uri=<URI>&response_type=code&scope=<SCOPE>` |
| トークンエンドポイント | `POST https://expense.moneyforward.com/oauth/token`(`grant_type=authorization_code`) |
| トークン情報 | `GET https://expense.moneyforward.com/oauth/token/info`(Bearer トークンで確認) |

スコープ例(必要なものだけを最小限に): `office_setting:write` / `user_setting:write` /
`transaction:write` / `report:write` / `account:write` / `public_resource:read`
(**最新は Swagger で確認**: https://expense.moneyforward.com/api/index.html )。

---

## B'. ローカル開発での Redirect URI(よくある疑問)

Redirect URI は「認可後にブラウザが **`?code=<認可コード>` を付けて戻ってくる先**」。**その URL に
実際のサーバ/ページが無くても、ブラウザのアドレスバーに出る `code` を手でコピーできれば成立する**
(= 本プロジェクトの `MONEYFORWARD_<PRODUCT>_AUTH_CODE` に貼る値)。

| 系統 | ローカルでの Redirect URI | 備考 |
|---|---|---|
| 会計(accounting) | `http://localhost:8765/callback`(任意ポート/パス可) | **localhost http が許可**。対応ページが無くてもよい(公式) |
| 経費(expense) | **HTTPS 必須**。`https://expense.moneyforward.com/api/oauth2-redirect.html` | localhost http は不可。提供の HTTPS リダイレクトを使う(Swagger の Authorize でも可) |

> 本プロジェクトの [`config/moneyforward.config.json`](../../config/moneyforward.config.json) の
> `products.<product>.oauth.redirect_uri` 既定値は **この表どおり**(会計=localhost / 経費=提供 HTTPS)。
> そのまま使える。

**鉄則**: アプリに**登録した redirect_uri** と、認可リクエスト・トークンリクエストで渡す `redirect_uri` は
**完全一致**(1文字でも違うと弾かれる)。本プロジェクトでは config の `redirect_uri` が唯一の出どころ。

手動コピーの手順(最も確実):

1. アプリ登録の Redirect URI に上表の値を入れる(config の `redirect_uri` と完全一致させる)。
2. **認可 URL を生成してブラウザを開く**(`.env` の client_id・config の redirect_uri/scopes から自動生成):
   ```powershell
   cd Accounting
   ..\.venv\Scripts\python.exe -m scripts.cli mf authorize --product accounting   # 経費は expense
   #   --no-open を付けると URL の表示のみ(自分で開く)
   ```
   ブラウザでログイン → **許可**。手で組み立てる場合は認可エンドポイント(A-3 / B-3)に
   `client_id`・`redirect_uri`(上表)・`response_type=code`・`scope` を付けてアクセスする。
3. 遷移先 URL の **`code=` をアドレスバーからコピー** → `.env` の
   `MONEYFORWARD_ACCOUNTING_AUTH_CODE` / `MONEYFORWARD_EXPENSE_AUTH_CODE` に貼る
   (`mf authorize` が表示する `state` が戻り先 URL の `state` と一致することも確認)。
4. `scripts/spike_moneyforward.py --product <accounting|expense>` でトークン交換。

> 経費で自前の `https://localhost` を使うには自己署名証明書が要る。提供の `oauth2-redirect.html` か、
> `ngrok` 等のトンネル(一時 HTTPS → localhost)が手軽。localhost で `code` を自動受信する簡易リスナは
> [BACKLOG.md](../../BACKLOG.md) BL-AC-016。

---

## C. 取得した値をプロジェクトに反映する

設定の仕組みは [docs/design.md](../design.md)。**非秘密は config、秘密は env** に分ける。

**会計と経費は別系統**として並行設定できる(env もプロダクト別。`<PRODUCT>` = `ACCOUNTING` | `EXPENSE`)。

### C-1. 秘密(ルート共有 `.env` — Git 追跡外)

```bash
# .env(抜粋)。.env.example をコピーして埋める。コミット禁止(pre-commit が検査)。
# クラウド会計
MONEYFORWARD_ACCOUNTING_CLIENT_ID=<会計の client_id>
MONEYFORWARD_ACCOUNTING_CLIENT_SECRET=<会計の client_secret>
MONEYFORWARD_ACCOUNTING_AUTH_CODE=<会計の認可後 code>
# クラウド経費
MONEYFORWARD_EXPENSE_CLIENT_ID=<経費の client_id>
MONEYFORWARD_EXPENSE_CLIENT_SECRET=<経費の client_secret>
MONEYFORWARD_EXPENSE_AUTH_CODE=<経費の認可後 code>
```

> どちらか一方だけ使うなら、その系統のキーだけ設定すればよい(もう一方は未設定のままで OK)。
> MoneyForward は **認可コードフロー**(`grant_type=authorization_code`。client_credentials ではない)。
> grant の上書きは `MONEYFORWARD_<PRODUCT>_GRANT_TYPE`。

### C-2. 非秘密(`Accounting/config/moneyforward.config.json`)

`products.accounting` / `products.expense` を**両方**持つ。OAuth エンドポイントは公式の既定値を記入済み。
`scopes` と `api.base`(会計)は使う API に合わせて追記する:

```jsonc
{
  "products": {
    "accounting": {
      "oauth": {
        "authorize_url": "https://api.biz.moneyforward.com/authorize",
        "token_url":     "https://api.biz.moneyforward.com/token",
        "redirect_uri":  "https://<あなたのリダイレクト先>",
        "scopes":        ["<使う API のリファレンスで確認>"]
      },
      "api": { "base": "<開発者サイトで確認>" }
    },
    "expense": {
      "oauth": {
        "authorize_url": "https://expense.moneyforward.com/oauth/authorize",
        "token_url":     "https://expense.moneyforward.com/oauth/token",
        "redirect_uri":  "https://expense.moneyforward.com/api/oauth2-redirect.html",
        "scopes":        ["transaction:write", "public_resource:read"]
      },
      "api": { "base": "https://expense.moneyforward.com/api" }
    }
  }
}
```

> 各フィールドの解決順は `MONEYFORWARD_<PRODUCT>_<FIELD>`(env)→ config の値。
> client_secret は config に置かず必ず env(`core/moneyforward.py`)。

### C-3. 確認

```powershell
cd Accounting
..\.venv\Scripts\python.exe -m scripts.cli mf config                       # 会計・経費の両方を表示(秘密はマスク)
..\.venv\Scripts\python.exe -m scripts.cli mf config --product expense     # 経費だけ表示
..\.venv\Scripts\python.exe -m scripts.cli mf config --check               # いずれか1系統が ready なら exit 0
..\.venv\Scripts\python.exe -m scripts.cli mf config --product expense --check  # 経費が ready かを判定
```

---

## D. 認可コードフローの実行(概略)

OAuth 認可コードフローは **ブラウザでのユーザー同意** を伴う(完全自動化はしない)。最小手順:

1. `python -m scripts.cli mf authorize --product <accounting|expense>` で**認可 URL を生成しブラウザを開く**
   (または **認可エンドポイント**(A-3 / B-3)に `client_id`・`redirect_uri`・`response_type=code`・`scope` を
   付けて手でアクセス)→ ログイン → **許可**。
2. リダイレクト URI に付与される **`code`** を控え、`.env` の `MONEYFORWARD_<PRODUCT>_AUTH_CODE` に設定
   (会計なら `MONEYFORWARD_ACCOUNTING_AUTH_CODE`、経費なら `MONEYFORWARD_EXPENSE_AUTH_CODE`)。
3. 疎通スパイクで token 交換 → offices を開く(最初の確認 — [caveats.md](../caveats.md)):
   ```powershell
   ..\.venv\Scripts\python.exe scripts\spike_moneyforward.py --product expense
   ..\.venv\Scripts\python.exe scripts\spike_moneyforward.py --product accounting
   ```
   (`scripts/spike_moneyforward.py` はプロダクト別設定を読み、token エンドポイントへ交換 → offices を取得。
   `MONEYFORWARD_<PRODUCT>_GRANT_TYPE` / `MONEYFORWARD_<PRODUCT>_OFFICES_URL` で調整可)

> アクセストークンには**有効期限**がある。リフレッシュトークンでの更新は系統の仕様に従う
> (開発者サイト / Swagger で確認)。

---

## E. セキュリティ上の注意

- **client_secret・認可コード・トークンをコミットしない**。`.env` は `.gitignore` + pre-commit で検査
  (`git add -f` で迂回しない)。コードにも書かず env から読む。
- **リダイレクト URI は HTTPS**(経費は必須)。想定外の URI を登録しない。
- **スコープは最小限**(write 系を不要に付けない)。会計側はユーザーの「アプリ連携権限」も最小に。
- **証憑・口座の生値をログに残さない**([caveats.md](../caveats.md))。offices などの応答は件数のみ表示する運用。
- **不可逆操作(送金・支払実行・削除)はエージェントにさせない**。本連携は抽出・登録の下準備まで。

---

## 参照(一次情報)

- マネーフォワード クラウド 開発者サイト(API ドキュメント): https://developers.biz.moneyforward.com/docs/
- 認可サーバー API v2 / トークンエンドポイント: https://developers.biz.moneyforward.com/docs/api/auth/ ・ https://developers.biz.moneyforward.com/en/docs/api/auth/02-token/
- API 共通仕様: https://developers.biz.moneyforward.com/docs/common/api_common_specifications/
- アプリポータル「連携用アプリを登録する」: https://biz.moneyforward.com/support/app-portal/guide/g011.html
- クラウド会計 API について: https://biz.moneyforward.com/support/account/guide/others/ot09.html
- クラウド経費「API連携（開発者向け）」: https://biz.moneyforward.com/support/expense/faq/setting/se09.html
- クラウド経費 API ドキュメント(Swagger): https://expense.moneyforward.com/api/index.html
- 会計スコープ一覧の参考(サードパーティ・要公式照合): https://note.com/note_tds/n/n9b554722016d ・ https://www.fyve.co.jp/claude-code/articles/claude-code-moneyforward-mcp-setup-guide
