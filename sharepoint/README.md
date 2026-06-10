# `sharepoint/` — SharePoint 連携時の入出力 root(ローカルミラー)

`sharepoint.config.json` の `"enabled": true` のとき、プロトタイプの入出力は**この
ディレクトリ**を root として行われる。中身は SharePoint ドキュメントライブラリの
**ローカルミラー**で、`scripts/sharepoint.py` の `pull` / `push` で遠隔と同期する
(クライアントシークレット認証には OS レベルのマウントが無いため、同期方式を採る)。

`local/` と**同一のサブフォルダ構成**を持つ:

| サブフォルダ | 用途 | 同期方向 |
|---|---|---|
| `input/` | 対象資料・添付メディア(レビュー/合議の入力) | `pull`(遠隔 → ローカル) |
| `media-output/` | 生成チャート(.png / .svg) | `push`(ローカル → 遠隔) |
| `reviews/` | document-review の成果物 | `push` |
| `deliberations/` | deliberation の成果物・議論ログ | `push` |
| `brainstorms/` | brainstorm の成果物・アイデアマップ | `push` |
| `persona-tests/` | persona-test の比較レポート | `push` |

中身はリモートから取得されるため、リポジトリ上は初期状態(`.gitkeep` のみ)。
設定・認証・権限・コマンドは ルート `README.md` / `DOCS.md` の **SharePoint 連携の節**を参照。

> 各サブフォルダの中身は `.gitignore` 済み(`.gitkeep` のみ追跡)。
