# MAGI App

エヴァンゲリオンのMAGIシステムに着想を得た、人格ベースの合議制AIエージェントのWebアプリ。

> Phase 0プロトタイプの本実装版。仕様の一次資料は `../prototype/DOCS.md`。

## ドキュメント

- **README.md**(本書) — プロジェクト概要
- **CLAUDE.md** — Claude Code向け開発ルール
- **DEVELOPMENT.md** — マイルストーン別開発ロードマップ

## 技術スタック

Next.js 15 (App Router) / TypeScript / shadcn/ui / Tailwind /
Anthropic SDK / Drizzle ORM / SQLite / SSE / Recharts

## 始め方

```bash
# 1. 開発開始(まだプロジェクト初期化していない場合)
npx create-next-app@latest . --typescript --tailwind --app --eslint

# 2. Anthropic API キーを設定
cp .env.example .env.local
# .env.local の ANTHROPIC_API_KEY を編集

# 3. Claude Code起動
claude

# 4. 最初の指示
# > CLAUDE.md と DEVELOPMENT.md を読んで、M0のタスクをプランモードで提案してくれ
```

詳細は `DEVELOPMENT.md` 参照。

## ステータス

- [ ] M0: プロジェクト初期化
- [ ] M1: 議論エンジン最小実装
- [ ] M2: API層とストリーミング
- [ ] M3: フロントエンドUI
- [ ] M4: 永続化
- [ ] M5: 成果物生成
- [ ] M6: Standard/Fullモード
- [ ] M7: 仕上げとデプロイ

## プロトタイプとの関係

機能仕様の決定はプロトタイプ(`../prototype/`)で行い、ここはその実装。
仕様変更は両方を同期して更新する。
