# ADR-0010: docs/ とルート管理表の SharePoint 一方向ミラー(git main 追従)

| 項目 | 内容 |
|---|---|
| 日付 | 2026-06-13 |
| ステータス | 承認済み(決裁権者の計画承認による) |
| 関連 | ADR-0009(workspace 双方向同期)/ scripts/sharepoint.py / scripts/hooks/ / BL-040 |

## 背景

ADR-0009 で workspace/(シナリオ入出力)は SharePoint と双方向同期されるようになり、
議事録・合議ログは Teams から見える。一方、プロジェクトの**仕様・管理ドキュメント**
(docs/ 一次資料・ADR・README・REQUIREMENTS 等の管理表)は git 上にしかなく、
Teams/SharePoint だけではプロジェクト全体像を閲覧できなかった。

利用者要望: docs/ も SharePoint にアップしたい。**main ブランチの内容のみ**を、
**コミット・プッシュのタイミング**で同期したい(「origin/main と同期させるイメージ」)。

## 決定事項

### 1. git main → SharePoint `Docs/` の一方向ミラー(`sharepoint.py mirror`)

- 対象: `docs/` 一式 + ルート管理表(README / DOCS / REQUIREMENTS / FEATURES /
  TESTCASES / BACKLOG / DEVELOPMENT)。`sharepoint.config.json` の `git_mirror` 節で定義
- 配置: ドキュメントライブラリ直下の **`Docs/`**(`Workspace/` の隣)に
  リポジトリ相対パスを維持して置く(例: `Docs/docs/01_要件定義書.md`、`Docs/README.md`)
- **内容は作業ツリーではなく git の main コミットから読む**(`git show <sha>:<path>`)。
  未コミットの編集は決して流れない = 「main の内容のみ」を機械的に保証する

### 2. 完全ミラー(削除・リネームも反映)

- workspace 双方向同期の「削除非伝播」(ADR-0009 §2)とは**別方針**。こちらは
  一方向で真実源が常に git main のため、main から消えたファイルは SharePoint からも
  削除する(古い仕様書が残留して誤読される方が害が大きい)
- SharePoint 側の `Docs/` は**読み取り専用ミラー**。編集は git で行う
  (遠隔での手編集は次回ミラーで検出されず、ミラー対象ファイルなら次の変更時に上書きされる。
  修復は `mirror --full`)

### 3. 差分ベースの増分同期 + 状態ファイル

- `var/sharepoint_mirror.json` に前回ミラー済みコミット sha を記録
- 実行時: `git diff --name-status <前回sha>..<main>` の対象パスのみ
  push(A/M/T)/ 遠隔削除(D)/ 削除+push(R)。main が前回と同一なら通信せず終了
- **全アクション成功時のみ状態を進める**。失敗時は次回実行が前回 sha からの
  差分で自動的に追いつく(ネットワーク断に強い)
- 初回(状態なし)と `--full` は全ファイル push + 遠隔の余剰ファイル削除(prune)

### 4. トリガーは git フック(`tc hooks install` で導入・fail-open)

| フック | 動作 |
|---|---|
| post-commit | 現在ブランチが main のときだけ `mirror` 実行 |
| pre-push | `mirror` 実行(ff マージ等 post-commit が発火しないケースを回収) |

- **fail-open(warn のみ・常に exit 0)**: ミラー失敗でコミット/プッシュを止めない。
  ドキュメント閲覧ミラーの不達は致命でなく、状態が進まないので自動回復する
  (発注系の fail-closed とは安全性の向きが逆であることに注意)
- `enabled=false`(SharePoint 連携オフ)時は何もしない
- 手動同期はいつでも `python scripts/sharepoint.py mirror [--full]`

## 却下した代替案

| 代替案 | 却下理由 |
|---|---|
| workspace 双方向 sync に docs を追加 | docs の真実源は git。双方向だと SharePoint 側の編集が git を迂回して逆流する(LLM非執行と同型の「検証なし反映」リスク)。削除非伝播も古い仕様書を残す |
| 作業ツリーからの push | 未コミット・ブランチ作業中の内容が漏れ「main のみ」を保証できない |
| 毎回フル比較(タイムスタンプ) | git blob に mtime が無く比較基準が曖昧。差分 + sha 状態の方が正確で通信も最小 |
| CI(GitHub Actions)でミラー | シークレットを GitHub に複製する必要が生じる。ローカルフックなら .env のまま |
| 失敗時にコミットをブロック(fail-closed) | ネットワーク断でドキュメント作業が止まる。閲覧ミラーに執行リスクは無く warn で十分 |

## 影響・注記

- `tc hooks install` は pre-commit / post-commit / pre-push の3フックを書く(冪等)
- post-commit のたびに数秒の通信が入る(up to date 時は rev-parse 比較のみで通信なし)
- 秘密情報はコミット済み内容しか流れず、上流の pre-commit 秘密検査が防御線
- prototype/ は対象外(削除判断 BL-039 まで現状維持)
