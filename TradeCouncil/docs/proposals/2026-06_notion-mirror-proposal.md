# 提案書: Notion 可視化ミラー(ドキュメント系データの一覧化)

| 項目 | 内容 |
|---|---|
| 日付 | 2026-06-11 |
| ステータス | **採用(閲覧専用)— 2026-06-12、ADR-0005**。ツール採用として運用開始。通知・可視化方針としての正式批准は第0回会議の P-11 決裁で行う |
| 提案者 | 決裁権者の要望(ドキュメント系データの可視化)に基づき Claude Code が起草 |
| 関連 | ADR-0002 §5 / docs/03 P-11 / scripts/sharepoint.py(既存の SharePoint 連携) |

---

## 1. 目的と位置づけ

会議議事録・ポリシー台帳・KPI・決裁キューといった**ドキュメント系データ**を、
Notion のデータベースビュー(テーブル/ボード/タイムライン)で一覧・検索できるようにする。

- Notion は**可視化ミラー(読み取り用の写し)**であり、決裁・執行の経路には一切入らない
- コードは実装しない。Claude Code セッションに接続済みの **Notion MCP** を、
  ファシリテーターがシナリオの**事後処理**として使う運用とする(追加実装ゼロで開始できる)

## 2. 原則(不変条項との整合)

1. **真実の源泉は動かさない**: 議事録 = `<root>/council/` の Markdown(git 管理)、
   ポリシー = `config/policies/*.yaml` + DB(policies / policy_decisions)、KPI = SQLite。
   Notion はそれらの写しに過ぎない
2. **一方向同期のみ**(リポジトリ → Notion)。Notion 上の編集をシステムへ反映する経路は
   作らない・作ってはならない(LLM非執行原則/不変条項3の監査ログは git+DB 側で完結)
3. 各 Notion ページの冒頭に「**本ページは閲覧用ミラー。ここでの編集は効力を持たない。
   原本: <リポジトリ内パス>**」を明記する
4. シークレット(API キー・Workflow URL 等)を Notion に書かない

## 3. 対象データと Notion データベース設計

ワークスペースに「TradeCouncil」ページを作り、配下に以下の5データベースを置く。

### 3.1 会議議事録(Council Minutes)

| プロパティ | 型 | 元データ |
|---|---|---|
| 会議名 | Title | 議事録ファイル名(例 `2026-06-22-council-0`) |
| 種別 | Select(kickoff/monthly/adhoc/weekly) | council_sessions.kind |
| 開催日 | Date | council_sessions.started_at |
| 決裁結果 | Multi-select(P-XX approve/defer 等) | 議事録の決裁サマリ |
| 原本パス | Text | `<root>/council/<file>.md` |
| 本文 | ページ本文 | 議事録 Markdown を転記 |

### 3.2 ポリシー台帳(Policy Registry Mirror)

| プロパティ | 型 | 元データ |
|---|---|---|
| ポリシー | Title(例 `P-03 口座リスク上限`) | policies.policy_id + title |
| status | Select(draft/proposed/active/retired) | policies.status |
| version | Number | policies.version |
| 現在値 | Text(要約) | policies.value_json |
| review_after | Date | policies.review_after(期限切れビューで再上程漏れを可視化) |
| 最終決裁 | Text(`D-P-XX-vNNN`) | policy_decisions |

### 3.3 週次KPI(Bot KPI Weekly)

| プロパティ | 型 | 元データ |
|---|---|---|
| BOT×週 | Title(例 `dummy_rw 2026-W24`) | bot_kpi_weekly |
| PF / Sharpe / MaxDD / 勝率 / 取引数 | Number | 同上 |
| status | Select(ACTIVE/REDUCED/PAPER/RETIRED) | 同上(悪BOT状態遷移をボードビューで可視化) |

### 3.4 決裁キュー(Proposals)

| プロパティ | 型 | 元データ |
|---|---|---|
| 提案 | Title | proposals.content_json の要約 |
| status | Select(pending_decision/approved/rejected/deferred) | proposals.status |
| 対象ポリシー | Select(P-XX) | proposals.target_policy_id |

pending の滞留をボードビューで見える化する(決裁は従来どおり `tc approve` のみ)。

### 3.5 シナリオ成果物(Deliberations / Reviews / Brainstorms)

| プロパティ | 型 | 元データ |
|---|---|---|
| タイトル | Title | 成果物ファイル名 |
| シナリオ | Select(deliberation/document-review/brainstorm/persona-test) | 出力ディレクトリ |
| 日付 | Date | ファイル名の日付 |
| 原本パス | Text | `<root>/<dir>/<file>` |

## 4. 運用手順(ファシリテーター向け)

同期タイミング: **①会議(council)終了時 ②週次 KPI 集計時 ③シナリオ成果物の生成時**。

1. 初回のみ: `notion-create-database` で §3 の5データベースを作成(本提案の採用決裁後)
2. 会議終了時: 議事録を書き出した後、`notion-create-pages` で「会議議事録」DB に追加し、
   決裁があれば `notion-update-page` で「ポリシー台帳」の該当行(status/version/現在値)を更新
3. 週次: `tc kpi` の結果を「週次KPI」DB に `notion-create-pages` で追加
4. 提案の起票・解決時: 「決裁キュー」DB の該当行を更新
5. いずれも完了後、成果物のローカルパスと Notion ページ URL の**両方**をユーザーに提示する

プロンプト例(会議シナリオの最終ラウンド後):
> 「議事録 `local/council/2026-06-22-council-0.md` を Notion の会議議事録DBへミラーし、
> P-01〜P-04 の決裁結果でポリシー台帳を更新してください」

## 5. SharePoint 連携との関係

- 既存の SharePoint 連携(`scripts/sharepoint.py`)は**ファイルの保管・共有**
  (input の受領、成果物の配布)を担い、Notion は**構造化された一覧・検索**を担う
- 二重ミラーの維持コストが問題になる場合、どちらかへ寄せる判断は会議論点とする

## 6. 不採用とした代替案

| 案 | 不採用理由 |
|---|---|
| Notion API のコード実装(`scripts/notion.py`) | Phase 0 のコード・シークレット管理を増やす割に、同期は人間参加シナリオの事後処理で足りる。L1 常駐プロセスからの自動同期が必要になった時点で別 ADR として再検討 |
| SharePoint リストでの代替 | 既存連携はドキュメントライブラリのみ。リスト用の権限・実装追加が必要で、Notion DB ほどビューが柔軟でない |
| 同期の双方向化 | LLM非執行原則・監査ログの一元性に抵触するため恒久的に不採用(原則2) |

## 7. 決裁を求める事項

1. Notion ミラー運用の採否(採用なら初回データベース作成を実施)
2. 対象データ範囲(§3 の5種で開始してよいか)
3. SharePoint との役割分担(§5)
