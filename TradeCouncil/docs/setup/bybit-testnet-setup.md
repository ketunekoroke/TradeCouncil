# Bybit testnet セットアップ手順

Bybit testnet(模擬資金)へ実接続し、実レイテンシ・実手数料・実約定で執行経路を
検証するための手順。設計判断は [ADR-0008](../adr/0008-bybit-testnet.md)。

> ⚠️ ここで扱うのはすべて **testnet(模擬資金)**。mainnet への発注経路は
> コード上存在しない(ADR-0008 §2)。

> 🌐 **地域制限(2026-06-12 実測)**: Bybit API(testnet・mainnet とも)は制限対象国
> (米国等)の IP を CloudFront の国別ブロックで 403 遮断する。実測: 米国(VPN出口)=403 /
> タイ(AIS)=200。VPN 利用時は出口国に注意。Bybit 利用規約の制限管轄に従い、
> **制限地域からの規制回避を目的とした迂回は行わない**こと(ADR-0008 既知の制約4)。

## 1. testnet アカウントと API キーの作成

1. https://testnet.bybit.com にアクセスし、**mainnet とは別の** testnet アカウントを登録する
   (mainnet のアカウント/資金とは完全に分離されている)
2. ログイン後、プロフィール → **API** → **Create New Key** → System-generated
3. 権限は最小にする:
   - **Read-Write**(発注に必要)
   - 必要スコープ: **Spot Trade** のみ(Withdraw 等は付与しない)
   - IP 制限: 可能なら開発機/サーバの IP を登録
4. テスト資金: testnet の **Faucet**(資産画面)から USDT を請求する(無料・定期請求可)

検証専用に使うこと(手動取引と残高が混ざると `reconcile` の突合が読みにくくなる)。

## 2. シークレット設定(.env)

ルートの `.env` に追記(`.env.example` 参照。コード・コミットに含めない):

```
BYBIT_TESTNET_API_KEY=xxxxxxxxxxxx
BYBIT_TESTNET_API_SECRET=xxxxxxxxxxxx
```

## 3. 依存のインストール

```powershell
.venv\Scripts\pip install ccxt
# または: .venv\Scripts\pip install -e .[dev]  (pyproject 経由)
```

## 4. 設定の確認

| ファイル | 内容 |
|---|---|
| `config/instruments/btc_usdt_bybit_testnet.yaml` | `bybit_testnet.btc_usdt.spot`(BTC/USDT 現物・USDT 建て) |
| `config/bots/dummy_rw_bybit.yaml` | 接続検証用 BOT(dummy_random_walk × 上記 instrument)。**`enabled: true` に変更して使う** |
| `config/system.yaml` の `fx.usdjpy_rate` | USDT→JPY の保守的固定レート(円安側 = 損失過大評価の安全側) |
| `config/system.yaml` の `feed.bybit.environment` | `testnet`(既定)\| `mainnet`(公開データのみ。testnet 価格が歪むとき) |

## 5. 起動(testnet は paper の範疇 — ADR-0008 §2)

```powershell
# サンドボックスで試すのを推奨(本番 var/ を汚さない)
$env:TC_VAR_DIR = "var-sandbox"
.venv\Scripts\python.exe -m scripts.cli db init
.venv\Scripts\python.exe -m scripts.cli paper --bot dummy_rw_bybit
```

起動時に testnet へ接続し、1分バーの確定を待って売買サイクルが回る
(dummy 戦略は 3 バー周期 — 初回注文まで数分待つ)。

## 6. 検証(TC-206)

1. **根拠連鎖**: `tc kpi` → orphan 注文 = 0(全注文が decision_id 付き)
2. **建玉**: `tc status` → 建玉が表示される。Bybit testnet の Web UI(資産・注文履歴)と一致
3. **実手数料**: DB の `fills.fee` に Bybit の実手数料が入っている(模擬の固定 bps でない)
4. **レイテンシ**: ログの注文送信〜執行記録の時刻差を確認
5. **突合**: BOT を再起動 → `reconcile` の不整合報告が出ないこと
   (手動取引をした場合は「DBに無い建玉」が出る — 仕様どおり)

## 7. トラブルシューティング

| 症状 | 対処 |
|---|---|
| 403 Forbidden(CloudFront: blocked from your country) | 地域制限。VPN の出口国を確認(米国出口は遮断される)。`GET https://api-testnet.bybit.com/v5/market/time` が 200 になるネットワークで実行 |
| `BYBIT_TESTNET_API_KEY が未設定` で起動失敗 | §2 の .env 設定。設定後は新しいコンソールで(env 再読込) |
| 認証エラー(10003/10004) | キーの打ち間違い・testnet ではなく mainnet のキーを使っていないか |
| 注文拒否(最小ロット) | BTC/USDT の最小数量未満。`config/bots/` の `order_qty` を増やす |
| 価格が極端(testnet の歪み) | `feed.bybit.environment: mainnet` で公開データのみ mainnet に切替(発注は testnet のまま) |
| STALE_DATA で全拒否 | testnet の kline 配信遅延。P-04 `stale_data_sec` と照らして実測値をログで確認 |
