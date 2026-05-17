# backend/app/config_db.py
"""Helper get_config: prevalença BD > env."""
from __future__ import annotations
from typing import Any


def get_config(key: str, default: Any = None) -> Any:
    """Llegeix una clau de system_config; fallback a default si no hi ha valor.

    Llei especial: si value_type=='int' i el valor és '0', retorna None
    (0 = sense límit explícit per a max_tokens).
    """
    try:
        from .db import get_session
        from .models.db_models import SystemConfigModel
        with get_session() as db:
            entry = db.get(SystemConfigModel, key)
            if entry is None or entry.value is None or entry.value == '':
                return default
            return _cast(entry.value, entry.value_type, default)
    except Exception:
        return default


def _cast(value: str, value_type: str, default: Any) -> Any:
    try:
        if value_type == 'int':
            cast = int(value)
            return None if cast == 0 else cast
        if value_type == 'float':
            return float(value)
        if value_type == 'bool':
            return value.lower() in ('true', '1', 'yes')
        return value
    except (ValueError, TypeError):
        return default
