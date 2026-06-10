# `local/` — SharePoint 不使用時の入出力 root

`sharepoint.config.json` の `"enabled": false` のとき、プロトタイプの入出力は**この
ディレクトリ**を root として行われる(従来の `media/` `reviews/` `deliberations/` の後継)。
ネットワークは使わず、純ローカルで完結する。

`sharepoint/` と**同一のサブフォルダ構成**を持つ:

| サブフォルダ | 用途 |
|---|---|
| `input/` | 対象資料・添付メディア(レビュー/合議の入力) |
| `media-output/` | 生成チャート(.png / .svg) |
| `reviews/` | 資料チェック&リバイス(document-review)の成果物 |
| `deliberations/` | 合議(deliberation)の成果物・議論ログ |
| `brainstorms/` | ブレスト(brainstorm)の成果物・アイデアマップ |
| `persona-tests/` | 人格テスト(persona-test)の比較レポート |

アクティブな root は `python scripts/sharepoint.py root` で確認できる。
SharePoint 連携を有効にすると root は `sharepoint/` に切り替わる(→ ルート `README.md` /
`DOCS.md` の SharePoint 連携の節)。

> 各サブフォルダの中身は個人情報・容量の都合で `.gitignore` 済み(`.gitkeep` のみ追跡)。
