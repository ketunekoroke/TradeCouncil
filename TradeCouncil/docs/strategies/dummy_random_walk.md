---
strategy_key: dummy_random_walk
bot_ids: [dummy_rw]
status: paper
horizon: ""              # なし(収益を狙わない試験用)
instruments: [paper.btc_jpy.spot]
created: 2026-06-11
updated: 2026-06-12
---

# 戦略カード: dummy_random_walk

## 仮説

(収益仮説なし)Phase 0 の24時間無人稼働試験用。**「発注 → risk_guard → 執行 →
記録」のループを決定的に回し続ける**ことだけが目的で、市場の非効率は捉えない。
売り・買い両経路を必ず通すため、根拠連鎖(decision_id)・冪等性・リスクチェックの
全経路がテストされる。

## ロジック概要

固定サイクル(決定的・乱数なし):

- エントリー: ポジションが無く、バー番号が `hold_bars` 周期の先頭なら
  `order_qty` を成行買い
- イグジット: ポジションを `hold_bars` 本のバーで保有したら全量売り
- 想定最大損失(est_max_loss_jpy): 想定元本(qty × close)の 1%(ダミー用の
  控えめな固定見積もり。実戦略では戦略ロジックから導出すること)

## パラメータと根拠

| パラメータ | 値 | 根拠(なぜこの値か) |
|---|---|---|
| order_qty | 0.001 BTC | P-02 の上限に対し十分小さく、拒否されずループが回る量 |
| hold_bars | 3 | 1時間足で約3時間サイクル。24h試験で売買とも十分な回数(各 ~8回)発生する |

## 合格基準

収益基準は適用しない(P-06 の対象外)。代わりに Phase 0 完了条件(設計書 §9)を
合格基準とする:

- 24時間無人稼働でプロセス停止・heartbeat 途絶なし
- 全注文が decision_id 付きで記録され `tc kpi` の根拠連鎖検証が orphan=0
- インシデント(critical)0件

## 検証結果

| 日付 | 検証 | 結果の要約と解釈 |
|---|---|---|
| 2026-06-11 | e2e テスト(tests/e2e/test_paper_bot.py) | ポリシーなし→全拒否(fail-closed)、決裁後→根拠連鎖が candle まで遡及可能。経路検証として合格 |
| (予定) | 24時間無人稼働試験(BL-007) | — |

## 運用での学び(append-only)

- 2026-06-11: カード以前に実装(Phase 0 基盤と同時)。戦略テンプレートの
  rationale-base パターン(rule / bar_ts / close / position_qty を必ず入れる)の出典
- 2026-06-12: カード作成。実戦略との違いとして「est_max_loss_jpy を固定率で
  見積もるのはダミーだから許される手抜き」であることを明記 — 実戦略では
  ストップ幅等のロジックから導出する

## 関連

- 実装: [bots/dummy_random_walk.py](../../bots/dummy_random_walk.py) /
  設定: [config/bots/dummy_rw.yaml](../../config/bots/dummy_rw.yaml) /
  テスト: [tests/e2e/test_paper_bot.py](../../tests/e2e/test_paper_bot.py)
- 関連: BL-007(24時間無人稼働試験)/ docs/01 設計書 §9(Phase 0 完了条件)
