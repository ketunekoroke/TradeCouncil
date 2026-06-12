# 機能一覧(Features)

実装されている機能の棚卸し。各機能がどの要件([REQUIREMENTS.md](REQUIREMENTS.md))を
満たし、どこに実装されているかを対応づける。検証は [TESTCASES.md](TESTCASES.md)。

- 状態: **実装済**(コード + テストで動作確認済み)/ **仕様**(プロトコルとして定義・
  ファシリテーターが手動実行)/ **未**(未実装)

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
| FEAT-41 | 保護パス(generated/policies/prototype/var)+ 秘密検査(PreToolUse Edit/Write) | 実装済 | [scripts/hooks/protect_paths.py](scripts/hooks/protect_paths.py) | REQ-S01, REQ-S03 |
| FEAT-42 | 編集後テスト自動実行(PostToolUse) | 実装済 | [scripts/hooks/post_edit_test.py](scripts/hooks/post_edit_test.py) | — |
| FEAT-43 | git pre-commit(秘密・決裁レコードなしポリシー・generated手編集の検出) | 実装済 | [scripts/hooks/pre_commit.py](scripts/hooks/pre_commit.py) | REQ-S01, REQ-S03 |
| FEAT-44 | risk-auditor / code-reviewer サブエージェント | 仕様 | [.claude/agents/](.claude/agents/) | REQ-S04 |

## 会議・シナリオ(MAGI 継承)

| ID | 機能 | 状態 | 実装/定義 | 関連要件 |
|---|---|---|---|---|
| FEAT-50 | モード判定ルーター + シナリオ選択 | 仕様 | [CLAUDE.md](CLAUDE.md) | REQ-SC01 |
| FEAT-51 | 意思決定会議プロトコル(式次第・決裁レコード生成・tc policy record 適用) | 仕様 | [scenarios/council.md](scenarios/council.md) | REQ-G03, REQ-SC06 |
| FEAT-52 | TradeCouncil ペルソナ5名(偏り設計・risk_manager の veto) | 仕様 | [.claude/agents/](.claude/agents/) | REQ-SC06 |
| FEAT-53 | MAGI 3人格 + 4シナリオ(合議/資料レビュー/ブレスト/人格テスト) | 仕様 | [scenarios/](scenarios/), [.claude/agents/](.claude/agents/) | REQ-SC04 |
| FEAT-54 | LLMブリッジ(OpenAI/Gemini。リトライ・フォールバック・ファイル添付・履歴) | 実装済 | [scripts/ask_openai.py](scripts/ask_openai.py), [scripts/ask_gemini.py](scripts/ask_gemini.py), [scripts/bridge_common.py](scripts/bridge_common.py) | REQ-SC03 |
| FEAT-55 | メディア変換(Office抽出・md→docx・docx置換) | 実装済 | [scripts/extract_office.py](scripts/extract_office.py) ほか | REQ-SC04 |
| FEAT-56 | SharePoint 同期(単一 workspace/ root + `sync` 双方向・追加型・newer-wins・mtime 整合。削除非伝播。pull/push はリカバリ用 — ADR-0009) | 実装済 | [scripts/sharepoint.py](scripts/sharepoint.py) | REQ-SC05 |
| FEAT-57 | 会議の開催記録(council_sessions へ tc council log) | 実装済 | [scripts/cli.py](scripts/cli.py) | REQ-G02 |

## シナリオ・ブリッジ基盤 詳細(MAGI 継承 — BL-038 で prototype から統合)

> FEAT-50〜57 の要約行を細分化した詳細棚卸し。一次資料は [docs/07_シナリオ・人格基盤.md](docs/07_シナリオ・人格基盤.md)。
> 旧 FEAT 番号との対応は本ファイル末尾の付録参照。

### オーケストレーション・シナリオ

