import logging
import hashlib
import json
import re
import time
import os
from pathlib import Path
import httpx
from fastapi import APIRouter, HTTPException
from models import AiParseRequest
from config import SECURE_SETTINGS_FILE
from crypto import decrypt_vault_with_key, encrypt_vault_with_key, parse_vault_header
from storage import derive_unlocked_purpose_key, is_unlocked

logger = logging.getLogger(__name__)
router = APIRouter()
AI_PARSE_COOLDOWN_SECONDS = 5
AI_PARSE_MAX_INPUT_CHARS = 6000
_last_parse_at = 0.0
_last_parse_text_hash = ""
AI_SETTINGS_PURPOSE = "ai-settings"

SYSTEM_PROMPT = """你是 SecretBase 的密码条目解析器。你的任务是把用户输入的一段自然语言、聊天记录、备忘录或混杂文本解析成一个或多个独立的密码管理条目。

你必须严格只输出一个 JSON object，不要输出 Markdown，不要输出解释，不要输出代码块。

顶层 JSON 必须且只能使用这个结构：
{
  "entries": [
    {
      "title": "条目标题",
      "url": "https://example.com",
      "fields": [
        {"name": "字段名", "value": "字段值", "copyable": true}
      ],
      "tags": ["标签1", "标签2"],
      "remarks": "备注"
    }
  ]
}

规则：
1. entries 永远是数组；即使只有一条，也必须放在 entries 数组里。
2. 如果文本里包含多个不同网站、系统、服务器、银行卡、API Key、邮箱、路由器、NAS、数据库、证件或安全笔记，必须拆成多个 entries，不要混在一个 entry 中。
3. 常见多条信号包括：编号、换行、分号、“还有”、“另外”、“再加一个”、“别混一起”、“这个也存一下”、“1）/2）/3）”。
4. 每个 entry 必须包含 title、url、fields、tags、remarks 五个键。
5. title 必填；没有明确标题时，根据上下文推断一个短标题，例如“公司邮箱”、“云服务器”、“家里路由器”。
6. url 没有就返回空字符串；只有 http:// 或 https:// 开头的链接才能放入 url。IP、域名、主机名不能放到 url，应该作为字段。
7. fields 必须是数组；每个字段必须包含 name、value、copyable 三个键。name 和 value 都必须是字符串，copyable 必须是布尔值。
8. 所有识别到的账号、用户名、邮箱、密码、IP、端口、API Key、Token、恢复码、卡号、姓名、有效期、备注信息都要保留，不能丢弃。
9. 密码、密钥、Token、API Key、恢复码、卡号等敏感字段 copyable=true；端口、环境、备注类字段 copyable=false；账号/用户名/邮箱通常 copyable=true。
10. tags 必须是字符串数组，建议 1 到 4 个短标签。
11. remarks 没有就返回空字符串；无法确定归属但可能有用的信息放入 remarks。
12. 禁止返回 null；没有内容时用空字符串或空数组。
13. 不要编造不存在的账号、密码、网址、IP、Token 或标签。无法确定的信息放入 remarks，不要擅自归类到敏感字段。
14. 字段名在同一个 entry 内不能重复；如果原文有重复字段，用更具体的字段名区分，例如“服务器密码”“数据库密码”。
15. 如果输入非常杂乱，优先保守拆分：只为有明确归属的信息创建 entry，无法归属的信息写入最相关 entry 的 remarks。
16. 不要把多个无关服务合并为“杂项密码”条目，除非原文完全无法区分归属。
17. 单次最多返回 20 个 entries；如果明显超过 20 个，优先解析前 20 个，并在 remarks 说明还有未处理内容。

示例输入：
帮我记一下：示例邮箱 demo@example.com 密码 demo-mail-pass；还有示例服务器，IP 192.0.2.10，SSH 端口 2222，管理员密码 demo-server-pass，别混一起。

示例输出：
{"entries":[{"title":"示例邮箱","url":"","fields":[{"name":"邮箱","value":"demo@example.com","copyable":true},{"name":"密码","value":"demo-mail-pass","copyable":true}],"tags":["邮箱","示例"],"remarks":""},{"title":"示例服务器","url":"","fields":[{"name":"IP","value":"192.0.2.10","copyable":true},{"name":"SSH 端口","value":"2222","copyable":false},{"name":"密码","value":"demo-server-pass","copyable":true}],"tags":["服务器","示例"],"remarks":""}]}"""


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
        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
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


def _clean_text(value, max_length: int = 10000) -> str:
    return str(value or "").strip()[:max_length]


