# Prototype 開発ガイド

プロトタイプ(Phase 0)の編集・改善・拡張のための作業ガイド。

> このプロトタイプは **「動く仕様書」** として位置づけられている。
> ここで決めた挙動が `app/` の実装の元になる。仕様変更には責任が伴う。

---

## どこから Claude Code を起動するか

| 目的 | 起動場所 | 理由 |
|---|---|---|
| **シナリオを実行する**(合議・資料レビュー等) | `cd prototype && claude` | ルーター(CLAUDE.md)がロードされ、ファシリテーターとして動く |
| **プロトタイプを編集する** | `cd magi && claude` | ルーターがロードされず純粋な編集モード |

開発作業は必ず `magi/` ルートから起動するのを推奨。

---

## 編集対象ファイル

| ファイル | 内容 | 編集頻度 |
|---|---|---|
| `.claude/agents/melchior.md` | 科学者人格の定義 | 中 |
| `.claude/agents/balthasar.md` | 母人格の定義 | 中 |
| `.claude/agents/casper.md` | 個人人格の定義 | 中 |
| `CLAUDE.md` | ルーター(シナリオ選択+全シナリオ共通の作法) | 低(慎重に) |
| `scenarios/deliberation.md` | 合議シナリオのプロトコル(Round 0〜9) | 低(慎重に) |
| `scenarios/document-review.md` | 資料チェック&リバイス シナリオ(Round 0〜6) | 中 |
| `scenarios/README.md` | シナリオ一覧・ルーティング早見表 | 中(シナリオ追加時) |
| `DOCS.md` | 仕様の包括ドキュメント(一次資料) | 高(変更を反映) |
| `REQUIREMENTS.md` | 要件一覧(ID 付き) | 中(機能追加時に反映) |
| `FEATURES.md` | 機能一覧(要件・実装の対応表) | 中(機能追加時に反映) |
| `TESTCASES.md` | テストケース一覧(P0〜P3) | 中(機能追加時にケース追加) |
| `scripts/ask_openai.py` | OpenAI ブリッジ(openai 人格用) | 中 |
| `scripts/sharepoint.py` | SharePoint(Graph)同期ブリッジ(pull/push) | 中 |
| `sharepoint.config.json` | SharePoint 連携設定(enabled でオンオフ) | 低 |
| `README.md` | クイックスタート | 低 |

---

## よくある変更パターン

### パターン1: 人格を微調整する

例: 「MELCHIORをもっと論理的にしたい」「BALTHASARの優しさを強めたい」

```bash
cd magi
claude
> "MELCHIORの人格定義を編集して、確率論的な思考をさらに強める方向で
>  書き換えてくれ。今より厳密に、感情論への反論を辛口にしたい。
>  ただし『意図的な弱み』のセクションは変えないこと。"
```

**手順**:
1. `.claude/agents/<name>.md` を編集
2. **YAMLフロントマター(name, description, model)はそのまま**
3. 既存の節構成(人格 / 好奇心・興味 / 議論スタイル / 苦手なこと / 発言時の注意 / 議題への向き合い方)は維持
4. 編集後、`prototype/DOCS.md` の「3. 3つの人格」セクションも更新
5. **人格テストシナリオ(`scenarios/persona-test.md`)で挙動確認** — 同一プローブを3人格に独立に投げ、
   調整が実挙動に出たか・個性が保たれているか(似すぎ警告)を差分マトリクスで定点観測する
   (議論を回すより軽い。回帰テスト。→ `TESTCASES.md` TC-068)
6. コミット: `feat(prototype/personas): strengthen MELCHIOR's probabilistic reasoning`

### パターン2: 新しい人格を追加する

例: 「観察者」「批判家」など4人目の人格を追加。

```bash
> ".claude/agents/observer.md を新規作成してくれ。
>  この人格は議論を一段上から俯瞰し、3人格が見落としている
>  メタな論点を指摘する役割。既存の3人格と被らない弱みも設定すること。"
```

**手順**:
1. 既存ファイル(`melchior.md` 等)の構造を踏襲して新ファイル作成
2. `prototype/CLAUDE.md` の「役割」「召喚ルール」セクションに追記
3. `prototype/CLAUDE.md` の各ラウンドの参加人数を見直し(投票・スコアの集計式が変わる)
4. `prototype/DOCS.md` を全面的に更新(人格表、システム構成図、議論プロトコル等)
5. `prototype/README.md` の構成セクションも更新
6. 実際に議論を回して4人格の動作確認
7. コミット: `feat(prototype/personas): add OBSERVER persona`

### パターン3: ラウンドを追加・変更する

例: 「Round 2.5として『質問の振り返り』を追加」「Round 3のペア対話を3往復に増やす」

```bash
> "合議のRound 3のペア対話を、現在の2往復から3往復に変更してくれ。
>  scenarios/deliberation.md と DOCS.md の両方を更新すること。"
```

**手順**:
1. 該当する `prototype/scenarios/<name>.md` のラウンド定義を編集
2. モード別の含まれるラウンド表(同ファイル冒頭付近)も整合性確認
3. `prototype/DOCS.md` の「4. シナリオとプロトコル」の該当シナリオ節を更新
4. 想定時間が変わる場合、モード表の時間目安も更新
5. 1〜2件で実際に動かし、想定通りの挙動か確認
6. コミット: `feat(prototype/protocol): extend pair dialogues to 3 turns`

### パターン4: 成果物形式を追加・変更する

例: 「PowerPoint出力を追加」「Excelのシート構成を変更」