| ID | 機能 | 状態 | 実装/定義 | 関連要件 |
|---|---|---|---|---|
| FEAT-60 | チームメイト召喚と人格間対話(claude は SendMessage、使えない環境はファシリテーター仲介=ダイジェスト/`--history` フォールバック) | 仕様 | [CLAUDE.md](CLAUDE.md) | REQ-DL07, REQ-SC02 |
| FEAT-61 | シナリオ別出力先の分離(workspace/deliberations 等 — ADR-0009) | 実装済 | [CLAUDE.md](CLAUDE.md), [.gitignore](.gitignore) | REQ-SC05 |
| FEAT-62 | 合議: 3モード(Lite/Standard/Full)と Round 0〜9 の進行 | 仕様 | [scenarios/deliberation.md](scenarios/deliberation.md) | REQ-DL03, REQ-DL04 |
| FEAT-63 | 合議: 確信度加重の投票・少数意見の保持 | 仕様 | [scenarios/deliberation.md](scenarios/deliberation.md) | REQ-DL05 |
| FEAT-64 | レビュー: 価値観レンズの投影(正確性/読者/訴求力) | 仕様 | [scenarios/document-review.md](scenarios/document-review.md) | REQ-DR01 |
| FEAT-65 | レビュー: 深度モード(Quick/Standard/Deep)と Round 0〜6 | 仕様 | [scenarios/document-review.md](scenarios/document-review.md) | REQ-DR02〜04 |
| FEAT-66 | レビュー: 衝突指摘の裁定と must/should/nice/見送り分類 | 仕様 | [scenarios/document-review.md](scenarios/document-review.md) | REQ-DR05 |
| FEAT-67 | レビュー: 指摘レポート+同形式改訂版+変更履歴+未採用指摘の保持 | 仕様 | [scenarios/document-review.md](scenarios/document-review.md) | REQ-DR06〜09 |
| FEAT-68 | ブレスト: レンズを発散と評価の両方に投影(実現/人/独創) | 仕様 | [scenarios/brainstorm.md](scenarios/brainstorm.md) | REQ-BR01 |
| FEAT-69 | ブレスト: モードと Round 0〜8(発散巡数固定・早期収束) | 仕様 | [scenarios/brainstorm.md](scenarios/brainstorm.md) | REQ-BR03 |
| FEAT-70 | ブレスト: 独立大量発散 → マップ化(クラスタ・白地)→ build-on/掛け合わせ二次発散 | 仕様 | [scenarios/brainstorm.md](scenarios/brainstorm.md) | REQ-BR02, REQ-BR04 |
| FEAT-71 | ブレスト: レンズ別 0〜10 採点(内訳保持)・割れた尖り案の別枠保持 | 仕様 | [scenarios/brainstorm.md](scenarios/brainstorm.md) | REQ-BR05, REQ-BR06 |
| FEAT-72 | ブレスト: 上位案の3レンズ協働ブラッシュアップ+Deep プレモーテム | 仕様 | [scenarios/brainstorm.md](scenarios/brainstorm.md) | REQ-BR07 |
| FEAT-73 | ブレスト: 成果物一式(アイデア集・Mermaid マップ・評価マトリクス・上位案) | 仕様 | [scenarios/brainstorm.md](scenarios/brainstorm.md) | REQ-BR08 |
| FEAT-74 | 人格テスト: 固定プローブ・バッテリの独立投下・差分マトリクス・人格別判定(Round 0〜4・3モード) | 仕様 | [scenarios/persona-test.md](scenarios/persona-test.md) | REQ-PT01〜03, REQ-PT06 |
| FEAT-75 | 人格テスト: 識別性チェック(似すぎ警告)+ベースライン回帰比較(Deep)・backend 揃え | 仕様 | [scenarios/persona-test.md](scenarios/persona-test.md) | REQ-PT04, REQ-PT05, REQ-PT07 |
| FEAT-76 | 成果物生成: Markdown ログ常時 + Excel/Word/チャート任意 + 同形式改訂版 | 仕様 | scenarios/ 各「成果物」節 | REQ-SC07, REQ-DR06 |

### 人格・バックエンド

