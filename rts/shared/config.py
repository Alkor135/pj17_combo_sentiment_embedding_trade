"""Загрузка rts/settings.yaml с плоским слиянием common + выбранной секции.

Используется скриптами в rts/shared, rts/embedding, rts/sentiment и rts/combine_predictions.py:

    from shared.config import load_settings
    settings = load_settings('embedding')   # вернёт common + embedding (specific overrides)
    settings = load_settings('sentiment')
    settings = load_settings()              # только common

Формат значений (placeholders {ticker}, {ticker_lc}) подставляется на месте —
это совместимо с тем, как скрипты pj14/pj16 сами делали .replace/.format.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml


def _find_settings(start: Path) -> Path:
    """Идёт вверх от start, ищет settings.yaml в папке тикера (rts/, mix/, …)."""
    for parent in [start] + list(start.parents):
        candidate = parent / "settings.yaml"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"settings.yaml не найден выше {start}")


def _resolve_placeholders(obj, ticker: str, ticker_lc: str):
    if isinstance(obj, str):
        return obj.replace("{ticker}", ticker).replace("{ticker_lc}", ticker_lc)
    if isinstance(obj, dict):
        return {k: _resolve_placeholders(v, ticker, ticker_lc) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_placeholders(v, ticker, ticker_lc) for v in obj]
    return obj


def load_settings(section: Optional[str] = None, start: Optional[Path] = None) -> dict:
    settings_file = _find_settings(Path(start) if start else Path(__file__).resolve().parent)
    raw = yaml.safe_load(settings_file.read_text(encoding="utf-8")) or {}
    common = raw.get("common", {}) or {}
    merged = dict(common)
    if section:
        specific = raw.get(section, {}) or {}
        merged.update(specific)
    ticker = merged.get("ticker", "")
    ticker_lc = merged.get("ticker_lc", ticker.lower() if ticker else "")
    merged = _resolve_placeholders(merged, ticker, ticker_lc)
    merged["_settings_file"] = str(settings_file)
    return merged


def settings_path(start: Optional[Path] = None) -> Path:
    return _find_settings(Path(start) if start else Path(__file__).resolve().parent)
