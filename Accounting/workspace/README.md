# workspace — シナリオ入出力

経理処理シナリオ(scenarios/monthly-review.md)の入出力。**個人情報・容量の理由でデフォルト git 除外**
(ADR-0009 / ルート .gitignore)。`.gitkeep` と本 README、`council/**/*.md`(監査テキスト)のみ追跡。

| ディレクトリ | 用途 |
|---|---|
| `input/` | 証憑・明細の取り込み(紙スキャン/メール添付/アップロード) |
| `reviews/` | 抽出・検証・要確認のレビュー結果 |
| `council/` | 月次レビュー等の記録(議事テキストは追跡。メディアは除外) |
| `media-output/` | 生成された表・図(除外) |

SharePoint 連携(`sharepoint.config.json` の `enabled`)時は `python ../shared/sharepoint.py sync --project .`。
秘匿情報(口座番号・カード番号)はログ・コミットに残さない。
