"""shared — Magi / TradeCouncil 共通のツール層(LLMブリッジ・SharePoint・office変換・git フック)。

各プロジェクトはこの層を **path 起動**(例 `python shared/sharepoint.py`)か `from shared import ...`
で利用する。重依存は持たない(office libは関数内 lazy import)。詳細は shared/README.md。
"""