def _to_bool(value, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1", "是", "可复制"}:
            return True
        if normalized in {"false", "no", "0", "否", "不可复制"}:
            return False
    return bool(value)


def _normalize_field(field):
    if isinstance(field, (str, int, float, bool)):
        field = {"name": "内容", "value": field, "copyable": False}
    if not isinstance(field, dict):
        return None
    name = _clean_text(field.get("name") or field.get("label") or field.get("key") or field.get("field"), 100)
    if not name:
        return None
    raw_value = field.get("value")
    if raw_value is None:
        raw_value = field.get("text") or field.get("content") or field.get("val") or ""
    return {
        "name": name,
        "value": _clean_text(raw_value, 10000),
        "copyable": _to_bool(field.get("copyable"), True)
    }


def _normalize_fields(raw_fields):
    if isinstance(raw_fields, dict):
        raw_fields = [
            {"name": key, "value": value, "copyable": True}
            for key, value in raw_fields.items()
        ]
    if not isinstance(raw_fields, list):
        raw_fields = []

    fields = []
    seen_field_names = set()
    for field in raw_fields:
        normalized = _normalize_field(field)
        if not normalized or normalized["name"] in seen_field_names:
            continue
        seen_field_names.add(normalized["name"])
        fields.append(normalized)
    return fields


def _normalize_tags(raw_tags):
    if isinstance(raw_tags, str):
        raw_tags = re.split(r"[,，;；]+", raw_tags)
    if not isinstance(raw_tags, list):
        raw_tags = []

    tags = []
    seen_tags = set()
    for tag in raw_tags:
        normalized_tag = _clean_text(tag, 50)
        if not normalized_tag or normalized_tag in seen_tags:
            continue
        seen_tags.add(normalized_tag)
        tags.append(normalized_tag)
    return tags


def _normalize_entry(entry, index: int = 0):
    if not isinstance(entry, dict):
        entry = {}

    title = _clean_text(entry.get("title") or entry.get("name") or entry.get("site") or entry.get("service"), 200) or f"AI 解析条目 {index + 1}"
    url = _clean_text(entry.get("url") or entry.get("link") or entry.get("website"), 2000)
    if url and not url.startswith(("http://", "https://")):
        url = ""

    fields = _normalize_fields(entry.get("fields") or entry.get("field_items") or entry.get("credentials"))
    tags = _normalize_tags(entry.get("tags") or entry.get("labels") or entry.get("categories"))

    return {
        "title": title,
        "url": url,
        "fields": fields,
        "tags": tags,
        "remarks": _clean_text(entry.get("remarks") or entry.get("note") or entry.get("notes") or entry.get("comment"), 2000)
    }


def _normalize_ai_payload(payload):
    if isinstance(payload, list):
        raw_entries = payload
    elif isinstance(payload, dict) and isinstance(payload.get("entries"), list):
        raw_entries = payload["entries"]
    elif isinstance(payload, dict) and isinstance(payload.get("parsed_entries"), list):
        raw_entries = payload["parsed_entries"]
    elif isinstance(payload, dict) and isinstance(payload.get("items"), list):
        raw_entries = payload["items"]
    elif isinstance(payload, dict) and isinstance(payload.get("accounts"), list):
        raw_entries = payload["accounts"]
    elif isinstance(payload, dict) and isinstance(payload.get("records"), list):
        raw_entries = payload["records"]
    elif isinstance(payload, dict) and isinstance(payload.get("data"), list):
        raw_entries = payload["data"]
    elif isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return _normalize_ai_payload(payload["data"])
    elif isinstance(payload, dict):
        raw_entries = [payload]
    else:
        raw_entries = [{}]

    entries = [_normalize_entry(entry, index) for index, entry in enumerate(raw_entries)]
    entries = [entry for entry in entries if entry["title"] or entry["fields"] or entry["tags"]]
    if not entries:
        entries = [_normalize_entry({}, 0)]
    return entries


def _quality_warnings(entries, source_text: str) -> list[str]:
    warnings = []
    if len(source_text) > 3000:
        warnings.append("输入内容较长，建议分批解析并逐条检查结果。")
    if len(source_text.splitlines()) > 60:
        warnings.append("输入行数较多，AI 可能误分或合并条目，请重点检查。")
    if len(entries) > 8:
        warnings.append("解析结果条目较多，请逐条确认后再创建。")
    if any(not entry.get("fields") for entry in entries):
        warnings.append("部分条目没有字段，可能需要手动补充。")
    if any(entry.get("title", "").startswith("AI 解析条目") for entry in entries):
        warnings.append("部分条目标题由系统兜底生成，建议手动改成更明确的标题。")
    return list(dict.fromkeys(warnings))


@router.get("/status")
async def ai_status():
    """查询 AI 配置状态，不返回 API Key。"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")

    return {
        "success": True,
        "data": _ai_status_from_config(_load_ai_config())
    }


@router.post("/models")
async def ai_models(payload: dict):
    """实时从 OpenAI-compatible 服务商拉取模型列表，不保存配置。"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")

    base_url = _normalize_base_url(_payload_value(payload, "baseUrl", "base_url"))
    api_key = _payload_value(payload, "apiKey", "api_key")
    if not api_key:
        saved_config = _load_ai_config()
        if saved_config and saved_config.get("base_url") == base_url:
            api_key = saved_config["api_key"]
        else:
            raise HTTPException(status_code=422, detail="API Key 不能为空")

    models = await _fetch_model_ids(base_url, api_key)
    return {
        "success": True,
        "data": {"models": models}
    }


