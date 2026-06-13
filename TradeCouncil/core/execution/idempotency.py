"""注文の冪等性キー(FR-4.2: 二重発注防止)。"""

from __future__ import annotations

import hashlib


def make_idempotency_key(
    bot_id: str, decision_id: str, instrument_id: str, side: str, qty: float
) -> str:
    raw = f"{bot_id}|{decision_id}|{instrument_id}|{side}|{qty:.12f}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
