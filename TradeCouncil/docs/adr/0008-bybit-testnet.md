# ADR-0008: Bybit testnet 接続(実データフィード + 実発注アダプタ)

| 項目 | 内容 |
|---|---|
| 日付 | 2026-06-12 |
| ステータス | 承認済み(決裁権者の計画承認による) |
| 関連 | docs/02 §2.5(資産クラス別接続)/ docs/setup/bybit-testnet-setup.md / P-02(レバレッジ・paper 限定)/ BL-024(paper/live ポリシー分離)/ ADR-0004(環境戦略) |

## 背景

Phase 0 の執行は `PaperCryptoAdapter`(ローカル模擬約定)+ `RandomWalkFeed`(合成価格)のみで、
アルゴリズムの検証はできるが**接続・執行の実態**(実レイテンシ・実手数料・部分約定・
実スプレッド・取引所側の拒否)は検証できない。利用者は Bybit アカウントを保有しており、
実取引所の testnet(模擬資金)への接続検証を求めた。

## 決定事項

### 1. 検証環境を2系統に分離する(役割分担)

| 系統 | 構成 | 検証対象 |
|---|---|---|
| ローカルペーパー(既存) | RandomWalkFeed + PaperCryptoAdapter | アルゴリズム(決定的・無料・高速・オフライン) |
| Bybit testnet(本 ADR) | BybitFeed + BybitAdapter(模擬資金) | 接続・執行品質(実レイテンシ・実手数料・部分約定・実スプレッド) |

### 2. Bybit testnet は P-02 の「paper」の範疇とする

- testnet は**模擬資金**であり、実弾(live)ではない。P-02 決裁(paper 限定)の範疇として
  `tc paper` コマンドのまま運用する
- **mainnet への発注経路はコード上存在させない**: `BybitAdapter` は testnet エンドポイントを
  強制し(environment は `"testnet"` のみ受理)、mainnet 用の発注コードを実装しない
  (絶対ルール3「live 系機能を Phase 0 に存在させない」と BL-024 に整合)。
  mainnet 発注の追加は P-02 再決裁(BL-024 の paper/live ポリシー分離)が前提

### 3. ライブラリは ccxt(docs/02 §3 の既定スタック)

- testnet 切替(`set_sandbox_mode`)・統一シンボル(`BTC/USDT`)・100+取引所の抽象化。
  将来の bitFlyer/GMO(JPY ペア・実弾段階)や取引所追加に同一 IF で対応できる
- 本体依存に追加するが、import はアダプタ/フィード内に遅延し、ローカルペーパーのみの
  構成では ccxt 不要のまま動く

### 4. USDT 建て instrument の JPY 換算は保守的固定レート

- Bybit に JPY ペアがないため BTC/USDT を扱う。リスク上限(P-02/P-03)は JPY 建てのため
  換算が必要
- `config/system.yaml` の `fx.usdjpy_rate`(技術設定)に**実勢より円安側の固定レート**を
  置く = JPY 換算の想定損失・エクスポージャーを**過大評価する安全側**。値は四半期ごとに
  見直す(コメントで明記)
- 換算点は bot_runner に集約: `MarketContext`(equity/exposure/pnl)を JPY 換算し、
  `OrderIntent.fx_rate_jpy`(新設、既定 1.0)で notional_jpy を換算する。
  **price は instrument 通貨のまま**保持し、orders.price と fills.price の通貨を一致させる
  (監査の混乱を避ける)
- USDT/USD 以外の通貨は未対応エラーで拒否(fail-closed)

### 5. フィードは testnet/mainnet 切替可、発注は常に testnet

- 公開市場データ(kline/ticker)の取得は読み取り専用で発注リスクがないため、
  testnet の流動性が薄く価格が歪む場合に mainnet の公開データへ切替できる
- 既定は testnet(執行と同一環境で価格整合)

## 既知の制約(受容)

1. **pnl_daily / fills は instrument 通貨建て**で記録される(bot 間で JPY と USDT が混在)。
   `tc kpi` の通貨統合評価は REQ-M04(Phase 6)で対応。それまで KPI は bot 単位で読む
2. **spot の avg_price は取引所から取得できない** → `fetch_positions` は base 通貨残高から
   建玉を導出し avg_price=0.0。`reconcile` は qty のみ比較(現行仕様どおり)
3. testnet 口座の残高は**手動取引と混在**する。検証専用のサブアカウント利用を手順書で推奨
4. **地域制限(2026-06-12 実測)**: Bybit API(testnet・mainnet とも)は制限対象国の IP を
   403 で遮断する(CloudFront 国別ブロック)。実測: **米国(VPN 出口)= 403 / タイ(AIS)=
   200 で接続・実データ取得とも成功**。接続検証は Bybit がサービス提供する地域の
   ネットワークから行うこと(Bybit 利用規約の制限管轄に従う。**制限地域からの
   規制回避を目的とした迂回はしない**)。サーバ設置時(BL-021)はリージョンの IP が
   ブロック対象でないか事前に `GET /v5/market/time` で確認する

## 却下した代替案

| 代替案 | 却下理由 |
|---|---|
| pybit(Bybit 公式 SDK) | Bybit 専用。取引所追加時に別実装になり docs/02 の ccxt 方針と乖離 |
| 自前 REST | 署名・レート制限・ページネーションの保守費用が大きい |
| mainnet 読み取り専用キー(残高参照) | 今回は不要(testnet で完結)。必要になったら ADR 追補 |
| 実勢 FX レートの定期取得 | 外部依存・鮮度切れ処理が増える。固定レート(安全側)で Phase 6 まで足りる |
| DB(pnl)を JPY 換算で記録 | fills の実値(USDT)と orders の通貨が割れ、監査の一次情報を加工することになる |