@router.put("/settings")
async def save_ai_settings(payload: dict):
    """保存 AI 配置。保存前必须拉取模型列表并完成固定连通测试。"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")

    base_url = _normalize_base_url(_payload_value(payload, "baseUrl", "base_url"))
    api_key = _payload_value(payload, "apiKey", "api_key")
    model = _payload_value(payload, "model")
    if not model:
        raise HTTPException(status_code=422, detail="请选择模型")

    saved_config = _load_ai_config()
    if not api_key:
        if saved_config and saved_config.get("base_url") == base_url:
            api_key = saved_config["api_key"]
        else:
            raise HTTPException(status_code=422, detail="API Key 不能为空")

    models = await _fetch_model_ids(base_url, api_key)
    if model not in models:
        raise HTTPException(status_code=422, detail="只能保存服务商模型列表中返回的模型")
    await _verify_ai_config(base_url, api_key, model)

    settings = _load_secure_settings_for_write()
    settings["ai"] = {
        "base_url": base_url,
        "api_key": api_key,
        "api_key_mask": _mask_api_key(api_key),
        "model": model,
        "saved_at": int(time.time()),
    }
    _save_secure_settings(settings)

    return {
        "success": True,
        "data": _ai_status_from_config(settings["ai"]),
        "message": "AI 设置已保存"
    }


@router.delete("/settings")
async def clear_ai_settings():
    """显式清除本机保存的 AI 配置。"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")

    settings = _load_secure_settings_for_write()
    if "ai" in settings or Path(SECURE_SETTINGS_FILE).exists():
        settings.pop("ai", None)
        _save_secure_settings(settings)

    return {
        "success": True,
        "data": _empty_ai_status(),
        "message": "AI 设置已清除"
    }


@router.post("/parse")
async def ai_parse(request: AiParseRequest):
    """AI 解析文本为条目"""
    global _last_parse_at, _last_parse_text_hash

    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")

    ai_config = _load_ai_config()
    if not ai_config:
        raise HTTPException(status_code=502, detail="AI 服务未配置")

    text = request.text.strip()
    if len(text) > AI_PARSE_MAX_INPUT_CHARS:
        raise HTTPException(status_code=413, detail=f"AI 输入过长，请分批解析，单次最多 {AI_PARSE_MAX_INPUT_CHARS} 字符")

    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    now = time.time()
    if text_hash == _last_parse_text_hash:
        raise HTTPException(status_code=429, detail="内容未变化，请修改后再解析")
    remaining = AI_PARSE_COOLDOWN_SECONDS - (now - _last_parse_at)
    if remaining > 0:
        raise HTTPException(status_code=429, detail=f"AI 解析过于频繁，请等待 {int(remaining) + 1} 秒")

    _last_parse_at = now
    _last_parse_text_hash = text_hash
    
    try:
        content = await _request_chat_completion(
            ai_config["base_url"],
            ai_config["api_key"],
            ai_config["model"],
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            3000,
        )

        payload = _extract_json_content(content)
        parsed_entries = _normalize_ai_payload(payload)
        warnings = _quality_warnings(parsed_entries, text)
        parsed = parsed_entries[0]

        logger.info(f"AI 解析成功: {len(parsed_entries)} 条")

        return {
            "success": True,
            "data": {
                "parsed": parsed,
                "parsed_entries": parsed_entries,
                "entry_count": len(parsed_entries),
                "warnings": warnings,
                "confidence": 0.9
            }
        }

    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.error(f"AI 返回的 JSON 解析失败: {e}")
        raise HTTPException(status_code=422, detail="AI 返回格式错误")
    except Exception as e:
        logger.error(f"AI 解析失败: {e}")
        raise HTTPException(status_code=502, detail="AI 服务调用失败")
