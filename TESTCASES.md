# テストケース一覧(Test Cases)

TradeCouncil の検証用テストケース集。**重要度ランク(P0〜P3)** で分類してあり、
毎回すべてを流す必要はない。関連: [REQUIREMENTS.md](REQUIREMENTS.md) / [FEATURES.md](FEATURES.md)。

## 重要度ランクとテスト選択ガイド

| ランク | 意味 | いつ流すか | 性質 |
|---|---|---|---|
| **P0** | クリティカル。壊れたら全体が成立しない | **毎回(コミット前)** | 無課金・自動(pytest / py_compile) |
| **P1** | コア。主要なハッピーパス | core/・scenarios/・人格定義の変更時 | 一部 手動・LLM実行 |
| **P2** | 拡張。外部API・長時間 | リリース前・フル回帰 | API課金 / 長時間 |
| **P3** | エッジ。例外・環境依存 | 環境変更時・気になった時 | 再現条件が特殊 |

| タイミング | 実行するランク |
|---|---|
| 各コミット前 | **P0**(pre-commit + `python -m scripts.cli test`) |
| core/risk・governance・execution を変更した | **P0 + TC-201**(カバレッジゲート)+ risk-auditor |
| シナリオ・人格定義を変更した | **P0 + P1** |
| フル回帰(リリース前) | **P0 + P1 + P2** |

---

## P0(自動・無課金)

| ID | タイトル | 実行方法 | 関連 |
|---|---|---|---|
| TC-001 | 全 pytest スイート(100+件)が緑 | `python -m scripts.cli test` | 全FEAT |
| TC-002 | **fail-closed**: ポリシー0件/1件欠如/非active/失効/キー欠落 → 全拒否 | `pytest tests/risk/test_fail_closed.py` | REQ-R01 |
| TC-003 | 各リスク上限の境界値(ちょうど=可、+ε=拒否) | `pytest tests/risk/test_limits.py` | REQ-R03, R06 |
| TC-004 | キルスイッチ(最優先拒否・冪等・ループ停止) | `pytest tests/risk/test_kill_switch.py tests/e2e -k kill` | REQ-R05 |
| TC-005 | 決裁レコード検証(owner以外拒否・必須項目欠落拒否) | `pytest tests/governance/test_registry.py` | REQ-G02 |
| TC-006 | ライフサイクル・ロールバック・履歴 append-only | 同上 | REQ-G01, G07 |
| TC-007 | decision_gate 3分岐(reject/auto-apply/queue。P-01自体は常にqueue) | `pytest tests/governance/test_decision_gate.py` | REQ-G04, G05 |
| TC-008 | 冪等性(同一 decision_id → 注文1件)・decision_id なし拒否 | `pytest tests/execution` | REQ-E01, E02 |
| TC-009 | E2E: ポリシーなしでBOT実行 → 全注文 rejected(**Phase 0 DoD**) | `pytest tests/e2e` | REQ-R01 |
| TC-010 | E2E: 決裁後の全注文が 根拠 → candle まで遡及可能 | 同上 | REQ-E01, E04 |
| TC-011 | bots/ から core.exchange/execution への import 禁止 | `pytest tests/risk -k import` | REQ-R02 |
| TC-012 | riskカバレッジ90%ゲート | `python -m scripts.cli test --risk` | REQ-R08 |
| TC-013 | 全スクリプト構文チェック | `python -m py_compile scripts/*.py scripts/hooks/*.py` | — |
| TC-014 | hooks 単体: live/resume ブロック、generated/policies/prototype 保護、秘密検出 | stdin JSON を hooks に流して exit code 確認(FEATURES の FEAT-40〜41) | REQ-S01〜S03 |
| TC-015 | pre-commit: 決裁レコードなしポリシー / .env / 秘密 を拒否 | ダミーをステージして `python scripts/hooks/pre_commit.py` | REQ-S01, S03 |
| TC-016 | 人格 frontmatter の妥当性(name/backend/model が揃う) | 目視 or grep(8ファイル) | REQ-SC03 |
| TC-017 | 通知: backend 切替・Adaptive Card 形式・severity 色・facts・切詰め・例外吸収・チャネルルーティング(明示>routing>default のフォールバック連鎖)・Workflow URL(sig付き)の秘密検出 | `pytest tests/notify` | REQ-O01, REQ-S01 |
| TC-018 | シークレット解決順(環境変数 → .env → settings.local.json、placeholder/空は除外) | `pytest tests/scripts` | REQ-S01 |
| TC-019 | TC_VAR_DIR: 絶対/相対の読み替え・サブ構造維持・未設定時の従来挙動・var 外パス非影響・動的解決 | `pytest tests/config` | REQ-O04 |
| TC-020 | tc snapshot: 整合コピーの行一致・元DB無傷・dest既存エラー・親dir作成・WALコミット済データ反映 | `pytest tests/db` | REQ-O05 |
| TC-021 | 構造化ログ: JSON 形式の妥当性・例外フィールド・plain 後方互換・冪等・level フィルタ・config 解決・不正 format 拒否 | `pytest tests/log` | REQ-O06 |
| TC-022 | CLI 出力の cp932 耐性(BL-018): 非対応グリフ(✓✗)は「?」置換で落ちない・encoding 不変・reconfigure 非対応ストリーム許容・`status` が cp932 厳格ストリームで完走 | `pytest tests/scripts/test_cli_encoding.py` | FEAT-32 |

