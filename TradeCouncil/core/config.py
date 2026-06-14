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


def _shared_env_path() -> Path:
    """シークレットを集約したルート共有 `.env` を上方向探索で見つける(モノレポ — ADR-0011)。

    プロジェクト dir(PROJECT_ROOT)から上に向かって `.git` を持つリポジトリルートを探し、
    その `.env` を返す。見つからなければ従来どおり PROJECT_ROOT/.env。
    """
    for parent in (PROJECT_ROOT, *PROJECT_ROOT.parents):
        if (parent / ".git").exists():
            return parent / ".env"
    return PROJECT_ROOT / ".env"


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
    # ログ形式: plain(従来・人間可読)| json(CloudWatch Logs 取り込み用。ADR-0006)
    log_format: Literal["plain", "json"] = "plain"
    log_level: str = "INFO"


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


class BybitFeedConfig(BaseModel):
    """Bybit 公開市場データフィード(ADR-0008)。発注は常に testnet(アダプタ側で強制)。"""

    # testnet = 執行と同一環境(既定)/ mainnet = 公開データのみ(testnet 価格が歪むとき)
    environment: Literal["testnet", "mainnet"] = "testnet"
    bar_interval_sec: int = 60
    poll_sec: float = 5.0  # 新バー確定待ちのポーリング間隔


class FeedConfig(BaseModel):
    type: Literal["random_walk", "bybit"] = "random_walk"
    random_walk: RandomWalkConfig = Field(default_factory=RandomWalkConfig)
    bybit: BybitFeedConfig = Field(default_factory=BybitFeedConfig)


class FxConfig(BaseModel):
    """JPY 換算レート(技術設定 — ADR-0008)。

    リスク上限(P-02/P-03)は JPY 建てのため、JPY 以外の instrument 通貨は
    このレートで換算する。実勢より円安側の保守値(損失・エクスポージャーの
    過大評価 = 安全側)を設定し、定期的に見直す。
    """

    # ge=1: 1 未満は明白な誤設定(notional 縮小 = リスク上限が甘くなる方向)として
    # config 読込時点で拒否する(risk-auditor 審査の推奨。guard 側の gt=0 は最終防壁)
    usdjpy_rate: float | None = Field(default=None, ge=1)

    def rate_to_jpy(self, currency: str) -> float:
        """instrument 通貨 → JPY の換算レート。未対応・未設定は拒否(fail-closed)。"""
        if currency == "JPY":
            return 1.0
        if currency in ("USDT", "USD"):
            if self.usdjpy_rate is None:
                raise ValueError(
                    "fx.usdjpy_rate が未設定(system.yaml)。"
                    f"{currency} 建て instrument は換算レートなしでは扱えない(fail-closed)"
                )
            return self.usdjpy_rate
        raise ValueError(f"未対応の通貨: {currency}(JPY/USDT/USD のみ — ADR-0008)")


_CHANNEL_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_VALID_SEVERITIES = frozenset({"info", "warning", "critical"})


class NotifyConfig(BaseModel):
    backend: Literal["discord", "teams"] = "discord"
    min_severity: str = "info"
    # プロジェクト別 env 名のスコープ(ADR-0011)。TradeCouncil=TC。
    # URL は <TEAMS|DISCORD>_<env_prefix>_<...>_URL を優先し、未設定なら無印の共有名へフォールバック。
    env_prefix: str = "TC"
    # severity → チャネル名(例 {"warning": "alerts"})。URL は環境変数
    # TEAMS_<prefix>_WORKFLOW_URL_<チャネル名大文字> 等から解決する(ADR-0003)
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
    fx: FxConfig = Field(default_factory=FxConfig)
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
    load_dotenv(_shared_env_path())
    yaml_path = path or (PROJECT_ROOT / "config" / "system.yaml")
    if yaml_path.exists():
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    else:
        raw = {}
    return SystemConfig.model_validate(raw)


@lru_cache(maxsize=1)
def get_config() -> SystemConfig:
    return load_config()


# 通知 URL の env 名はプロジェクト別プレフィックス(TradeCouncil=TC)で名前空間を切る(ADR-0011)。
#   既定:    TEAMS_TC_WORKFLOW_URL[_<CHANNEL>] / DISCORD_TC_WEBHOOK_URL[_<CHANNEL>]
#   後方互換: 無印の TEAMS_WORKFLOW_URL[_<CHANNEL>] / DISCORD_WEBHOOK_URL[_<CHANNEL>]
def _base_url(kind: str, prefix: str) -> str | None:
    """kind は 'TEAMS_WORKFLOW' か 'DISCORD_WEBHOOK'。プロジェクト別名を優先し共有名へフォールバック。"""
    head, tail = kind.split("_", 1)  # 例 TEAMS / WORKFLOW
    if prefix:
        v = os.environ.get(f"{head}_{prefix}_{tail}_URL")
        if v:
            return v
    return os.environ.get(f"{kind}_URL") or None


def _scan_channel_urls(prefix: str) -> dict[str, str]:
    """`<prefix>_<CHANNEL>` 形式の環境変数を走査し {チャネル名(小文字): URL} を返す。"""
    head = prefix + "_"
    return {
        key[len(head):].lower(): value
        for key, value in os.environ.items()
        if key.startswith(head) and value
    }


def _channel_urls(kind: str, prefix: str) -> dict[str, str]:
    """共有名のチャネル URL に、プロジェクト別名のチャネル URL を上書きで重ねる。"""
    head, tail = kind.split("_", 1)
    urls = _scan_channel_urls(f"{kind}_URL")  # 後方互換(無印)
    if prefix:
        urls.update(_scan_channel_urls(f"{head}_{prefix}_{tail}_URL"))  # プロジェクト別が勝つ
    return urls


def discord_webhook_url(prefix: str = "") -> str | None:
    return _base_url("DISCORD_WEBHOOK", prefix)


def teams_workflow_url(prefix: str = "") -> str | None:
    """Power Automate「Webhook 要求の受信時」フローの URL(SAS 署名 sig= を含む秘密)。"""
    return _base_url("TEAMS_WORKFLOW", prefix)


def teams_channel_urls(prefix: str = "") -> dict[str, str]:
    """チャネル別 Workflow URL(TEAMS_TC_WORKFLOW_URL_OPS 等。無印も後方互換)。"""
    return _channel_urls("TEAMS_WORKFLOW", prefix)


def discord_channel_urls(prefix: str = "") -> dict[str, str]:
    """チャネル別 Discord Webhook URL(DISCORD_TC_WEBHOOK_URL_ALERTS 等。無印も後方互換)。"""
    return _channel_urls("DISCORD_WEBHOOK", prefix)
