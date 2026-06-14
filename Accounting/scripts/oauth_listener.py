"""ローカル loopback の OAuth リダイレクト受信(accounting のみ)。stdlib http.server。

認可後にブラウザが `redirect_uri`(`http://localhost:8765/callback?code=..&state=..`)へ戻る。
**単回だけ**受信して `code`/`state` を取り出し、サーバを閉じる。会計のみ対象
(expense は redirect が HTTPS 限定で loopback に届かない → 手動運用)。

セキュリティ:
- `127.0.0.1` のみ bind(単回・短時間)。
- `state` を `hmac.compare_digest` で検証(CSRF)。
- リクエストログを無効化(`log_message` no-op)し、`code` を stderr に残さない。
- `code` はメモリ上だけで扱い、呼び出し側が即 token 交換する。
"""

from __future__ import annotations

import hmac
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

from core.oauth import CallbackResult, parse_callback

_BIND_HOST = "127.0.0.1"  # loopback 固定(config の "localhost" の IPv6/DNS 揺れを避ける)

_SUCCESS_HTML = (
    "<!doctype html><meta charset=utf-8><title>認可完了</title>"
    "<body style='font-family:sans-serif;padding:2rem'>"
    "<h2>✅ 認可コードを受け取りました</h2>"
    "<p>このタブを閉じて、ターミナルに戻ってください。</p></body>"
).encode()

_ERROR_HTML = (
    "<!doctype html><meta charset=utf-8><title>認可エラー</title>"
    "<body style='font-family:sans-serif;padding:2rem'>"
    "<h2>⚠️ 認可に失敗しました</h2>"
    "<p>ターミナルの表示を確認してください。</p></body>"
).encode()


class ListenerUnavailable(RuntimeError):
    """loopback の bind に失敗(ポート使用中・権限など)。手動フォールバックへ。"""


def _split_redirect(redirect_uri: str) -> tuple[str, int, str]:
    """`redirect_uri` から (host, port, path) を取り出す。純粋(テスト可能)。"""
    parts = urllib.parse.urlsplit(redirect_uri)
    host = parts.hostname or _BIND_HOST
    port = parts.port or (443 if parts.scheme == "https" else 80)
    path = parts.path or "/"
    return host, port, path


def is_loopback_redirect(redirect_uri: str | None) -> bool:
    """loopback リスナで受けられる redirect か(http かつ localhost/127.0.0.1)。"""
    if not redirect_uri:
        return False
    parts = urllib.parse.urlsplit(redirect_uri)
    return parts.scheme == "http" and (parts.hostname or "") in ("127.0.0.1", "localhost", "::1")


def capture_code(
    redirect_uri: str,
    expected_state: str,
    *,
    timeout: int = 180,
    on_ready=None,
) -> CallbackResult:
    """loopback で単回コールバックを受信し `CallbackResult` を返す。

    `on_ready` はサーバが listen 開始した直後に呼ばれる(ここでブラウザを開くと取りこぼさない)。
    bind 失敗は `ListenerUnavailable`、タイムアウトや state 不一致は `error` 付き結果で返す。
    """
    _host, port, expected_path = _split_redirect(redirect_uri)
    captured: dict[str, CallbackResult | None] = {"result": None}
    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (http.server API)
            if urllib.parse.urlsplit(self.path).path != expected_path:
                self.send_response(404)
                self.end_headers()
                return  # favicon 等は無視(done を立てない)
            cb = parse_callback(self.path)
            state_ok = bool(
                cb.state and expected_state and hmac.compare_digest(cb.state, expected_state)
            )
            if cb.error:
                self._respond(400, _ERROR_HTML)
                captured["result"] = cb
            elif not cb.code:
                self._respond(400, _ERROR_HTML)
                captured["result"] = CallbackResult(
                    error="no_code", error_description="code がありません"
                )
            elif not state_ok:
                self._respond(400, _ERROR_HTML)
                captured["result"] = CallbackResult(
                    error="state_mismatch", error_description="state が一致しません(CSRF の疑い)"
                )
            else:
                self._respond(200, _SUCCESS_HTML)
                captured["result"] = cb
            done.set()

        def _respond(self, status: int, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args) -> None:  # noqa: N802
            pass  # code を含む URL を stderr に出さない

    try:
        server = HTTPServer((_BIND_HOST, port), Handler)
    except OSError as exc:
        raise ListenerUnavailable(f"{_BIND_HOST}:{port} を bind できません: {exc}") from exc

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        if on_ready is not None:
            on_ready()  # listen 開始後にブラウザを開く
        if not done.wait(timeout=timeout):
            return CallbackResult(
                error="timeout",
                error_description=f"{timeout}s 以内にコールバックがありませんでした",
            )
        return captured["result"] or CallbackResult(error="unknown")
    finally:
        server.shutdown()
        server.server_close()
