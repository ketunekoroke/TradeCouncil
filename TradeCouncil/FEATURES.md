# 機能一覧(Features)— TradeCouncil(自動売買)

TradeCouncil 固有の実装機能の棚卸し。各機能がどの要件([REQUIREMENTS.md](REQUIREMENTS.md))を
満たし、どこに実装されているかを対応づける。検証は [TESTCASES.md](TESTCASES.md)。

汎用シナリオ・人格・LLMブリッジの機能は別プロジェクトが管理する(モノレポ再編 — ADR-0011):
- シナリオ・人格(FEAT-60〜81): [../Magi/FEATURES.md](../Magi/FEATURES.md)
- LLMブリッジ・SharePoint(FEAT-82〜99): [../shared/FEATURES.md](../shared/FEATURES.md)

- 状態: **実装済**(コード + テストで動作確認済み)/ **仕様**(プロトコルとして定義・手動実行)/ **未**

---

## ガバナンス

| ID | 機能 | 状態 | 実装/定義 | 関連要件 |
|---|---|---|---|---|
| FEAT-01 | ポリシーレジストリ(YAML真実源 + DB監査ミラー、ライフサイクル強制) | 実装済 | [core/governance/registry.py](core/governance/registry.py) | REQ-G01 |
| FEAT-02 | 決裁レコード検証(必須項目・owner以外の拒否) | 実装済 | [core/governance/schema.py](core/governance/schema.py) | REQ-G02 |
| FEAT-03 | decision_gate 3分岐(不変条項reject / 委任内自動適用 / 決裁キュー回送) | 実装済 | [core/governance/decision_gate.py](core/governance/decision_gate.py) | REQ-G04, REQ-G05 |
| FEAT-04 | 実行用ビュー生成(risk_limits.yaml / delegation.yaml、手編集禁止ヘッダ) | 実装済 | [core/governance/registry.py](core/governance/registry.py) | REQ-G01 |
| FEAT-05 | 決裁履歴 append-only + ロールバック(旧値再決裁) | 実装済 | registry + [core/db/models.py](core/db/models.py) | REQ-G07 |
| FEAT-06 | 決裁キューへの決裁(approve/reject/defer) | 実装済 | [scripts/cli_policy.py](scripts/cli_policy.py) | REQ-G02 |

## リスク管理・執行

| ID | 機能 | 状態 | 実装/定義 | 関連要件 |
|---|---|---|---|---|
| FEAT-10 | RiskGuard 11段チェック(fail-closed・全しきい値をポリシーから読込) | 実装済 | [core/risk/guard.py](core/risk/guard.py) | REQ-R01〜R04, R06 |
| FEAT-11 | RiskApprovedOrder 型による経路遮断(guard のみ生成可) | 実装済 | [core/risk/guard.py](core/risk/guard.py) | REQ-R02 |
| FEAT-12 | キルスイッチ(フラグファイル・kill/resume CLI・ループ即時停止) | 実装済 | [core/risk/kill_switch.py](core/risk/kill_switch.py) | REQ-R05 |
| FEAT-13 | 拒否注文の監査記録(orders に rejected + reason_code) | 実装済 | [core/risk/guard.py](core/risk/guard.py) | REQ-E04 |
| FEAT-14 | Executor(冪等性キー UNIQUE・decision_id 必須・1トランザクション記録) | 実装済 | [core/execution/executor.py](core/execution/executor.py) | REQ-E01, REQ-E02 |
| FEAT-15 | trade_decisions 起票(全注文の根拠の結合点) | 実装済 | [core/execution/decisions.py](core/execution/decisions.py) | REQ-E01 |
| FEAT-16 | 建玉突合(reconcile) | 実装済 | [core/execution/executor.py](core/execution/executor.py) | REQ-E03 |

## マーケット・BOT

| ID | 機能 | 状態 | 実装/定義 | 関連要件 |
|---|---|---|---|---|
| FEAT-20 | 統一インストゥルメントモデル(YAML→DB同期) | 実装済 | [core/market/instrument.py](core/market/instrument.py) | REQ-M01 |
| FEAT-21 | BrokerAdapter 共通IF + PaperCryptoAdapter(スリッページ/手数料モデル) | 実装済 | [core/exchange/](core/exchange/) | REQ-M02 |
| FEAT-22 | RandomWalkFeed(シード固定で再現可能な価格フィード) | 実装済 | [core/exchange/feeds.py](core/exchange/feeds.py) | REQ-D01(暫定) |
| FEAT-28 | BybitAdapter(testnet 強制・mainnet 発注経路なし・実約定/実手数料の解決・orderLinkId 二重防壁・base残高→建玉導出 — ADR-0008) | 実装済 | [core/exchange/bybit.py](core/exchange/bybit.py) | REQ-M02 |
| FEAT-29 | BybitFeed(確定 kline のみ返す REST ポーリング・実スプレッド・data_age 実測 → P-04 鮮度チェックが実質動作。testnet/mainnet 切替) | 実装済 | [core/exchange/bybit_feed.py](core/exchange/bybit_feed.py) | REQ-D01 |
| FEAT-58 | JPY 換算(OrderIntent.fx_rate_jpy + FxConfig 保守的固定レート。bot_runner で equity/exposure/pnl/est_max_loss を換算、price は instrument 通貨を維持) | 実装済 | [core/config.py](core/config.py), [core/runner/bot_runner.py](core/runner/bot_runner.py) | REQ-M06 |
| FEAT-23 | bot_runner(バー駆動ループ・candles保存・heartbeat・異常時incident+通知) | 実装済 | [core/runner/bot_runner.py](core/runner/bot_runner.py) | REQ-E04, REQ-O02 |
| FEAT-24 | ダミー固定サイクル戦略(24h試験用・売買両経路) | 実装済 | [bots/dummy_random_walk.py](bots/dummy_random_walk.py) | — |
| FEAT-25 | bots/ の経路分離(core.exchange/execution import 禁止の性質テスト) | 実装済 | [tests/risk/test_limits.py](tests/risk/test_limits.py) | REQ-R02 |
| FEAT-26 | BOT スキャフォールド `tc bot new`(雛形4ファイル一括生成・既存拒否・enabled:false 既定・レジストリ登録はテスト駆動誘導 — ADR-0007) | 実装済 | [scripts/scaffold_bot.py](scripts/scaffold_bot.py) | REQ-N02 |
| FEAT-27 | 戦略カタログ(1戦略=1カード・状態遷移 draft→…→retired・学び append-only・数値は DB 参照) | 仕様 | [docs/strategies/README.md](docs/strategies/README.md) | REQ-N01 |

