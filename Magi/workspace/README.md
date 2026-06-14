# Magi/workspace — シナリオ入出力(ADR-0009 / ADR-0011)

Magi のシナリオ(ブレスト・合議・資料レビュー・人格テスト)の入出力を集約する単一ルート。
SharePoint 連携時(`sharepoint.config.json` の enabled=true)は
`python ../shared/sharepoint.py sync --project .` で双方向同期される。

| サブフォルダ | 用途 |
|---|---|
| `input/` | メディア入力(画像/PDF/Office) |
| `media-output/` | 生成チャート等 |
| `deliberations/` | 合議ログ |
| `reviews/` | 資料チェック&リバイス成果物 |
| `brainstorms/` | ブレスト成果物 |
| `persona-tests/` | 人格テスト結果 |
