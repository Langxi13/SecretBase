"""AI 安全配置、上游 HTTP 客户端与响应解包。"""

import json
import logging
import os
from pathlib import Path

import httpx
from fastapi import HTTPException

from config import SECURE_SETTINGS_FILE
from crypto import decrypt_vault_with_key, encrypt_vault_with_key, parse_vault_header
from secure_settings import AI_SETTINGS_PURPOSE
from storage import derive_unlocked_purpose_key
from ai_services.prompts import AI_CHAT_TIMEOUT_SECONDS


logger = logging.getLogger(__name__)


def _extract_json_content(content: str):
    """Extract the first JSON object/array from an AI response."""
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else ""
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

    decoder = json.JSONDecoder()
    for index, char in enumerate(content):
        if char not in "[{":
            continue
        try:
            parsed, _ = decoder.raw_decode(content[index:])
            return parsed
        except json.JSONDecodeError:
            continue
    raise json.JSONDecodeError("No JSON object found", content, 0)


def _empty_ai_status() -> dict:
    return {
        "configured": False,
        "base_url": "",
        "model": "",
        "api_key_mask": "",
    }


def _mask_api_key(api_key: str) -> str:
    api_key = str(api_key or "").strip()
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:3]}...{api_key[-4:]}"


def _normalize_base_url(base_url: str) -> str:
    base_url = str(base_url or "").strip().rstrip("/")
    for suffix in ("/chat/completions", "/models"):
        if base_url.endswith(suffix):
            base_url = base_url[: -len(suffix)].rstrip("/")
    if not base_url.startswith(("https://", "http://")):
        raise HTTPException(status_code=422, detail="Base URL 必须以 http:// 或 https:// 开头")
    return base_url


def _payload_value(payload: dict, *names: str) -> str:
    for name in names:
        value = payload.get(name)
        if value is not None:
            return str(value).strip()
    return ""


def _load_secure_settings() -> dict:
    path = Path(SECURE_SETTINGS_FILE)
    if not path.exists():
        return {}

    key, salt = derive_unlocked_purpose_key(AI_SETTINGS_PURPOSE)
    content = path.read_bytes()
    header = parse_vault_header(content)
    if header["salt"] != salt:
        raise ValueError("安全设置不是当前 vault 可解密的数据")
    plaintext = decrypt_vault_with_key(key, content)
    data = json.loads(plaintext.decode("utf-8"))
    return data if isinstance(data, dict) else {}


def _load_secure_settings_for_write() -> dict:
    try:
        return _load_secure_settings()
    except Exception as e:
        logger.warning(f"AI 安全设置不可读取，将重新创建: {e}")
        return {}


def _save_secure_settings(data: dict) -> None:
    path = Path(SECURE_SETTINGS_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not data:
        path.unlink(missing_ok=True)
        return

    key, salt = derive_unlocked_purpose_key(AI_SETTINGS_PURPOSE)
    plaintext = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    encrypted = encrypt_vault_with_key(key, salt, plaintext)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_bytes(encrypted)
    os.replace(tmp_path, path)


def _load_ai_config() -> dict | None:
    try:
        settings = _load_secure_settings()
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.error(f"加载 AI 安全设置失败: {e}")
        return None

    ai_config = settings.get("ai") if isinstance(settings, dict) else None
    if not isinstance(ai_config, dict):
        return None
    if not all(ai_config.get(key) for key in ("base_url", "api_key", "model")):
        return None
    return {
        "base_url": str(ai_config["base_url"]).rstrip("/"),
        "api_key": str(ai_config["api_key"]),
        "model": str(ai_config["model"]),
        "api_key_mask": str(ai_config.get("api_key_mask") or _mask_api_key(ai_config["api_key"])),
    }


def _ai_status_from_config(config: dict | None) -> dict:
    if not config:
        return _empty_ai_status()
    return {
        "configured": True,
        "base_url": config["base_url"],
        "model": config["model"],
        "api_key_mask": config["api_key_mask"],
    }


def _model_endpoint(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/models"


def _chat_endpoint(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/chat/completions"


def _auth_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


async def _fetch_model_ids(base_url: str, api_key: str) -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
            response = await client.get(_model_endpoint(base_url), headers=_auth_headers(api_key))
    except httpx.TimeoutException:
        raise HTTPException(status_code=502, detail="获取模型列表超时")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="无法连接 AI 服务")

    if response.status_code in {401, 403}:
        raise HTTPException(status_code=502, detail="获取模型列表失败：API Key 无效或无权限")
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail=f"获取模型列表失败：服务返回 {response.status_code}")

    try:
        payload = response.json()
    except Exception:
        raise HTTPException(status_code=502, detail="获取模型列表失败：响应不是有效 JSON")

    raw_models = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(raw_models, list):
        raise HTTPException(status_code=502, detail="获取模型列表失败：响应格式无效")

    models = []
    seen = set()
    for item in raw_models:
        model_id = item.get("id") if isinstance(item, dict) else item
        model_id = str(model_id or "").strip()
        if model_id and model_id not in seen:
            seen.add(model_id)
            models.append(model_id)

    if not models:
        raise HTTPException(status_code=502, detail="获取模型列表失败：服务商未返回可用模型")
    return models


async def _request_chat_completion(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    max_tokens: int,
) -> str:
    try:
        async with httpx.AsyncClient(timeout=AI_CHAT_TIMEOUT_SECONDS, trust_env=False) as client:
            response = await client.post(
                _chat_endpoint(base_url),
                headers=_auth_headers(api_key),
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                },
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=502, detail="AI 服务响应超时")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="AI 服务连接失败")

    if response.status_code in {401, 403}:
        raise HTTPException(status_code=502, detail="AI 服务认证失败，请检查 API Key")
    if response.status_code != 200:
        logger.error(f"AI 服务返回错误: {response.status_code}")
        raise HTTPException(status_code=502, detail="AI 服务调用失败")

    try:
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"AI 服务响应格式错误: {e}")
        raise HTTPException(status_code=422, detail="AI 返回格式错误")


async def _verify_ai_config(base_url: str, api_key: str, model: str) -> None:
    content = await _request_chat_completion(
        base_url,
        api_key,
        model,
        [{"role": "user", "content": 'Return exactly this JSON object: {"ok": true}'}],
        100,
    )
    try:
        payload = _extract_json_content(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="AI 连通测试失败：模型未返回有效 JSON")
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise HTTPException(status_code=502, detail="AI 连通测试失败：模型返回内容不符合预期")
