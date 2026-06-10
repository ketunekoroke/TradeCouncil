# MAGI App — 開発ロードマップとガイド

Phase 0プロトタイプ(`../prototype/`)から本格Webアプリへ移行する開発計画。
Claude Codeを開発ツールとして使い、MVPまでを段階的に進める。

---

## 開発の進め方(Claude Code活用)

### 基本サイクル

```
プランモード(設計) → 実装 → テスト/動作確認 → コミット → 次の機能へ
```

各ステップでClaude Codeに何をやらせるかを明確にする。設計判断はあなたが行い、
コードはClaude Codeに任せる、という分業が効率的。

### よく使うClaude Code機能

| 機能 | キー/コマンド | 用途 |
|---|---|---|
| プランモード | `Shift+Tab` ×2 | 実装前に計画を立てさせる(複雑な機能で必須) |
| 通常モード | `Shift+Tab` ×1 | 実装を進める |
| 自動承認モード | `Shift+Tab` ×3 | 信頼できる作業を任せる(範囲限定で) |
| サブエージェント | `/agents` | レビュアー等の専門役を作成 |
| メモリ更新 | `/memory` | CLAUDE.md の編集 |
| プロジェクト初期化 | `/init` | 既存コードからCLAUDE.md生成 |
| セッション再開 | `claude --continue` | 中断した作業の続行 |

### 推奨サブエージェント

開発専用のチームメイトを作っておくと便利:

- **`code-reviewer`** — 書いたコードをレビュー(可読性、セキュリティ、TS型安全性)
- **`test-writer`** — 失敗テストを先に書く役割
- **`ui-designer`** — Tailwind/shadcnでUIを整える専門
- **`db-architect`** — スキーマ変更とマイグレーション担当

---

## マイルストーン

### M0: プロジェクト初期化(0.5日)

**ゴール**: 空のNext.jsプロジェクトが起動する状態。

#### タスク

- [ ] `npx create-next-app@latest magi-app --typescript --tailwind --app --eslint`
- [ ] CLAUDE.md, DEVELOPMENT.md(本書)をルートに配置
- [ ] `.gitignore` / `.gitattributes` 整備
- [ ] Prettier, ESLint設定
- [ ] shadcn/ui 初期化(`npx shadcn@latest init`)
- [ ] 環境変数管理(`src/env.ts` with zod)
- [ ] `npm run dev` で起動確認
- [ ] Initial commit

#### Claude Codeへの最初の指示例

```
このプロジェクトでMAGI合議制AIエージェントのWebアプリを開発する。
まず CLAUDE.md と DEVELOPMENT.md を読んでほしい。
読み終えたらM0(プロジェクト初期化)を実施してくれ。
プランモードで計画を立て、私の承認を得てから実行すること。
```

### M1: 議論エンジンの最小実装(2-3日)

**ゴール**: コマンドラインから議論を回し、結果がコンソール出力される。

#### タスク

- [ ] 型定義(`src/lib/deliberation/types.ts`): `Persona`, `Round`, `Turn`, `Vote`
- [ ] 3人格定義(`src/lib/personas/*.ts`):プロトタイプから systemPrompt 移植
- [ ] Anthropic SDK ラッパー(`src/lib/anthropic/client.ts`)
- [ ] 議論エンジン本体(`src/lib/deliberation/facilitator.ts`)
- [ ] Liteモード(Round 0, 1, 2, 7-9)の通し実行
- [ ] スクリプト(`npm run deliberate <topic>`)で動作確認
- [ ] ユニットテスト(モックLLMで)

#### Claude Codeへの指示例

```
プロトタイプの ../prototype/CLAUDE.md と人格定義を参照しつつ、
M1のタスクを順に実装してほしい。
まず型定義から、その後人格、Anthropicラッパー、エンジンの順。
各実装の前にテストを書くこと。
1機能できたら必ずコミットしてから次へ進む。
```

### M2: API層とストリーミング(2日)

**ゴール**: ブラウザからリクエストし、議論がSSEでストリーミング表示される。

#### タスク

- [ ] route handler `POST /api/deliberate`(議論開始、SSEで返す)
- [ ] route handler `GET /api/deliberations/[id]/stream`(再接続用)
- [ ] AI SDK の `streamText` を活用
- [ ] エラーハンドリング、タイムアウト、リトライ
- [ ] curl での動作確認テスト

### M3: フロントエンドUI(3-4日)

**ゴール**: 議題を入力すると3人格の発言がストリーミング表示される。

#### タスク

- [ ] レイアウト(3カラム desktop / タブ mobile)
- [ ] PersonaPanel コンポーネント(発言表示、確信度メーター)
- [ ] DeliberationView コンポーネント(進行バー、Round表示)
- [ ] Zustand store で議論状態を管理
- [ ] SSE接続フック(`useDeliberation`)
- [ ] タイプライター効果でストリーミング表示
- [ ] レスポンシブ対応

