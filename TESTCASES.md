# テストケース一覧 — モノレポ全体

**モノレポ構造にかかわる検証だけ**。各プロジェクトのテストは
[Magi/TESTCASES.md](Magi/TESTCASES.md) / [TradeCouncil/TESTCASES.md](TradeCouncil/TESTCASES.md) /
[shared/TESTCASES.md](shared/TESTCASES.md)。

| ID | タイトル | 実行方法 | 関連 |
|---|---|---|---|
| TC-MR01 | 売買スイートが緑(TradeCouncil/ 内) | `cd TradeCouncil; ..\.venv\Scripts\python.exe -m scripts.cli test` | REQ-MR01 |
| TC-MR02 | 共通スイートが緑(ルートから) | `.venv\Scripts\python.exe -m pytest shared/tests` | REQ-MR03 |
| TC-MR03 | **疎結合の実証**: `Magi/` を一時退避しても `tc test` が緑(TradeCouncil の MAGI への実行時依存ゼロ) | Magi を mv → `tc test` → 戻す | REQ-MR02 |
| TC-MR04 | `core` の import グラフに `shared`/`Magi` 参照が無い | `grep -rE 'import (shared|Magi)' TradeCouncil/core` が空 | REQ-MR02 |
| TC-MR05 | per-project ミラー: TradeCouncil の docs 編集 → SharePoint `TradeCouncil/Docs/` のみ更新(Magi は無風)。Magi 側も対称 | `tc hooks install` 後にコミットで観察 | REQ-MR06 |
