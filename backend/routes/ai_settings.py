"""AI 配置与模型发现路由。"""

import time
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ai_services import client as ai_client
from ai_services.providers import provider_presets, provider_runtime
from storage import is_unlocked


router = APIRouter()


@router.get("/providers")
async def ai_providers():
    """Return built-in provider presets without any credentials."""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")
    return {"success": True, "data": {"providers": provider_presets()}}


@router.get("/status")
async def ai_status():
    """查询 AI 配置状态，不返回 API Key。"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")
    return {
        "success": True,
        "data": ai_client._ai_status_from_config(ai_client._load_ai_config()),
    }


@router.post("/models")
async def ai_models(payload: dict):
    """实时从 OpenAI-compatible 服务商拉取模型列表，不保存配置。"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")

    base_url = ai_client._normalize_base_url(ai_client._payload_value(payload, "baseUrl", "base_url"))
    provider_id = ai_client._payload_value(payload, "providerId", "provider_id") or "custom"
    api_key = ai_client._payload_value(payload, "apiKey", "api_key")
    if not api_key:
        saved_config = ai_client._load_ai_config()
        if saved_config and saved_config.get("base_url") == base_url:
            api_key = saved_config["api_key"]
        else:
            raise HTTPException(status_code=422, detail="API Key 不能为空")

    return {
        "success": True,
        "data": {
            "models": await ai_client._fetch_model_ids(base_url, api_key),
            "provider_id": provider_runtime(provider_id, base_url)["provider_id"],
        },
    }


@router.put("/settings")
async def save_ai_settings(payload: dict):
    """保存 AI 配置，并在写入前校验模型和连通性。"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")

    base_url = ai_client._normalize_base_url(ai_client._payload_value(payload, "baseUrl", "base_url"))
    provider_id = ai_client._payload_value(payload, "providerId", "provider_id") or "custom"
    api_key = ai_client._payload_value(payload, "apiKey", "api_key")
    model = ai_client._payload_value(payload, "model")
    if not model:
        raise HTTPException(status_code=422, detail="请选择模型")

    saved_config = ai_client._load_ai_config()
    if not api_key:
        if saved_config and saved_config.get("base_url") == base_url:
            api_key = saved_config["api_key"]
        else:
            raise HTTPException(status_code=422, detail="API Key 不能为空")

    runtime = await ai_client._verify_ai_config(base_url, api_key, model, provider_id)

    settings = ai_client._load_secure_settings_for_write()
    settings["ai"] = {
        **runtime,
        "api_key": api_key,
        "api_key_mask": ai_client._mask_api_key(api_key),
        "model": model,
        "saved_at": int(time.time()),
    }
    ai_client._save_secure_settings(settings)
    return {
        "success": True,
        "data": ai_client._ai_status_from_config(settings["ai"]),
        "message": "AI 设置已保存",
    }


@router.delete("/settings")
async def clear_ai_settings():
    """显式清除本机保存的 AI 配置。"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")

    settings = ai_client._load_secure_settings_for_write()
    if "ai" in settings or Path(ai_client.SECURE_SETTINGS_FILE).exists():
        settings.pop("ai", None)
        ai_client._save_secure_settings(settings)
    return {
        "success": True,
        "data": ai_client._empty_ai_status(),
        "message": "AI 设置已清除",
    }
