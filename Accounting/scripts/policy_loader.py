"""config/*.yaml を読み込み core/policy へ渡す dict を作る(scripts 層・PyYAML)。

core は zero-dep(stdlib のみ)なので YAML 解析はここで行い、結果の dict だけを core に注入する。
技術設定は config/system.yaml(fx 等)、勘定科目雛形は config/accounts.yaml(降格・任意の override)。
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SYSTEM_YAML = PROJECT_ROOT / "config" / "system.yaml"
ACCOUNTS_YAML = PROJECT_ROOT / "config" / "accounts.yaml"


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - 環境依存
        raise SystemExit(
            "error: PyYAML が必要です(`pip install PyYAML` か optional-deps 'pipeline')"
        ) from exc
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def fx_rule() -> dict:
    """system.yaml の fx セクション(base_rule / rate_source)。"""
    return dict(_load_yaml(SYSTEM_YAML).get("fx") or {})


def extract_settings() -> dict:
    """system.yaml の extract セクション(confidence_threshold 等)。"""
    return dict(_load_yaml(SYSTEM_YAML).get("extract") or {})


def high_value_jpy(default: int = 100000) -> int:
    """高額フラグのしきい値(将来 system.yaml に追加可能。今は既定値)。"""
    val = _load_yaml(SYSTEM_YAML).get("gate", {}).get("high_value_jpy")
    try:
        return int(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def notify_env_prefix(default: str = "AC") -> str:
    """system.yaml notify.env_prefix(Teams 等の env 名スコープ)。既定 AC。"""
    val = _load_yaml(SYSTEM_YAML).get("notify", {}).get("env_prefix")
    return str(val) if val else default


def overrides() -> list[dict]:
    """accounts.yaml の mappings を任意の手動 override として返す(降格・無くてもよい)。

    各要素は {match:[kw], ex_item|account}。policy は ex_item 優先(なければ account)。
    """
    data = _load_yaml(ACCOUNTS_YAML)
    mappings = data.get("mappings") or []
    return [m for m in mappings if isinstance(m, dict) and m.get("match")]
