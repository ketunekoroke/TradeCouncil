# シナリオ(scenarios/)— TradeCouncil

TradeCouncil 固有のシナリオは **意思決定会議(council)** のみ。運用ポリシーをペルソナ5名で
審議し、利用者の決裁で `config/policies/` を更新する。

| シナリオ | ファイル | 何をするか | 出力先 |
|---|---|---|---|
| **意思決定会議**(council) | [council.md](council.md) | ペルソナ5名(macro/momentum/contrarian/quant/risk_manager)が運用ポリシーを審議し、利用者の決裁で `config/policies/` を更新 | `../workspace/council/` + `config/policies/` |

> 汎用シナリオ(合議・資料レビュー・ブレスト・人格テスト)と MAGI 3人格は **Magi プロジェクト**
> にある(モノレポ再編 — ADR-0011)→ [../../Magi/scenarios/README.md](../../Magi/scenarios/README.md)。
> 役割・LLMバックエンド選択・召喚ルールなど共通作法は council 実行時も Magi の作法に準じる
> (ブリッジは共通層 `../../shared/`)。
