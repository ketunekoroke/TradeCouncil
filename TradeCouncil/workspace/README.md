# `workspace/` — シナリオ入出力の単一ルート(ADR-0009)

すべてのシナリオの入出力は**このディレクトリ1本**に集約される(旧 `local/`・`sharepoint/`
の二重ツリーは廃止)。SharePoint 連携(`sharepoint.config.json` の `enabled`)は
**同期するかどうか**だけを変え、作業場所は常にここ。

| サブフォルダ | 用途 |
|---|---|
| `council/` | 意思決定会議の議事録(**git 追跡** — ADR-0005) |
| `input/` | 対象資料・添付メディア(レビュー/合議の入力) |
| `media-output/` | 生成チャート(.png / .svg) |
| `reviews/` | 資料チェック&リバイス(document-review)の成果物 |
| `deliberations/` | 合議(deliberation)の成果物・議論ログ |
| `brainstorms/` | ブレスト(brainstorm)の成果物・アイデアマップ |
| `persona-tests/` | 人格テスト(persona-test)の比較レポート |

## SharePoint 同期(enabled=true のとき)

```
python scripts/sharepoint.py sync
```

- **双方向・追加型・新しい方が勝つ**(更新時刻比較。シナリオ開始/終了時に自動実行される)
- **削除は伝播しない**: 片側で消してももう片方に残る(誤削除に対する安全側)。
  完全に消すにはローカルと SharePoint の両方で削除する
- 除外: `.gitkeep`・この README・`*.tmp`

> サブフォルダの中身は個人情報・容量の都合で `.gitignore` 済み(例外:
> `council/**/*.md` = 議事録は監査テキストとして git 追跡する)。
