# MAGI App 開発ルール(Claude Code 向け)

これは **アプリ開発時に Claude Code が従うルール** を定義する。
合議制AIエージェントを Next.js + TypeScript で本実装するプロジェクト。

> Phase 0プロトタイプの仕様(議論プロトコル、3人格、成果物形式など)は
> `../prototype/DOCS.md` を一次資料とする。

---

## プロジェクトの目的

エヴァンゲリオンのMAGIを参考にした、人格ベースの合議制AIエージェントのWebアプリ。
ユーザーの相談に対し、3つの人格(MELCHIOR/BALTHASAR/CASPER)が議論し、
ファシリテーターが合意形成、議論過程と結論を可視化・永続化する。

## 技術スタック

- **フレームワーク**: Next.js 15(App Router)
- **言語**: TypeScript(strict mode)
- **UI**: React 19, shadcn/ui, Tailwind CSS
- **LLM**: Anthropic SDK(@anthropic-ai/sdk)+ Vercel AI SDK
- **状態管理**: Zustand
- **DB**: Drizzle ORM + SQLite(dev)/ PostgreSQL(prod)
- **ストリーミング**: Server-Sent Events
- **チャート**: Recharts
- **成果物生成**: docx (Node), exceljs
- **テスト**: Vitest + Testing Library + Playwright(E2E)
- **Lint/Format**: ESLint + Prettier(初期設定で済ませる)

## コーディング規約

### 全般

- **TypeScript strict mode 必須**。`any` の使用は禁止(やむを得ない場合はコメントで理由必須)
- **関数1つ = 機能1つ**。50行を超えるなら分割を検討
- **早期return** で if のネストを減らす
- **環境変数** は `.env.local`、参照は `src/env.ts`(zodで検証)経由
- **エラーハンドリング** は `Result<T, E>` パターン or try-catch を明示的に
- **i18n** は初期スコープ外。UIは日本語前提

### Next.js 固有

- **App Router 限定**(Pages Routerは使わない)
- **Server Components をデフォルト**にし、必要な箇所のみ `"use client"`
- **Server Actions** はフォーム送信などに活用
- **route handlers** は `src/app/api/<path>/route.ts` に配置
- **環境変数の使用範囲**: `NEXT_PUBLIC_` プレフィックスはクライアント露出に注意

### ディレクトリ規約

```
src/
├── app/              # Next.js App Router
├── components/       # 再利用可能なUIコンポーネント
│   ├── ui/           # shadcn/ui コンポーネント
│   └── feature/      # 機能特化コンポーネント
├── lib/              # ビジネスロジック・ライブラリ
│   ├── personas/     # 人格定義(.ts)
│   ├── deliberation/ # 議論エンジン
│   ├── anthropic/    # SDKラッパー
│   ├── db/           # スキーマ・クエリ
│   └── deliverables/ # Word/Excel/チャート生成
├── stores/           # Zustand store
├── types/            # 共通型定義
└── env.ts            # 環境変数(zod検証)
```

### 命名

- ファイル: kebab-case(`persona-panel.tsx`)、ただしコンポーネントの主ファイルは PascalCase 可
- React コンポーネント: PascalCase
- 関数・変数: camelCase
- 型・インターフェース: PascalCase
- 定数: SCREAMING_SNAKE_CASE
- 人格名はソース内では小文字(`melchior`, `balthasar`, `casper`)、UI表示は大文字

## 開発フロー

### 必ず守ること

1. **新機能着手前にプランモードで設計を確認** — Shift+Tab を 2回押してプランモードに入る
2. **テストを先に書く**(可能な限り) — 失敗するテスト → 実装 → 通る、の順
3. **動いた単位で即コミット** — Conventional Commits 準拠
4. **動作確認なしに「実装完了」と報告しない** — 必ず `npm run dev` で目視 or テストでパス確認
5. **不確実な仕様はユーザーに確認** — 勝手に決めずに質問する

### Conventional Commits

