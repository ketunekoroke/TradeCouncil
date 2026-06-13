"""DB初期化(tc db init から呼ばれる)。"""

from __future__ import annotations

from sqlalchemy import Engine

from core.config import get_config
from core.db.engine import get_engine
from core.db.models import Base


def init_db(engine: Engine | None = None) -> None:
    """スキーマを作成し、実行時ディレクトリを準備する(冪等)。"""
    get_config().ensure_runtime_dirs()
    Base.metadata.create_all(engine or get_engine())
