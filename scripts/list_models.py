#!/usr/bin/env python3
"""list_models.py — 各プロバイダで現在使えるモデル名を一覧表示する補助ツール。

人格の frontmatter(backend / model)に何を書けるかを確認するための道具。
API キーは bridge_common 経由で解決(環境変数 → ルートの .env → .claude/settings.local.json の env)。
モデル ID は随時増減するため、これで最新を取得して DOCS.md のスナップショットを更新する。

使い方:
  python scripts/list_models.py                # openai と gemini を議論向きに絞って表示
  python scripts/list_models.py openai         # OpenAI のみ
  python scripts/list_models.py gemini         # Gemini のみ
  python scripts/list_models.py --all          # 絞り込みせず全件(非テキスト系も含む)
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bridge_common as bc  # noqa: E402

# 議論(テキスト生成)に使わない系統を除外するためのキーワード
OPENAI_EXCLUDE = (
    "audio", "realtime", "tts", "transcribe", "search", "instruct",
    "embedding", "moderation", "image", "dall", "codex",
)
GEMINI_EXCLUDE = (
    "image", "tts", "robotics", "computer-use", "embedding", "aqa", "learnlm",
)


def list_openai(show_all):
    key = bc.get_setting("OPENAI_API_KEY")
    if not key:
        print("# OpenAI: OPENAI_API_KEY 未設定のためスキップ")
        return
    body = bc.http_json(
        "GET", "https://api.openai.com/v1/models",
        {"Authorization": f"Bearer {key}"}, None, "OpenAI",
    )
    ids = sorted(m["id"] for m in body.get("data", []))
    if not show_all:
        ids = [
            i for i in ids
            if i.startswith(("gpt-", "o1", "o3", "o4", "chatgpt"))
            and not any(x in i for x in OPENAI_EXCLUDE)
        ]
    print(f"# OpenAI (backend: openai) — {len(ids)}件")
    for i in ids:
        print(i)


def list_gemini(show_all):
    key = bc.get_setting("GEMINI_API_KEY", "GOOGLE_API_KEY")
    if not key:
        print("# Gemini: GEMINI_API_KEY 未設定のためスキップ")
        return
    body = bc.http_json(
        "GET", "https://generativelanguage.googleapis.com/v1beta/models",
        {"x-goog-api-key": key}, None, "Gemini",
    )
    names = []
    for m in body.get("models", []):
        if "generateContent" not in m.get("supportedGenerationMethods", []):
            continue
        name = m["name"].replace("models/", "")
        if not show_all:
            if not name.startswith("gemini"):
                continue
            if any(x in name for x in GEMINI_EXCLUDE):
                continue
        names.append(name)
    names.sort()
    print(f"# Gemini (backend: gemini) — {len(names)}件")
    for n in names:
        print(n)


def main():
    p = argparse.ArgumentParser(description="使えるモデル名を一覧表示")
    p.add_argument(
        "provider", nargs="?", default="all", choices=["all", "openai", "gemini"],
        help="表示するプロバイダ(既定: all)",
    )
    p.add_argument("--all", action="store_true", help="絞り込みせず全件表示(非テキスト系も含む)")
    a = p.parse_args()

    # Claude は API ではなく Claude Code 本体が扱うため、別名を案内
    if a.provider == "all":
        print("# Claude (backend: claude) — Claude Code の別名")
        print("opus")
        print("sonnet")
        print("haiku")
        print("inherit")
        print()

    if a.provider in ("all", "openai"):
        list_openai(a.all)
        if a.provider == "all":
            print()
    if a.provider in ("all", "gemini"):
        list_gemini(a.all)


if __name__ == "__main__":
    main()
