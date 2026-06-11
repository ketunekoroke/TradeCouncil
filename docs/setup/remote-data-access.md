# セットアップ手順書: 開発機から本番データを閲覧する

| 項目 | 内容 |
|---|---|
| 日付 | 2026-06-12 |
| 対象 | 開発する Windows 機から、本番(Phase 1+ サーバ)の議事録・DB データ・ファイルを安全に閲覧する |
| 関連 | ADR-0005 / docs/05 §3.5.1・§5 / docs/proposals/2026-06_notion-mirror-proposal.md |

> **大原則(ADR-0005)**: git は一方向(開発機 → push → 本番 pull)。**本番は push しない**。
> 本番で生成されるデータは git を通さず SSH / `tc snapshot` / SharePoint で開発機へ還流する。
> **生 SQLite を WAL 稼働中のまま直接コピー/共有しない**(破損の恐れ)。

データ種別ごとに経路が異なる。以下を種別ごとに参照。

---

## 1. ポリシー・決裁レコード → git(設定済み)

`config/policies/*.yaml` は git 追跡済み。開発機・本番ともに `git pull` で最新を得る。
決裁(`tc policy record`)は開発機で行い、`git push` → 本番 `git pull` で反映する。

## 2. 会議議事録(.md)→ git

council 会議は開発機で開催する(Claude Code ファシリテーター)。議事録は
`local/council/<日付>-<会議名>.md` に出力される。`.gitignore` の例外で
`council/*.md` のみ追跡対象なので、会議後に**開発機で**コミットする:

```powershell
git add local/council/2026-06-22-council-0.md
git commit -m "docs(council): 第0回意思決定会議 議事録"
git push
```

- 本番からは閲覧不要(会議は開発機の作業)。別マシンで見たいときは `git pull`
- **機微情報(APIキー・残高の生値等)を議事録本文に書かない**(git 追跡対象になる)
- かさばるメディア・チャートは追跡対象外 → 必要なら SharePoint(§4)

## 3. DB トランザクションデータ(注文・KPI・建玉)→ SSH ライブ読取

本番の DB ファイルは動かさず、**本番上で読取コマンドを実行して出力だけ受ける**:

```powershell
ssh prod "cd /opt/tradecouncil && .venv/bin/python -m scripts.cli kpi"
ssh prod "cd /opt/tradecouncil && .venv/bin/python -m scripts.cli status"
ssh prod "cd /opt/tradecouncil && .venv/bin/python -m scripts.cli policy list"
```

- リアルタイム・DB ファイルを転送しないので WAL 稼働中でも安全
- これらは読取専用コマンド(観測)。本番を変更するコマンド(kill/resume/record 等)は
  この経路で実行しない(変更は git + 決裁ゲート経由 — docs/05 §3.5)
- SSH 鍵は開発機 → 本番の片方向のみ設定(本番から開発機への鍵は不要)

## 4. シナリオ成果物・ファイル → SharePoint 同期

review / deliberation / brainstorm の成果物やメディアは SharePoint で同期する
(既存 `scripts/sharepoint.py`、設定は docs の「SharePoint 連携」参照):

```powershell
python scripts/sharepoint.py pull reviews deliberations    # 遠隔 → 開発機
python scripts/sharepoint.py push media-output             # 開発機 → 遠隔
```

## 5. DB 整合スナップショット / バックアップ → `tc snapshot`

オフラインで DB を解析したい、またはバックアップを取りたいときは、整合性のある
読取専用コピーを作る(`VACUUM INTO`。WAL 稼働中でも安全):

```powershell
# 本番(またはローカル)で実行 — var/snapshots/ にタイムスタンプ名で生成
python -m scripts.cli snapshot
# 出力先を明示する場合
python -m scripts.cli snapshot --output backup/2026-06-22.db
```

- 生成された .db は通常の SQLite として読取専用で開ける(元 DB は無傷)
- 本番で生成 → SharePoint または `scp` で開発機へ配布(git は使わない)
- `tc snapshot` は本番未構築でも**いま手元の DB に対して動く**(バックアップ用途)

```powershell
# 本番スナップショットを開発機へ(例)
ssh prod "cd /opt/tradecouncil && .venv/bin/python -m scripts.cli snapshot --output /tmp/snap.db"
scp prod:/tmp/snap.db .\snapshots\
```

## 6. 可視化(議事録・ポリシー・KPI)→ Notion ミラー(閲覧専用)

スマホ・ブラウザから読みやすく見たいデータは Notion へ一方向ミラーする
(採用済み — ADR-0005。コードはなく、ファシリテーターが MCP で同期)。
対象データ・データベース設計・同期手順は
[docs/proposals/2026-06_notion-mirror-proposal.md](../proposals/2026-06_notion-mirror-proposal.md) を参照。

- 同期タイミング: 会議終了時(議事録・ポリシー台帳)・週次(KPI)
- Notion は**閲覧用の写し**。Notion 上の編集はシステムに反映されない(真実の源泉は git/DB)

---

## まとめ(どの経路で何を見るか)

| 見たいもの | コマンド/操作 |
|---|---|
| 最新のポリシー・議事録 | `git pull` |
| 注文・KPI・建玉のいま | `ssh prod "... -m scripts.cli kpi/status"` |
| DB をオフライン解析・バックアップ | `tc snapshot` → SharePoint/scp |
| レビュー成果物・メディア | `sharepoint.py pull` |
| スマホで議事録・KPI 一覧 | Notion ミラー |