## 監視・運用・CLI

| ID | 機能 | 状態 | 実装/定義 | 関連要件 |
|---|---|---|---|---|
| FEAT-30 | Teams/Discord 通知(backend 切替。Teams は Power Automate Workflows へ Adaptive Card、severity 色 + FactSet。マルチチャネルルーティング: 明示 channel > routing > default のフォールバック連鎖 — ADR-0003。未設定時ログfallback) | 実装済 | [core/notify/notifier.py](core/notify/notifier.py) | REQ-O01 |
| FEAT-31 | watchdog(heartbeat 途絶検知 → incident + 通知) | 実装済 | [core/runner/watchdog.py](core/runner/watchdog.py) | REQ-O02 |
| FEAT-32 | tc CLI 一式(test/db/paper/watchdog/status/kill/policy/approve/kpi/council/hooks) | 実装済 | [scripts/cli.py](scripts/cli.py) | — |
| FEAT-33 | KPIレポート + 根拠連鎖の機械検証(orphan注文=0) | 実装済 | [feedback/kpi.py](feedback/kpi.py) | REQ-E05 |
| FEAT-34 | TC_VAR_DIR サンドボックス(var/ 接頭辞パスの読み替え・動的解決・var-* の gitignore/hooks 保護) | 実装済 | [core/config.py](core/config.py) | REQ-O04 |
| FEAT-35 | DB 整合スナップショット `tc snapshot`(VACUUM INTO・TC_VAR_DIR 追従・バックアップ/本番閲覧用) | 実装済 | [core/db/snapshot.py](core/db/snapshot.py) | REQ-O05 |
| FEAT-36 | 中央集権的な構造化ログ(plain/json 切替・stdout 出力・冪等。CloudWatch 取り込み下準備) | 実装済 | [core/logsetup.py](core/logsetup.py) | REQ-O06 |

## 安全フック

| ID | 機能 | 状態 | 実装/定義 | 関連要件 |
|---|---|---|---|---|
| FEAT-40 | 実弾系・resume・KILLフラグ削除のブロック(PreToolUse Bash) | 実装済 | [scripts/hooks/block_live.py](scripts/hooks/block_live.py) | REQ-S02 |
| FEAT-41 | 保護パス(generated/policies/var)+ 秘密検査(PreToolUse Edit/Write) | 実装済 | [scripts/hooks/protect_paths.py](scripts/hooks/protect_paths.py) | REQ-S01, REQ-S03 |
| FEAT-42 | 編集後テスト自動実行(PostToolUse・共有 .venv 参照) | 実装済 | [scripts/hooks/post_edit_test.py](scripts/hooks/post_edit_test.py) | — |
| FEAT-43 | git pre-commit(秘密・決裁レコードなしポリシー・generated手編集の検出。リポジトリ単位 — shared) | 実装済 | [../shared/hooks/pre_commit.py](../shared/hooks/pre_commit.py) | REQ-S01, REQ-S03 |
| FEAT-44 | risk-auditor / code-reviewer サブエージェント | 仕様 | [.claude/agents/](.claude/agents/) | REQ-S04 |

## 会議シナリオ(council — 売買固有)

> 汎用シナリオ基盤(Magi)を使うが、運用ポリシー決裁という売買固有目的のため TradeCouncil が所有。
> ルーター・ブリッジ・汎用4シナリオの機能は [../Magi/FEATURES.md](../Magi/FEATURES.md) /
> [../shared/FEATURES.md](../shared/FEATURES.md) を参照。

| ID | 機能 | 状態 | 実装/定義 | 関連要件 |
|---|---|---|---|---|
| FEAT-51 | 意思決定会議プロトコル(式次第・決裁レコード生成・tc policy record 適用) | 仕様 | [scenarios/council.md](scenarios/council.md) | REQ-G03, REQ-SC06 |
| FEAT-52 | TradeCouncil ペルソナ5名(偏り設計・risk_manager の veto) | 仕様 | [.claude/agents/](.claude/agents/) | REQ-SC06 |
| FEAT-57 | 会議の開催記録(council_sessions へ tc council log) | 実装済 | [scripts/cli.py](scripts/cli.py) | REQ-G02 |
