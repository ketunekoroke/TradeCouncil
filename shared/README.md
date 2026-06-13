# shared — 共通ツール層(LLMブリッジ・SharePoint・office変換・git フック)

Magi / TradeCouncil の双方が使う共通基盤。**path 起動**(`python shared/<tool>.py`)か
`from shared import ...` で利用する。重い依存は持たない(office libは関数内 lazy import)。
要件 [REQUIREMENTS.md](REQUIREMENTS.md) / 機能 [FEATURES.md](FEATURES.md) / 検証 [TESTCASES.md](TESTCASES.md)。

## ツール

| ファイル | 役割 |
|---|---|
| `bridge_common.py` | プロバイダ非依存の共有処理(キー3段解決・frontmatter 除去・Office 抽出・HTTP リトライ・履歴・UTF-8) |
| `ask_openai.py` / `ask_gemini.py` | LLM ブリッジ(人格をシステムプロンプトに、1ラウンド往復) |
| `list_models.py` | 利用可能モデル一覧 |
| `sharepoint.py` | workspace 双方向 sync(ADR-0009)+ docs 一方向ミラー(ADR-0010)。`--project <dir>` で基点指定 |
| `extract_office.py` / `md_to_docx.py` / `docx_replace.py` | Office ↔ Markdown 変換・docx 原本コピー編集 |
| `hooks/` | git ライフサイクルフック(pre-commit 検査・post-commit/pre-push の docs ミラー)+ `install_hooks` |

## LLMバックエンドの呼び出し

```bash
echo "<入力>" | python shared/ask_openai.py --system-file <人格md> --model gpt-4o
```

- `--system-file` のフロントマターは自動除去され本文だけがシステムプロンプトになる
- キー解決順: 環境変数 → リポジトリルート共有 `.env` → `.claude/settings.local.json` の env(placeholder/空は未設定扱い)
- リトライ: 一過性 HTTP(429/5xx)は指数バックオフ(`MAGI_HTTP_MAX_RETRIES` 既定4 / `MAGI_HTTP_TIMEOUT` 既定180秒)。
  空/拒否応答は `MAGI_GEN_MAX_RETRIES`(既定1)再試行
- フォールバック: `--fallback-model` / `MAGI_OPENAI_FALLBACK_MODEL` / `MAGI_GEMINI_FALLBACK_MODEL` で1回切替(発火したら成果物に実モデルを明記)
- ファイル: `--file <path>`(画像/PDF=ネイティブ、Office=テキスト抽出、txt/md/csv/json=本文注入)。多ラウンドは `upload` → `--file-id`
- 履歴: `--history <JSONファイルパス>`(`[{"role":"user"|"assistant","text":"…"}]`。**インライン JSON 不可** — 一時ファイルに書く)

## SharePoint(per-project — ADR-0010/0011)

```bash
python shared/sharepoint.py sync   --project <ProjectDir>   # workspace 双方向同期
python shared/sharepoint.py mirror --project <ProjectDir>   # docs/管理表を git main から <Project>/Docs/ へ一方向ミラー
```

config・workspace・var・ミラー状態は `--project`(既定 cwd)のディレクトリを基点に解決する。
git/差分の基点は常にリポジトリルート。`git_mirror.paths` はリポジトリ相対(例 `TradeCouncil/docs`)。

## git フック

`tc hooks install`(または `python -c "from shared.hooks import install_hooks; install_hooks('.')"`)で
`.git/hooks` に3種を導入する。post-commit / pre-push は全プロジェクトを走査して各 docs を
per-project でミラーする(fail-open)。