```bash
> "合議の成果物形式にPowerPointを追加したい。
>  経営会議向けの1枚サマリと、議論詳細の数枚で構成。
>  python-pptxを使う前提で scenarios/deliberation.md に仕様を追加してくれ。"
```

**手順**:
1. 該当する `prototype/scenarios/<name>.md` の「成果物」セクションに仕様追記
2. 必要なPythonライブラリを `prototype/README.md` のセットアップ手順に追加
3. `prototype/DOCS.md` の「5. 成果物」セクションを更新
4. 実際に回して成果物が想定通り生成されるか確認
5. コミット: `feat(prototype/deliverables): add PowerPoint output spec`

### パターン5: ドキュメントの誤字・表現修正

```bash
> "DOCS.md の文言を校正してくれ。冗長な表現を簡潔にし、
>  日本語として不自然な箇所を直す。意味は変えないこと。"
```

仕様変更を伴わないので、対象ファイルだけ修正してコミット。
コミット: `docs(prototype): proofread DOCS.md`

### パターン6: シナリオを追加する

例: 「ブレスト」「インタビュー」「計画レビュー」など、3人格の新しい用途を追加。

```bash
> "scenarios/brainstorm.md を新規作成してくれ。
>  3人格がアイデアを発散・収束させるシナリオ。
>  共通作法(人格/バックエンド/メディア/召喚)は重複させず CLAUDE.md を参照すること。"
```

**手順**:
1. `prototype/scenarios/<name>.md` を新規作成(既存シナリオの構成を踏襲)
   - そのシナリオ固有の**モード / ラウンド / 成果物 / 固有の心得**だけを書く
   - 共通部分は重複させず `CLAUDE.md` を参照する
2. `prototype/scenarios/README.md` の「シナリオ一覧」「選択の兆候」表に追記
3. `prototype/CLAUDE.md` の「シナリオの選択」判定表と「出力ディレクトリ」表に追記
4. 出力先ディレクトリを新設するなら `prototype/.gitignore` に除外ルールを追加し、
   `<dir>/.gitkeep` を置く
5. `prototype/DOCS.md`「4. シナリオとプロトコル」に節を追加(必要なら「9. ディレクトリ構成」も)
6. `REQUIREMENTS.md` → `FEATURES.md` → `TESTCASES.md` を併せて更新
7. 実際に1〜2件回してシナリオが想定通り進むか確認
8. コミット: `feat(prototype/scenarios): add brainstorm scenario`

**禁止事項**: 共通作法(人格定義・backend振り分け・メディア・召喚ルール)をシナリオ
ファイルに重複コピーしない。共通は `CLAUDE.md` を唯一の出典にする(乖離の防止)。

---

## 編集の検証方法

プロトタイプには自動テストはない。検証は **手動の議論実行** で行う。

### 軽い検証(変更が小さい時)

```bash
cd prototype
claude
> "MAGI合議を始める。議題: 「カフェで作業 vs 家で作業」(Liteモード)"
```

ラウンドが想定通り進むか、人格が変更を反映しているか、成果物が正しく出るかを確認。

**人格を調整した場合**は、合議を回すより **人格テストシナリオ(`scenarios/persona-test.md`)** が速くて確実
(同一プローブを3人格に独立投下し、調整の反映と個性の保持を差分で見る。→ TC-068)。

### 重い検証(プロトコル変更時)

3つの異なる性質の議題で試す:
1. **2択の単純判断**(例: 「転職すべきか」)
2. **複数選択肢の比較**(例: 「3つの引っ越し先候補から選ぶ」)
3. **創作系の議論**(例: 「短編小説のテーマを決める」)

それぞれLite/Standard/Fullで挙動を確認すると安心。

---

## 編集時の禁止事項

- **生成済みの議論ログを編集しない** — `<root>/deliberations/*.md`(`local/` または `sharepoint/`)は不変の履歴
- **人格に専門分野を持たせない** — 本プロジェクトの設計思想は「価値観で分ける」。
  「金融の専門家」「医師」のような専門ペルソナにしない
- **議論を予定調和に丸める変更をしない** — 各人格の「意図的な弱み」を消したり、
  「最終的にはみな同意する」プロトコルにしたりしない
- **DOCS.md と CLAUDE.md の乖離を放置しない** — 必ず同期して更新

---

## コミット規約

```
feat(prototype/personas): <人格関連の機能追加>
feat(prototype/protocol): <議論プロトコル変更>
feat(prototype/deliverables): <成果物関連の変更>
fix(prototype): <バグ修正・誤字修正>
docs(prototype): <ドキュメントのみ変更>
refactor(prototype): <挙動を変えないリファクタ>
```

仕様変更は **1コミットで CLAUDE.md と DOCS.md を両方更新する**。
別コミットに分けると、後から「仕様がいつ変わったか」が追いにくくなる。

---

## チェックリスト(変更前に確認)

- [ ] 変更の目的が明確か(なぜ変えるのか)
- [ ] 影響範囲を理解しているか(CLAUDE.md / DOCS.md / agents / README のどれを更新するか)
- [ ] 機能を足したら REQUIREMENTS / FEATURES / TESTCASES も更新したか(テストはランク付け)
- [ ] app/ への影響はあるか(あれば app側のドキュメントも更新)
- [ ] 実際に議論を回して挙動確認するか
- [ ] コミットメッセージはスコープを含めて書くか

---

## 困った時

- 仕様の判断に迷う → `DOCS.md` を一次資料として参照
- 大きな変更を入れたい → プランモード(`Shift+Tab` 2回)で計画を作り、ユーザー承認
- 動作確認できない → サンプル議題で再現を試み、結果をユーザーに報告
- 変更を取り消したい → `git checkout` でファイル単位、または `git reset` でコミット単位
