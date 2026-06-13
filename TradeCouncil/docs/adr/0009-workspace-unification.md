# ADR-0009: シナリオ入出力の統合(単一 workspace/ + 双方向自動同期)

| 項目 | 内容 |
|---|---|
| 日付 | 2026-06-12 |
| ステータス | 承認済み(決裁権者の計画承認による) |
| 関連 | ADR-0005(議事録の git 追跡)/ scripts/sharepoint.py / CLAUDE.md「入出力ディレクトリ」/ scenarios/ |

## 背景

シナリオ入出力は `local/`(既定)と `sharepoint/`(連携時ミラー)の**同一構造の
二重ツリー**で、`sharepoint.config.json` の `enabled` によりアクティブ root が
切り替わる方式だった。このため:

1. 「`<root>` は local/ または sharepoint/」という分岐説明が CLAUDE.md・
   scenarios 全ファイル・DOCS/DEVELOPMENT・.gitignore に散在し構成が複雑
2. 同期は手動の方向別コマンド(`pull input` → 作業 → `push <dir>`)で、
   対象フォルダの選択をユーザー/ファシリテーターが意識する必要があった
3. council(議事録)は同期対象外で、SharePoint/Teams から議事録が見えなかった

利用者から「単一フォルダに統合し、SharePoint オンで全ファイルが双方向に
自動同期される仕様でよいのではないか」と提案された。

## 決定事項

### 1. 入出力 root は単一の `workspace/` に統合する

- `local/`・`sharepoint/` を廃止し、`workspace/` 1本にする
  (council / input / media-output / reviews / deliberations / brainstorms / persona-tests)
- `enabled` は「root の切替」ではなく「**SharePoint と同期通信するか**」のみを制御する。
  オフでも作業場所は同じ `workspace/`(純ローカル運用)

### 2. 同期は双方向・追加型・newer-wins(`sharepoint.py sync`)

- 相対パスごとに判定: 片側のみ → コピー / 両側 → **更新時刻の新しい方が勝つ** /
  時刻差が許容誤差(2秒)以内 → スキップ
- **削除は伝播しない**(追加型)。片側で消してももう片方に残る = 誤削除に対する安全側。
  完全に消すには両側で削除する
- **mtime 整合**: push/pull 後に遠隔の lastModifiedDateTime をローカル mtime に反映し、
  アップロード時刻起因のピンポン同期を防ぐ
- 除外: `.gitkeep` / workspace 直下の `README.md` / `*.tmp`

### 3. 「自動」= シナリオ開始/終了時にファシリテーターが sync を実行する

- SharePoint 連携時の作法(CLAUDE.md): シナリオ開始時に
  `python scripts/sharepoint.py sync` → 成果物生成後にもう一度 `sync`。
  方向・フォルダの選択は不要(全フォルダ対象)
- 常駐 watch プロセスは作らない(プロセス管理を増やさない。必要になれば
  Phase 1 の systemd timer で再検討)
- `pull` / `push` は選択的リカバリ用コマンドとして残す

### 4. council(議事録)も同期対象に含める

- `sharepoint.config.json` の folders に `council` を追加。SharePoint は議事録の
  **閲覧用ミラー**になり、Teams のファイルタブから見える(可視化の向上)
- **git 追跡 = 監査の真実源は不変**(ADR-0005)。gitignore の追跡例外は
  `workspace/council/**/*.md` に引き継ぐ

## 却下した代替案

| 代替案 | 却下理由 |
|---|---|
| 二重ツリー現状維持 | 分岐説明の散在・手動同期の認知負荷が解消しない(本 ADR の動機) |
| 完全ミラー(削除も伝播) | 誤削除が反対側も消す。削除検出の状態管理が必要で実装も重い |
| OneDrive 同期クライアントに任せる | コード不要だがマシン依存(EC2/Linux 不可)、git 追跡ファイルとの相性問題、ヘッドレス運用に不向き |
| 常駐 watch プロセス | 管理対象プロセスが増える。シナリオ駆動の利用実態では開始/終了 sync で足りる |

## 影響・注記

- CLAUDE.md・scenarios 全ファイル・DOCS/DEVELOPMENT・.gitignore から
  「`<root>` = local/ または sharepoint/」の分岐記述を排除し `workspace/` に単純化
- 既存議事録は `git mv` で workspace/council/ へ移行(履歴維持)。DB の
  council_sessions.minutes_path は `tc council log` で更新
- **prototype/ は独立した参照資料(編集禁止)のため二重ツリー方式のまま**。
  ルートの scripts/sharepoint.py はここで分岐する(意図的な乖離)
