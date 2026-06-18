# 運用マニュアル

## 日次フロー

1. 取り込み: 紙(スキャン/撮影)→ 監視フォルダ・メール添付の自動取得、またはアップロードでステージへ。
2. 抽出: Claude のビジョンで構造化(確信度つき)。
3. 検証ゲート: 為替換算・税区分・証憑要件をチェック(`scripts/check_compliance.py`)。
4. Teams 確認: NG / 低信頼のみカードで提示 → 修正/承認。
5. 経費登録: 領収書アップロード + API。摘要に相関キー。電帳法保存は MoneyForward が提供。
6. 会計連携の確認: 直接連携後、相関キーで会計仕訳を突合 → `mf_journal_id` を確定。
7. 仕訳調整: 必要に応じ会計 API で勘定科目・税区分・摘要を補正する。

## 経費レシート取込(`ac expense` / BL-AC-020)

> **Claude への依頼で回す場合の定型文(依頼文言)と役割分担(認可コード・フロー含む)は
> [runbook-expense.md](runbook-expense.md) を参照。** 本節は CLI サブコマンドの仕様。

SharePoint をマスタデータとし、Claude Code が手動で回す半自動フロー(下書きまで。実 API 登録は後段)。
起動は `cd Accounting; ..\.venv\Scripts\python.exe -m scripts.cli expense <sub>`。

1. **前期実績の学習**: `expense refdata` — 前期(7月〜翌6月)の自分の経費明細(`me/ex_transactions`)から
   **よく使う費目・税区分**を集計し `var/expense/refdata/expense_usage.json` に保存。`--from/--to` で範囲調整。
2. **取り込み**: スマホ撮影/PDF を Teams の Expense チャネル(SharePoint 連携)へ投稿 → `expense pull` で
   SharePoint の expense-inbox を `var/expense/raw/` へ取得。
3. **分割(複数レシートPDF・任意)**: 1つの PDF に複数のレシートが入っている場合のみ、Claude が **分割
   サイドカー**(`var/expense/split/<ファイル名>.json`: どのページがどのレシートかを `parts:[{pages,suffix}]`
   で指定。連番分割は `mode:"per_page"`)を書き、`expense split`(既定ドライラン → `--confirm`)で **1ファイル
   1レシート**に分ける(`pypdf`)。分割後のパートは raw/ に新規ファイルとして置かれ、元 PDF は削除せず
   `var/expense/split_src/` へ退避(SharePoint inbox にも原本が残る=復元可)。**複数ページ=複数レシートとは
   限らない**(1レシートが複数ページの場合がある)ため、分割サイドカーが無いファイルは分割しない。ページ番号は
   1始まりで、範囲外(off-by-one)は実行前に弾く。
4. **抽出(Claude)**: `raw/`(分割後は各パート)の各ファイルを Claude が読み、日付・支払先・金額・通貨・内容・
   (登録番号)・費目ヒント・**画像の切出し枠**を `var/expense/extracted/<ファイル名>.json`(サイドカー)に書く。
   不明点(外貨レート・費目)は操作者に確認する(外貨レートは継続適用・源泉妥当性を税理士確認のフラグつきで記録)。
5. **処理**: `expense process` — リネーム(`YYYY-MM-DD_支払先`)・画像トリミング(原本は `_original`)・重複排除
   (内容ハッシュ完全一致 / 日付+支払先+金額の近接。重複は `--approve-overwrite` か対話 y/N の承認後に上書き=
   SharePoint 版履歴で復元可。削除はしない)・前期実績ベースの費目/税区分・内外判定・外貨円換算・相関キー付与で
   **経費明細の下書き**(`var/expense/drafts/`)を生成。検証ゲートの指摘(費目未確定・外貨未換算・参加者メモ要 等)を表示。
6. **保存(マスタ)**: `expense push` — `var/expense/processed/`(リネーム後 + `_original`)を SharePoint の
   expense-master へ反映。`expense csv` で下書きを CSV 出力。`expense status` / `expense drafts` で確認。
7. **API 登録(電帳法)**: `expense register`(既定ドライランで予定を確認 → `--confirm` で本番送信)。
   `POST me/ex_transactions` に証憑画像(`receipt_input`)を同梱し **1コールで登録 + 証憑添付**(CSV 取込は証憑を
   付けられず電帳法非対応のため API 登録を採用)。費目/税区分は前期実績の名前→ID で解決。ゲート error / 費目ID未解決は skip。
   登録成功時に **Teams(OPERATIONS チャネル)へ明細詳細を自動通知**(`scripts/notify.py`・`ac expense notify [--id]` で再送可)。
