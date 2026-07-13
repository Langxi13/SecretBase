"""Server-side pending turn and plan storage bound to an unlocked vault session."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException

from storage import vault_revision, vault_session_id


TTL_SECONDS = 15 * 60
MAX_PENDING_ITEMS = 64


@dataclass
class PendingItem:
    kind: str
    session_id: str
    source_revision: int
    payload: Any
    created_at: float


_LOCK = threading.Lock()
_ITEMS: dict[str, PendingItem] = {}


def _prune() -> None:
    now = time.time()
    expired = [token for token, item in _ITEMS.items() if now - item.created_at > TTL_SECONDS]
    for token in expired:
        _ITEMS.pop(token, None)
    if len(_ITEMS) <= MAX_PENDING_ITEMS:
        return
    oldest = sorted(_ITEMS.items(), key=lambda pair: pair[1].created_at)
    for token, _item in oldest[: len(_ITEMS) - MAX_PENDING_ITEMS]:
        _ITEMS.pop(token, None)


def put_pending(kind: str, payload: Any, source_revision: int | None = None) -> str:
    session_id = vault_session_id()
    if not session_id:
        raise HTTPException(status_code=401, detail="请先解锁")
    token = secrets.token_urlsafe(32)
    with _LOCK:
        _prune()
        _ITEMS[token] = PendingItem(
            kind=kind,
            session_id=session_id,
            source_revision=vault_revision() if source_revision is None else source_revision,
            payload=payload,
            created_at=time.time(),
        )
    return token


def get_pending(token: str, kind: str, expected_revision: int | None = None) -> PendingItem:
    with _LOCK:
        _prune()
        item = _ITEMS.get(str(token or ""))
    if not item or item.kind != kind:
        raise HTTPException(status_code=410, detail="AI 计划已失效，请重新生成")
    if item.session_id != vault_session_id():
        discard_pending(token)
        raise HTTPException(status_code=410, detail="AI 计划不属于当前解锁会话")
    current_revision = vault_revision()
    if item.source_revision != current_revision:
        discard_pending(token)
        raise HTTPException(status_code=409, detail="密码库已变化，请重新生成 AI 计划")
    if expected_revision is not None and expected_revision != current_revision:
        raise HTTPException(status_code=409, detail="页面数据已过期，请刷新后重试")
    return item


def discard_pending(token: str) -> None:
    with _LOCK:
        _ITEMS.pop(str(token or ""), None)


def consume_pending(token: str, kind: str, expected_revision: int | None = None) -> PendingItem:
    item = get_pending(token, kind, expected_revision)
    discard_pending(token)
    return item
