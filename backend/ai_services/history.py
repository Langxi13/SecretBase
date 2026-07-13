"""Device-local encrypted AI conversation history."""

from __future__ import annotations

import json
import logging
import secrets
import threading
from datetime import datetime
from pathlib import Path

from config import AI_HISTORY_FILE
from crypto import decrypt_vault_with_key, encrypt_vault_with_key, parse_vault_header
from secure_settings import AI_HISTORY_PURPOSE, replace_file_atomically
from storage import derive_unlocked_purpose_key


logger = logging.getLogger(__name__)
HISTORY_PATH = Path(AI_HISTORY_FILE)
MAX_CONVERSATIONS = 50
MAX_MESSAGES = 200
_LOCK = threading.RLock()


def _empty_history() -> dict:
    return {"version": 1, "conversations": []}


def _load_unlocked() -> dict:
    if not HISTORY_PATH.exists():
        return _empty_history()
    key, salt = derive_unlocked_purpose_key(AI_HISTORY_PURPOSE)
    content = HISTORY_PATH.read_bytes()
    header = parse_vault_header(content)
    if header["salt"] != salt:
        raise ValueError("AI 对话历史不属于当前密码库")
    data = json.loads(decrypt_vault_with_key(key, content).decode("utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("conversations"), list):
        raise ValueError("AI 对话历史格式无效")
    return data


def _load() -> dict:
    with _LOCK:
        try:
            return _load_unlocked()
        except FileNotFoundError:
            return _empty_history()
        except Exception as error:
            logger.warning("无法读取 AI 对话历史: %s", error)
            return _empty_history()


def _save(data: dict) -> None:
    with _LOCK:
        conversations = data.get("conversations", [])
        conversations.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        del conversations[MAX_CONVERSATIONS:]
        for conversation in conversations:
            messages = conversation.get("messages", [])
            if len(messages) > MAX_MESSAGES:
                conversation["messages"] = messages[-MAX_MESSAGES:]
        key, salt = derive_unlocked_purpose_key(AI_HISTORY_PURPOSE)
        plaintext = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        replace_file_atomically(HISTORY_PATH, encrypt_vault_with_key(key, salt, plaintext))


def _now() -> str:
    return datetime.now().isoformat()


def _conversation_summary(conversation: dict) -> dict:
    return {
        "id": conversation["id"],
        "title": conversation.get("title") or "新对话",
        "created_at": conversation.get("created_at", ""),
        "updated_at": conversation.get("updated_at", ""),
        "message_count": len(conversation.get("messages", [])),
    }


def create_conversation(title: str = "") -> dict:
    data = _load()
    now = _now()
    conversation = {
        "id": secrets.token_urlsafe(16),
        "title": str(title or "").strip()[:60] or "新对话",
        "created_at": now,
        "updated_at": now,
        "messages": [],
    }
    data["conversations"].insert(0, conversation)
    _save(data)
    return _conversation_summary(conversation)


def list_conversations() -> list[dict]:
    return [_conversation_summary(item) for item in _load().get("conversations", [])]


def get_conversation(conversation_id: str) -> dict | None:
    for conversation in _load().get("conversations", []):
        if conversation.get("id") == conversation_id:
            return conversation
    return None


def ensure_conversation(conversation_id: str | None, first_message: str = "") -> dict:
    if conversation_id:
        conversation = get_conversation(conversation_id)
        if conversation:
            return conversation
    title = " ".join(str(first_message or "").split())[:32]
    created = create_conversation(title or "新对话")
    return get_conversation(created["id"])


def append_messages(conversation_id: str, messages: list[dict]) -> dict:
    with _LOCK:
        data = _load_unlocked() if HISTORY_PATH.exists() else _empty_history()
        conversation = next(
            (item for item in data["conversations"] if item.get("id") == conversation_id),
            None,
        )
        if conversation is None:
            raise ValueError("AI 对话不存在")
        now = _now()
        for message in messages:
            content = str(message.get("content") or "").strip()
            if not content:
                continue
            conversation["messages"].append({
                "id": secrets.token_urlsafe(12),
                "role": message.get("role") if message.get("role") in {"user", "assistant", "system"} else "assistant",
                "content": content[:12000],
                "mode": str(message.get("mode") or "assistant"),
                "created_at": now,
                "meta": message.get("meta") if isinstance(message.get("meta"), dict) else {},
            })
        conversation["updated_at"] = now
        if conversation.get("title") == "新对话":
            first_user = next((item for item in conversation["messages"] if item.get("role") == "user"), None)
            if first_user:
                conversation["title"] = " ".join(first_user["content"].split())[:32] or "新对话"
        _save(data)
        return conversation


def model_context(conversation_id: str, maximum_messages: int = 16) -> list[dict]:
    conversation = get_conversation(conversation_id)
    if not conversation:
        return []
    context = []
    for message in conversation.get("messages", [])[-maximum_messages:]:
        if message.get("role") not in {"user", "assistant"}:
            continue
        context.append({"role": message["role"], "content": str(message.get("content") or "")[:4000]})
    return context


def delete_conversation(conversation_id: str) -> bool:
    data = _load()
    original = len(data["conversations"])
    data["conversations"] = [item for item in data["conversations"] if item.get("id") != conversation_id]
    if len(data["conversations"]) == original:
        return False
    _save(data)
    return True


def clear_history() -> None:
    replace_file_atomically(HISTORY_PATH, None)