### M4: 永続化(1-2日)

**ゴール**: 議論がDBに保存され、後から一覧・再表示できる。

#### タスク

- [ ] Drizzle セットアップ、SQLite接続
- [ ] スキーマ定義(deliberations, turns, scores, votes)
- [ ] マイグレーション
- [ ] 議論履歴ページ(`/deliberations`)
- [ ] 個別議論ページ(`/deliberations/[id]`)
- [ ] 進行中議論の中断・再開

### M5: 成果物生成(2日)

**ゴール**: Word/Excel/チャートをダウンロードできる。

#### タスク

- [ ] `src/lib/deliverables/markdown.ts` — Markdown生成
- [ ] `src/lib/deliverables/excel.ts` — exceljs で意思決定マトリクス
- [ ] `src/lib/deliverables/docx.ts` — docx ライブラリで議論レポート
- [ ] Recharts でレーダー/ヒートマップ
- [ ] ダウンロードボタンの設置

### M6: Standard/Fullモード(1-2日)

**ゴール**: Round 1.5, 3, 4, 5, 6 が動作する。

#### タスク

- [ ] Round 1.5(自己疑念)、3(ペア対話)、4(Steelman)、5(立場更新)
- [ ] Round 6(自由討議)とその制御ロジック
- [ ] モード選択UI

### M7: 仕上げとデプロイ(2-3日)

#### タスク

- [ ] E2Eテスト(Playwright)主要フロー1-2本
- [ ] エラーハンドリング、ローディング状態の改善
- [ ] パフォーマンス最適化
- [ ] README整備、デモ動画
- [ ] Vercelデプロイ(またはローカル限定運用なら割愛)

---

## 想定スケジュール

| 期間 | フルタイム想定 | 副業/休日想定 |
|---|---|---|
| M0-M3(MVP動作) | 1-1.5週間 | 3-4週間 |
| M4-M5(永続化+成果物) | 0.5-1週間 | 1.5-2週間 |
| M6-M7(全モード+仕上げ) | 1週間 | 2-3週間 |
| **合計** | **3-4週間** | **約2か月** |

Claude Code の支援を受ければかなり加速します。1機能あたり数時間で動くことも珍しくない。

---

## 開発時の注意

### コスト管理

- Claude Code の長時間セッションはトークン消費が大きい。**`/clear`** でこまめに文脈リセット
- 議論エンジンのテストは**モックLLM**で行う。本番APIを叩き続けない
- 開発中の議論実行は**`claude-haiku-4-5`** などの軽量モデルに切り替えると安価

### よくある詰まり所と対策

| 詰まり | 対策 |
|---|---|
| SSEがブラウザで切れる | nginxのbuffering off、`X-Accel-Buffering: no` ヘッダ追加 |
| Zustand storeが SSR で壊れる | `"use client"` 確認、selectorで安定化 |
| Drizzle のマイグレーションが衝突 | `drizzle-kit push` ではなく `generate` → `migrate` を運用 |
| Anthropic SDK が遅い | ストリーミング前提で組む、Promise.allで並列召喚 |
| TSが厳しすぎて進まない | strict のまま、`unknown` + 型ガードで段階的に解決 |

### Claude Codeで失敗しがちなパターン

- **大きすぎる指示**: 「アプリ全部作って」はNG。M0→M1と順に
- **プランなしの実装**: 複雑な機能はプランモードを必ず使う
- **テストなしの実装報告**: 「実装完了」を信用せず、動作確認を要求する
- **コミットなしの長時間作業**: 動いたら即コミット、戻せる地点を確保

---

## プロトタイプとの関係

| 項目 | プロトタイプ | 本アプリ |
|---|---|---|
| 議論プロトコル | `CLAUDE.md`(自然言語) | `src/lib/deliberation/`(コード) |
| 人格定義 | `.claude/agents/*.md` | `src/lib/personas/*.ts` |
| 永続化 | ファイル | DB |
| UI | ターミナル | Web |
| 並列実行 | tmux | Promise.all |
| 状態管理 | Claude Code内部 | Zustand + DB |

プロトタイプは**「動く仕様書」**として残し続けることを推奨。新機能はまず
プロトタイプで議論プロトコル化 → 動作確認 → コードへ落とし込む、の流れが安全。

---

## 次にやること

1. このプロジェクトディレクトリで `git init`
2. `npx create-next-app@latest .` を実行(またはClaude Codeに任せる)
3. Anthropic APIキーを `.env.local` に設定
4. Claude Code を起動し、M0 のプロンプトを投げる
5. 動いたらコミット、M1へ進む

各マイルストーン完了時に、本ドキュメントの該当チェックボックスを更新すること。