## P1(手動・主要パス)

| ID | タイトル | 手順 | 関連 |
|---|---|---|---|
| TC-101 | CLI スモーク: db init → status → policy list → kpi → kill → (人間が)resume | README クイックスタート手順 | FEAT-32 |
| TC-102 | **第0回会議のドライラン**: 「臨時会議」で任意の非★ポリシー(例: P-08)を1件審議→決裁→`policy list` で active 確認→`policy show` で decision ブロック確認 | scenarios/council.md | REQ-G03, SC06 |
| TC-103 | 決裁レコードの読み上げ確認なしに record が実行されないこと(プロトコル遵守の目視) | 会議中に観察 | REQ-G03 |
| TC-104 | 合議シナリオ(Lite)が完走し `<root>/deliberations/` に出力される | 「議題: <軽いお題>」 | REQ-SC04 |
| TC-105 | ペーパーBOT 1時間稼働: status の heartbeat OK・kpi の根拠連鎖 OK | `paper` + `watchdog` | FEAT-23 |
| TC-106 | veto 動作: 根拠なき上限緩和案を会議に出し risk_manager が veto するか | 会議中に観察 | REQ-SC06 |

## P2(API課金・長時間)

| ID | タイトル | 手順 | 関連 |
|---|---|---|---|
| TC-201 | OpenAI ブリッジ疎通(人格1名を gpt-4o で1ラウンド) | `echo test \| python scripts/ask_openai.py --system-file .claude/agents/melchior.md --model gpt-4o` | REQ-SC03 |
| TC-202 | Gemini ブリッジ疎通(同上) | `scripts/ask_gemini.py` | REQ-SC03 |
| TC-203 | backend 混在の会議(1名を openai/gemini に切替)が完走し成果物に model 明記 | frontmatter 変更 → 会議 | REQ-SC03 |
| TC-204 | **24時間無人稼働試験**(Phase 0 DoD): 翌日 status/kpi 確認・incident 0 | README §3 | FEAT-23 |
| TC-205 | SharePoint 同期(enabled=true で pull/push/root) | `python scripts/sharepoint.py test` | FEAT-56 |

## P3(エッジ・環境依存)

| ID | タイトル | 内容 | 関連 |
|---|---|---|---|
| TC-301 | tc.exe ランチャがブロックされる環境 → `python -m scripts.cli` で代替できる | ADR-0001 | — |
| TC-302 | 通知 URL 未設定(Teams/Discord いずれの backend でも)→ 通知がログfallbackし本体が止まらない | .env 空で kill 等を実行(自動版は `pytest tests/notify`) | REQ-O01 |
| TC-303 | DB ファイル破損/削除 → `db init` で再構築、reconcile が不整合を報告 | var/ 削除 → 再init | REQ-E03 |
| TC-304 | Windows スリープ復帰後の watchdog 途絶検知 | スリープ→復帰 | REQ-O02 |
| TC-305 | ポリシーYAML手編集 → pre-commit / hooks が検出 | わざと編集 | REQ-S03 |
