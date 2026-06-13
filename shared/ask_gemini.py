#!/usr/bin/env python3
"""ask_gemini.py — MAGI人格を Google Gemini で動かすための薄いブリッジ。

人格定義ファイル(.claude/agents/<name>.md)の本文を system_instruction として
Gemini **generateContent** API に渡し、標準入力で受け取ったラウンド入力をユーザー入力として
送り、返ってきたテキストを標準出力に出す。画像・PDF・Office もネイティブ/準ネイティブに扱える。

provider: gemini を指定した人格を、ファシリテーター(Claude Code メインセッション)が
召喚する代わりにこのスクリプトで動かす想定。CLAUDE.md「人格ごとのLLMバックエンド選択」を参照。
ask_openai.py と CLI・挙動を対称に揃えてある。

ファイルの扱い:
  画像(.jpg/.png/.gif/.webp) … Files API へアップロード(または inline base64)し file_data/inline_data で渡す(ネイティブ)
  PDF(.pdf)                  … 同上(Gemini はPDFをネイティブに解釈)
  Office(.docx/.xlsx/.pptx)  … Gemini はネイティブ非対応のため、ローカルでテキスト抽出して注入
  その他テキスト(.txt/.md/.csv/.json) … そのままテキストとして注入

共通処理は bridge_common.py を参照。
環境変数(解決順: 環境変数 → ルートの .env → .claude/settings.local.json の env):
  GEMINI_API_KEY (または GOOGLE_API_KEY)  必須。
  GEMINI_BASE_URL  任意。既定 https://generativelanguage.googleapis.com/v1beta
  BRIDGE_HTTP_MAX_RETRIES  任意。一過性エラー(429/5xx・接続タイムアウト)の最大再試行回数(既定 4)。
  BRIDGE_HTTP_TIMEOUT      任意。各 HTTP リクエストのタイムアウト秒(既定 180)。
  BRIDGE_GEN_MAX_RETRIES   任意。空応答・拒否応答時に同じ要求を再試行する回数(既定 1)。
  BRIDGE_GEMINI_FALLBACK_MODEL  任意。primary が過負荷/不在(429/5xx/404)のとき切り替える代替モデル(--fallback-model でも可)。
  (旧 MAGI_* も後方互換で読む — ADR-0011)

使い方:
  # 1) 画像/PDF を一度アップロードして file 名(files/xxxx)を得る(多ラウンドで使い回す場合)
  python scripts/ask_gemini.py upload media/input/house.jpg     # -> files/xxxx

  # 2) ラウンド実行
  echo "<ラウンド入力>" | python scripts/ask_gemini.py \
      --system-file .claude/agents/melchior.md --model gemini-2.5-flash \
      --file-id files/xxxx --file docs/spec.pdf --file report.xlsx
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bridge_common as bc  # noqa: E402

PROVIDER = "Gemini API"
DEFAULT_MODEL = "gemini-2.5-flash"


def _require_key():
    api_key = bc.get_setting("GEMINI_API_KEY", "GOOGLE_API_KEY")
    if not api_key:
        raise SystemExit(
            "error: GEMINI_API_KEY が未設定です。ルートの .env(推奨)か環境変数"
            "(GEMINI_API_KEY か GOOGLE_API_KEY)、または .claude/settings.local.json の"
            " env に実キーを設定してください"
        )
    return api_key


def _base_url():
    return (
        bc.get_setting("GEMINI_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta"
    ).rstrip("/")


def _upload_files_url():
    """アップロードは /upload/<version>/files。base の /v1beta の前に /upload を挿入する。"""
    base = _base_url()
    if "/v1beta" in base:
        return base.replace("/v1beta", "/upload/v1beta") + "/files"
    return base + "/upload/files"


def _header_ci(headers, name):
    """ヘッダ辞書から大文字小文字を無視して値を取る。"""
    low = name.lower()
    for k, v in headers.items():
        if k.lower() == low:
            return v
    return None


# --------------------------------------------------------------------------- #
# Files API(resumable upload + メタ取得 + ACTIVE 待ち)
# --------------------------------------------------------------------------- #
def upload_file(path):
    """画像/PDF を Gemini Files API にアップロードし、file 名(files/xxxx)を返す。"""
    kind = bc.classify(path)
    if kind == "office":
        raise SystemExit(
            "error: Office ファイルは Gemini がネイティブ処理できないためアップロード"
            "非対応です。実行時に --file で渡すとローカル抽出して注入します"
        )
    with open(path, "rb") as f:
        file_bytes = f.read()
    mime = bc.guess_mime(path)
    key = _require_key()

    # 1) start: アップロードURLを得る
    start_headers = {
        "x-goog-api-key": key,
        "X-Goog-Upload-Protocol": "resumable",
        "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": str(len(file_bytes)),
        "X-Goog-Upload-Header-Content-Type": mime,
        "Content-Type": "application/json",
    }
    meta = json.dumps({"file": {"display_name": os.path.basename(path)}}).encode("utf-8")
    resp_headers, _ = bc.http_raw("POST", _upload_files_url(), start_headers, meta, PROVIDER)
    upload_url = _header_ci(resp_headers, "X-Goog-Upload-URL")
    if not upload_url:
        raise SystemExit("error: アップロードURL(X-Goog-Upload-URL)が取得できませんでした")

    # 2) upload + finalize: 実体を送る
    up_headers = {
        "x-goog-api-key": key,
        "X-Goog-Upload-Offset": "0",
        "X-Goog-Upload-Command": "upload, finalize",
    }
    _, body = bc.http_raw("POST", upload_url, up_headers, file_bytes, PROVIDER)
    info = json.loads(body.decode("utf-8")).get("file", {})
    name = info.get("name")
    if not name:
        raise SystemExit(f"error: アップロード応答に file 名がありません: {body[:200]!r}")
    _wait_active(name)
    return name


def file_meta(name):
    """files/xxxx のメタ(uri / mimeType / state)を取得。"""
    headers = {"x-goog-api-key": _require_key()}
    return bc.http_json("GET", f"{_base_url()}/{name}", headers, None, PROVIDER)


def _wait_active(name, tries=12, interval=1.5):
    """state が ACTIVE になるまで待つ(画像/PDFは通常すぐ。大きい/動画は処理に時間)。"""
    for _ in range(tries):
        meta = file_meta(name)
        state = meta.get("state")
        if state == "ACTIVE":
            return meta
        if state == "FAILED":
            raise SystemExit(f"error: ファイル処理に失敗しました: {name}")
        time.sleep(interval)
    return file_meta(name)


# --------------------------------------------------------------------------- #
# 入力の組み立て(generateContent の parts 配列)
# --------------------------------------------------------------------------- #
def build_parts(user_text, files, file_ids):
    parts = []
    if user_text and user_text.strip():
        parts.append({"text": user_text})

    for name in file_ids:
        meta = _wait_active(name)
        uri = meta.get("uri")
        mime = meta.get("mimeType") or "application/octet-stream"
        if not uri:
            raise SystemExit(f"error: file の uri を取得できませんでした: {name}")
        parts.append({"file_data": {"mime_type": mime, "file_uri": uri}})

    for path in files:
        kind = bc.classify(path)
        if kind in ("image", "pdf"):
            parts.append({"inline_data": {"mime_type": bc.guess_mime(path), "data": bc.file_b64(path)}})
        elif kind == "office":
            ext = os.path.splitext(path)[1].lower()
            parts.append({"text": bc.extract_office(path, ext)})
        elif kind == "text":
            parts.append({"text": bc.read_text_file(path)})
        else:
            raise SystemExit(f"error: 未対応のファイル形式です: {path}")

    if not parts:
        raise SystemExit("error: 入力が空です(stdin/--input か --file/--file-id を渡してください)")
    return parts


# --------------------------------------------------------------------------- #
# generateContent 呼び出し
# --------------------------------------------------------------------------- #
def call_generate(model, instructions, parts, temperature, history=None):
    # 履歴(過去ラウンド)を先に積む。Gemini のロールは user / model(assistant→model に写像)
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["text"]}]}
        for m in (history or [])
    ]
    contents.append({"role": "user", "parts": parts})
    payload = {
        "system_instruction": {"parts": [{"text": instructions}]},
        "contents": contents,
    }
    if temperature is not None:
        payload["generationConfig"] = {"temperature": temperature}
    headers = {"Content-Type": "application/json", "x-goog-api-key": _require_key()}
    url = f"{_base_url()}/models/{model}:generateContent"
    body = bc.http_json("POST", url, headers, json.dumps(payload).encode("utf-8"), PROVIDER)
    return extract_output_text(body)


def extract_output_text(body):
    candidates = body.get("candidates") or []
    if not candidates:
        reason = body.get("promptFeedback", {}).get("blockReason")
        if reason:
            # 入力ブロックは同じ入力では再現するため、再試行せず即エラー
            raise SystemExit(f"error: Gemini が入力をブロックしました(blockReason: {reason})")
        raise bc.EmptyOrRefusalResponse("empty", json.dumps(body, ensure_ascii=False)[:300])
    cand = candidates[0]
    texts = [
        p["text"] for p in cand.get("content", {}).get("parts", []) if isinstance(p.get("text"), str)
    ]
    joined = "".join(texts)
    if joined.strip():
        return joined
    # 空応答・拒否応答は run_with_retry が拾って同じ要求を再試行する
    finish = cand.get("finishReason")
    if finish == "SAFETY":
        raise bc.EmptyOrRefusalResponse("refusal", "finishReason: SAFETY")
    raise bc.EmptyOrRefusalResponse("empty", f"finishReason: {finish}")


# --------------------------------------------------------------------------- #
# エントリポイント
# --------------------------------------------------------------------------- #
def cmd_upload(argv):
    p = argparse.ArgumentParser(
        prog="ask_gemini.py upload", description="画像/PDF を Gemini Files API にアップロード"
    )
    p.add_argument("path", help="アップロードする画像 or PDF のパス")
    a = p.parse_args(argv)
    print(upload_file(a.path))


def cmd_run(argv):
    p = argparse.ArgumentParser(description="MAGI人格を Gemini(generateContent)で動かすブリッジ")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini モデル名(既定: {DEFAULT_MODEL})")
    p.add_argument("--system", help="システムプロンプト文字列(直接指定)")
    p.add_argument("--system-file", help="人格定義ファイルのパス(フロントマターは自動除去)")
    p.add_argument("--input", help="ユーザー入力ファイル(省略時は stdin)")
    p.add_argument("--file", action="append", default=[], help="添付ファイル(画像/PDF/Office/テキスト)。複数可")
    p.add_argument("--file-id", action="append", default=[], help="アップロード済みファイル名(files/xxxx)。複数可")
    p.add_argument("--temperature", type=float, default=None, help="温度(省略時はモデル既定値)")
    p.add_argument(
        "--history",
        help='会話履歴 JSON のパス([{"role":"user|assistant","text":...}, ...])。'
        "ステートレス人格に過去ラウンドの文脈を多ターンで渡す",
    )
    p.add_argument(
        "--fallback-model",
        help="primary が過負荷/不在(429/5xx/404)のとき切り替える代替モデル"
        "(env BRIDGE_GEMINI_FALLBACK_MODEL でも可)",
    )
    a = p.parse_args(argv)

    instructions = bc.load_system_prompt(a.system, a.system_file)
    user_text = bc.load_user_text(a.input)
    parts = build_parts(user_text, a.file, a.file_id)
    history = bc.load_history(a.history)
    fallback = a.fallback_model or bc.setting("BRIDGE_GEMINI_FALLBACK_MODEL")
    out = bc.run_with_fallback(
        lambda model: bc.run_with_retry(
            lambda: call_generate(model, instructions, parts, a.temperature, history), PROVIDER
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
