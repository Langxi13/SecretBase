import logging
import hashlib
import json
import re
import time
import httpx
from fastapi import APIRouter, HTTPException
from models import AiParseRequest
from config import AI_MODEL, AI_API_KEY, AI_API_URL
from storage import is_unlocked

logger = logging.getLogger(__name__)
router = APIRouter()
AI_PARSE_COOLDOWN_SECONDS = 5
AI_PARSE_MAX_INPUT_CHARS = 6000
_last_parse_at = 0.0
_last_parse_text_hash = ""

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
        "data": {
            "configured": bool(AI_API_KEY),
            "model": AI_MODEL
        }
    }


@router.post("/parse")
async def ai_parse(request: AiParseRequest):
    """AI 解析文本为条目"""
    global _last_parse_at, _last_parse_text_hash

    if not is_unlocked():
        raise HTTPException(status_code=401, detail="请先解锁")

    if not AI_API_KEY:
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
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                AI_API_URL,
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": AI_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": text}
                    ],
                    "temperature": 0,
                    "max_tokens": 3000,
                    "response_format": {"type": "json_object"}
                }
            )
            
            if response.status_code != 200:
                logger.error(f"AI 服务返回错误: {response.status_code}")
                raise HTTPException(status_code=502, detail="AI 服务调用失败")
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
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
            
    except httpx.TimeoutException:
        raise HTTPException(status_code=502, detail="AI 服务响应超时")
    except json.JSONDecodeError as e:
        logger.error(f"AI 返回的 JSON 解析失败: {e}")
        raise HTTPException(status_code=422, detail="AI 返回格式错误")
    except Exception as e:
        logger.error(f"AI 解析失败: {e}")
        raise HTTPException(status_code=502, detail="AI 服务调用失败")
