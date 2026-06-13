"""統一インストゥルメントモデル(FR-8.1)。

BOT・リスク管理・会議・KPI はすべて instrument_id を介して動き、
資産クラス固有の知識はブローカーアダプタと margin_rule に閉じ込める。
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

ASSET_CLASSES = (
    "crypto_spot",
    "crypto_margin",
    "equity_jp",
    "equity_foreign",
    "futures",
    "fx",
    "bond_etf",
)


class InstrumentSpec(BaseModel):
    instrument_id: str
    asset_class: str
    broker: str
    symbol: str
    currency: str
    tick_size: float
    lot_size: float
    session_calendar: str
    margin_rule: str


def load_instruments(instruments_dir: Path | None = None) -> dict[str, InstrumentSpec]:
    """config/instruments/*.yaml を読み込む。"""
    if instruments_dir is None:
        from core.config import get_config

        instruments_dir = get_config().instruments_dir
    specs: dict[str, InstrumentSpec] = {}
    if not instruments_dir.exists():
        return specs
    for path in sorted(instruments_dir.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        spec = InstrumentSpec.model_validate(raw)
        specs[spec.instrument_id] = spec
    return specs


def sync_instruments_to_db(
    session_factory: sessionmaker[Session],
    specs: dict[str, InstrumentSpec] | None = None,
) -> int:
    """YAML 定義を instruments テーブルへ反映する(冪等)。"""
    from core.db.models import Instrument

    if specs is None:
        specs = load_instruments()
    with session_factory() as session:
        for spec in specs.values():
            row = session.get(Instrument, spec.instrument_id)
            if row is None:
                session.add(Instrument(**spec.model_dump()))
            else:
                for key, value in spec.model_dump().items():
                    setattr(row, key, value)
        session.commit()
    return len(specs)