| ID | 機能 | 状態 | 実装/定義 | 関連要件 |
|---|---|---|---|---|
| FEAT-77 | 価値観ベース人格 + frontmatter スキーマ(name/description/backend/model) | 実装済 | [.claude/agents/](.claude/agents/) | REQ-PE01〜03 |
| FEAT-78 | 好奇心・興味の共通駆動(レンズ別に対象・強度が屈折、向きにくい対象が弱みと呼応) | 実装済 | [.claude/agents/](.claude/agents/), [docs/07](docs/07_シナリオ・人格基盤.md) | REQ-PE04 |
| FEAT-79 | backend 振り分け(claude/openai/gemini)・混在・使用モデルのログ明記 | 仕様 | [CLAUDE.md](CLAUDE.md) | REQ-LB01〜03, REQ-SC08 |
| FEAT-80 | ステートレス人格の継続(毎ラウンド文脈付与・`--history` 多ターン履歴) | 実装済 | [scripts/bridge_common.py](scripts/bridge_common.py) `load_history` | REQ-LB04 |
| FEAT-81 | 拒否/空応答の自動再試行(`MAGI_GEN_MAX_RETRIES`)+言い換え再実行の作法 | 実装済 | `run_with_retry` / `extract_output_text` | REQ-LB05 |

### ブリッジ実装

| ID | 機能 | 状態 | 実装/定義 | 関連要件 |
|---|---|---|---|---|
| FEAT-82 | bridge_common: プロバイダ非依存の共有処理(キー3段解決/フロントマター除去/Office抽出/HTTP/履歴/UTF-8) | 実装済 | [scripts/bridge_common.py](scripts/bridge_common.py) | REQ-LB06, REQ-S06 |
| FEAT-83 | 一過性 HTTP エラーの指数バックオフ自動リトライ(`Retry-After` 尊重・`MAGI_HTTP_*`) | 実装済 | `_urlopen_retrying` | REQ-NF05 |
| FEAT-84 | 過負荷/モデル不在時のフォールバックモデル切替(`--fallback-model` / `MAGI_*_FALLBACK_MODEL`) | 実装済 | `run_with_fallback` | REQ-LB07 |
| FEAT-85 | OpenAI ブリッジ: Responses API 往復(instructions=人格本文・frontmatter 自動除去) | 実装済 | [scripts/ask_openai.py](scripts/ask_openai.py) | REQ-LB02, REQ-PE03 |
| FEAT-86 | ファイル入力: 画像/PDF ネイティブ・Office 抽出注入・テキスト注入(両ブリッジ対称) | 実装済 | `build_content_parts` / `build_parts` | REQ-FI01〜05 |
| FEAT-87 | `upload` + `--file-id` 参照(OpenAI Files API / Gemini Files API・ACTIVE 待ち) | 実装済 | `upload_file` / `file_meta` | REQ-FI06 |
| FEAT-88 | UTF-8 入出力固定(Windows パイプ/コンソール)・整形エラー・`*_BASE_URL` 上書き | 実装済 | 両ブリッジ共通 | REQ-NF02, REQ-NF03 |
| FEAT-89 | Gemini ブリッジ: generateContent 往復・ブロック/空応答の整形(promptFeedback/finishReason) | 実装済 | [scripts/ask_gemini.py](scripts/ask_gemini.py) | REQ-LB02, REQ-NF03 |
| FEAT-90 | モデル一覧取得(openai/gemini を議論向けに抽出・`--all`) | 実装済 | [scripts/list_models.py](scripts/list_models.py) | REQ-LB01 |
| FEAT-91 | Office→Markdown 抽出 CLI(docx/pptx/xlsx・本文順・GFM表) | 実装済 | [scripts/extract_office.py](scripts/extract_office.py) | REQ-FI03, REQ-DR03 |
| FEAT-92 | Markdown→docx 変換 CLI(見出し/表/太字・日本語フォント・全面再構築) | 実装済 | [scripts/md_to_docx.py](scripts/md_to_docx.py) | REQ-DR06 |
| FEAT-93 | docx 原本コピー編集 CLI(find→replace・体裁/画像保持・原本不変) | 実装済 | [scripts/docx_replace.py](scripts/docx_replace.py) | REQ-DR06, REQ-DR10 |

