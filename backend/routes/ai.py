import logging
import hashlib
import json
import re
import time
import os
from pathlib import Path
from datetime import datetime
import httpx
from fastapi import APIRouter, HTTPException
from models import (
    AiOrganizeApplyRequest,
    AiOrganizePreviewRequest,
    AiParseRequest,
    AiTagGovernanceApplyRequest,
    AiTagGovernancePreviewRequest,
)
from config import SECURE_SETTINGS_FILE
from crypto import decrypt_vault_with_key, encrypt_vault_with_key, parse_vault_header
from storage import derive_unlocked_purpose_key, get_vault_data, is_unlocked, save_vault_data
from tag_utils import (
    TAG_COLOR_PATTERN,
    ensure_entry_tags_meta,
    ensure_tag_meta,
    list_tag_entities,
    normalize_tag_name,
    remove_tag_from_entries,
    rename_tag_everywhere,
)

logger = logging.getLogger(__name__)
router = APIRouter()
AI_PARSE_COOLDOWN_SECONDS = 5
AI_PARSE_MAX_INPUT_CHARS = 6000
AI_ORGANIZE_MAX_ENTRIES = 100
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
        {"name": "字段名", "value": "字段值", "copyable": true, "hidden": false}
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
7. fields 必须是数组；每个字段必须包含 name、value、copyable、hidden 四个键。name 和 value 都必须是字符串，copyable 和 hidden 必须是布尔值。
8. 所有识别到的账号、用户名、邮箱、密码、IP、端口、API Key、Token、恢复码、卡号、姓名、有效期、备注信息都要保留，不能丢弃。
9. 密码、密钥、Token、API Key、恢复码、卡号等敏感字段 copyable=true 且 hidden=true；端口、环境、备注类字段 copyable=false 且 hidden=false；账号/用户名/邮箱通常 copyable=true 且 hidden=false。
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
{"entries":[{"title":"示例邮箱","url":"","fields":[{"name":"邮箱","value":"demo@example.com","copyable":true,"hidden":false},{"name":"密码","value":"demo-mail-pass","copyable":true,"hidden":true}],"tags":["邮箱","示例"],"remarks":""},{"title":"示例服务器","url":"","fields":[{"name":"IP","value":"192.0.2.10","copyable":true,"hidden":false},{"name":"SSH 端口","value":"2222","copyable":false,"hidden":false},{"name":"密码","value":"demo-server-pass","copyable":true,"hidden":true}],"tags":["服务器","示例"],"remarks":""}]}"""

ORGANIZE_SYSTEM_PROMPT = """你是 SecretBase 的密码库整理助手。你的任务是根据条目标题、网址、字段名、已有标签和已有密码组，建议如何整理标签和密码组。

你必须严格只输出一个 JSON object，不要输出 Markdown，不要输出解释，不要输出代码块。

顶层 JSON 必须使用这个结构：
{
  "suggestions": [
    {
      "entry_id": "条目ID",
      "add_tags": ["建议新增标签"],
      "remove_tags": ["建议移除标签"],
      "add_groups": ["建议新增密码组"],
      "remove_groups": ["建议移除密码组"],
      "group_descriptions": {"密码组名": "简介"},
      "reason": "简短原因"
    }
  ],
  "warnings": []
}

规则：
1. 只能为输入中出现的 entry_id 生成建议，不要编造条目。
2. 标签用于描述属性和细筛选，例如 邮箱、生产、开发、学校、工作、API。
3. 密码组用于较大的组织集合，例如 工作账号、学校账号、服务器、家庭设备、开发资源、金融账号。
4. 当 organize_groups=true 时，必须优先考虑 add_groups；不要只把“工作、邮箱、服务器、开发资源”等归类结果放进 add_tags。
5. 当 organize_tags=false 且 organize_groups=true 时，仍然必须返回密码组建议，不要因为不整理标签就返回空建议。
6. 可以建议新增和移除标签或密码组，但必须保守，理由不充分时返回空数组。
7. 标签和密码组名称必须简短，单个名称不超过 50 个字符。
8. group_descriptions 只为新密码组提供一句中文简介。
9. 不要依赖字段值；输入不会提供字段值。
10. 不要输出 null；没有建议时用空数组或空字符串。"""

TAG_GOVERNANCE_SYSTEM_PROMPT = """你是 SecretBase 的标签系统管理助手。你的任务是从整个密码库的条目标题、网址、字段名、已有标签、密码组和备注中，建议如何治理标签体系。

