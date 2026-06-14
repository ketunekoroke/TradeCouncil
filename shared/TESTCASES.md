# テストケース一覧(Test Cases)— shared(共通ツール層)

LLMブリッジ・SharePoint・git フックの検証。自動テストはリポジトリルートで
`.venv\Scripts\python.exe -m pytest shared/tests`。詳細な手動手順(ブリッジ実機)は
[../Magi/docs/testing/scenario-bridge-testcases.md](../Magi/docs/testing/scenario-bridge-testcases.md)。

## P0(自動・無課金)

| ID | タイトル | 実行方法 | 関連 |
|---|---|---|---|
| TC-018 | シークレット解決順(環境変数 → ルート共有 .env → settings.local.json、placeholder/空は除外) | `pytest shared/tests/test_env_resolution.py` | REQ-SH02 |
| TC-026 | workspace 同期計画(ADR-0009): 片側のみ→コピー・newer-wins・skew 内 skip・削除非伝播・除外(.gitkeep/直下README/*.tmp)・root が `<project>/workspace`・config が project 追従 | `pytest shared/tests/test_sharepoint_sync.py` | REQ-SP03 |
| TC-028 | docs ミラー計画(ADR-0010): A/M/T→push・D→delete・R→delete+push・対象外パス除外・空 diff・full 時の prune・状態ファイル round-trip / 破損 JSON は初回扱い・`install_hooks` が3フック導入 | `pytest shared/tests/test_sharepoint_mirror.py` | REQ-SP09〜SP12, REQ-SH03 |
| TC-027b | **ブリッジ P0 一式**(構文・キー3段解決・HTTP/生成リトライ・`--history` 整形・フォールバック分岐 — docs/testing §P0 のブリッジ分) | [../Magi/docs/testing/scenario-bridge-testcases.md](../Magi/docs/testing/scenario-bridge-testcases.md) §P0 | REQ-LB, REQ-FI, REQ-NF |

## P2(API課金・長時間)

| ID | タイトル | 手順 | 関連 |
|---|---|---|---|
| TC-201 | OpenAI ブリッジ疎通(人格1名を1ラウンド) | `echo test \| python shared/ask_openai.py --system-file ../Magi/.claude/agents/melchior.md --model gpt-4o` | REQ-LB02 |
| TC-202 | Gemini ブリッジ疎通(同上) | `shared/ask_gemini.py` | REQ-LB02 |
| TC-205 | SharePoint 同期実機(enabled=true で `sync` の双方向往復: ローカル新規→遠隔 / 遠隔新規→ローカル / 再実行で全 skip / 片側削除が伝播しない) | `python shared/sharepoint.py test --project <p>` → `sync` ×2 | REQ-SP03 |
| TC-208 | docs ミラー実機(ADR-0010): 初回 `mirror --project <p>` で docs/+管理表が SharePoint `<Project>/Docs/` に現れる → 直後再実行で「up to date」→ main へのコミットで post-commit フックが差分のみ push → オフラインでもコミットは成功し次回追いつく | `python shared/sharepoint.py mirror --project <p>` → コミットで観察 | REQ-SP09〜SP12 |
| TC-207b | **ブリッジ P2 一式**(upload/file-id 使い回し・SharePoint 実 sync 往復 — docs/testing §P2 のブリッジ分) | [../Magi/docs/testing/scenario-bridge-testcases.md](../Magi/docs/testing/scenario-bridge-testcases.md) §P2 | REQ-FI, REQ-SP |
