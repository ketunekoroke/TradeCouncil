# 領収書取込・認証 — Claude への依頼ランブック

> このファイルは **「ユーザーが Claude Code に経理作業を依頼するときの定型文(依頼文言)」** と、
> 依頼を受けて Claude が回す手順をまとめたもの。**【依頼文言】の太字をそのままチャットに貼れば、
> Claude が記載の手順を実行する。** CLI 仕様の網羅は [manual.md](manual.md)、判断方針は
> [accounting-policy.md](accounting-policy.md) が正本。

## 0. 前提・共通ルール(Claude が必ず守る)

- 作業は `cd Accounting`。実行は `..\.venv\Scripts\python.exe -m scripts.cli expense <sub>`。
- **不可逆/外部書き込み**(`register --confirm` / `revise-past --confirm` / `clean-inbox --confirm`)は
  実 MoneyForward 書き込み・実削除で **Teams(OPERATIONS)へ通知が飛ぶ**。Claude は本実行の前に必ず
  **ドライランのプレビューを提示 → ユーザー承認**を取ってから `--confirm` する。
- **判断できない用途・高額・証憑のデータ欠落は推測で確定しない**。`AskUserQuestion` で確認する。
- **秘匿情報(MF ログイン認証情報)を Claude は入力しない**。認可は URL 生成とコード交換まで(→ §2)。
- 税区分の最終判断は税理士。Claude は一次チェック(フラグ)まで。

---

## 1. 領収書の取込 → 登録(メインフロー)

### 依頼文言
> **「Inbox から経費を登録して」**
>
> (絞り込み例: 「Inbox から経費を登録して(5月分だけ)」「〜(タイ分だけ)」)

### Claude が回す手順
1. **pull**: `expense pull` — SharePoint Inbox → `var/expense/raw/`。新着(サイドカー未作成)を一覧化。
2. **抽出(Claude が証憑を読む)**: `raw/` の各 PDF/画像を Read し、`var/expense/extracted/<名>.json`
   (サイドカー)を作成。判断の指針:
   - **内外判定を最初に**。国外消費 = **対象外/不課税**。国内 = **課税仕入 10%**(食品の贈答は
     **軽減 課税仕入 (軽)8%**、郵券は非課税)。
   - 外貨は **前月末仲値(TTM)** で円換算(レートは `var/expense/murc_*.xls`。THB は月次 4.8〜4.9 台、
     USD は同ファイルの月末 TTM)。
   - 飲食: 単独 = **会議費**、複数名+酒 = **接待飲食費**。参加者メモ(人数・社内外)は WEB 登録。
   - 同日・同額の別レシートは支払先に入庫時刻等を付けて区別(重複誤判定の回避)。
3. **process**: `expense process` — リネーム/トリミング/重複排除/ポリシー適用/下書き/台帳。
4. **登録プレビュー**: `expense register`(ドライラン)で送信予定(費目・税区分・円換算・証憑添付)を提示。
5. **ユーザー承認後**: `expense register --confirm` — MF へ登録(証憑添付=電帳法)+ Teams 通知。
   - 未学習費目(例: 支払手数料)・税区分(例: (軽)8%)が **ID 未解決で skip** される場合は §2 後段の
     `expense masters` でマスタを取得して再登録、または WEB で費目選択。
6. **inbox 整理**: `expense clean-inbox --confirm` — **登録済みのみ** Inbox から削除(ごみ箱から復元可)。
7. **台帳**: `expense xlsx --push` — 明細台帳(証憑サムネ付き)を SharePoint ドキュメント/Expense/ へ。

---

## 2. 認証(トークン)の更新 — 認可コード・フロー ★

クラウド経費 API のトークンが失効した / スコープを増やした(例: 費目・税区分マスタ取得に必要な
`office_setting:write`)ときに行う。**MF へのログインと認可はユーザー、URL 生成とコード交換は Claude**、と
役割を分ける。

### 依頼文言
> **「クラウド経費の認証を更新して」**
>
> (スコープを増やすとき: 「クラウド経費を全権限で再認可して」)

### フロー(役割分担)

| # | 手順 | 実行者 | 具体 |
|---|---|---|---|
| 1 | 認可 URL を生成し、ブラウザを開く | **Claude** | `ac mf authorize --product expense`(URL を表示し既定ブラウザを起動。開かなければ表示 URL を手で開く) |
| 2 | MoneyForward にログインし、権限を許可 | **あなた** | Claude は認証情報を入力しない |
| 3 | 表示された **認可コード(`code=` の値)** をコピー | **あなた** | |
| 4 | コードを **チャットに貼り付け** | **あなた** | コードだけでも可(例: `Mh2weBok...`) |
| 5 | トークン交換・保存 | **Claude** | `ac mf login --product expense --no-listen --code <CODE>` |
| 6 | (必要なら)費目/税区分マスタ取得 | **Claude** | `ac expense masters --show` — 未学習の費目/税区分 ID を usage へマージ |

### 注意
- Claude は `--no-listen --code` で **コード交換のみ**(対話ペースト式の `login` は stdin 待ちになり、
  Claude の非対話実行では使えない)。