你必须严格只输出一个 JSON object，不要输出 Markdown，不要输出解释，不要输出代码块。

顶层 JSON 必须使用这个结构：
{
  "suggestions": [
    {
      "action": "create_tag|update_tag|delete_tag|merge_tags|replace_tag|assign_tag",
      "tag": "标签名",
      "new_tag": "新标签名",
      "source_tags": ["源标签"],
      "target_tag": "目标标签",
      "entry_ids": ["条目ID"],
      "description": "标签简介",
      "color": "#2563eb",
      "reason": "简短原因"
    }
  ],
  "warnings": []
}

动作语义：
1. create_tag：创建新标签，可用 entry_ids 建议分配给部分条目。
2. update_tag：修改标签名称、简介或颜色；原标签放 tag，新名称放 new_tag。
3. delete_tag：删除无价值标签，并从条目移除。
4. merge_tags：把 source_tags 合并到 target_tag。
5. replace_tag：仅在 entry_ids 指定条目中把 tag 替换为 new_tag。
6. assign_tag：把 tag 分配给 entry_ids 指定条目。

规则：
1. 只能使用输入中出现的 entry_id，不要编造条目。
2. 可以建议新增、修改、删除、替换、合并和分配标签，但必须保守。
3. 不要建议同时把同一标签删除又分配；冲突时优先返回更少动作。
4. 标签名称必须简短，单个名称不超过 50 个字符。
5. 标签简介使用一句中文说明，最多 300 字。
6. color 必须是 #RRGGBB；无法确定时可省略。
7. 不要依赖字段值；输入不会提供字段值。
8. 不要输出 null；没有建议时用空数组或空字符串。"""

ORGANIZE_GROUP_RULES = [
    ("开发资源", "代码仓库、开发平台、API Key 和 CI/CD 相关账号", ["开发", "代码", "git", "github", "gitlab", "gitee", "仓库", "ci", "api", "token", "npm", "docker", "k8s", "kubernetes"]),
    ("工作账号", "公司邮箱、协作工具和内部系统账号", ["工作", "公司", "企业", "办公", "内网", "oa", "邮箱", "mail", "exchange", "飞书", "钉钉", "企业微信"]),
    ("服务器", "服务器、云主机、数据库和运维入口", ["服务器", "ssh", "root", "主机", "云", "ecs", "vps", "数据库", "mysql", "redis", "postgres", "ip", "端口"]),
    ("学校账号", "学校、校园、课程和教育系统账号", ["学校", "校园", "教务", "课程", "学生", "edu"]),
    ("家庭设备", "家庭网络、路由器、NAS 和智能设备账号", ["家庭", "家里", "路由器", "nas", "wifi", "设备", "摄像头"]),
    ("金融账号", "银行、支付、证券和账单相关账号", ["银行", "支付", "支付宝", "微信", "证券", "基金", "账单", "信用卡", "银行卡"]),
]


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
        field = {"name": "内容", "value": field, "copyable": False, "hidden": False}
    if not isinstance(field, dict):
        return None
    name = _clean_text(field.get("name") or field.get("label") or field.get("key") or field.get("field"), 100)
    if not name:
        return None
    raw_value = field.get("value")
    if raw_value is None:
        raw_value = field.get("text") or field.get("content") or field.get("val") or ""
    copyable = _to_bool(field.get("copyable"), True)
    return {
        "name": name,
        "value": _clean_text(raw_value, 10000),
        "copyable": copyable,
        "hidden": _to_bool(field.get("hidden"), copyable)
    }


def _normalize_fields(raw_fields):
    if isinstance(raw_fields, dict):
        raw_fields = [
            {"name": key, "value": value, "copyable": True, "hidden": True}
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


def _clean_name_list(raw_items) -> list[str]:
    if isinstance(raw_items, str):
        raw_items = re.split(r"[,，;；]+", raw_items)
    if not isinstance(raw_items, list):
        raw_items = []

    names = []
    seen = set()
    for item in raw_items:
        name = _clean_text(item, 50)
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _normalize_suggestion(item, valid_entry_ids: set[str]) -> dict | None:
    if not isinstance(item, dict):
        return None
    entry_id = _clean_text(item.get("entry_id") or item.get("id"), 100)
    if entry_id not in valid_entry_ids:
        return None

    descriptions = item.get("group_descriptions")
    if not isinstance(descriptions, dict):
        descriptions = {}
    cleaned_descriptions = {
        _clean_text(name, 50): _clean_text(description, 300)
        for name, description in descriptions.items()
        if _clean_text(name, 50)
    }

    return {
        "entry_id": entry_id,
        "selected": True,
        "add_tags": _clean_name_list(item.get("add_tags") or item.get("tags_to_add")),
        "remove_tags": _clean_name_list(item.get("remove_tags") or item.get("tags_to_remove")),
        "add_groups": _clean_name_list(item.get("add_groups") or item.get("groups_to_add")),
        "remove_groups": _clean_name_list(item.get("remove_groups") or item.get("groups_to_remove")),
        "group_descriptions": cleaned_descriptions,
        "reason": _clean_text(item.get("reason") or item.get("explanation"), 500),
    }


def _normalize_organize_payload(payload, valid_entry_ids: set[str]) -> tuple[list[dict], list[str]]:
    if isinstance(payload, list):
        raw_suggestions = payload
        raw_warnings = []
    elif isinstance(payload, dict):
        raw_suggestions = payload.get("suggestions") or payload.get("items") or payload.get("data") or []
        raw_warnings = payload.get("warnings") or []
    else:
        raw_suggestions = []
        raw_warnings = []

    if not isinstance(raw_suggestions, list):
        raw_suggestions = []

    suggestions = []
    seen = set()
    for item in raw_suggestions:
        suggestion = _normalize_suggestion(item, valid_entry_ids)
        if not suggestion or suggestion["entry_id"] in seen:
            continue
        seen.add(suggestion["entry_id"])
        suggestions.append(suggestion)

    warnings = [_clean_text(warning, 200) for warning in raw_warnings if _clean_text(warning, 200)] if isinstance(raw_warnings, list) else []
    return suggestions, list(dict.fromkeys(warnings))


def _filter_entries_for_organize(vault, filters: dict) -> list:
    filters = filters if isinstance(filters, dict) else {}
    entries = [entry for entry in vault.entries if not entry.deleted]

    entry_ids = filters.get("entryIds") or filters.get("entry_ids") or []
    if isinstance(entry_ids, str):
        entry_ids = [item.strip() for item in entry_ids.split(",") if item.strip()]
    if isinstance(entry_ids, list) and entry_ids:
        allowed_ids = set(str(item) for item in entry_ids)
        entries = [entry for entry in entries if entry.id in allowed_ids]

    search = str(filters.get("search") or "").strip().lower()
    search_scopes = filters.get("searchScopes") or filters.get("search_scopes") or []
    if isinstance(search_scopes, str):
        search_scopes = [item.strip() for item in search_scopes.split(",") if item.strip()]
    if search:
        if not search_scopes:
            entries = []
        else:
            scoped_entries = []
            for entry in entries:
                matched = False
                if "title" in search_scopes and search in entry.title.lower():
                    matched = True
                if "url" in search_scopes and search in (entry.url or "").lower():
                    matched = True
                if "tags" in search_scopes and any(search in tag.lower() for tag in entry.tags):
                    matched = True
                if "field_names" in search_scopes and any(search in field.name.lower() for field in entry.fields):
                    matched = True
                if "field_values" in search_scopes and any(search in field.value.lower() for field in entry.fields if not _field_is_hidden_for_organize(field)):
                    matched = True
                if "remarks" in search_scopes and search in (entry.remarks or "").lower():
                    matched = True
                if matched:
                    scoped_entries.append(entry)
            entries = scoped_entries

    tag = str(filters.get("tag") or "").strip()
    if tag:
        entries = [entry for entry in entries if tag in entry.tags]

    group = str(filters.get("group") or "").strip()
    if group:
        entries = [entry for entry in entries if group in (getattr(entry, "groups", []) or [])]

    required_tags = filters.get("tags") or []
    if isinstance(required_tags, str):
        required_tags = [item.strip() for item in required_tags.split(",") if item.strip()]
    if isinstance(required_tags, list) and required_tags:
        entries = [entry for entry in entries if all(tag in entry.tags for tag in required_tags)]

    if filters.get("untagged"):
        entries = [entry for entry in entries if not entry.tags]

    if filters.get("starred"):
        entries = [entry for entry in entries if entry.starred]

    created_from = str(filters.get("createdFrom") or filters.get("created_from") or "").strip()
    created_to = str(filters.get("createdTo") or filters.get("created_to") or "").strip()
    if created_from:
        entries = [entry for entry in entries if entry.created_at >= created_from]
    if created_to:
        entries = [entry for entry in entries if entry.created_at <= created_to]

    has_url = filters.get("hasUrl") if "hasUrl" in filters else filters.get("has_url")
    if has_url in ("yes", True, "true"):
        entries = [entry for entry in entries if bool(entry.url)]
    elif has_url in ("no", False, "false"):
        entries = [entry for entry in entries if not entry.url]

    has_remarks = filters.get("hasRemarks") if "hasRemarks" in filters else filters.get("has_remarks")
    if has_remarks in ("yes", True, "true"):
        entries = [entry for entry in entries if bool(entry.remarks)]
    elif has_remarks in ("no", False, "false"):
        entries = [entry for entry in entries if not entry.remarks]

    sort_by = str(filters.get("sortBy") or filters.get("sort_by") or "updated_at")
    sort_order = str(filters.get("sortOrder") or filters.get("sort_order") or "desc")
    if sort_by not in {"updated_at", "created_at", "title"}:
        sort_by = "updated_at"
    reverse = sort_order != "asc"
    entries.sort(key=lambda entry: getattr(entry, sort_by, "") or "", reverse=reverse)
    return entries


def _field_is_hidden_for_organize(field) -> bool:
    hidden = getattr(field, "hidden", None)
    if hidden is None:
        return bool(getattr(field, "copyable", False))
    return bool(hidden)


def _entry_for_ai_organize(entry) -> dict:
    return {
        "id": entry.id,
        "title": entry.title,
        "url": entry.url or "",
        "tags": entry.tags,
        "groups": getattr(entry, "groups", []) or [],
        "field_names": [field.name for field in entry.fields],
        "remarks": entry.remarks or "",
        "starred": entry.starred,
    }


def _append_unique(items: list[str], name: str) -> bool:
    if name and name not in items:
        items.append(name)
        return True
    return False


def _infer_organize_groups(entry, suggestion: dict, existing_groups: list[str]) -> list[str]:
    source_parts = [
        entry.title,
        entry.url or "",
        entry.remarks or "",
        " ".join(entry.tags),
        " ".join(getattr(entry, "groups", []) or []),
        " ".join(field.name for field in entry.fields),
        " ".join(suggestion.get("add_tags", [])),
    ]
    source_text = " ".join(part for part in source_parts if part).lower()
    current_groups = set(getattr(entry, "groups", []) or [])
    inferred = []

    for group in existing_groups:
        if group not in current_groups and group.lower() in source_text:
            _append_unique(inferred, group)

    for group, _description, keywords in ORGANIZE_GROUP_RULES:
        if group in current_groups:
            continue
        if any(keyword.lower() in source_text for keyword in keywords):
            _append_unique(inferred, group)

    return inferred[:2]


def _group_description(group: str) -> str:
    for group_name, description, _keywords in ORGANIZE_GROUP_RULES:
        if group == group_name:
            return description
    return f"{group}相关账号和密码条目"


def _fallback_group_suggestions(entries, existing_groups: list[str]) -> list[dict]:
    suggestions = []
    for entry in entries:
        suggestion = {
            "entry_id": entry.id,
            "selected": True,
            "add_tags": [],
            "remove_tags": [],
            "add_groups": [],
            "remove_groups": [],
            "group_descriptions": {},
            "reason": "根据标题、字段名、标签和备注推断适合加入这些密码组",
        }
        for group in _infer_organize_groups(entry, suggestion, existing_groups):
            if _append_unique(suggestion["add_groups"], group):
                suggestion["group_descriptions"][group] = _group_description(group)
        if suggestion["add_groups"]:
            suggestions.append(suggestion)
    return suggestions


def _organize_summary(suggestions: list[dict]) -> dict:
    selected = [item for item in suggestions if item.get("selected", True)]
    return {
        "affected_entries": len(selected),
        "add_tags": sum(len(item.get("add_tags", [])) for item in selected),
        "remove_tags": sum(len(item.get("remove_tags", [])) for item in selected),
        "add_groups": sum(len(item.get("add_groups", [])) for item in selected),
        "remove_groups": sum(len(item.get("remove_groups", [])) for item in selected),
    }


def _entry_for_ai_tag_governance(entry) -> dict:
    return {
        "id": entry.id,
        "title": entry.title,
        "url": entry.url or "",
        "tags": entry.tags,
        "groups": getattr(entry, "groups", []) or [],
        "field_names": [field.name for field in entry.fields],
        "remarks": entry.remarks or "",
        "starred": entry.starred,
    }


def _clean_color(value) -> str | None:
    color = _clean_text(value, 20)
    return color.lower() if TAG_COLOR_PATTERN.match(color) else None


def _normalize_tag_governance_suggestion(item, valid_entry_ids: set[str]) -> dict | None:
    if not isinstance(item, dict):
        return None
    action = _clean_text(item.get("action"), 30)
    if action not in {"create_tag", "update_tag", "delete_tag", "merge_tags", "replace_tag", "assign_tag"}:
        return None

    raw_entry_ids = item.get("entry_ids") or item.get("entries") or []
    if isinstance(raw_entry_ids, str):
        raw_entry_ids = [part.strip() for part in raw_entry_ids.split(",") if part.strip()]
    entry_ids = []
    if isinstance(raw_entry_ids, list):
        for entry_id in raw_entry_ids:
            cleaned = _clean_text(entry_id, 100)
            if cleaned in valid_entry_ids and cleaned not in entry_ids:
                entry_ids.append(cleaned)

    return {
        "action": action,
        "selected": True,
        "tag": normalize_tag_name(item.get("tag") or item.get("old_tag") or item.get("old_name")) or None,
        "new_tag": normalize_tag_name(item.get("new_tag") or item.get("new_name")) or None,
        "source_tags": _clean_name_list(item.get("source_tags") or item.get("sources")),
        "target_tag": normalize_tag_name(item.get("target_tag") or item.get("target")) or None,
        "entry_ids": entry_ids,
        "description": _clean_text(item.get("description"), 300),
        "color": _clean_color(item.get("color")),
        "reason": _clean_text(item.get("reason") or item.get("explanation"), 500),
    }


def _normalize_tag_governance_payload(payload, valid_entry_ids: set[str]) -> tuple[list[dict], list[str]]:
    if isinstance(payload, list):
        raw_suggestions = payload
        raw_warnings = []
    elif isinstance(payload, dict):
        raw_suggestions = payload.get("suggestions") or payload.get("items") or payload.get("data") or []
        raw_warnings = payload.get("warnings") or []
    else:
        raw_suggestions = []
        raw_warnings = []

    suggestions = []
    if isinstance(raw_suggestions, list):
        for item in raw_suggestions:
            suggestion = _normalize_tag_governance_suggestion(item, valid_entry_ids)
            if suggestion:
                suggestions.append(suggestion)

    warnings = [_clean_text(warning, 200) for warning in raw_warnings if _clean_text(warning, 200)] if isinstance(raw_warnings, list) else []
    return suggestions, list(dict.fromkeys(warnings))


def _tag_governance_summary(suggestions: list[dict]) -> dict:
    selected = [item for item in suggestions if item.get("selected", True)]
    affected_entries = {
        entry_id
        for item in selected
        for entry_id in (item.get("entry_ids") or [])
    }
    summary = {
        "total_actions": len(selected),
        "affected_entries": len(affected_entries),
    }
    for action in ("create_tag", "update_tag", "delete_tag", "merge_tags", "replace_tag", "assign_tag"):
        summary[action] = sum(1 for item in selected if item.get("action") == action)
    return summary


def _add_tag_to_entry(entry, tag: str) -> bool:
    if not tag or tag in (entry.tags or []):
        return False
    entry.tags.append(tag)
    return True


def _replace_tag_in_entry(entry, old_tag: str, new_tag: str) -> bool:
    if old_tag not in (entry.tags or []):
        return False
    changed = False
    tags = []
    for tag in entry.tags:
        replacement = new_tag if tag == old_tag else tag
        if replacement not in tags:
            tags.append(replacement)
        if replacement != tag:
            changed = True
    entry.tags = tags
    return changed


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


@router.post("/organize/preview")
async def ai_organize_preview(request: AiOrganizePreviewRequest):
    """AI 生成标签和密码组整理建议，不直接写入。"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")
    if not request.organize_tags and not request.organize_groups:
        raise HTTPException(status_code=422, detail="请至少选择整理标签或密码组")
    if request.organize_tags and request.organize_groups:
        raise HTTPException(status_code=422, detail="标签和密码组请分开整理，避免建议冲突")

    ai_config = _load_ai_config()
    if not ai_config:
        raise HTTPException(status_code=502, detail="AI 服务未配置")

    vault = get_vault_data()
    entries = _filter_entries_for_organize(vault, request.filters)
    if not entries:
        raise HTTPException(status_code=422, detail="当前筛选范围没有可整理条目")
    if len(entries) > AI_ORGANIZE_MAX_ENTRIES:
        raise HTTPException(status_code=413, detail=f"单次 AI 整理最多支持 {AI_ORGANIZE_MAX_ENTRIES} 条，请缩小筛选范围")

    existing_tags = sorted({tag for entry in vault.entries if not entry.deleted for tag in entry.tags})
    existing_groups = sorted({
        group
        for entry in vault.entries
        if not entry.deleted
        for group in (getattr(entry, "groups", []) or [])
    } | set((vault.groups_meta or {}).keys()))

    user_payload = {
        "organize_tags": request.organize_tags,
        "organize_groups": request.organize_groups,
        "existing_tags": existing_tags,
        "existing_groups": existing_groups,
        "entries": [_entry_for_ai_organize(entry) for entry in entries],
        "privacy_note": "字段值不会发送给 AI，只有字段名和条目结构信息。",
    }

    try:
        content = await _request_chat_completion(
            ai_config["base_url"],
            ai_config["api_key"],
            ai_config["model"],
            [
                {"role": "system", "content": ORGANIZE_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}
            ],
            4000,
        )
        payload = _extract_json_content(content)
        suggestions, warnings = _normalize_organize_payload(payload, {entry.id for entry in entries})
        if request.organize_groups and not suggestions:
            suggestions = _fallback_group_suggestions(entries, existing_groups)
        entries_by_id = {entry.id: entry for entry in entries}
        for suggestion in suggestions:
            entry = entries_by_id[suggestion["entry_id"]]
            if request.organize_groups and not suggestion.get("add_groups") and not suggestion.get("remove_groups"):
                for group in _infer_organize_groups(entry, suggestion, existing_groups):
                    if _append_unique(suggestion["add_groups"], group):
                        suggestion["group_descriptions"].setdefault(group, _group_description(group))
                if suggestion["add_groups"] and not suggestion.get("reason"):
                    suggestion["reason"] = "根据标题、字段名、标签和备注推断适合加入这些密码组"
            if not request.organize_tags:
                suggestion["add_tags"] = []
                suggestion["remove_tags"] = []
            if not request.organize_groups:
                suggestion["add_groups"] = []
                suggestion["remove_groups"] = []
                suggestion["group_descriptions"] = {}
            suggestion["entry_title"] = entry.title
            suggestion["current_tags"] = entry.tags
            suggestion["current_groups"] = getattr(entry, "groups", []) or []
    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.error(f"AI 整理返回的 JSON 解析失败: {e}")
        raise HTTPException(status_code=422, detail="AI 返回格式错误")
    except Exception as e:
        logger.error(f"AI 整理失败: {e}")
        raise HTTPException(status_code=502, detail="AI 服务调用失败")

    return {
        "success": True,
        "data": {
            "entry_count": len(entries),
            "suggestions": suggestions,
            "summary": _organize_summary(suggestions),
            "warnings": warnings,
            "privacy_note": "本次整理未向 AI 发送任何字段值。",
        }
    }


