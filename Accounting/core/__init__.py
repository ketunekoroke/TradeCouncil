"""Accounting ドメインロジック(会計経理支援システムの実行時コード)。[Phase 0 = 雛形]

依存規約(ADR-0011): この package は **標準ライブラリ + 自前モジュールのみ** に依存する。
`Magi` / `TradeCouncil` を import しない(削除可能性。tests/test_decoupling.py が検査する)。
外部 LLM 召喚・SharePoint・Office 変換が必要な処理は `scripts/` / `scenarios/` 側で `../shared/` を使う。

予定構成(BL-AC-012 以降で実装する。先回りで作らない):
  core/ingest      取り込み: 紙スキャン/メール添付/アップロードのステージング・重複検知
  core/extract     抽出: 証憑の構造化(日付・金額・通貨・取引先・取引内容 + 確信度)
  core/policy      会計ポリシー適用: 適用開始日で版を選び、消費税(内外判定・税区分)・為替換算を当てる
  core/gate        検証ゲート: 為替・税区分・証憑要件(電帳法 検索3項目)の機械チェック(scripts/check_compliance と共有)
  core/register    経費登録: MoneyForward 経費 API への書き込み(摘要に相関キー)。不可逆操作はしない
  core/reconcile   会計連携: 相関キーで会計仕訳を突合し mf_journal_id を確定、仕訳調整

正本の判断方針は docs/accounting-policy.md。技術設定は config/system.yaml、勘定科目は config/accounts.yaml。
"""
