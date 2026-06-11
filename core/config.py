"""システム設定ローダ。

config/system.yaml(技術設定)と .env(シークレット)を読み込む。
運用ポリシー(決裁事項)はここでは扱わない — core/governance/ のレジストリが担う。
パス解決はすべて本モジュールに集約する(Windows 対応のため pathlib・ルート相対)。
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_VAR_PREFIX = "var"


def _var_base() -> Path | None:
    """環境変数 TC_VAR_DIR を解決する。未設定・空なら None(従来挙動)。

    絶対パスはそのまま、相対パスは PROJECT_ROOT 相対として解決する。
    DB エンジン等はプロセス内でキャッシュされるため、TC_VAR_DIR は
    プロセス起動前に確定させること(ADR-0004、docs/05 §3.3)。
    """
    raw = (os.environ.get("TC_VAR_DIR") or "").strip()
    if not raw:
        return None
    p = Path(raw)
    return p if p.is_absolute() else PROJECT_ROOT / p


def resolve_runtime_path(rel: str) -> Path:
    """system.yaml の実行時パスを解決する。

    TC_VAR_DIR 設定時のみ `var/` 接頭辞を読み替える(run/・logs/ のサブ構造は維持)。
    var/ 配下でないパスは常に PROJECT_ROOT 相対のまま。
    """
    normalized = rel.replace("\\", "/").strip("/")
    base = _var_base()
    if base is not None and (
        normalized == _VAR_PREFIX or normalized.startswith(_VAR_PREFIX + "/")
    ):
        suffix = normalized[len(_VAR_PREFIX) + 1 :]
        return base / suffix if suffix else base
    return PROJECT_ROOT / rel


class DbConfig(BaseModel):
    path: str = "var/tradecouncil.db"


class RuntimeConfig(BaseModel):
    kill_flag: str = "var/run/KILL"
    log_dir: str = "var/logs"
    heartbeat_interval_sec: int = 30
    watchdog_stale_sec: int = 120


class PaperConfig(BaseModel):
    fee_bps: float = 10.0
    slippage_bps: float = 5.0
    initial_balance_jpy: float = 1_000_000.0


class RandomWalkConfig(BaseModel):
    start_price: float = 10_000_000.0
    drift_bps_per_bar: float = 0.0
    vol_bps_per_bar: float = 20.0
    bar_interval_sec: int = 60
    seed: int | None = None


class FeedConfig(BaseModel):
    type: str = "random_walk"
    random_walk: RandomWalkConfig = Field(default_factory=RandomWalkConfig)


_CHANNEL_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_VALID_SEVERITIES = frozenset({"info", "warning", "critical"})


class NotifyConfig(BaseModel):
    backend: Literal["discord", "teams"] = "discord"
    min_severity: str = "info"
    # severity → チャネル名(例 {"warning": "alerts"})。URL は環境変数
    # <TEAMS_WORKFLOW_URL|DISCORD_WEBHOOK_URL>_<チャネル名大文字> から解決する(ADR-0003)
    routing: dict[str, str] = Field(default_factory=dict)

    @field_validator("routing")
    @classmethod
    def _validate_routing(cls, v: dict[str, str]) -> dict[str, str]:
        for sev, ch in v.items():
            if sev not in _VALID_SEVERITIES:
                raise ValueError(f"routing のキーが不正: {sev!r}(info/warning/critical のみ)")
            if not _CHANNEL_NAME_RE.match(ch or ""):
                raise ValueError(f"チャネル名が不正: {ch!r}(小文字英数字と _、先頭は英字)")
        return v


class SystemConfig(BaseModel):
    db: DbConfig = Field(default_factory=DbConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    paper: PaperConfig = Field(default_factory=PaperConfig)
    feed: FeedConfig = Field(default_factory=FeedConfig)
    notify: NotifyConfig = Field(default_factory=NotifyConfig)

    # --- パス解決(すべてルート相対) ---

    @property
    def root(self) -> Path:
        return PROJECT_ROOT

    @property
    def db_path(self) -> Path:
        return resolve_runtime_path(self.db.path)

    @property
    def kill_flag_path(self) -> Path:
        return resolve_runtime_path(self.runtime.kill_flag)

    @property
    def log_dir_path(self) -> Path:
        return resolve_runtime_path(self.runtime.log_dir)

    @property
    def policies_dir(self) -> Path:
        return PROJECT_ROOT / "config" / "policies"

    @property
    def generated_dir(self) -> Path:
        return PROJECT_ROOT / "config" / "generated"

    @property
    def instruments_dir(self) -> Path:
        return PROJECT_ROOT / "config" / "instruments"

    @property
    def bots_dir(self) -> Path:
        return PROJECT_ROOT / "config" / "bots"

    def ensure_runtime_dirs(self) -> None:
        """var/ 配下の実行時ディレクトリを作成する。"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.kill_flag_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_dir_path.mkdir(parents=True, exist_ok=True)


def load_config(path: Path | None = None) -> SystemConfig:
    """system.yaml と .env を読み込む。path 指定はテスト用。"""
    load_dotenv(PROJECT_ROOT / ".env")
    yaml_path = path or (PROJECT_ROOT / "config" / "system.yaml")
    if yaml_path.exists():
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    else:
        raw = {}
    return SystemConfig.model_validate(raw)


@lru_cache(maxsize=1)
def get_config() -> SystemConfig:
    return load_config()


def discord_webhook_url() -> str | None:
    return os.environ.get("DISCORD_WEBHOOK_URL") or None


def teams_workflow_url() -> str | None:
    """Power Automate「Webhook 要求の受信時」フローの URL(SAS 署名 sig= を含む秘密)。"""
    return os.environ.get("TEAMS_WORKFLOW_URL") or None


def _scan_channel_urls(prefix: str) -> dict[str, str]:
    """`<prefix>_<CHANNEL>` 形式の環境変数を走査し {チャネル名(小文字): URL} を返す。"""
    head = prefix + "_"
    return {
        key[len(head):].lower(): value
        for key, value in os.environ.items()
        if key.startswith(head) and value
    }


def teams_channel_urls() -> dict[str, str]:
    """チャネル別 Workflow URL(TEAMS_WORKFLOW_URL_OPS 等)。"""
    return _scan_channel_urls("TEAMS_WORKFLOW_URL")


def discord_channel_urls() -> dict[str, str]:
    """チャネル別 Discord Webhook URL(DISCORD_WEBHOOK_URL_ALERTS 等)。"""
    return _scan_channel_urls("DISCORD_WEBHOOK_URL")