@router.post("/organize/apply")
async def ai_organize_apply(request: AiOrganizeApplyRequest):
    """应用用户确认后的 AI 整理建议。"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")

    vault = get_vault_data()
    entries_by_id = {
        entry.id: entry
        for entry in vault.entries
        if not entry.deleted
    }
    if not isinstance(vault.groups_meta, dict):
        vault.groups_meta = {}

    updated_count = 0
    created_groups = []
    now = datetime.now().isoformat()

    for suggestion in request.suggestions:
        if not suggestion.selected:
            continue
        entry = entries_by_id.get(suggestion.entry_id)
        if not entry:
            continue

        changed = False
        original_tags = list(entry.tags)
        original_groups = list(getattr(entry, "groups", []) or [])

        tags = [tag for tag in original_tags if tag not in suggestion.remove_tags]
        for tag in suggestion.add_tags:
            if tag not in tags:
                tags.append(tag)
        ensure_entry_tags_meta(vault, tags)

        groups = [group for group in original_groups if group not in suggestion.remove_groups]
        for group in suggestion.add_groups:
            if group not in groups:
                groups.append(group)
            if group not in vault.groups_meta:
                vault.groups_meta[group] = {
                    "description": str(suggestion.group_descriptions.get(group, "")).strip(),
                    "created_at": now,
                    "updated_at": now,
                }
                created_groups.append(group)
            elif suggestion.group_descriptions.get(group) and not str(vault.groups_meta[group].get("description", "")).strip():
                vault.groups_meta[group]["description"] = str(suggestion.group_descriptions[group]).strip()
                vault.groups_meta[group]["updated_at"] = now

        if tags != original_tags:
            entry.tags = tags
            changed = True
        if groups != original_groups:
            entry.groups = groups
            changed = True
        if changed:
            entry.updated_at = now
            updated_count += 1

    if updated_count > 0 or created_groups:
        save_vault_data(vault)

    return {
        "success": True,
        "data": {
            "updated_count": updated_count,
            "created_groups": sorted(set(created_groups)),
        },
        "message": f"已整理 {updated_count} 个条目"
    }


@router.post("/tags/preview")
async def ai_tag_governance_preview(request: AiTagGovernancePreviewRequest):
    """AI 生成全局标签系统管理建议，不直接写入。"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")

    vault = get_vault_data()
    entries = _filter_entries_for_organize(vault, request.filters)
    if not entries:
        raise HTTPException(status_code=422, detail="当前密码库没有可分析条目")
    if len(entries) > AI_ORGANIZE_MAX_ENTRIES:
        raise HTTPException(status_code=413, detail=f"AI 标签系统管理最多支持 {AI_ORGANIZE_MAX_ENTRIES} 条，请先缩小范围")

    ai_config = _load_ai_config()
    if not ai_config:
        raise HTTPException(status_code=502, detail="AI 服务未配置")

    user_payload = {
        "existing_tags": list_tag_entities(vault),
        "existing_groups": sorted({
            group
            for entry in vault.entries
            if not entry.deleted
            for group in (getattr(entry, "groups", []) or [])
        } | set((vault.groups_meta or {}).keys())),
        "entries": [_entry_for_ai_tag_governance(entry) for entry in entries],
        "privacy_note": "字段值不会发送给 AI，只有字段名和条目结构信息。",
    }

    try:
        content = await _request_chat_completion(
            ai_config["base_url"],
            ai_config["api_key"],
            ai_config["model"],
            [
                {"role": "system", "content": TAG_GOVERNANCE_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}
            ],
            4000,
        )
        payload = _extract_json_content(content)
        suggestions, warnings = _normalize_tag_governance_payload(payload, {entry.id for entry in entries})
    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.error(f"AI 标签系统管理返回的 JSON 解析失败: {e}")
        raise HTTPException(status_code=422, detail="AI 返回格式错误")
    except Exception as e:
        logger.error(f"AI 标签系统管理失败: {e}")
        raise HTTPException(status_code=502, detail="AI 服务调用失败")

    return {
        "success": True,
        "data": {
            "entry_count": len(entries),
            "suggestions": suggestions,
            "summary": _tag_governance_summary(suggestions),
            "warnings": warnings,
            "privacy_note": "本次标签系统管理不会发送任何字段值。",
        }
    }