- 付与スコープは [config/moneyforward.config.json](../config/moneyforward.config.json) の
  `products.expense.oauth.scopes` で決まる。**広げる場合は先にそこを編集してから手順 1**(現状は全6:
  `office_setting:write / user_setting:write / transaction:write / report:write / account:write /
  public_resource:read`)。
- 認可 URL の `state` を控え、リダイレクト方式なら戻り先 URL の `state` 一致を確認(CSRF 対策)。

---

## 3. 過去分の取込(年度別・別フォルダ)

クラウド経費の既存明細を取り込む。**`import-past` の既定レンジは当期のみ**なので、過年度は
**明示レンジ + 別フォルダ**(期を混ぜない)で行う。

### 依頼文言
> **「FY2024(2024-07-01〜2025-06-30)を別フォルダで取り込んで」**

### Claude が回す手順
- `EXPENSE_VAR_DIR=var/expense-<年度>` を設定して `expense import-past --from <開始> --to <終了>`。
  これで台帳・証憑 DL・スナップショットが **その年度フォルダに隔離**される(メイン台帳は無変更)。
- 証憑あり明細は `var/expense-<年度>/past/` に DL、証憑なしは「WEB 手動」フラグ。
- 取込後に件数・期間・他フォルダへの非影響を検証して報告。

---

## 4. 定期支払い(サブスク・固定費)の一覧化

### 依頼文言
> **「定期支払いを一覧化して」**

### Claude が回す手順
- past_ 台帳(複数年度フォルダ横断)から **3か月以上出現するベンダー**を集約し、月次の固定費・サブスクと
  不定期反復に分けて、費目・代表額(原通貨)・円概算・出現/月数・期間で一覧化(`recurring_payments.md`)。

---

## 5. 過去分の OCR 誤りを補正

クラウド経費内蔵 OCR の誤りを、証憑を Claude が再読込して当期ポリシーで是正(PUT)。**今期(未締め)のみ**。

### 依頼文言
> **「過去分の OCR 誤りを補正して」**

### Claude が回す手順
1. `import-past`(対象期間)→ 2. Claude が `past/<id>` を Read → `extracted/past_<id>.json` を生成 →
3. `revise-past`(ドライランで差分プレビュー → **ユーザー承認** → `--confirm` で変更フィールドのみ PUT)。
証憑は再アップロードしない。差分ゼロは skip。

---

## 6. 別PCでの作業継続(`var` ↔ SharePoint 同期)

`var/`(作業領域)を SharePoint と双方向同期し、別PCで続きの作業をできるようにする。

### 依頼文言
> **「var を同期して」**(軽量にするなら「var を同期して(状態の核だけ)」)

### Claude が回す手順
- `expense sync-var` — 現在の `var/expense`(`EXPENSE_VAR_DIR` 指定時はその年度フォルダ)を
  **`Expense/Var/<フォルダ名>`** と双方向同期(mtime newer-wins・追加型)。`--core-only` で状態の核
  (台帳/サイドカー/refdata/下書き/murc/スナップショット)だけの軽量同期。
- **運用規律**: 各PCで **作業開始時に `sync-var`(pull)→ 作業終了時に `sync-var`(push)**。

### 別PCの初期セットアップ(1回だけ)
1. リポジトリを `git clone`(または `git pull`)で main を取得。
2. ルート共有 `.venv` を構築(依存導入)。
3. **ルート `.env` を用意** — MF/SharePoint のシークレットは **git にも SharePoint にも乗らない**。
   元PCの `.env` を安全な手段でコピーするか、再入力する。
4. **MF トークンを再認可**(→ §2「クラウド経費の認証を更新して」)。トークンは秘密のため同期しない。
5. **「var を同期して」** で状態・証憑を取得 → 作業継続。

### 留意点
- 既存同期は **追加型(削除を伝播しない)**。`raw/`(`clean-inbox` で消える)等が別PCで復活し得るが、
  処理済みは重複 skip・登録済みは無害。気になれば `--core-only` 運用、または将来 `--mirror`(遠隔の余剰削除)で対処。
- **シークレット(`.env`・トークン)は同期対象外**(SharePoint に秘密を置かない原則)。別PCでは手動投入＋再認可。
- 同一ファイルを2台で同時編集しない(newer-wins のため後勝ち)。「開始pull / 終了push」を守る。

---

## 依頼文言・早見表

| やりたいこと | 依頼文言 |
|---|---|
| Inbox の領収書を登録 | **Inbox から経費を登録して** |
| 認証(トークン)更新 | **クラウド経費の認証を更新して** |
| 過年度を別フォルダで取込 | **FY20XX(YYYY-MM-DD〜YYYY-MM-DD)を別フォルダで取り込んで** |
| 定期支払いの一覧 | **定期支払いを一覧化して** |
| 過去分の OCR 補正 | **過去分の OCR 誤りを補正して** |
| 別PCへ var 同期 | **var を同期して** |

> いずれも Claude は **不可逆操作の前に必ずドライラン提示 → 承認**を挟む。中断・修正はいつでも口頭で指示可。
