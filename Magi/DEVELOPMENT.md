# DEVELOPMENT — Magi(シナリオ・人格基盤の開発ガイド)

Magi(汎用マルチエージェント基盤)の編集・拡張ガイド。Magi は **「動く仕様書」** で、ここで
決めた人格・シナリオの挙動がそのまま成果物の質になる。深い仕様の一次資料は
[docs/07_シナリオ・人格基盤.md](docs/07_シナリオ・人格基盤.md)、共通ブリッジ(LLM/SharePoint/office)は
[../shared/](../shared/)(変更は全プロジェクトに影響)。ナビ: [README](README.md) / [CLAUDE](CLAUDE.md) /
[DOCS](DOCS.md) / 要件 [REQUIREMENTS](REQUIREMENTS.md) / 機能 [FEATURES](FEATURES.md) / テスト [TESTCASES](TESTCASES.md)。

## どこから Claude Code を起動するか

| 目的 | 起動場所 | 動き |
|---|---|---|
| シナリオを実行する(合議・資料レビュー等) | `cd Magi && claude` | ルーター([CLAUDE.md](CLAUDE.md))がモード判定し、ファシリテーターとして動く |
| Magi を編集する(人格・シナリオ・docs) | `cd Magi && claude` | 発話が開発系ならそのまま開発モード |
| 共通ブリッジを直す(LLM/SharePoint/office) | `../shared/` を編集 | 全プロジェクトに影響(売買にも波及) |

> council(意思決定会議)は別プロジェクト → [../TradeCouncil/](../TradeCouncil/CLAUDE.md)。

## 編集対象ファイル

| ファイル | 内容 | 編集頻度 |
|---|---|---|
| `.claude/agents/{melchior,balthasar,casper}.md` | 3人格の定義(本文=システムプロンプト) | 中 |
| `CLAUDE.md` | ルーター(モード判定 + 全シナリオ共通の作法) | 低(慎重に) |
| `scenarios/{deliberation,document-review,brainstorm,persona-test}.md` | 各シナリオのプロトコル | 低〜中 |
| `scenarios/README.md` | シナリオ一覧・ルーティング早見 | 中(シナリオ追加時) |
| `docs/07_シナリオ・人格基盤.md` | 深い仕様の一次資料 | 高(挙動変更を反映) |
| `REQUIREMENTS.md` / `FEATURES.md` / `TESTCASES.md` | 管理表(機能追加時に同期) | 中 |
| `docs/testing/scenario-bridge-testcases.md` | 詳細テストケース(独立 TC 名前空間) | 中 |
| `sharepoint.config.json` | SharePoint 連携設定(env_prefix=MAGI・enabled 等) | 低 |
| `README.md` | クイックスタート・使い方 | 低 |
| (共通)`../shared/ask_openai.py` ほか | LLMブリッジ本体 | 中(shared で編集) |

## よくある変更パターン

### パターン1: 人格を微調整する
例: 「MELCHIOR をもっと論理的に」「BALTHASAR の優しさを強める」

1. `.claude/agents/<name>.md` を編集(**YAML フロントマター name/description/backend/model は維持**)
2. 既存の節構成(人格 / 好奇心・興味 / 議論スタイル / 苦手なこと / 発言時の注意 / 議題への向き合い方)を保つ。
   **意図的な弱みは消さない**
3. [docs/07](docs/07_シナリオ・人格基盤.md)「3. 人格」を更新
4. **人格テスト([scenarios/persona-test.md](scenarios/persona-test.md))で回帰** — 同一プローブを3人格に独立投下し、
   調整が実挙動に出たか・個性が保たれているか(似すぎ警告)を差分マトリクスで定点観測する(議論を回すより軽い)
5. コミット: `feat(Magi/personas): strengthen MELCHIOR's probabilistic reasoning`

### パターン2: 新しい人格を追加する
1. 既存ファイルの構造を踏襲して `.claude/agents/<name>.md` を作成(既存3人格と被らない弱みを設定)
2. [CLAUDE.md](CLAUDE.md) の「役割と人格」「召喚ルール」に追記
3. 各ラウンドの参加人数を見直す(投票・スコアの集計式が変わる)→ 該当 `scenarios/*.md` と docs/07
4. [docs/07](docs/07_シナリオ・人格基盤.md)(人格表・構成図・プロトコル)と [README.md](README.md) の構成を更新
5. 実際に議論を回して動作確認 → コミット: `feat(Magi/personas): add OBSERVER persona`

### パターン3: ラウンドを追加・変更する
1. 該当 `scenarios/<name>.md` のラウンド定義を編集(冒頭のモード別ラウンド表も整合確認)
2. [docs/07](docs/07_シナリオ・人格基盤.md)「4. シナリオとプロトコル」の該当節を更新(想定時間が変われば時間目安も)
3. 1〜2件で実走し想定どおりか確認 → コミット: `feat(Magi/protocol): extend pair dialogues to 3 turns`

### パターン4: 成果物形式を追加・変更する
1. 該当 `scenarios/<name>.md` の「成果物」節に仕様追記(例: PowerPoint 出力)
2. 必要な Python ライブラリを [README.md](README.md) のセットアップ手順 / docs/07 §7 に追加
3. [docs/07](docs/07_シナリオ・人格基盤.md)「5. 成果物」を更新 → 実走確認 → `feat(Magi/deliverables): add PowerPoint output spec`

