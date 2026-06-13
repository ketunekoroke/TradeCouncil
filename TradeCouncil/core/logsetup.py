"""中央集権的なロギング設定(ADR-0006)。

plain(従来の人間可読)/ json(CloudWatch Logs 取り込み用の構造化)を切り替える。
アプリは stdout に出し、CloudWatch Agent / journald が集約する(12-factor、疎結合)。
既定は plain で完全後方互換。AWS では config の runtime.log_format: json にする。
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

_PLAIN_FORMAT = "%(asctime)s %(name)s %(levelname)s %(message)s"


class JsonFormatter(logging.Formatter):
    """1行1 JSON のフォーマッタ(構造化ログ)。標準ライブラリのみ。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(fmt: str | None = None, level: str | None = None) -> None:
    """root logger を設定する。

    引数が None のときは config(runtime.log_format / log_level)から解決する。
    stdout へ出力する単一ハンドラを設定し、再呼び出ししてもハンドラを重複させない(冪等)。
    """
    if fmt is None or level is None:
        from core.config import get_config

        runtime = get_config().runtime
        fmt = fmt or runtime.log_format
        level = level or runtime.log_level

    root = logging.getLogger()
    # 既存の TradeCouncil ハンドラを取り除いてから1本だけ張り直す(冪等)
    for handler in [h for h in root.handlers if getattr(h, "_tradecouncil", False)]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler._tradecouncil = True  # type: ignore[attr-defined]
    handler.setFormatter(JsonFormatter() if fmt == "json" else logging.Formatter(_PLAIN_FORMAT))
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
