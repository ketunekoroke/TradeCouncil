# MAGI

エヴァンゲリオンのMAGIシステムに着想を得た、**人格ベースのマルチエージェント・システム**。
価値観で分かれた3人格を、ファシリテーターが**用途シナリオ**に応じて動かす。最初の
シナリオは「合議」(議論して合意形成)、第2のシナリオは「資料チェック&リバイス」
(資料をレビューして指摘+改訂版を出す)。過程と結論を成果物として残す。

## このリポジトリの構成

このリポジトリは2つのフェーズを1つのリポジトリで管理する monorepo 構成です。

```
magi/
├── README.md             ← 本書(全体概要)
├── .gitignore            ← 全体共通の除外ルール
├── .gitattributes        ← 改行コード統一(全体共通)
├── prototype/            ← Phase 0: Claude Code Agent Teams版プロトタイプ
└── app/                  ← Phase 1: Next.js + TypeScript版アプリ(開発中)
```

| ディレクトリ | フェーズ | 目的 | エントリポイント |
|---|---|---|---|
| `prototype/` | Phase 0 | 仕様検証・シナリオ/人格プロトコルの動作確認 | `prototype/README.md` |
| `app/` | Phase 1 | 本格Webアプリ実装 | `app/README.md` |

## どちらから読めばいい?

- **プロジェクト全体の仕様を知りたい** → [`prototype/DOCS.md`](prototype/DOCS.md)
- **プロトタイプを実際に動かしたい** → [`prototype/README.md`](prototype/README.md)
- **本格アプリの開発を始めたい** → [`app/README.md`](app/README.md) と [`app/DEVELOPMENT.md`](app/DEVELOPMENT.md)
- **AIが従うルール(シナリオ選択+共通作法)を見たい** → [`prototype/CLAUDE.md`](prototype/CLAUDE.md)
- **各シナリオのプロトコルを見たい** → [`prototype/scenarios/`](prototype/scenarios/)
- **アプリ開発時のコーディング規約を見たい** → [`app/CLAUDE.md`](app/CLAUDE.md)

## 2つのフェーズの関係

```
┌─────────────────────────┐         ┌─────────────────────────┐
│ Phase 0: prototype/     │ 仕様提供 │ Phase 1: app/           │
│                         │ ────→  │                         │
│ ・シナリオ/人格定義       │         │ ・Next.js + TypeScript  │
│ ・3人格の挙動確認         │         │ ・Webアプリとして実装     │
│ ・成果物形式の試行錯誤     │         │ ・永続化・UI・API化       │
│ ・自然言語で記述          │         │ ・コードとして実装        │
└─────────────────────────┘         └─────────────────────────┘
       「動く仕様書」                       「本実装」
```

**プロトタイプは「動く仕様書」として残し続ける**ことを推奨。新機能はまず
プロトタイプでシナリオ/プロトコル化 → 動作確認 → アプリに実装、の流れが安全です。

## 開発フローのおすすめ

### 仕様変更があるとき

1. `prototype/CLAUDE.md`(ルーター)/ `prototype/scenarios/<name>.md` / 人格定義を編集
2. プロトタイプで実際に動かして確認
3. `prototype/DOCS.md` を更新
4. `app/` で実装変更
5. **1コミットにまとめてプッシュ**(monorepoの強み: 仕様と実装の同期が履歴上で明確に)

### コミットメッセージ規約

スコープにディレクトリ名を入れて履歴を読みやすくします:

```
feat(prototype): add fourth persona OBSERVER
feat(app/personas): port MELCHIOR system prompt from prototype
docs(prototype): clarify Round 4 Steelman rules
fix(app/streaming): handle SSE reconnection
chore: update root README
```

Conventional Commits 準拠。スコープは `prototype` / `app/<feature>` / 共通の場合は省略。

## クイックスタート

### プロトタイプを試す

```bash
cd prototype
# README.mdの手順に従う
```

必要なもの: Claude Code v2.1.32以上、Python 3(成果物生成用)

### アプリ開発を始める

```bash
cd app
# DEVELOPMENT.mdのM0から進める
```

必要なもの: Node.js、Anthropic API キー

## ライセンス

(必要に応じて追加)

---

仕様の一次資料: [`prototype/DOCS.md`](prototype/DOCS.md)
