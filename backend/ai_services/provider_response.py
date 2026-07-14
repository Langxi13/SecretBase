"""Compatibility parsing for OpenAI-style provider responses."""

from __future__ import annotations


def extract_chat_message_content(result: dict) -> str:
    content = result["choices"][0]["message"].get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    if content is None:
        return ""
    raise TypeError("message.content must be text")
