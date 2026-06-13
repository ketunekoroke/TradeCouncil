#!/usr/bin/env python3
"""ask_openai.py — MAGI人格を OpenAI(ChatGPT)で動かすための薄いブリッジ。

人格定義ファイル(.claude/agents/<name>.md)の本文をシステムプロンプト(instructions)として
OpenAI **Responses API** に渡し、標準入力で受け取ったラウンド入力をユーザー入力として送り、
返ってきたテキストを標準出力に出す。画像・PDF・Office ファイルもネイティブ/準ネイティブに扱える。

provider: openai を指定した人格を、ファシリテーター(Claude Code メインセッション)が
召喚する代わりにこのスクリプトで動かす想定。CLAUDE.md「人格ごとのLLMバックエンド選択」を参照。

ファイルの扱い:
  画像(.jpg/.png/.gif/.webp) … Files API へアップロード(または base64)し input_image として渡す(ネイティブ vision)
  PDF(.pdf)                  … Files API へアップロード(または base64)し input_file として渡す(ネイティブ)
  Office(.docx/.xlsx/.pptx)  … OpenAI はネイティブ非対応のため、ローカルでテキスト抽出して注入
  その他テキスト(.txt/.md/.csv/.json) … そのままテキストとして注入

共通処理(キー解決・フロントマター除去・Office抽出・HTTP など)は bridge_common.py を参照。
環境変数(解決順: 環境変数 → ルートの .env → .claude/settings.local.json の env):
  OPENAI_API_KEY   必須。OpenAI の API キー。
  OPENAI_BASE_URL  任意。既定 https://api.openai.com/v1 (Azure/プロキシ用に上書き可)。
  BRIDGE_HTTP_MAX_RETRIES  任意。一過性エラー(429/5xx・接続タイムアウト)の最大再試行回数(既定 4)。
  BRIDGE_HTTP_TIMEOUT      任意。各 HTTP リクエストのタイムアウト秒(既定 180)。
  BRIDGE_GEN_MAX_RETRIES   任意。空応答・拒否応答時に同じ要求を再試行する回数(既定 1)。
  BRIDGE_OPENAI_FALLBACK_MODEL  任意。primary が過負荷/不在(429/5xx/404)のとき切り替える代替モデル(--fallback-model でも可)。
  (旧 MAGI_* も後方互換で読む — ADR-0011)

使い方:
  # 1) 画像/PDF を一度アップロードして file_id を得る(多ラウンドで使い回す場合)
  python scripts/ask_openai.py upload media/input/house.jpg        # -> file-xxxx

  # 2) ラウンド実行(file_id 参照 + その場 --file + stdin のラウンド入力)
  echo "<ラウンド入力>" | python scripts/ask_openai.py \
      --system-file .claude/agents/melchior.md --model gpt-4o \
      --file-id file-xxxx --file docs/spec.pdf --file report.xlsx
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bridge_common as bc  # noqa: E402

PROVIDER = "OpenAI API"


def _require_key():
    api_key = bc.get_setting("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit(
            "error: OPENAI_API_KEY が未設定です。ルートの .env(推奨)か環境変数、"
            "または .claude/settings.local.json の env に実キーを設定してください"
        )
    return api_key


def _base_url():
    return (bc.get_setting("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")


# --------------------------------------------------------------------------- #
# Files API
# --------------------------------------------------------------------------- #
def upload_file(path, purpose=None):
    """画像/PDF を Files API にアップロードし file_id を返す。"""
    kind = bc.classify(path)
    if kind == "office":
        raise SystemExit(
            f"error: Office ファイルは OpenAI がネイティブ処理できないためアップロード"
            "非対応です。実行時に --file で渡すとローカル抽出して注入します"
        )
    if purpose is None:
        purpose = "vision" if kind == "image" else "user_data"
    with open(path, "rb") as f:
        file_bytes = f.read()
    body, content_type = bc.encode_multipart(
        {"purpose": purpose}, "file", os.path.basename(path), file_bytes, bc.guess_mime(path)
    )
    headers = {"Authorization": f"Bearer {_require_key()}", "Content-Type": content_type}
    res = bc.http_json("POST", f"{_base_url()}/files", headers, body, PROVIDER)
    fid = res.get("id")
    if not fid:
        raise SystemExit(f"error: アップロード応答に id がありません: {json.dumps(res)}")
    return fid


def file_meta(file_id):
    headers = {"Authorization": f"Bearer {_require_key()}"}
    return bc.http_json("GET", f"{_base_url()}/files/{file_id}", headers, None, PROVIDER)


# --------------------------------------------------------------------------- #
# 入力の組み立て(Responses API の content 配列)
# --------------------------------------------------------------------------- #
def build_content_parts(user_text, files, file_ids):
    parts = []
    if user_text and user_text.strip():
        parts.append({"type": "input_text", "text": user_text})

    for fid in file_ids:
        meta = file_meta(fid)
        fname = (meta.get("filename") or "").lower()
        is_image = meta.get("purpose") == "vision" or os.path.splitext(fname)[1] in bc.IMAGE_EXTS
        parts.append(
            {"type": "input_image", "file_id": fid}
            if is_image
            else {"type": "input_file", "file_id": fid}
        )

    for path in files:
        kind = bc.classify(path)
        if kind == "image":
            url, _ = bc.data_url(path)
            parts.append({"type": "input_image", "image_url": url})
        elif kind == "pdf":
            url, _ = bc.data_url(path)
            parts.append(
                {"type": "input_file", "filename": os.path.basename(path), "file_data": url}
            )
        elif kind == "office":
            ext = os.path.splitext(path)[1].lower()
            parts.append({"type": "input_text", "text": bc.extract_office(path, ext)})
        elif kind == "text":
            parts.append({"type": "input_text", "text": bc.read_text_file(path)})
        else:
            raise SystemExit(f"error: 未対応のファイル形式です: {path}")

    if not parts:
        raise SystemExit("error: 入力が空です(stdin/--input か --file/--file-id を渡してください)")
    return parts


# --------------------------------------------------------------------------- #
# Responses API 呼び出し
# --------------------------------------------------------------------------- #
def call_responses(model, instructions, content_parts, temperature, history=None):
    # 履歴(過去ラウンド)を先に積み、最後に今回のユーザー入力(ファイル含む parts)を置く
    input_items = [{"role": m["role"], "content": m["text"]} for m in (history or [])]
    input_items.append({"role": "user", "content": content_parts})
    payload = {
        "model": model,
        "instructions": instructions,
        "input": input_items,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {_require_key()}"}
    body = bc.http_json(
        "POST", f"{_base_url()}/responses", headers, json.dumps(payload).encode("utf-8"), PROVIDER
    )
    return extract_output_text(body)


def extract_output_text(body):
    if isinstance(body.get("output_text"), str) and body["output_text"].strip():
        return body["output_text"]
    texts, refusals = [], []
    for item in body.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                ptype = part.get("type")
                if ptype == "output_text" and part.get("text"):
                    texts.append(part["text"])
                elif ptype == "refusal" and part.get("refusal"):
                    refusals.append(part["refusal"])
    if texts:
        return "\n".join(texts)
    # 空応答・拒否応答は run_with_retry が拾って同じ要求を再試行する
    if refusals:
        raise bc.EmptyOrRefusalResponse("refusal", " / ".join(refusals))
    if (body.get("incomplete_details") or {}).get("reason") == "content_filter":
        raise bc.EmptyOrRefusalResponse("refusal", "content_filter")
    raise bc.EmptyOrRefusalResponse("empty", json.dumps(body, ensure_ascii=False)[:300])


# --------------------------------------------------------------------------- #
# エントリポイント
# --------------------------------------------------------------------------- #
def cmd_upload(argv):
    p = argparse.ArgumentParser(
        prog="ask_openai.py upload", description="画像/PDF を Files API にアップロード"
    )
    p.add_argument("path", help="アップロードする画像 or PDF のパス")
    p.add_argument("--purpose", default=None, help="Files API の purpose(既定: 画像=vision / それ以外=user_data)")
    a = p.parse_args(argv)
    print(upload_file(a.path, a.purpose))


def cmd_run(argv):
    p = argparse.ArgumentParser(description="MAGI人格を OpenAI(Responses API)で動かすブリッジ")
    p.add_argument("--model", default="gpt-4o", help="OpenAI モデル名(既定: gpt-4o)")
    p.add_argument("--system", help="システムプロンプト文字列(直接指定)")
    p.add_argument("--system-file", help="人格定義ファイルのパス(フロントマターは自動除去)")
    p.add_argument("--input", help="ユーザー入力ファイル(省略時は stdin)")
    p.add_argument("--file", action="append", default=[], help="添付ファイル(画像/PDF/Office/テキスト)。複数可")
    p.add_argument("--file-id", action="append", default=[], help="アップロード済みファイルの file_id。複数可")
    p.add_argument("--temperature", type=float, default=None, help="温度(省略時はモデル既定値)")
    p.add_argument(
        "--history",
        help='会話履歴 JSON のパス([{"role":"user|assistant","text":...}, ...])。'
        "ステートレス人格に過去ラウンドの文脈を多ターンで渡す",
    )
    p.add_argument(
        "--fallback-model",
        help="primary が過負荷/不在(429/5xx/404)のとき切り替える代替モデル"
        "(env BRIDGE_OPENAI_FALLBACK_MODEL でも可)",
    )
    a = p.parse_args(argv)

    instructions = bc.load_system_prompt(a.system, a.system_file)
    user_text = bc.load_user_text(a.input)
    parts = build_content_parts(user_text, a.file, a.file_id)
    history = bc.load_history(a.history)
    fallback = a.fallback_model or bc.setting("BRIDGE_OPENAI_FALLBACK_MODEL")
    out = bc.run_with_fallback(
        lambda model: bc.run_with_retry(
            lambda: call_responses(model, instructions, parts, a.temperature, history), PROVIDER
        ),
        a.model,
        fallback,
        PROVIDER,
    )
    sys.stdout.write(out)
    if not out.endswith("\n"):
        sys.stdout.write("\n")


def main():
    argv = sys.argv[1:]
    try:
        if argv and argv[0] == "upload":
            cmd_upload(argv[1:])
        else:
            cmd_run(argv)
    except bc.ProviderHTTPError as e:
        raise SystemExit(bc.fmt_http_error(PROVIDER, e))


if __name__ == "__main__":
    main()
