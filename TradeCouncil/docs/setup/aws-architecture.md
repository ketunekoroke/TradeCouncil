# セットアップ手順書: AWS 構成(ホスティング・ログ集約・ダッシュボード)

| 項目 | 内容 |
|---|---|
| 日付 | 2026-06-12 |
| 対象 | Phase 1 の本番を AWS に構築する(EC2・CloudWatch Logs・S3/Athena・Power BI ダッシュボード) |
| 関連 | ADR-0006 / docs/05 §4・§5 / ADR-0005(git 一方向)/ ADR-0002・0003(Teams 通知) |
| 状態 | **Phase 1 の手引き**(本番未構築)。構造化ログのみ実装済み |

---

## 1. 全体構成

```
                    ┌──────────────────────── AWS (ap-northeast-1) ────────────────────────┐
 開発機(Windows)   │  EC2 1台 (t4g.small, systemd)                                        │
 ┌───────────┐     │   ├ bot_runner + watchdog … 構造化JSONログ → stdout                  │
 │ Claude    │ git │   ├ SQLite on EBS(gp3)   … コア(監査・FK連鎖そのまま)              │
 │ Code      │ push│   ├ CloudWatch Agent       … stdout/journald → CloudWatch Logs        │
 │ (開発)    │────▶│   │                          + カスタムメトリクス(heartbeat 経過 等) │
 └─────┬─────┘pull │   ├ CloudWatch Alarms ──▶ SNS ──▶ 既存 Teams 通知(notifier)         │
       │ SSH(観測) │   └ 定期エクスポート(timer)… 主要テーブル → Parquet → S3            │
       │           │                                              │                        │
       │           │   S3(エクスポート)─▶ Glue/Athena            │  CloudWatch ダッシュボード │
       └───────────┤                            │                 │   = サーバ状態           │
                   └────────────────────────────┼─────────────────┴────────────────────────┘
                                                 ▼
                                      Power BI(Teams タブ埋め込み)= 取引ダッシュボード
```

git は一方向(EC2 は pull のみ・push しない。ADR-0005)。本番生成データは S3/CloudWatch/SSH で還流。

## 2. コンポーネントと役割

| AWS サービス | 役割 | 備考 |
|---|---|---|
| EC2(t4g.small, ARM) | BOT・watchdog の常駐(systemd) | スポット/Savings Plans でコスト最適化可 |
| EBS(gp3) | SQLite 本体(`var/tradecouncil.db`)の永続化 | 日次 EBS スナップショット or `tc snapshot`→S3 でバックアップ |
| CloudWatch Logs | アプリ stdout(構造化 JSON)の集約・検索・保持 | ロググループ例 `/tradecouncil/app` |
| CloudWatch Metrics/Alarms | CPU・プロセス死活・heartbeat 経過・incident 件数 | アラーム → SNS |
| SNS | アラーム通知のファンアウト | → Lambda/HTTP で Teams Workflow URL へ(notifier 連携) |
| S3 | テーブルの分析用エクスポート(Parquet)・snapshot・ログ長期保管 | バケット例 `tradecouncil-analytics` |
| Glue Data Catalog | S3 上 Parquet のスキーマカタログ | クローラ or 手動定義 |
| Athena | S3 を SQL 照会(従量課金・アイドルほぼ0円) | Power BI のデータソース |
| Power BI(M365) | 取引ダッシュボード(Teams タブ埋め込み) | Athena コネクタ/ODBC で接続 |

## 3. ログ集約(CloudWatch Logs)

1. アプリ側: `config/system.yaml` の `runtime.log_format: json` にする(実装済み。
   `core/logsetup.py` が 1行1JSON を stdout に出力)
2. EC2 に **CloudWatch Agent** を導入し、systemd ユニットの stdout(journald)または
   ログファイルを CloudWatch Logs へ送る。アプリに boto3 を埋めない(疎結合)
3. ロググループ・保持期間(例 30日)・メトリクスフィルタ(`level=ERROR` の件数 等)を設定

> アプリから直接送りたい場合の代替: `pyproject.toml` の optional extra `aws`
> (`watchtower`)で logging ハンドラを追加できるが、Phase 1 は Agent 方式を推奨。

## 4. 取引ダッシュボード(S3 → Athena → Power BI)

1. EC2 上の systemd timer で主要テーブル(orders/fills/pnl_daily/bot_kpi_weekly/positions)を
   **Parquet にエクスポート → S3**(BL-022 で実装。`tc snapshot` の整合コピーを入力にする)
2. Glue でスキーマをカタログ化(クローラ or DDL)
3. Athena で SQL 照会(パーティション = 日付でコスト最適化)
4. Power BI Desktop で **Amazon Athena コネクタ**(ODBC)接続 → レポート作成 → Power BI Service に発行
5. Teams のチャネルに **タブを追加 → Power BI** → 発行したレポートを選択(Teams タブ埋め込み)

認証: Power BI → Athena は IAM ユーザー/ロール + ODBC ドライバ。読み取り専用ポリシーに限定。

## 5. サーバ状態ダッシュボード(CloudWatch)

- CloudWatch ダッシュボードに CPU/メモリ/ディスク + カスタムメトリクス(heartbeat 経過秒・
  プロセス死活・incident 件数)を配置
- 重大条件(heartbeat 途絶・critical incident)は CloudWatch Alarm → SNS → 既存 Teams 通知
  (🚨アラートチャネル)へ。watchdog の通知と二重化される点は許容(別経路の冗長)

## 6. コスト概算(A-6: 月1万円内の目安)

| 項目 | 概算/月 |
|---|---|
| EC2 t4g.small(オンデマンド) | ~¥1,500〜2,500(Savings/スポットで更に減) |
| EBS gp3 20GB | ~¥300 |
| CloudWatch Logs(数GB) | ~¥100〜500 |
| S3 + Athena(少量・従量) | ~¥100〜300(アイドル時ほぼ0) |
| 合計(インフラ) | おおむね ¥2,000〜3,500 |

LLM API(A-6 の主費目)と合算しても 1万円内に収まる見込み。Power BI は M365 ライセンス側。

## 7. 構築タスク(BACKLOG)

- **BL-021**: EC2/IAM/EBS/S3 の作成、CloudWatch Agent 導入、systemd ユニット、SSH 鍵
- **BL-022**: テーブル→Parquet エクスポート(systemd timer)+ Glue/Athena + Power BI ダッシュボード
- **BL-023**: CloudWatch Alarm → SNS → Teams 通知連携

git は一方向(ADR-0005)・実弾は Phase 5 で paper と同居(ADR-0004)の原則は AWS でも不変。