```
feat(scope): 新機能
fix(scope): バグ修正
refactor(scope): リファクタ
docs(scope): ドキュメント
test(scope): テスト
chore(scope): その他

scope例: personas, deliberation, ui, db, deliverables, infra
```

## 議論エンジン実装の指針

### 設計の核

- **議論はステートマシン**として表現する。Round 0〜9 が状態、各人格の発言がイベント
- **状態は永続化前提** — メモリだけでなくDBに保存し、いつでも再開可能に
- **ストリーミング前提** — 各人格の発言は段階的にクライアントへ送る
- **モード(Lite/Standard/Full)** はランタイムで分岐、Round の有無を制御

### 人格の実装

`src/lib/personas/<name>.ts` に、システムプロンプトと判断軸スコアリング用の
メタ情報を持つオブジェクトを定義。プロトタイプの `.claude/agents/<name>.md` の
内容をそのまま移植してよい。

```typescript
// src/lib/personas/melchior.ts の例
export const melchior: Persona = {
  id: 'melchior',
  displayName: 'MELCHIOR',
  systemPrompt: `あなたは MELCHIOR...`,  // プロトタイプの内容
  weights: { logic: 0.5, empathy: 0.2, intuition: 0.3 },  // 評価軸の重み
  model: 'claude-sonnet-4-5',
};
```

### ファシリテーターの実装

`src/lib/deliberation/facilitator.ts` に状態遷移ロジックを置く。
各 Round の入出力は型で厳密に定義する(`src/lib/deliberation/types.ts`)。

### Anthropic API 呼び出し

- すべて `src/lib/anthropic/` 配下のラッパー経由
- ストリーミングは AI SDK の `streamText` を活用
- リトライ・タイムアウト・トークン上限はラッパーで一元管理
- APIキーは絶対にクライアントへ露出させない(Server-side only)

## DB スキーマの初期方針

```typescript
// 議論セッション
deliberations: { id, topic, mode, status, createdAt, updatedAt, summary }

// 各ラウンドの発言ログ
turns: { id, deliberationId, round, personaId, content, createdAt }

// 評価軸スコア
scores: { id, deliberationId, personaId, axis, value }

// 投票結果
votes: { id, deliberationId, personaId, position, confidence, rationale }
```

## UI 設計指針

- **3カラムレイアウト**(デスクトップ): 各人格のパネルを横並び、議論進行で発言が降ってくる
- **モバイル**: 縦タブで人格切替、現在発言中の人格を強調
- **ストリーミング表示**: タイプライター効果で発言を表示、終了で確定
- **進捗バー**: 現在のRoundを上部に常時表示
- **配色**: 3人格それぞれにテーマカラー(原作風: 黄/緑/青、または独自)

## テスト方針

- **ユニット**(Vitest): 人格の発言生成、評価ロジック、スコア集計
- **統合**: 議論エンジンの全Round通し実行(モックLLM使用)
- **E2E**(Playwright): 主要ユーザーフロー1〜2本

## セキュリティ

- APIキーはServer-side環境変数のみ。クライアントに露出させない
- ユーザー入力はzodで検証
- 議論内容はユーザー所有。デフォルトでは他人と共有しない
- 公開用デモは別途認証を実装(初期は無認証ローカル前提)

## やってはいけないこと

- **`any` の安易な使用** — 型を諦めない
- **コミット前のlint/format忘れ** — pre-commit hook で自動化する
- **長大なコンポーネント** — 200行を超えたら必ず分割
- **テストなしのリリース** — 主要パスはカバー
- **prototype の DOCS.md と乖離した実装** — 仕様変更時は両方更新

## 参考ファイル

- `../prototype/DOCS.md` — 仕様の一次資料
- `../prototype/CLAUDE.md` — 議論プロトコル(実装の元ネタ)
- `../prototype/.claude/agents/*.md` — 人格定義(systemPrompt 移植元)

## 困った時の対処

- 仕様が不明確 → ユーザーに質問する
- 設計判断が大きい → プランモードで提案、承認を得る
- 動作確認できない → サンプルデータで再現、ユーザーに状況報告
- prototype と矛盾する要件 → ユーザーに確認、両方更新
