# MAGI Monorepo 開発モード(Claude Code向け)

このCLAUDE.mdが読まれているということは、あなたは **monorepo全体の開発作業** を
行っています。具体的には:

- `prototype/` の編集・改善・拡張(人格定義、議論プロトコル、ドキュメント)
- `app/` の開発(Next.jsアプリの実装)
- ルートレベルの設定(README、.gitignore、.gitattributes)
- 横断的なリファクタリング、ドキュメント整備

## 重要: あなたは今、議論モードではありません

このディレクトリで起動した場合、**MAGI合議を実行する役割ではありません**。
`prototype/CLAUDE.md` の議論プロトコル(MELCHIOR/BALTHASAR/CASPER のオーケストレーター)は
ロードされていません。あなたは**通常の開発アシスタント**として動作してください。

ユーザーから「議題」「相談」「合議を始める」といった要求があった場合は:
> 「議論を実行するには `cd prototype && claude` で起動し直してください」
と案内してください。

## プロジェクト構成

```
magi/
├── prototype/    ← Phase 0: シナリオ/人格プロトコル定義(動く仕様書)
│   ├── CLAUDE.md      ルーター: シナリオ選択+全シナリオ共通の作法(編集対象)
│   ├── scenarios/    シナリオ別プロトコル: deliberation / document-review(編集対象)
│   ├── DOCS.md        仕様の一次資料(編集対象)
│   ├── DEVELOPMENT.md プロトタイプ開発ガイド(編集対象)
│   └── .claude/agents/  人格定義(編集対象)
└── app/          ← Phase 1: Next.js本実装
    ├── CLAUDE.md       アプリ開発ルール
    └── DEVELOPMENT.md  マイルストーン
```

## 作業の流れ

### prototype/ に対する作業

人格調整、議論プロトコル変更、ドキュメント更新など。

1. `prototype/DEVELOPMENT.md` を読んで作業の規約を確認
2. 該当ファイルを編集
3. **仕様変更を伴う場合は `prototype/DOCS.md` も同期して更新**
4. 必要なら `app/CLAUDE.md` や `app/DEVELOPMENT.md` も更新(仕様が両方に影響する場合)
5. Conventional Commits でコミット

### app/ に対する作業

Next.jsアプリの開発。詳細は `app/CLAUDE.md` を参照。
作業内容によっては `cd app && claude` で起動し直した方が
コーディング規約が明示的にロードされて効率的な場合もある。

## 共通の開発規約

### コミットメッセージ

Conventional Commits 準拠、スコープを明示:

```
feat(prototype): add fourth persona OBSERVER
feat(app/personas): port MELCHIOR system prompt from prototype
docs(prototype): clarify Round 4 Steelman rules
fix(app/streaming): handle SSE reconnection
chore: update root README
refactor(prototype/protocol): simplify Round 2 structure
```

スコープが不明なら `chore`/`docs` のみで省略可。

### コミット粒度

- 動く単位ごとに1コミット
- 仕様変更と実装変更を**同じPR/コミット**にまとめると、後から履歴を追いやすい
  (monorepoの強み)

### ドキュメントの一貫性

仕様変更時の更新箇所(忘れがち):

| 変更内容 | 更新が必要なファイル |
|---|---|
| 人格を編集 | `prototype/.claude/agents/<name>.md`, `prototype/DOCS.md` の3.章 |
| ラウンドを追加・変更 | `prototype/scenarios/<name>.md`, `prototype/DOCS.md` の4.章 |
| 成果物形式を変更 | `prototype/scenarios/<name>.md`, `prototype/DOCS.md` の5.章 |
| モード/シナリオを追加 | 上記 + `prototype/CLAUDE.md`(シナリオ選択), `prototype/scenarios/README.md`, `prototype/README.md` の使い方 |

迷ったら `prototype/DOCS.md` を一次資料とし、それ以外を追従させる方針。

## やってはいけないこと

- **利用モード(シナリオ実行)と開発モードを混在させない** — 人格として発言したり、Round進行を始めたりしない
- **prototype/CLAUDE.md(ルーター)や scenarios/*.md のプロトコルを破壊する** — 大きな変更は必ずユーザーに確認
- **共通作法をシナリオに重複させる** — 人格/backend/メディア/召喚は `prototype/CLAUDE.md` を唯一の出典に
- **DOCS.md と CLAUDE.md/scenarios の乖離を放置** — 一方だけ更新するのは禁止
- **生成済みのログを編集** — `prototype/deliberations/*.md` / `prototype/reviews/*` は履歴として不変

## 困った時

- 仕様が不明 → `prototype/DOCS.md` を読む、なければユーザーに質問
- 大きな設計判断が必要 → プランモード(Shift+Tab 2回)で提案
- ユーザーの意図が不明 → 「開発作業ですか? シナリオを実行したいですか(合議 / 資料レビュー)?」と確認
