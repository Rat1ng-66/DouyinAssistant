# -*- coding: utf-8 -*-
"""Config loader compatible with previous DouyinAssistant versions."""
import json
from pathlib import Path

from paths import app_data_dir

DATA_DIR = app_data_dir()
CONFIG_FILE = DATA_DIR / "message_config.json"

DEFAULT_CONFIG = {
    "messages": [],
    "interval": 60,
    "limit": 10,
    "room_url": "",
    "task_mode": "count",
    "duration_value": 5,
    "duration_unit_seconds": 60,
}


def _safe_int(value, default, min_value, max_value):
    try:
        n = int(value)
    except (ValueError, TypeError):
        n = default
    return max(min_value, min(n, max_value))


def load_config():
    result = dict(DEFAULT_CONFIG)
    result["messages"] = []

    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as f:
            existing = json.load(f)
    except (OSError, json.JSONDecodeError, UnicodeError):
        return result

    if not isinstance(existing, dict):
        return result

    messages = existing.get("messages")
    if isinstance(messages, list):
        result["messages"] = [
            item for item in messages
            if isinstance(item, str) and item.strip()
        ][:100]

    result["interval"] = _safe_int(existing.get("interval"), 60, 1, 600)
    result["limit"] = _safe_int(existing.get("limit"), 10, 1, 20)

    room = existing.get("room_url", "")
    if isinstance(room, str):
        result["room_url"] = room

    mode = existing.get("task_mode", "count")
    if mode in ("count", "duration"):
        result["task_mode"] = mode

    unit = _safe_int(
        existing.get("duration_unit_seconds", 60),
        60, 60, 86400
    )
    if unit not in (60, 3600, 86400):
        unit = 60
    result["duration_unit_seconds"] = unit
    max_value = 31536000 // unit
    result["duration_value"] = _safe_int(
        existing.get("duration_value", 5), 5, 1, max_value
    )

    return result


def save_config(config):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Merge fields so future/other preferences are not silently discarded.
    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as f:
            merged = json.load(f)
        if not isinstance(merged, dict):
            merged = {}
    except (OSError, json.JSONDecodeError, UnicodeError):
        merged = {}

    merged.update(config)

    tmp_path = CONFIG_FILE.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)
    tmp_path.replace(CONFIG_FILE)