@router.post("/tags/apply")
async def ai_tag_governance_apply(request: AiTagGovernanceApplyRequest):
    """应用用户确认后的 AI 标签系统管理建议。"""
    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")

    vault = get_vault_data()
    entries_by_id = {entry.id: entry for entry in vault.entries if not entry.deleted}
    updated_entry_ids: set[str] = set()
    applied_count = 0
    now = datetime.now().isoformat()

    def mark_updated(entry):
        entry.updated_at = now
        updated_entry_ids.add(entry.id)

    for suggestion in request.suggestions:
        if not suggestion.selected:
            continue

        action = suggestion.action
        tag = normalize_tag_name(suggestion.tag or "")
        new_tag = normalize_tag_name(suggestion.new_tag or "")
        target_tag = normalize_tag_name(suggestion.target_tag or "")
        source_tags = [normalize_tag_name(item) for item in suggestion.source_tags if normalize_tag_name(item)]
        entry_ids = [entry_id for entry_id in suggestion.entry_ids if entry_id in entries_by_id]
        changed = False

        if action == "create_tag":
            if not tag:
                continue
            ensure_tag_meta(vault, tag, suggestion.description, suggestion.color)
            for entry_id in entry_ids:
                entry = entries_by_id[entry_id]
                if _add_tag_to_entry(entry, tag):
                    mark_updated(entry)
                    changed = True
            changed = True

        elif action == "update_tag":
            if not tag:
                continue
            destination = new_tag or tag
            description = suggestion.description
            if destination != tag:
                rename_tag_everywhere(vault, tag, destination)
                if isinstance(vault.tags_meta, dict):
                    old_meta = vault.tags_meta.pop(tag, {})
                    if isinstance(old_meta, dict) and not description:
                        description = str(old_meta.get("description", ""))
                for entry in vault.entries:
                    if not entry.deleted and destination in (entry.tags or []):
                        mark_updated(entry)
                changed = True
            ensure_tag_meta(vault, destination, description, suggestion.color)
            changed = True

        elif action == "delete_tag":
            if not tag:
                continue
            affected = 0
            for entry in vault.entries:
                if not entry.deleted and tag in (entry.tags or []):
                    entry.tags = [item for item in entry.tags if item != tag]
                    mark_updated(entry)
                    affected += 1
            if isinstance(vault.tags_meta, dict) and tag in vault.tags_meta:
                vault.tags_meta.pop(tag, None)
                changed = True
            changed = changed or affected > 0

        elif action == "merge_tags":
            if not source_tags or not target_tag:
                continue
            ensure_tag_meta(vault, target_tag, suggestion.description, suggestion.color)
            for entry in vault.entries:
                if entry.deleted:
                    continue
                if any(source in (entry.tags or []) for source in source_tags):
                    entry.tags = [item for item in entry.tags if item not in source_tags]
                    _add_tag_to_entry(entry, target_tag)
                    mark_updated(entry)
                    changed = True
            if isinstance(vault.tags_meta, dict):
                for source in source_tags:
                    if source in vault.tags_meta:
                        vault.tags_meta.pop(source, None)
                        changed = True

        elif action == "replace_tag":
            if not tag or not new_tag:
                continue
            ensure_tag_meta(vault, new_tag, suggestion.description, suggestion.color)
            target_entries = [entries_by_id[entry_id] for entry_id in entry_ids] if entry_ids else list(entries_by_id.values())
            for entry in target_entries:
                if _replace_tag_in_entry(entry, tag, new_tag):
                    mark_updated(entry)
                    changed = True

        elif action == "assign_tag":
            if not tag or not entry_ids:
                continue
            ensure_tag_meta(vault, tag, suggestion.description, suggestion.color)
            for entry_id in entry_ids:
                entry = entries_by_id[entry_id]
                if _add_tag_to_entry(entry, tag):
                    mark_updated(entry)
                    changed = True

        if changed:
            applied_count += 1

    if applied_count > 0:
        for entry in vault.entries:
            if not entry.deleted:
                ensure_entry_tags_meta(vault, entry.tags)
        save_vault_data(vault)

    return {
        "success": True,
        "data": {
            "applied_count": applied_count,
            "updated_entries": len(updated_entry_ids),
        },
        "message": f"已应用 {applied_count} 条标签管理建议"
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
