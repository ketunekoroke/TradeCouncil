# ADR-0006: AWS ホスティングと可観測性・ダッシュボード設計

| 項目 | 内容 |
|---|---|
| 日付 | 2026-06-12 |
| ステータス | 承認済み(決裁権者の計画承認による) |
| 関連 | docs/01 A-5・A-6 / docs/02 §2 / docs/05 §4・§5(ホスティング)/ docs/setup/aws-architecture.md / ADR-0004(環境戦略)/ ADR-0005(git 一方向)/ ADR-0002・0003(Teams 通知) |

## 背景

Phase 1 のホスティング(A-5)が未決だった(docs/05 §4 で VPS/Azure/自宅を比較)。
決裁権者は **AWS に習熟**しており AWS を希望。Teams を使うため Azure 親和性の優劣、
ログ集約(CloudWatch Logs)、DynamoDB のコスト妥当性、サーバ状態・取引ダッシュボードを
**Teams タブの Power BI** で作る構想について判断が必要だった。

### Azure 親和性の評価(結論: AWS で問題ない)
- Teams 通知は既に **Power Automate Workflows(HTTP webhook)** で実装済みで**クラウド非依存**。
  AWS から POST しても同一に動く(ADR-0002/0003)
- Power BI は Athena / RDS / S3 等 **AWS データソースに接続できる**
- Azure の親和性優位(Entra ID 認証・クロスクラウド転送ゼロ・Power BI ゲートウェイ簡素)は
  実在するが小さく、AWS 習熟というメリットを上回らない

## 決定事項

### 1. ホスティング(A-5)= AWS

- EC2 1台(`t4g.small` 級・ARM、`ap-northeast-1`)+ systemd で BOT・watchdog を常駐
- SQLite は EBS(gp3)上。月額は A-6(1万円)内に収まる(EC2 + EBS + CloudWatch + S3/Athena 従量)

### 2. コア DB は SQLite を維持(DynamoDB はコアに使わない)

- 注文・決裁・監査ログは**リレーショナル前提**: 根拠連鎖検証(orphan=0)・FK 連鎖
  (orders→trade_decisions、fills→orders)・JOIN(feedback/kpi.py)・append-only 監査
  (policy_decisions)。NoSQL 化は不変条項を損なう大規模再設計になる
- 分析・ダッシュボード用途は、コアを移行せず **S3 へ定期エクスポート → Athena**(従量課金・
  アイドルほぼ0円)で賄う。これがコスト関心(DynamoDB を検討した理由)への回答
- 将来スケール時の選択肢は Aurora/RDS Postgres(SQLAlchemy のため移行可・docs/04 §5)。
  ただし Aurora Serverless v2 の最低 ACU コストは A-6 を超えうるため Phase 1 では採らない

### 3. ログは構造化(JSON)→ stdout → CloudWatch Logs に集約

- アプリは構造化 JSON を **stdout** に出す(12-factor)。CloudWatch Agent が
  stdout/journald を CloudWatch Logs へ送る(アプリに AWS SDK を埋めない疎結合)
- 既定は従来どおり plain(後方互換)。AWS では `runtime.log_format: json`

### 4. ダッシュボード = CloudWatch(サーバ状態)+ Power BI/Athena(取引)

- **サーバ状態**: CloudWatch Logs/Metrics/Alarms + CloudWatch ダッシュボード
  (CPU・プロセス死活・heartbeat 経過・incident)
- **取引**: 主要テーブル(orders/fills/pnl_daily/bot_kpi_weekly/positions)を S3 へ
  エクスポート → Glue/Athena → **Power BI を Teams タブに埋め込み**で参照
- CloudWatch Alarm → SNS → 既存 Teams 通知(notifier 連携)で重大イベントを即時通知

### 5. git は一方向を維持(ADR-0005)

- EC2 は `git pull`(デプロイ)のみで **push しない**。S3 エクスポート・snapshot・
  CloudWatch は git を経由しない還流経路。本番に push 認証を置かない

## 却下した代替案

| 案 | 却下理由 |
|---|---|
| DynamoDB をコア DB に | FK 連鎖・JOIN・append-only 監査がリレーショナル前提。不変条項を損なう |
| Aurora/RDS Postgres へ即移行 | 最低 ACU コストが A-6 を圧迫。スケール時の将来選択肢に留める |
| Amazon QuickSight に統一 | 決裁権者が希望した「Teams タブの Power BI」を使えない |
| Azure VM | AWS 習熟を活かせず、コストやや高。親和性優位は小さく決め手にならない |

## 実装範囲(段階)

- **本 ADR と同時**: 中央集権的な構造化(JSON)ログ(`core/logsetup.py`)— CloudWatch 取り込みの下準備
- **Phase 1(BACKLOG)**: BL-021 EC2/IAM/S3/CloudWatch Agent 構築 / BL-022 テーブル→Parquet
  エクスポート + Glue/Athena + Power BI ダッシュボード / BL-023 CloudWatch Alarm→SNS→Teams 連携
- AWS SDK(boto3 等)は本体依存に足さず `pyproject.toml` の optional extra `aws` に置く