8. **inbox 整理**: `expense clean-inbox`(既定ドライラン → `--confirm`)。**登録済みの証憑のみ** SharePoint inbox から
   削除(証憑が MF に入った後だけ消す。ごみ箱から復元可)。
9. **明細台帳(Excel)**: `expense xlsx --push` — ledger から証憑サムネイル + クラウド経費明細番号 + 内容の一覧を
   xlsx 化し ドキュメント/Expense/ 直下へ。過去分(下記)も同じ行形式で台帳に載る。

### 過去分の確認・補正(`ac expense import-past` / `revise-past` — BL-AC-025)

クラウド経費の **内蔵 OCR は精度が低い**。**新しいポリシーを追加した際** などに、**今期(未締め)分** の既存
明細を取り込み、証憑を Claude が再読込して **当期ポリシーを再適用 → 誤りを補正(PUT)** する。

1. **取込**: `expense import-past`(既定 今期=`2025-07-01`〜今日。`--from/--to` で調整)— `me/ex_transactions` を
   取得し、各明細の証憑画像を `GET .../{id}/mf_file` で `var/expense/past/<id>.<ext>` にDL(リサイズなし)、MF 現値
   スナップショット `<id>.mf.json` を保存、台帳に `imported` で登録。**証憑なし明細(紙・添付なし)は「証憑なし
   WEB確認」とフラグ**(自動補正の対象外=クラウド経費 WEB で手動対応)。
2. **(Claude)** `var/expense/past/<id>.<ext>` を Read → 正しい値で `extracted/past_<id>.<ext>.json`(サイドカー)を
   生成(日付・支払先・金額・通貨・登録番号・費目・税区分・外貨レート)。不明点は操作者に確認。
3. **補正**: `expense revise-past`(既定ドライランで差分プレビュー → `--confirm` で本番 PUT・`--id` で限定)—
   サイドカー(無ければ MF 現値)に当期ポリシーを再適用し、MF 現値との差分(`費目: 旧→新` 等)を提示。`--confirm` で
   **変更フィールドのみ** を `PUT me/ex_transactions/{id}` で更新(費目/税区分は名前→ID で解決)。摘要は既定で温存し
   `--rewrite-remark` 指定時のみ店名先頭へ整形。**証憑は再アップロードしない**(再 OCR を避ける)。差分ゼロは skip
   (二重 PUT 防止)。補正成功で台帳 `revised`、OPERATIONS へ通知。

> **適用範囲(重要)**: 「過去取引は取引日基準で旧ルールを維持(再計算しない)」は **締め済み(申告済み)期間** を
> 守る規定。本機能は **今期(未締め)分のみ** を対象に当期ポリシーを再適用する(締め前の是正)。**過年度(締め済み)
> は対象にしない**。証憑どおりの事実(費目名/金額/支払先)の補正は OCR 是正であり、版の遡及ではない。

会計の勘定科目は扱わない(クラウド経費で承認 → 会計登録時に MF がマトリクスで費目→勘定科目へ自動変換)。
接待/会議費の**参加者メモはクラウド経費の WEB で登録**する(またはサイドカー `attendants:[自社,社外]` で API 同梱)。
ヘッドレス抽出(ビジョンブリッジ)+ Teams 確認・クラウドBOX 連携は後続タスク。

## Teams 確認の運用

- カードには抽出値と NG 項目(例: 登録番号なし、税区分なし、レート要確認)を表示する。
- 修正して承認すると確定値がエージェントに戻る。低信頼分は日次でまとめて処理してよい。

## 月次レビュー

- フラグ(税理士確認・要確認)の棚卸し。
- `compliance-checklist.md` に沿ったサンプル監査。
- 税区分・勘定科目・為替記録の偏差、重複の確認。

## 決算前

- 税理士連携。外貨建資産・負債の評価替え、要確認事項の整理。

## エラー対応

- API 429(レート制限): バックオフして再試行。
- レート取得不可: フラグして人手確認。
- 抽出失敗・重複検知: 該当を保留し、台帳に記録。

## ポリシー改定手順

1. ローカルの Claude Code で `docs/` を改定(適用開始日・理由を明記)。
2. 差分レビュー → コミット(`policy: ...`)→ push。
3. 自動処理サーバが pull で最新化する。
4. 過去取引は取引日基準で旧ルールを維持する(再計算しない)。
