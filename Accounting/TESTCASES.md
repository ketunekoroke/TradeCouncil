# テストケース一覧 — Accounting(会計経理支援システム)

モノレポ構造の検証はルート [../TESTCASES.md](../TESTCASES.md)。本表は Accounting 固有。
優先度: P0(必須・回帰の核)/ P1 / P2 / P3。

| ID | タイトル | 実行方法 | 優先 | 関連 |
|---|---|---|---|---|
| TC-AC01 | 足場スイートが緑(Accounting/ 内) | `cd Accounting; ..\.venv\Scripts\python.exe -m scripts.cli test` | P0 | REQ-AC01 |
| TC-AC02 | import 健全性(scripts.cli / core が読める) | `tests/test_smoke.py` | P0 | REQ-AC01 |
| TC-AC03 | **削除可能性**: `core/` に `import Magi` / `import TradeCouncil` が無い | `tests/test_decoupling.py` | P0 | REQ-AC02 |
| TC-AC04 | docs lint: `accounting-policy.md` に「適用開始日」が存在し矛盾が無い | `tests/test_docs_lint.py` | P0 | REQ-AC03 |
| TC-AC05 | sharepoint.config.json が有効な JSON で env_prefix/git_mirror が ADR-0010 形 | `tests/test_smoke.py`(config 読込) | P1 | REQ-AC03 |
| TC-AC06 | Accounting/ を一時退避しても TradeCouncil/Magi のスイートが緑(相互非依存) | Accounting を mv → 各 `test` → 戻す | P1 | REQ-AC02 |
| TC-AC07 | 検証ゲート(為替・税区分・証憑要件)の単体検証 | `scripts/check_compliance.py`(実装後) | P1 | REQ-EX02(将来) |
| TC-AC08 | MoneyForward 疎通スパイク(offices 取得まで) | `scripts/spike_moneyforward.py`(手動・実 creds・最小データ) | P2 | REQ-EX01 |
| TC-AC11 | 疎通スパイクの純粋ロジック単体検証(token リクエスト組立=認可コード grant・basic/post 認証・auth_code 欠落で SystemExit、offices URL 解決、offices 件数抽出=応答形状の差を吸収) | `tests/test_spike_moneyforward.py`(ネットワーク・実 creds 不要) | P1 | REQ-EX01 |
| TC-AC09 | MoneyForward 設定の解決(`MONEYFORWARD_<PRODUCT>_<FIELD>` env → config)・会計/経費の独立性・プレースホルダ除外・秘密マスク | `tests/test_moneyforward_config.py` | P0 | REQ-EX06 |
| TC-AC10 | `ac mf config [--product] --check` が未設定で exit 1、いずれか系統 ready で exit 0。両系統を表示 | `tests/test_moneyforward_config.py`(CLI 経由) | P1 | REQ-EX06 |