### パターン5: シナリオを追加する
1. `scenarios/<name>.md` を新規作成(既存の構成を踏襲。そのシナリオ固有の**モード/ラウンド/成果物/心得**だけ書く。
   **共通作法は重複させず [CLAUDE.md](CLAUDE.md) を参照**)
2. [scenarios/README.md](scenarios/README.md) の一覧・選択の兆候表に追記
3. [CLAUDE.md](CLAUDE.md) のモード判定表・出力ディレクトリに追記
4. 出力先を新設するなら [../.gitignore](../.gitignore) の除外規則(`**/workspace/...`)に沿って `workspace/<dir>/.gitkeep` を置く
5. [docs/07](docs/07_シナリオ・人格基盤.md)「4」に節追加(必要なら「9. ディレクトリ構成」も)
6. [REQUIREMENTS.md](REQUIREMENTS.md) → [FEATURES.md](FEATURES.md) → [TESTCASES.md](TESTCASES.md) を同期
7. 1〜2件で実走 → コミット: `feat(Magi/scenarios): add interview scenario`

> **禁止**: 共通作法(人格定義・backend 振り分け・メディア・召喚ルール)をシナリオファイルへ
> 重複コピーしない。共通は CLAUDE.md を唯一の出典にする(乖離の防止)。

### パターン6: ブリッジ(LLM/SharePoint/office)を直す
1. `../shared/` で修正(ask_openai/ask_gemini/bridge_common/sharepoint/extract_office 等)。**全プロジェクトに影響**
2. `../shared/tests` の自動テストと、必要なら [docs/testing/scenario-bridge-testcases.md](docs/testing/scenario-bridge-testcases.md) を更新
3. コミット: `fix(shared): ...`(Magi ではなく shared スコープ)

### パターン7: ドキュメントの誤字・表現修正
仕様変更を伴わないので対象ファイルだけ修正。コミット: `docs(Magi): proofread docs/07`

## 編集の検証方法

Magi 側(シナリオ・人格)は **手動の実行**で検証する(ブリッジの自動テストは `../shared/tests`)。

- **軽い検証**(変更が小さい): `cd Magi && claude` →「議題: 〈軽いお題〉(Lite)」で合議を1本回し、
  ラウンド進行・人格の反映・成果物を確認
- **人格を調整した場合**: 合議より **人格テスト**([scenarios/persona-test.md](scenarios/persona-test.md))が速くて確実
  (同一プローブを3人格に独立投下し、調整の反映と個性の保持を差分で見る = 回帰テスト)
- **重い検証**(プロトコル変更): 性質の異なる3議題(①2択判断 ②複数選択肢の比較 ③創作系)を
  Lite/Standard/Full で試す

## 編集時の禁止事項

- **生成済みの成果物を編集しない** — `workspace/{deliberations,reviews,...}/*.md` は不変の履歴
- **人格に専門分野を持たせない** — 設計思想は「価値観で分ける」。「金融の専門家」「医師」のような専門ペルソナにしない
- **議論を予定調和に丸めない** — 各人格の「意図的な弱み」を消したり「最終的に全員同意」プロトコルにしない
- **docs/07 と CLAUDE.md の乖離を放置しない** — 挙動を変えたら同期して更新

## ドキュメント同期ルール

挙動・機能を変えたら同一コミットで: [docs/07_シナリオ・人格基盤.md](docs/07_シナリオ・人格基盤.md)(一次資料・直接改訂可)→
[DOCS.md](DOCS.md) → [REQUIREMENTS.md](REQUIREMENTS.md) → [FEATURES.md](FEATURES.md) → [TESTCASES.md](TESTCASES.md)。
人格を変えたら persona-test で回帰。CLAUDE.md と docs/07 は必ず一緒に更新する(乖離が一番の事故)。

## コミット規約(Conventional Commits)

```
feat(Magi/personas): <人格関連>      feat(Magi/protocol): <議論プロトコル>
feat(Magi/scenarios): <シナリオ追加>  feat(Magi/deliverables): <成果物>
fix(shared): <ブリッジ修正>           docs(Magi): <ドキュメントのみ>
```
仕様変更は **1コミットで CLAUDE.md と docs/07 を両方更新**(後から「いつ変わったか」を追えるように)。

## チェックリスト(変更前)

- [ ] 変更の目的が明確か / 影響範囲(CLAUDE.md・docs/07・agents・README のどれを更新するか)を把握したか
- [ ] 機能を足したら REQUIREMENTS / FEATURES / TESTCASES も更新したか
- [ ] ブリッジ変更なら `../shared` で行い `../shared/tests` を通したか(全プロジェクト影響を意識)
- [ ] 人格を変えたら persona-test で回帰したか / 実際に1〜2件回して挙動確認したか

## 困った時

- 仕様の判断に迷う → [docs/07](docs/07_シナリオ・人格基盤.md) を一次資料として参照
- 大きな変更 → プランモードで計画を作りユーザー承認を得る
- ブリッジの挙動確認 → `../shared/README.md` と `../shared/tests`
- 変更を取り消したい → `git checkout <file>`(ファイル単位)/ `git reset`(コミット単位)
