"""システム設定ローダ。

config/system.yaml(技術設定)と .env(シークレット)を読み込む。
運用ポリシー(決裁事項)はここでは扱わない — core/governance/ のレジストリが担う。
パス解決はすべて本モジュールに集約する(Windows 対応のため pathlib・ルート相対)。
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent


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


class NotifyConfig(BaseModel):
    min_severity: str = "info"


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
        return PROJECT_ROOT / self.db.path

    @property
    def kill_flag_path(self) -> Path:
        return PROJECT_ROOT / self.runtime.kill_flag

    @property
    def log_dir_path(self) -> Path:
        return PROJECT_ROOT / self.runtime.log_dir

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
