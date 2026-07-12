from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path


_PREFERENCES_LOCK = threading.RLock()


def load_preferences(settings_path: Path) -> dict:
    with _PREFERENCES_LOCK:
        try:
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (FileNotFoundError, OSError, TypeError, ValueError, json.JSONDecodeError):
            return {}


def update_preferences(settings_path: Path, updates: dict) -> None:
    with _PREFERENCES_LOCK:
        payload = load_preferences(settings_path)
        payload.update(updates)
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                prefix=f".{settings_path.name}.",
                suffix=".tmp",
                dir=settings_path.parent,
                delete=False,
            ) as temporary:
                json.dump(payload, temporary, ensure_ascii=False, indent=2)
                temporary.write("\n")
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)
            os.replace(temporary_path, settings_path)
        finally:
            if temporary_path and temporary_path.exists():
                temporary_path.unlink()
