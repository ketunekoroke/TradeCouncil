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

SharePoint をマスタデータとし、Claude Code が手動で回す半自動フロー(下書きまで。実 API 登録は後段)。
起動は `cd Accounting; ..\.venv\Scripts\python.exe -m scripts.cli expense <sub>`。

1. **前期実績の学習**: `expense refdata` — 前期(7月〜翌6月)の自分の経費明細(`me/ex_transactions`)から
   **よく使う費目・税区分**を集計し `var/expense/refdata/expense_usage.json` に保存。`--from/--to` で範囲調整。
2. **取り込み**: スマホ撮影/PDF を Teams の Expense チャネル(SharePoint 連携)へ投稿 → `expense pull` で
   SharePoint の expense-inbox を `var/expense/raw/` へ取得。
3. **抽出(Claude)**: `raw/` の各ファイルを Claude が読み、日付・支払先・金額・通貨・内容・(登録番号)・費目
   ヒント・**画像の切出し枠**を `var/expense/extracted/<ファイル名>.json`(サイドカー)に書く。不明点(外貨レート・
   費目)は操作者に確認する(外貨レートは継続適用・源泉妥当性を税理士確認のフラグつきで記録)。
4. **処理**: `expense process` — リネーム(`YYYY-MM-DD_支払先`)・画像トリミング(原本は `_original`)・重複排除
   (内容ハッシュ完全一致 / 日付+支払先+金額の近接。重複は `--approve-overwrite` か対話 y/N の承認後に上書き=
   SharePoint 版履歴で復元可。削除はしない)・前期実績ベースの費目/税区分・内外判定・外貨円換算・相関キー付与で
   **経費明細の下書き**(`var/expense/drafts/`)を生成。検証ゲートの指摘(費目未確定・外貨未換算・参加者メモ要 等)を表示。
5. **保存(マスタ)**: `expense push` — `var/expense/processed/`(リネーム後 + `_original`)を SharePoint の
   expense-master へ反映。`expense csv` で下書きを CSV 出力。`expense status` / `expense drafts` で確認。
6. **API 登録(電帳法)**: `expense register`(既定ドライランで予定を確認 → `--confirm` で本番送信)。
   `POST me/ex_transactions` に証憑画像(`receipt_input`)を同梱し **1コールで登録 + 証憑添付**(CSV 取込は証憑を
   付けられず電帳法非対応のため API 登録を採用)。費目/税区分は前期実績の名前→ID で解決。ゲート error / 費目ID未解決は skip。
   登録成功時に **Teams(OPERATIONS チャネル)へ明細詳細を自動通知**(`scripts/notify.py`・`ac expense notify [--id]` で再送可)。
7. **inbox 整理**: `expense clean-inbox`(既定ドライラン → `--confirm`)。**登録済みの証憑のみ** SharePoint inbox から
   削除(証憑が MF に入った後だけ消す。ごみ箱から復元可)。
8. **明細台帳(Excel)**: `expense xlsx --push` — ledger から証憑サムネイル + クラウド経費明細番号 + 内容の一覧を
   xlsx 化し ドキュメント/Expense/ 直下へ。将来はクラウド経費の過去分(`me/ex_transactions` 全件)も同形式で取込。

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
