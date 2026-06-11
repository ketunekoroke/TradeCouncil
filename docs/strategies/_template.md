---
strategy_key: {strategy_key}
bot_ids: [{bot_id}]
status: draft            # draft | backtest | paper | live | retired
horizon: ""              # 短期 | 中期 | 長期(FR-9 のスリーブと対応)
instruments: []          # 例: [paper.btc_jpy.spot]
created: {date}
updated: {date}
---

# 戦略カード: {strategy_key}

> 書き方は [README.md](README.md) の運用ルールを参照。実装より先に
> 「仮説」「合格基準」を書く(ドキュメント駆動)。

## 仮説

(なぜこの戦略が機能すると考えるか。市場のどの非効率・構造を捉えるのか。
 1〜3文で。検証で棄却できる形に書く)

## ロジック概要

(on_bar が何を見て何を出すか。エントリー/イグジット条件を擬似コードか箇条書きで。
 実装の写しではなく「意図」を書く)

- エントリー:
- イグジット:
- 想定最大損失(est_max_loss_jpy)の見積もり方:

## パラメータと根拠

| パラメータ | 値 | 根拠(なぜこの値か) |
|---|---|---|
| (例: order_qty) | | |

## 合格基準

P-06(フェーズゲート基準)を既定とし、戦略固有の追加基準があれば書く:

- バックテスト → paper: PF > 1.2 / 最大DD < 15% / 取引数 ≥ 100(手数料込み)
- 追加基準:(あれば)

## 検証結果

(バックテスト・ペーパー試走の結果と解釈。実績数値は DB が真実源
(`tc kpi`)— ここには評価の解釈と判断を書く)

| 日付 | 検証 | 結果の要約と解釈 |
|---|---|---|
| | | |

## 運用での学び(append-only)

(日付付きで追記のみ。消さない・上書きしない)

- {date}: カード作成(draft)

## 関連

- 実装: [bots/{strategy_key}.py](../../bots/{strategy_key}.py) /
  設定: [config/bots/{bot_id}.yaml](../../config/bots/{bot_id}.yaml) /
  テスト: [tests/bots/test_{strategy_key}.py](../../tests/bots/test_{strategy_key}.py)
- 関連 ADR / 議事録 / 関連戦略:(あれば)
