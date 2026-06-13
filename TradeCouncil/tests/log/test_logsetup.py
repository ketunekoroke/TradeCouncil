"""中央集権的な構造化ログ(ADR-0006)のテスト。

JSON フォーマット(CloudWatch Logs 取り込み用)/ plain フォーマット(従来)を
config から切り替える。既定 plain で完全後方互換。
"""

from __future__ import annotations

import json
import logging

import pytest
from pydantic import ValidationError

from core.config import RuntimeConfig
from core.logsetup import JsonFormatter, configure_logging

LOGGER = "tradecouncil.test"


def _record(msg: str = "hello", *, exc: bool = False) -> logging.LogRecord:
    exc_info = None
    if exc:
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            exc_info = sys.exc_info()
    return logging.LogRecord(
        name=LOGGER, level=logging.INFO, pathname=__file__, lineno=1,
        msg=msg, args=(), exc_info=exc_info,
    )


def test_json_formatter_emits_valid_json() -> None:
    out = JsonFormatter().format(_record("構造化"))
    obj = json.loads(out)
    assert obj["level"] == "INFO"
    assert obj["logger"] == LOGGER
    assert obj["message"] == "構造化"
    assert "ts" in obj


def test_json_formatter_includes_exception() -> None:
    out = JsonFormatter().format(_record(exc=True))
    obj = json.loads(out)
    assert "exc" in obj
    assert "ValueError" in obj["exc"]


def test_configure_logging_json(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    configure_logging(fmt="json", level="INFO")
    logging.getLogger(LOGGER).info("from-json")
    line = capsys.readouterr().out.strip().splitlines()[-1]
    obj = json.loads(line)
    assert obj["message"] == "from-json"


def test_configure_logging_plain(capsys: pytest.CaptureFixture) -> None:
    configure_logging(fmt="plain", level="INFO")
    logging.getLogger(LOGGER).info("from-plain")
    out = capsys.readouterr().out.strip()
    assert "from-plain" in out
    assert LOGGER in out
    with pytest.raises(json.JSONDecodeError):
        json.loads(out.splitlines()[-1])


def test_configure_logging_is_idempotent() -> None:
    configure_logging(fmt="json")
    configure_logging(fmt="json")
    configure_logging(fmt="plain")
    handlers = logging.getLogger().handlers
    assert len([h for h in handlers if getattr(h, "_tradecouncil", False)]) == 1


def test_level_filters_below(capsys: pytest.CaptureFixture) -> None:
    configure_logging(fmt="plain", level="INFO")
    logging.getLogger(LOGGER).debug("should-not-appear")
    assert "should-not-appear" not in capsys.readouterr().out


def test_configure_logging_reads_config(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    import core.config as config_mod

    cfg = config_mod.load_config()
    cfg.runtime.log_format = "json"  # type: ignore[assignment]
    cfg.runtime.log_level = "INFO"
    monkeypatch.setattr(config_mod, "get_config", lambda: cfg)

    configure_logging()  # 引数なし → config から解決
    logging.getLogger(LOGGER).info("from-config")
    line = capsys.readouterr().out.strip().splitlines()[-1]
    assert json.loads(line)["message"] == "from-config"


def test_runtime_config_rejects_invalid_log_format() -> None:
    with pytest.raises(ValidationError):
        RuntimeConfig(log_format="xml")  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _reset_root_logging() -> None:
    """各テスト後に root のハンドラを掃除(テスト間の汚染防止)。"""
    yield
    root = logging.getLogger()
    for h in [h for h in root.handlers if getattr(h, "_tradecouncil", False)]:
        root.removeHandler(h)