### SharePoint 連携詳細

| ID | 機能 | 状態 | 実装/定義 | 関連要件 |
|---|---|---|---|---|
| FEAT-94 | Graph クライアントシークレット認証・サイト/ドライブ解決・`test` 検証(日本語テナントの既定ライブラリへフォールバック) | 実装済 | [scripts/sharepoint.py](scripts/sharepoint.py) | REQ-SP01, REQ-SP04 |
| FEAT-95 | `pull`/`push`(再帰・4MB 超はアップロードセッション分割)+ `info`(SharePoint URL) | 実装済 | `pull_folder` / `push_folder` / `cmd_info` | REQ-SP05 |
| FEAT-96 | 設定解決(env(.env)→ sharepoint.config.json)+ 非機密設定ファイル(folders に council 含む) | 実装済 | `load_config`, [sharepoint.config.json](sharepoint.config.json) | REQ-SP02 |
| FEAT-97 | Azure アプリ登録セットアップマニュアル(登録→シークレット→権限+同意→Sites.Selected→確認→トラブルシュート) | 実装済 | [docs/setup/sharepoint-azure-app-setup.md](docs/setup/sharepoint-azure-app-setup.md) | REQ-SP07, REQ-SP08 |
| FEAT-98 | docs ミラー `mirror [--full]`(git main → SharePoint `Docs/` 一方向・差分ベース・削除反映・sha 状態ファイル・失敗時は状態を進めず次回追いつく — ADR-0010) | 実装済 | `cmd_mirror` / `plan_mirror`([scripts/sharepoint.py](scripts/sharepoint.py)) | REQ-SP09〜SP11 |
| FEAT-99 | ミラーの git フック自動実行(post-commit=main 時のみ / pre-push。fail-open=warn のみ。`tc hooks install` が3フック一括導入) | 実装済 | [scripts/hooks/post_commit.py](scripts/hooks/post_commit.py) / [scripts/hooks/pre_push.py](scripts/hooks/pre_push.py) / `cmd_hooks` | REQ-SP12 |

---

## 付録: prototype からの FEAT 対応表(BL-038 統合・トレーサビリティ)

prototype/FEATURES.md の旧 FEAT 番号 → 本ファイルの新番号(衝突回避のための再番号。
要約行 FEAT-50〜57 はそのまま、詳細は FEAT-60〜97 に展開):

| 旧(prototype) | 新 | 旧 | 新 | 旧 | 新 |
|---|---|---|---|---|---|
| 01, 42 | FEAT-50 に吸収 | 04 | 60 | 43, 44 | 61(+SC 要件) |
| 02 | 62 | 03 | 63 | 45 | 64 |
| 46 | 65 | 47 | 66 | 48, 49 | 67, 76 |
| 65 | 68 | 66 | 69 | 67 | 70 |
| 68 | 71 | 69 | 72 | 70 | 73 |
| 72 | 74 | 73 | 75 | 25, 26 | 76 |
| 05, 06 | 77 | 71 | 78 | 07, 08 | 79 |
| 09, 51 | 80 | 10 | 81 | 27 | 82 |
| 50 | 83 | 55 | 84 | 11, 12 | 85 |
| 14〜17, 29 | 86 | 18, 19, 30 | 87 | 20〜23, 31 | 88 |
| 28, 32 | 89 | 33 | 90 | 52 | 91 |
| 53 | 92 | 54 | 93 | 57, 58 | 94 |
| 59, 60 | 95 | 56, 63 | 96(**ADR-0009 仕様に改訂**) | 64 | 97 |
| 13, 24 | REQ-S06 / FEAT-82 に吸収 | 61 | CLAUDE.md 作法(sync)に置換 | 62 | FEAT-82 に吸収 |
